#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/aerotech_a1_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Slew-scan model for Aerotech Automation1 controllers using the pyautomation library.
# Executes a single continuous trajectory (start → end) with hardware-timed
# detector pulses — one pulse per point, all triggered by the controller.
#
# Required controller_params (from ControllerConfig.params):
#   ip              - controller IP address
#   axis_name       - axis name in Automation1 (e.g. "Theta")
#   counts_per_unit - encoder counts per physical unit (e.g. 1491308.09)
#
# Optional controller_params:
#   username            - Automation1 username (default "")
#   password            - Automation1 password (default "")
#   travel_direction    - 1 (positive) or -1 (negative), default 1
#   pso_distance_input  - PSO distance input enum name, default "iXC4ePrimaryFeedback"
#   pso_window_input    - PSO window input enum name, default "iXC4ePrimaryFeedback"
#   pso_output_pin      - PSO output pin enum name, default "iXC4eAuxiliaryMarkerDifferential"
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
from typing import Callable

from epics import caget, caput

from crystalsweep.model.scan_model import ScanSpec

__all__ = ["AerotechA1Model"]

_log = logging.getLogger(__name__)

_MISSING = "pyautomation is not installed. Run: pip install pyautomation"

try:
    from pyautomation import PyAutomation, PsoDistanceInput, PsoOutputPin, PsoWindowInput
    from pyautomation.controller import AutomationAxis
    from pyautomation.modules import Trajectory
except ImportError:
    PyAutomation = None  # type: ignore[assignment,misc]
    AutomationAxis = None  # type: ignore[assignment,misc]
    Trajectory = None  # type: ignore[assignment,misc]
    PsoDistanceInput = None  # type: ignore[assignment,misc]
    PsoWindowInput = None  # type: ignore[assignment,misc]
    PsoOutputPin = None  # type: ignore[assignment,misc]


class AerotechA1Model:
    """Slew-scan model for Aerotech Automation1 controllers."""

    def __init__(self) -> None:
        self._automation = None
        self._aborted = False

    def prepare(self, spec: ScanSpec) -> None:
        if spec.points == 1:
            return

        if PyAutomation is None:
            raise RuntimeError(_MISSING)
        if spec.points < 1:
            raise ValueError(f"points must be >= 1, got {spec.points}.")
        if spec.exposure <= 0:
            raise ValueError(f"exposure must be > 0, got {spec.exposure}.")

        p = spec.controller_params
        for key in ("ip", "axis_name", "counts_per_unit"):
            if not p.get(key):
                raise ValueError(f"AerotechA1Model requires controller_params['{key}'].")

        axis = AutomationAxis(
            name=p["axis_name"],
            counts_per_unit=float(p["counts_per_unit"]),
        )
        self._automation = PyAutomation(
            ip=p["ip"],
            axis=[axis],
            verbose=bool(p.get("verbose", False)),
            pso_distance_input=getattr(PsoDistanceInput, p.get("pso_distance_input", "iXC4ePrimaryFeedback")),
            pso_window_input=getattr(PsoWindowInput, p.get("pso_window_input", "iXC4ePrimaryFeedback")),
            pso_output_pin=getattr(PsoOutputPin, p.get("pso_output_pin", "iXC4eAuxiliaryMarkerDifferential")),
        )
        self._automation.enable_controller()
        _log.debug("AerotechA1Model connected and enabled (%s, axis=%s)", p["ip"], p["axis_name"])

    def run(self, spec: ScanSpec, on_point: Callable[[int, float], None]) -> None:
        if self._aborted:
            _log.info("AerotechA1Model aborted before run()")
            return

        if spec.points == 1 and spec.pv:
            self._run_wide_slew(spec)
            if not self._aborted:
                on_point(0, spec.end)
            return

        travel_direction = int(spec.controller_params.get("travel_direction", 1))

        trajectory = Trajectory(
            start_position=spec.start,
            end_position=spec.end,
            exposure=spec.exposure,
            number_of_pulses=spec.points,
            travel_direction=travel_direction,
        )

        self._automation.load_trajectory(trajectory)
        _log.debug(
            "AerotechA1Model: trajectory loaded (start=%.4f end=%.4f exposure=%.4f points=%d dir=%d)",
            spec.start, spec.end, spec.exposure, spec.points, travel_direction,
        )

        if self._aborted:
            _log.info("AerotechA1Model aborted before run_trajectory()")
            return

        self._automation.run_trajectory()
        _log.debug("AerotechA1Model: trajectory complete")

        if not self._aborted:
            on_point(0, spec.end)

    def _run_wide_slew(self, spec: ScanSpec) -> None:
        pv_base = spec.pv.removesuffix(".VAL")
        delta = abs(spec.end - spec.start)
        velocity = delta / spec.exposure

        old_velocity = caget(f"{pv_base}.VELO")
        caput(f"{pv_base}.VELO", velocity, wait=True)
        caput(f"{pv_base}.VAL", spec.end, wait=True)
        caput(f"{pv_base}.VELO", old_velocity, wait=True)

        _log.debug(
            "AerotechA1Model wide slew: pv=%s end=%.4f velocity=%.4f",
            pv_base, spec.end, velocity,
        )

    def abort(self) -> None:
        self._aborted = True
        if self._automation is not None:
            try:
                self._automation.abort_trajectory()
            except Exception:
                pass
