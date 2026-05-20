#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/scan/engine.py
# ----------------------------------------------------------------------------------
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
import threading
from typing import Callable

from crystalsweep.model.beamline_config_model import BeamlineConfig, MotorConfig
from crystalsweep.model.collection_model import CollectionPoint
from crystalsweep.scan.driver import ScanSpec
from crystalsweep.scan.registry import get_driver

__all__ = ["ScanEngine"]

_log = logging.getLogger(__name__)


class ScanEngine:
    """Runs a single CollectionPoint scan in a background thread."""

    def __init__(self) -> None:
        self._driver = None
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

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

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()

    def abort(self) -> None:
        if self._driver is not None:
            self._driver.abort()

    @staticmethod
    def _find_motor(config: BeamlineConfig, shorthand: str) -> MotorConfig | None:
        return next((m for m in config.motors if m.shorthand == shorthand), None)
