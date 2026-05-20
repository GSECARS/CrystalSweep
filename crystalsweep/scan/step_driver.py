#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/scan/step_driver.py
# ----------------------------------------------------------------------------------
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
import time
from typing import Callable

from epics import caput

from crystalsweep.scan.driver import ScanSpec

__all__ = ["StepDriver"]

_log = logging.getLogger(__name__)


class StepDriver:
    """EPICS caput step-scan: move → settle → expose → repeat."""

    def __init__(self) -> None:
        self._abort = False

    def prepare(self, spec: ScanSpec) -> None:
        if not spec.pv:
            raise ValueError("StepDriver requires a non-empty PV.")
        if spec.points < 1:
            raise ValueError(f"points must be >= 1, got {spec.points}.")
        if spec.exposure <= 0:
            raise ValueError(f"exposure must be > 0, got {spec.exposure}.")

    def run(self, spec: ScanSpec, on_point: Callable[[int, float], None]) -> None:
        self._abort = False
        settle = float(spec.controller_params.get("settle_time", 0.05))

        for i, pos in enumerate(spec.positions()):
            if self._abort:
                _log.info("StepDriver aborted at point %d", i)
                break
            caput(spec.pv, pos, wait=True)
            time.sleep(settle)
            time.sleep(spec.exposure)
            on_point(i, pos)
            _log.debug("StepDriver point %d/%d pos=%.4f", i + 1, spec.points, pos)

    def abort(self) -> None:
        self._abort = True
