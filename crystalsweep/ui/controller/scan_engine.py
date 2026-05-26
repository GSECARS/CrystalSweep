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
from pathlib import Path
from typing import Callable

from epics import caget, caput

from crystalsweep.model.beamline_config_model import BeamlineConfig, MotorConfig
from crystalsweep.model.collection_model import CollectionPoint
from crystalsweep.model.detector_model import get_detector_model
from crystalsweep.model.file_settings_model import FileSettingsModel
from crystalsweep.model.motor_limits import check_soft_limits
from crystalsweep.model.scan_model import ScanSpec, get_driver
from crystalsweep.model.script_model import ScriptModel

__all__ = ["ScanEngine"]

_log = logging.getLogger(__name__)


class ScanEngine:
    """Orchestrates scan execution in a background thread.

    Supported scan types
    --------------------
    still  — move rotation motor to rotation_start, trigger one detector frame.
    """

    def __init__(self, script_model: ScriptModel | None = None) -> None:
        self._driver = None
        self._thread: threading.Thread | None = None
        self._scripts = script_model

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def pre_scan(self, point: CollectionPoint, config: BeamlineConfig) -> str | None:
        """Validate a point before scanning. Delegates to the user script if available.

        Returns an error string if the scan cannot proceed, or None if OK.
        """
        if self._scripts is not None:
            result = self._scripts.call("pre_scan", point, config)
            if isinstance(result, str):
                return result
        return None

    def post_scan(self, point: CollectionPoint, config: BeamlineConfig) -> None:
        """Run post-scan cleanup after each point. Delegates to the user script if available."""
        if self._scripts is not None:
            self._scripts.call("post_scan", point, config)

    def run_still(
        self,
        point: CollectionPoint,
        config: BeamlineConfig,
        on_done: Callable[[], None],
        on_error: Callable[[Exception], None],
        file_settings: FileSettingsModel | None = None,
        on_file_number_updated: Callable[[int], None] | None = None,
        on_status: Callable[[str], None] | None = None,
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

        try:
            omega_start = float(point.rotation_start) if point.rotation_start else 0.0
        except ValueError:
            omega_start = 0.0

        pv_base = rotation_cfg.pv.removesuffix(".VAL")
        detector = get_detector_model(det.type, det.pv_prefix, det.file_format)

        def _worker() -> None:
            saved_auto_inc = 1
            disable_inc = False
            try:
                limit_err = check_soft_limits(rotation_cfg.pv, omega_start)
                if limit_err:
                    on_error(ValueError(f"Soft limit violation — {limit_err}"))
                    return
                if on_status: on_status("moving")
                caput(f"{pv_base}.VAL", omega_start, wait=True)
                if file_settings is not None:
                    remote_dir, filename, frame_number, disable_inc, file_template = self._resolve_file_info(file_settings, point, config)
                    saved_auto_inc = detector.set_file_info(remote_dir, filename, frame_number, disable_inc, file_template)
                if on_status: on_status("collecting")
                detector.collect_still(exposure)
                on_done()
            except Exception as exc:
                _log.exception("ScanEngine still-scan error")
                on_error(exc)
            finally:
                if disable_inc:
                    detector.restore_auto_increment(saved_auto_inc)
                if on_file_number_updated is not None:
                    try:
                        _, _, file_number = detector.fetch_file_info()
                        on_file_number_updated(file_number)
                    except Exception:
                        pass
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
        file_settings: FileSettingsModel | None = None,
        on_file_number_updated: Callable[[int], None] | None = None,
        on_status: Callable[[str], None] | None = None,
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
        _EPICS_TYPES = {"epics", "step"}

        if not slew or controller_type in _EPICS_TYPES:
            def _worker_epics() -> None:
                saved_auto_inc = 1
                disable_inc = False
                try:
                    for chk_pos in (omega_start, omega_end):
                        limit_err = check_soft_limits(rotation_cfg.pv, chk_pos)
                        if limit_err:
                            on_error(ValueError(f"Soft limit violation — {limit_err}"))
                            return
                    if file_settings is not None:
                        remote_dir, filename, frame_number, disable_inc, file_template = self._resolve_file_info(file_settings, point, config)
                        saved_auto_inc = detector.set_file_info(remote_dir, filename, frame_number, disable_inc, file_template)
                    if on_status: on_status("preparing")
                    driver.prepare(spec)
                    pv_base = rotation_cfg.pv.removesuffix(".VAL")
                    if on_status: on_status("moving")
                    caput(f"{pv_base}.VAL", omega_start, wait=True)
                    detector.arm_plugin(n_frames)
                    if on_status: on_status("collecting")
                    for frame_idx in range(n_frames):
                        if self._driver is None:
                            break
                        angle = omega_start + frame_idx * step_size
                        limit_err = check_soft_limits(rotation_cfg.pv, angle)
                        if limit_err:
                            on_error(ValueError(f"Soft limit violation — {limit_err}"))
                            return
                        caput(f"{pv_base}.VAL", angle, wait=True)
                        detector.collect_frame(exposure)
                        on_frame(frame_idx + 1, n_frames)
                    on_done()
                except Exception as exc:
                    _log.exception("ScanEngine step-epics error")
                    on_error(exc)
                finally:
                    if disable_inc:
                        detector.restore_auto_increment(saved_auto_inc)
                    if on_file_number_updated is not None:
                        try:
                            _, _, file_number = detector.fetch_file_info()
                            on_file_number_updated(file_number)
                        except Exception:
                            pass
                    self._driver = None

            self._thread = threading.Thread(target=_worker_epics, daemon=True, name="scan-step-epics")
            self._thread.start()

        else:
            _PLUGIN_MAP = {"hdf5": "HDF1", "cbf": "CBF1", "tif": "TIFF1"}
            plugin = _PLUGIN_MAP.get(det.file_format, "HDF1")
            capture_pv = f"{prefix}{plugin}:Capture_RBV"

            def _worker_slew() -> None:
                saved_auto_inc = 1
                disable_inc = False
                try:
                    if file_settings is not None:
                        remote_dir, filename, frame_number, disable_inc, file_template = self._resolve_file_info(file_settings, point, config)
                        saved_auto_inc = detector.set_file_info(remote_dir, filename, frame_number, disable_inc, file_template)
                    if on_status: on_status("preparing")
                    driver.prepare(spec)
                    if on_status: on_status("collecting")
                    detector.collect_step(exposure, n_frames)

                    import threading as _threading
                    traj_done = _threading.Event()

                    traj_error: list[Exception] = []

                    def _run_traj() -> None:
                        try:
                            driver.run(spec, lambda i, pos: None)
                        except Exception as exc:
                            _log.exception("ScanEngine step-slew trajectory error")
                            traj_error.append(exc)
                        finally:
                            traj_done.set()

                    _threading.Thread(target=_run_traj, daemon=True, name="scan-step-traj").start()

                    last_reported = -1
                    timeout = exposure * n_frames + 60.0
                    deadline = time.monotonic() + timeout
                    while not traj_done.is_set() or int(caget(capture_pv) or 0):
                        if time.monotonic() > deadline:
                            _log.warning("ScanEngine step-slew: timed out (traj_done=%s capture=%s)", traj_done.is_set(), caget(capture_pv))
                            break
                        captured = detector.frames_captured()
                        if captured != last_reported:
                            on_frame(captured, n_frames)
                            last_reported = captured
                        time.sleep(0.05)

                    captured = detector.frames_captured()
                    if captured != last_reported:
                        on_frame(captured, n_frames)

                    if traj_error:
                        raise traj_error[0]

                    _log.debug("ScanEngine step-slew: loop exited (traj_done=%s)", traj_done.is_set())
                    on_done()
                except Exception as exc:
                    _log.exception("ScanEngine step-slew error")
                    on_error(exc)
                finally:
                    if disable_inc:
                        detector.restore_auto_increment(saved_auto_inc)
                    if on_file_number_updated is not None:
                        try:
                            _, _, file_number = detector.fetch_file_info()
                            on_file_number_updated(file_number)
                        except Exception:
                            pass
                    self._driver = None

            self._thread = threading.Thread(target=_worker_slew, daemon=True, name="scan-step-slew")
            self._thread.start()

    def run_wide(
        self,
        point: CollectionPoint,
        config: BeamlineConfig,
        on_done: Callable[[], None],
        on_error: Callable[[Exception], None],
        file_settings: FileSettingsModel | None = None,
        on_file_number_updated: Callable[[int], None] | None = None,
        on_status: Callable[[str], None] | None = None,
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
            saved_auto_inc = 1
            disable_inc = False
            try:
                for chk_pos in (omega_start, omega_end):
                    limit_err = check_soft_limits(rotation_cfg.pv, chk_pos)
                    if limit_err:
                        on_error(ValueError(f"Soft limit violation — {limit_err}"))
                        return
                if file_settings is not None:
                    remote_dir, filename, frame_number, disable_inc, file_template = self._resolve_file_info(file_settings, point, config)
                    saved_auto_inc = detector.set_file_info(remote_dir, filename, frame_number, disable_inc, file_template)
                if on_status: on_status("preparing")
                driver.prepare(spec)
                if on_status: on_status("moving")
                caput(f"{pv_base}.VAL", omega_start, wait=True)
                if on_status: on_status("collecting")
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
                if disable_inc:
                    detector.restore_auto_increment(saved_auto_inc)
                if on_file_number_updated is not None:
                    try:
                        _, _, file_number = detector.fetch_file_info()
                        on_file_number_updated(file_number)
                    except Exception:
                        pass
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

    def run_map_row_trajectory(
        self,
        config: BeamlineConfig,
        map_motor_shorthand: str,
        epics_positions: list[float],
        exposure: float,
        file_settings,
        row_points: list[CollectionPoint],
        on_frame: Callable[[int, int], None],
        on_done: Callable[[], None],
        on_error: Callable[[Exception], None],
        on_file_number_updated: Callable[[int], None] | None = None,
    ) -> None:
        """Run a trajectory across one map row, collecting one still frame per point.

        The detector is armed for *n_points* frames before the trajectory fires.
        File info is set from the first point in *row_points*.
        """
        if self.is_running:
            raise RuntimeError("A scan is already in progress.")

        n_points = len(epics_positions)
        if n_points < 1:
            on_error(ValueError("No positions in map row."))
            return

        motor_cfg = self._find_motor(config, map_motor_shorthand)
        if motor_cfg is None:
            on_error(ValueError(f"Map motor '{map_motor_shorthand}' not found in active config."))
            return

        det = config.active_detector_config
        if det is None or not det.pv_prefix.strip():
            on_error(ValueError("No active detector configured."))
            return

        controller_cfg = next((c for c in config.controllers if c.name == motor_cfg.controller), None)
        params = dict(controller_cfg.params) if controller_cfg else {}
        controller_type = controller_cfg.type if controller_cfg else motor_cfg.controller

        detector = get_detector_model(det.type, det.pv_prefix, det.file_format)
        driver = get_driver(controller_type)
        self._driver = driver

        prefix = det.pv_prefix.strip()
        if not prefix.endswith(":"):
            prefix += ":"
        acquire_pv = f"{prefix}cam1:Acquire"

        ref_point = row_points[0] if row_points else None

        xps_group = params.get("xps_group") or motor_cfg.xps_group or ""
        xps_positioner = params.get("xps_positioner") or motor_cfg.xps_positioner or ""
        is_xps = controller_type == "newport_xps" and xps_group and xps_positioner

        spec = ScanSpec(
            pv=motor_cfg.pv,
            start=epics_positions[0],
            end=epics_positions[-1],
            points=n_points,
            exposure=exposure,
            controller_params=params,
        )

        def _worker() -> None:
            saved_auto_inc = 1
            disable_inc = False
            try:
                if file_settings is not None and ref_point is not None:
                    remote_dir, filename, frame_number, disable_inc, file_template = self._resolve_file_info(file_settings, ref_point, config)
                    saved_auto_inc = detector.set_file_info(remote_dir, filename, frame_number, disable_inc, file_template)
                detector.arm_plugin(n_points)
                detector.collect_step(exposure, n_points)
                if is_xps:
                    driver.prepare(spec)
                    driver.prepare_array(motor_cfg.pv, epics_positions, exposure, xps_positioner, xps_group)
                    driver.run_array(lambda i, pos: on_frame(i + 1, n_points), n_points)
                else:
                    driver.prepare(spec)
                    driver.run(spec, lambda i, pos: on_frame(i + 1, n_points))
                while caget(acquire_pv):
                    time.sleep(0.05)
                on_done()
            except Exception as exc:
                _log.exception("ScanEngine map-row-trajectory error")
                on_error(exc)
            finally:
                if disable_inc:
                    detector.restore_auto_increment(saved_auto_inc)
                if on_file_number_updated is not None:
                    try:
                        _, _, file_number = detector.fetch_file_info()
                        on_file_number_updated(file_number)
                    except Exception:
                        pass
                self._driver = None

        self._thread = threading.Thread(target=_worker, daemon=True, name="scan-map-traj")
        self._thread.start()

    def abort(self) -> None:
        if self._driver is not None:
            self._driver.abort()

    @staticmethod
    def _resolve_file_info(
        file_settings: "FileSettingsModel",
        point: "CollectionPoint",
        config: "BeamlineConfig",
    ) -> tuple[str, str, int, bool, str]:
        """Return (remote_directory, filename, frame_number, disable_auto_increment, file_template) for the given point.

        The directory is translated from the local Windows path to the IOC
        path using the prefix map stored in *config* (if configured).
        If either prefix is empty the local path string is used as-is.
        AutoIncrement is disabled when the collection point has a non-empty label.
        """
        local_dir = str(file_settings.directory)
        det = config.active_detector_config
        remote_dir = det.translate_path(local_dir) if det else local_dir
        use_ext = getattr(file_settings, "use_ext", True)
        label = point.label.strip() if use_ext else ""
        disable_auto_increment = bool(label)
        base = file_settings.filename or ""
        map_ext = file_settings.map_ext.strip()
        if point.map_group:
            folder_suffix = map_ext if map_ext else "map"
            folder_name = f"{base}_{folder_suffix}" if base else folder_suffix
            remote_dir = f"{remote_dir.rstrip('/')}/{folder_name}"
            parts = [p for p in [base, map_ext, label] if p]
        else:
            parts = [p for p in [base, label] if p]
        filename = "_".join(parts) if parts else ""
        file_template = det.file_template if det else ""
        return remote_dir, filename, file_settings.frame_number, disable_auto_increment, file_template

    @staticmethod
    def _find_motor(config: BeamlineConfig, shorthand: str) -> MotorConfig | None:
        all_motors = list(config.motors)
        if config.rotation_motor:
            all_motors = [config.rotation_motor] + all_motors
        return next((m for m in all_motors if m.shorthand == shorthand), None)
