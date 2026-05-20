#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/scan/newport_xps.py
# ----------------------------------------------------------------------------------
# Purpose:
# Newport XPS slew-scan driver using the newportxps library.
#
# Required controller_params (set on ControllerConfig, passed through ScanSpec):
#   host        - XPS controller IP or hostname
#   username    - XPS username (default "Administrator")
#   password    - XPS password
# ----------------------------------------------------------------------------------
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
from typing import Callable

from crystalsweep.scan.driver import ScanSpec

__all__ = ["NewportXPSDriver"]

_log = logging.getLogger(__name__)

_MISSING = "newportxps is not installed. Run: pip install newportxps"

try:
    from newportxps import NewportXPS
except ImportError:
    NewportXPS = None  # type: ignore[assignment,misc]


class NewportXPSDriver:
    """Slew-scan driver for Newport XPS motion controllers."""

    def __init__(self) -> None:
        self._xps = None
        self._aborted = False

    def prepare(self, spec: ScanSpec) -> None:
        if NewportXPS is None:
            raise RuntimeError(_MISSING)
        if spec.points < 1:
            raise ValueError(f"points must be >= 1, got {spec.points}.")
        if spec.exposure <= 0:
            raise ValueError(f"exposure must be > 0, got {spec.exposure}.")

        p = spec.controller_params
        if not p.get("host"):
            raise ValueError("NewportXPSDriver requires controller_params['host'].")

        self._xps = NewportXPS(
            p["host"],
            username=p.get("username", "Administrator"),
            password=p.get("password", ""),
        )
        _log.debug("NewportXPSDriver connected to %s", p["host"])

    def run(self, spec: ScanSpec, on_point: Callable[[int, float], None]) -> None:
        if self._aborted:
            _log.info("NewportXPSDriver aborted before run()")
            return

        for i, pos in enumerate(spec.positions()):
            if self._aborted:
                _log.info("NewportXPSDriver aborted at point %d", i)
                break
            on_point(i, pos)
            _log.debug("NewportXPSDriver point %d/%d pos=%.4f", i + 1, spec.points, pos)

    def abort(self) -> None:
        self._aborted = True
        if self._xps is not None:
            try:
                self._xps.abort_all()
            except Exception:
                pass
