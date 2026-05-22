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
from typing import Callable

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
        """Validate a point before scanning.

        Returns an error string if the scan cannot proceed, or None if OK.
        Currently always returns None (empty pre-scan hook).
        """
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

        driver = get_driver(motor_cfg.controller)
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
