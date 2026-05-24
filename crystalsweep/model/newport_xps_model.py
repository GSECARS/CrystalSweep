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

import numpy as np
from epics import caget

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

        group = p.get("xps_group")
        positioner = p.get("xps_positioner")
        omega_range = abs(spec.end - spec.start)

        if group and positioner and spec.points == 1:
            self._xps.define_line_trajectories_general(
                stop_values=[[0, 0, 0, omega_range]],
                scan_time=spec.exposure,
                pulse_time=0.1,
                accel_values=None,
            )
            _log.debug("NewportXPSModel wide trajectory defined (range=%.4f exposure=%.4f)", omega_range, spec.exposure)

        elif group and positioner and spec.points > 1:
            total_time = spec.exposure * spec.points
            self._xps.define_line_trajectories_general(
                stop_values=[[0, 0, 0, omega_range]],
                scan_time=total_time,
                pulse_time=spec.exposure,
                accel_values=None,
            )
            _log.debug(
                "NewportXPSModel step trajectory defined (range=%.4f exposure=%.4f points=%d)",
                omega_range, spec.exposure, spec.points,
            )

    def run(self, spec: ScanSpec, on_point: Callable[[int, float], None]) -> None:
        if self._aborted:
            _log.info("NewportXPSModel aborted before run()")
            return

        p = spec.controller_params
        group = p.get("xps_group")
        positioner = p.get("xps_positioner")

        if group and positioner and spec.points == 1:
            if not self._aborted:
                self._xps.run_line_trajectory_general()
                _log.debug("NewportXPSModel wide trajectory complete")
            if not self._aborted:
                on_point(0, spec.end)
            return

        if group and positioner and spec.points > 1:
            if not self._aborted:
                self._xps.run_line_trajectory_general()
                _log.debug("NewportXPSModel step trajectory complete (points=%d)", spec.points)
            if not self._aborted:
                on_point(spec.points - 1, spec.end)
            return

        for i, pos in enumerate(spec.positions()):
            if self._aborted:
                _log.info("NewportXPSModel aborted at point %d", i)
                break
            on_point(i, pos)
            _log.debug("NewportXPSModel point %d/%d pos=%.4f", i + 1, spec.points, pos)

    def prepare_array(self, motor_pv: str, epics_positions: list[float], exposure: float, positioner_name: str, group_name: str) -> None:
        """Prepare an array trajectory for a linear map motor using define_array_trajectory."""
        if self._xps is None:
            raise RuntimeError("XPS not connected. Call prepare() first.")

        pv_base = motor_pv.removesuffix(".VAL")
        try:
            offset = float(caget(f"{pv_base}.OFF") or 0.0)
        except Exception:
            offset = 0.0
        try:
            direction = int(caget(f"{pv_base}.DIR") or 0)
        except Exception:
            direction = 0

        if direction:
            xps_positions = [(p - offset) * -1 for p in epics_positions]
        else:
            xps_positions = [p - offset for p in epics_positions]

        axis_name = positioner_name
        if axis_name.startswith(group_name):
            axis_name = axis_name[len(group_name):].lstrip("-.")

        self._xps.set_trajectory_group(group_name)
        result = self._xps.define_array_trajectory(
            positions={axis_name: np.array(xps_positions)},
            dtime=exposure,
            name="forward",
            verbose=False,
        )
        if result is None:
            raise RuntimeError(
                f"define_array_trajectory failed — check positioner name '{axis_name}' "
                f"against XPS group '{group_name}' axes."
            )
        _log.debug("NewportXPSModel array trajectory defined: %d positions, dtime=%.4f", len(xps_positions), exposure)

    def run_array(self, on_point: Callable[[int, float], None], n_points: int) -> None:
        """Run the previously defined array trajectory."""
        if self._aborted:
            return
        self._xps.arm_trajectory(name="forward", move_to_start=True)
        self._xps.run_trajectory(name="forward", save=False, clean=True, move_to_start=False)
        _log.debug("NewportXPSModel array trajectory complete")
        if not self._aborted:
            on_point(n_points - 1, 0.0)

    def abort(self) -> None:
        self._aborted = True
        if self._xps is not None:
            try:
                self._xps.abort_all()
            except Exception:
                pass
