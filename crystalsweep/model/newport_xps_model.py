#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/newport_xps_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Slew-scan model for Newport XPS motion controllers using the newportxps library.
#
# Required controller_params (from ControllerConfig.params):
#   host        - XPS controller IP or hostname
#   username    - XPS username (default "Administrator")
#   password    - XPS password
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
from typing import Callable

from crystalsweep.model.scan_model import ScanSpec

__all__ = ["NewportXPSModel"]

_log = logging.getLogger(__name__)

_MISSING = "newportxps is not installed. Run: pip install newportxps"

try:
    from newportxps import NewportXPS
except ImportError:
    NewportXPS = None  # type: ignore[assignment,misc]


class NewportXPSModel:
    """Slew-scan model for Newport XPS motion controllers."""

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
            raise ValueError("NewportXPSModel requires controller_params['host'].")

        self._xps = NewportXPS(
            p["host"],
            username=p.get("username", "Administrator"),
            password=p.get("password", ""),
        )
        _log.debug("NewportXPSModel connected to %s", p["host"])

    def run(self, spec: ScanSpec, on_point: Callable[[int, float], None]) -> None:
        if self._aborted:
            _log.info("NewportXPSModel aborted before run()")
            return

        p = spec.controller_params
        group = p.get("xps_group")
        positioner = p.get("xps_positioner")

        if group and positioner and spec.points == 1:
            self._run_wide_trajectory(spec, group, positioner)
            if not self._aborted:
                on_point(0, spec.end)
            return

        for i, pos in enumerate(spec.positions()):
            if self._aborted:
                _log.info("NewportXPSModel aborted at point %d", i)
                break
            on_point(i, pos)
            _log.debug("NewportXPSModel point %d/%d pos=%.4f", i + 1, spec.points, pos)

    def _run_wide_trajectory(self, spec: ScanSpec, group: str, positioner: str) -> None:
        omega_range = abs(spec.end - spec.start)
        self._xps.define_line_trajectories_general(
            stop_values=[[0, 0, 0, omega_range]],
            scan_time=spec.exposure,
            pulse_time=0.1,
            accel_values=None,
        )
        if self._aborted:
            return
        self._xps.run_line_trajectory_general()
        _log.debug("NewportXPSModel wide trajectory complete (range=%.4f exposure=%.4f)", omega_range, spec.exposure)

    def abort(self) -> None:
        self._aborted = True
        if self._xps is not None:
            try:
                self._xps.abort_all()
            except Exception:
                pass
