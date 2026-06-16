#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/newport_xps_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Slew-scan model for Newport XPS motion controllers. Matches SXRD_Collect:
# define_line_trajectories with start=0/stop=range (relative), caller pre-moves
# omega to start, arm/run with move_to_start=False. Reuses a live NewportXPS
# connection passed in via controller_params['_xps_connection'].
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

    _TRAJ_NAME = "foreward"

    def __init__(self) -> None:
        self._xps = None
        self._owns_connection = False
        self._aborted = False
        self._has_line_traj = False

    def prepare(self, spec: ScanSpec) -> None:
        if NewportXPS is None:
            raise RuntimeError(_MISSING)
        if spec.points < 1:
            raise ValueError(f"points must be >= 1, got {spec.points}.")
        if spec.exposure <= 0:
            raise ValueError(f"exposure must be > 0, got {spec.exposure}.")

        p = spec.controller_params
        shared = p.get("_connection")
        if isinstance(shared, NewportXPS):
            self._xps = shared
            self._owns_connection = False
        else:
            if not p.get("host"):
                raise ValueError("NewportXPSModel requires controller_params['host'] when no shared connection is provided.")
            self._xps = NewportXPS(
                p["host"],
                username=p.get("username", "Administrator"),
                password=p.get("password", ""),
            )
            self._owns_connection = True
            _log.debug("NewportXPSModel opened connection to %s", p["host"])

        group = p.get("xps_group")
        positioner = p.get("xps_positioner")

        if not group or not positioner:
            self._has_line_traj = False
            _log.info("NewportXPSModel prepare: no xps_group/xps_positioner; skipping trajectory definition")
            return

        axis_name = self._axis_name(positioner, group)
        signed_range = self._epics_to_xps_range(spec.pv, spec.start, spec.end)
        rng = abs(signed_range)
        if rng == 0.0:
            raise ValueError("XPS slew scan requires spec.start != spec.end.")

        if spec.points == 1:
            step = 0.01
            scantime = spec.exposure
        else:
            step = rng / spec.points
            scantime = spec.exposure * spec.points

        self._define_line_trajectory(group, axis_name, 0.0, signed_range, step, scantime)
        self._has_line_traj = True

        _log.debug(
            "NewportXPSModel prepare: group=%s axis=%s stop=%.4f step=%.4f scantime=%.4f points=%d",
            group, axis_name, signed_range, step, scantime, spec.points,
        )

    def run(
        self,
        spec: ScanSpec,
        on_point: Callable[[int, float], None],
        on_at_start: Callable[[], None] | None = None,
    ) -> None:
        if self._aborted:
            return

        if self._has_line_traj:
            if self._xps is None:
                raise RuntimeError("XPS not connected. Call prepare() first.")
            self._xps.arm_trajectory(name=self._TRAJ_NAME, move_to_start=False)
            if on_at_start is not None and not self._aborted:
                on_at_start()
            if self._aborted:
                return
            self._xps.run_trajectory(name=self._TRAJ_NAME, save=False, clean=True, move_to_start=False)
            if not self._aborted:
                on_point(spec.points - 1, spec.end)
            return

        if on_at_start is not None:
            on_at_start()
        for i, pos in enumerate(spec.positions()):
            if self._aborted:
                break
            on_point(i, pos)

    def prepare_array(
        self,
        motor_pv: str,
        epics_positions: list[float],
        exposure: float,
        positioner_name: str,
        group_name: str,
    ) -> None:
        if self._xps is None:
            raise RuntimeError("XPS not connected. Call prepare() first.")
        self._define_array_trajectory(motor_pv, epics_positions, exposure, positioner_name, group_name)
        self._has_line_traj = False

    def run_array(
        self,
        on_point: Callable[[int, float], None],
        n_points: int,
        on_at_start: Callable[[], None] | None = None,
    ) -> None:
        if self._aborted:
            return
        self._xps.arm_trajectory(name="forward", move_to_start=True)
        if on_at_start is not None:
            on_at_start()
        self._xps.run_trajectory(name="forward", save=False, clean=True, move_to_start=False)
        if not self._aborted:
            on_point(n_points - 1, 0.0)

    @staticmethod
    def _axis_name(positioner: str, group: str) -> str:
        if positioner.startswith(group):
            return positioner[len(group):].lstrip("-.")
        return positioner

    @staticmethod
    def _epics_to_xps_range(motor_pv: str, start: float, end: float) -> float:
        pv_base = motor_pv.removesuffix(".VAL")
        try:
            direction = int(caget(f"{pv_base}.DIR") or 0)
        except Exception:
            direction = 0
        delta = end - start
        return -delta if direction else delta

    def _define_line_trajectory(
        self,
        group_name: str,
        axis_name: str,
        start_xps: float,
        stop_xps: float,
        step: float,
        scantime: float,
    ) -> None:
        if self._xps is None:
            raise RuntimeError("XPS not connected.")
        self._xps.set_trajectory_group(group_name)
        ret = self._xps.define_line_trajectories(
            axis=axis_name,
            group=group_name,
            start=start_xps,
            stop=stop_xps,
            step=step,
            scantime=scantime,
            verbose=False,
        )
        if ret is False:
            raise RuntimeError(
                f"define_line_trajectories failed — check positioner '{axis_name}' in XPS group '{group_name}'."
            )
        traj = self._xps.trajectories.get(self._TRAJ_NAME, {})
        if traj:
            _log.info(
                "NewportXPSModel line trajectory: group=%s axis=%s stop=%.4f step=%.4f scantime=%.4f -> pixeltime=%s npulses=%s",
                group_name, axis_name, stop_xps, step, scantime,
                traj.get("pixeltime"), traj.get("npulses"),
            )

    def _define_array_trajectory(
        self,
        motor_pv: str,
        epics_positions: list[float],
        exposure: float,
        positioner_name: str,
        group_name: str,
    ) -> None:
        if self._xps is None:
            raise RuntimeError("XPS not connected.")
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
        axis_name = self._axis_name(positioner_name, group_name)
        self._xps.set_trajectory_group(group_name)
        result = self._xps.define_array_trajectory(
            positions={axis_name: np.array(xps_positions)},
            dtime=exposure,
            name="forward",
            verbose=False,
        )
        if result is None:
            raise RuntimeError(
                f"define_array_trajectory failed — check positioner name '{axis_name}' against XPS group '{group_name}' axes."
            )

    def abort(self) -> None:
        self._aborted = True
        if self._xps is not None:
            try:
                self._xps.abort_all()
            except Exception:
                pass
