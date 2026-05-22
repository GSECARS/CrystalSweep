#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/controller/scan_engine.py
# ----------------------------------------------------------------------------------
# Purpose:
# Orchestrates scan execution in a background thread. Bridges the collection
# model (CollectionPoint, BeamlineConfig) and the motion/detector models.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
import threading
import time
from typing import Callable

from epics import caget, caput

from crystalsweep.model.beamline_config_model import BeamlineConfig, MotorConfig
from crystalsweep.model.collection_model import CollectionPoint
from crystalsweep.model.detector_model import get_detector_model
from crystalsweep.model.scan_model import ScanSpec, get_driver

__all__ = ["ScanEngine"]

_log = logging.getLogger(__name__)


class ScanEngine:
    """Orchestrates scan execution in a background thread.

    Supported scan types
    --------------------
    still  — move rotation motor to rotation_start, trigger one detector frame.
    """

    def __init__(self) -> None:
        self._driver = None
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def pre_scan(self, point: CollectionPoint, config: BeamlineConfig) -> str | None:
        """Validate a point before scanning and configure hardware routing gates.

        Returns an error string if the scan cannot proceed, or None if OK.
        Sets any trigger_pv_* entries from the rotation motor's controller params to 0
        so PSO pulses are routed correctly to the detector.
        """
        rotation_cfg = config.rotation_motor
        if rotation_cfg is not None:
            controller_cfg = next(
                (c for c in config.controllers if c.name == rotation_cfg.controller), None
            )
            if controller_cfg is not None:
                for key, pv in controller_cfg.params.items():
                    if key.startswith("trigger_pv_"):
                        try:
                            caput(pv, 0, wait=True)
                            _log.debug("pre_scan: set %s (%s) = 0", key, pv)
                        except Exception as exc:
                            _log.warning("pre_scan: failed to set %s (%s): %s", key, pv, exc)
        return None

    def run_still(
        self,
        point: CollectionPoint,
        config: BeamlineConfig,
        on_done: Callable[[], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        """Move rotation motor to rotation_start and trigger one detector frame."""
        if self.is_running:
            raise RuntimeError("A scan is already in progress.")

        rotation_cfg = config.rotation_motor
        if rotation_cfg is None:
            on_error(ValueError("No rotation motor configured."))
            return

        det = config.active_detector_config
        if det is None or not det.pv_prefix.strip():
            on_error(ValueError("No active detector configured."))
            return

        try:
            exposure = float(point.time) if point.time else 1.0
        except ValueError as exc:
            on_error(exc)
            return

        detector = get_detector_model(det.type, det.pv_prefix, det.file_format)

        def _worker() -> None:
            try:
                detector.collect_still(exposure)
                on_done()
            except Exception as exc:
                _log.exception("ScanEngine still-scan error")
                on_error(exc)
            finally:
                self._driver = None

        self._thread = threading.Thread(target=_worker, daemon=True, name="scan-still")
        self._thread.start()

    def run_step(
        self,
        point: CollectionPoint,
        config: BeamlineConfig,
        on_frame: Callable[[int, int], None],
        on_done: Callable[[], None],
        on_error: Callable[[Exception], None],
        slew: bool = True,
    ) -> None:
        """Execute a step scan: slew trajectory (default) or per-angle EPICS stills."""
        if self.is_running:
            raise RuntimeError("A scan is already in progress.")

        rotation_cfg = config.rotation_motor
        if rotation_cfg is None:
            on_error(ValueError("No rotation motor configured."))
            return

        det = config.active_detector_config
        if det is None or not det.pv_prefix.strip():
            on_error(ValueError("No active detector configured."))
            return

        try:
            omega_start = float(point.rotation_start) if point.rotation_start else 0.0
            omega_end = float(point.rotation_end) if point.rotation_end else 0.0
            step_size = float(point.step) if point.step else 1.0
            exposure = float(point.time) if point.time else 1.0
        except ValueError as exc:
            on_error(exc)
            return

        if step_size <= 0:
            on_error(ValueError(f"Step size must be > 0, got {step_size}."))
            return
        if omega_start == omega_end:
            on_error(ValueError("rotation_start and rotation_end must differ for a step scan."))
            return

        n_frames = max(1, round(abs(omega_end - omega_start) / step_size))

        controller_cfg = next((c for c in config.controllers if c.name == rotation_cfg.controller), None)
        params = dict(controller_cfg.params) if controller_cfg else {}
        if rotation_cfg.xps_group:
            params["xps_group"] = rotation_cfg.xps_group
        if rotation_cfg.xps_positioner:
            params["xps_positioner"] = rotation_cfg.xps_positioner

        controller_type = controller_cfg.type if controller_cfg else rotation_cfg.controller

        spec = ScanSpec(
            pv=rotation_cfg.pv,
            start=omega_start,
            end=omega_end,
            points=n_frames,
            exposure=exposure,
            controller_params=params,
        )

        detector = get_detector_model(det.type, det.pv_prefix, det.file_format)
        driver = get_driver(controller_type)
        self._driver = driver

        prefix = det.pv_prefix.strip()
        if not prefix.endswith(":"):
            prefix += ":"
        acquire_pv = f"{prefix}cam1:Acquire"

        _EPICS_TYPES = {"epics", "step"}

        if not slew or controller_type in _EPICS_TYPES:
            def _worker_epics() -> None:
                try:
                    driver.prepare(spec)
                    pv_base = rotation_cfg.pv.removesuffix(".VAL")
                    caput(f"{pv_base}.VAL", omega_start, wait=True)
                    detector.arm_plugin(n_frames)
                    for frame_idx in range(n_frames):
                        if self._driver is None:
                            break
                        angle = omega_start + frame_idx * step_size
                        caput(f"{pv_base}.VAL", angle, wait=True)
                        detector.collect_frame(exposure)
                        on_frame(frame_idx + 1, n_frames)
                    on_done()
                except Exception as exc:
                    _log.exception("ScanEngine step-epics error")
                    on_error(exc)
                finally:
                    self._driver = None

            self._thread = threading.Thread(target=_worker_epics, daemon=True, name="scan-step-epics")
            self._thread.start()

        else:
            pv_base = rotation_cfg.pv.removesuffix(".VAL")

            def _worker_slew() -> None:
                try:
                    driver.prepare(spec)
                    caput(f"{pv_base}.VAL", omega_start, wait=True)
                    detector.collect_step(exposure, n_frames)

                    import threading as _threading
                    traj_done = _threading.Event()

                    def _run_traj() -> None:
                        driver.run(spec, lambda i, pos: None)
                        traj_done.set()

                    _threading.Thread(target=_run_traj, daemon=True, name="scan-step-traj").start()

                    last_reported = -1
                    while not traj_done.is_set() or caget(acquire_pv):
                        captured = detector.frames_captured()
                        if captured != last_reported:
                            on_frame(captured, n_frames)
                            last_reported = captured
                        time.sleep(0.05)

                    captured = detector.frames_captured()
                    if captured != last_reported:
                        on_frame(captured, n_frames)

                    _log.debug("ScanEngine step-slew: detector readout complete")
                    on_done()
                except Exception as exc:
                    _log.exception("ScanEngine step-slew error")
                    on_error(exc)
                finally:
                    self._driver = None

            self._thread = threading.Thread(target=_worker_slew, daemon=True, name="scan-step-slew")
            self._thread.start()

    def run_wide(
        self,
        point: CollectionPoint,
        config: BeamlineConfig,
        on_done: Callable[[], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        """Arm detector for external trigger, run the slew trajectory, wait for readout."""
        if self.is_running:
            raise RuntimeError("A scan is already in progress.")

        rotation_cfg = config.rotation_motor
        if rotation_cfg is None:
            on_error(ValueError("No rotation motor configured."))
            return

        det = config.active_detector_config
        if det is None or not det.pv_prefix.strip():
            on_error(ValueError("No active detector configured."))
            return

        try:
            omega_start = float(point.rotation_start) if point.rotation_start else 0.0
            omega_end = float(point.rotation_end) if point.rotation_end else 0.0
            exposure = float(point.time) if point.time else 1.0
        except ValueError as exc:
            on_error(exc)
            return

        if omega_start == omega_end:
            on_error(ValueError("rotation_start and rotation_end must differ for a wide scan."))
            return

        controller_cfg = next((c for c in config.controllers if c.name == rotation_cfg.controller), None)
        params = dict(controller_cfg.params) if controller_cfg else {}
        if rotation_cfg.xps_group:
            params["xps_group"] = rotation_cfg.xps_group
        if rotation_cfg.xps_positioner:
            params["xps_positioner"] = rotation_cfg.xps_positioner

        omega_range = abs(omega_end - omega_start)
        spec = ScanSpec(
            pv=rotation_cfg.pv,
            start=omega_start,
            end=omega_end,
            points=1,
            exposure=exposure,
            controller_params=params,
        )

        controller_type = controller_cfg.type if controller_cfg else rotation_cfg.controller

        detector = get_detector_model(det.type, det.pv_prefix, det.file_format)
        driver = get_driver(controller_type)
        self._driver = driver

        prefix = det.pv_prefix.strip()
        if not prefix.endswith(":"):
            prefix += ":"
        acquire_pv = f"{prefix}cam1:Acquire"

        pv_base = rotation_cfg.pv.removesuffix(".VAL")

        def _worker() -> None:
            try:
                driver.prepare(spec)
                caput(f"{pv_base}.VAL", omega_start, wait=True)
                detector.collect_wide(exposure)
                driver.run(spec, lambda i, pos: None)
                while caget(acquire_pv):
                    time.sleep(0.05)
                _log.debug("ScanEngine wide: detector readout complete")
                on_done()
            except Exception as exc:
                _log.exception("ScanEngine wide-scan error")
                on_error(exc)
            finally:
                self._driver = None

        self._thread = threading.Thread(target=_worker, daemon=True, name="scan-wide")
        self._thread.start()

    def run_point(
        self,
        point: CollectionPoint,
        config: BeamlineConfig,
        map_motor_shorthand: str,
        map_start: float,
        map_end: float,
        map_points: int,
        exposure: float,
        on_progress: Callable[[int, int, float], None],
        on_done: Callable[[], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        if self.is_running:
            raise RuntimeError("A scan is already in progress.")

        motor_cfg = self._find_motor(config, map_motor_shorthand)
        if motor_cfg is None:
            on_error(ValueError(f"Motor '{map_motor_shorthand}' not found in active config."))
            return

        controller_cfg = next((c for c in config.controllers if c.name == motor_cfg.controller), None)
        params = dict(controller_cfg.params) if controller_cfg else {}
        if motor_cfg.xps_group:
            params["xps_group"] = motor_cfg.xps_group
        if motor_cfg.xps_positioner:
            params["xps_positioner"] = motor_cfg.xps_positioner

        spec = ScanSpec(
            pv=motor_cfg.pv,
            start=map_start,
            end=map_end,
            points=map_points,
            exposure=exposure,
            controller_params=params,
        )

        controller_type = controller_cfg.type if controller_cfg else motor_cfg.controller

        driver = get_driver(controller_type)
        self._driver = driver

        def _worker() -> None:
            try:
                driver.prepare(spec)
                driver.run(spec, lambda i, pos: on_progress(i, map_points, pos))
                on_done()
            except Exception as exc:
                _log.exception("ScanEngine error")
                on_error(exc)
            finally:
                self._driver = None

        self._thread = threading.Thread(target=_worker, daemon=True, name="scan-map")
        self._thread.start()

    def abort(self) -> None:
        if self._driver is not None:
            self._driver.abort()

    @staticmethod
    def _find_motor(config: BeamlineConfig, shorthand: str) -> MotorConfig | None:
        all_motors = list(config.motors)
        if config.rotation_motor:
            all_motors = [config.rotation_motor] + all_motors
        return next((m for m in all_motors if m.shorthand == shorthand), None)
