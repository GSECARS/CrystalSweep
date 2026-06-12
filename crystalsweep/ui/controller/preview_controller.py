#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/controller/preview_controller.py
# ----------------------------------------------------------------------------------
# Purpose:
# Controller for the Preview tab inside the Single-Crystal Centering Tools
# section.  Manages the centering-motors column: it builds rows from the active
# beamline config, subscribes camonitor() on each motor's readback PV, and
# performs relative caput moves when the user clicks the jog arrows.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
import threading

import wx
from epics import caget, camonitor, camonitor_clear, caput

from crystalsweep.model import MainModel
from crystalsweep.model.beamline_config_model import BeamlineConfig, MotorConfig
from crystalsweep.ui.view.preview_view import CenteringMotorSpec, PreviewView

__all__ = ["PreviewController"]

_log = logging.getLogger(__name__)


def _rbv_pv(pv: str) -> str:
    """Return the canonical readback PV name for a motor record .VAL field."""
    base = pv.removesuffix(".VAL")
    return f"{base}.RBV"


def _val_pv(pv: str) -> str:
    """Return the canonical setpoint PV (always with the .VAL field)."""
    base = pv.removesuffix(".VAL")
    return f"{base}.VAL"


class PreviewController:
    """Bridges PreviewView with the active beamline config and EPICS."""

    def __init__(self, model: MainModel, view: PreviewView) -> None:
        self._model = model
        self._view = view
        self._monitored_rbvs: list[str] = []
        # Map readback PV -> setpoint PV so the camonitor callback can locate
        # the row to update via view.update_centering_value(pv=setpoint).
        self._rbv_to_setpoint: dict[str, str] = {}

        self._view.bind_jog_minus(self._on_jog_minus)
        self._view.bind_jog_plus(self._on_jog_plus)

        self.on_config_applied(self._model.beamline.active)

    def on_config_applied(self, cfg: BeamlineConfig | None) -> None:
        """Rebuild rows + monitors whenever the active beamline config changes."""
        self._clear_monitors()
        specs = self._collect_specs(cfg)
        self._view.set_centering_motors(specs)
        if not specs:
            return
        self._subscribe_monitors(specs)
        self._prime_initial_values(specs)

    def shutdown(self) -> None:
        """Best-effort cleanup; safe to call multiple times."""
        self._clear_monitors()

    @staticmethod
    def _collect_specs(cfg: BeamlineConfig | None) -> list[CenteringMotorSpec]:
        if cfg is None:
            return []
        specs: list[CenteringMotorSpec] = []
        candidates: list[MotorConfig] = []
        if cfg.rotation_motor is not None:
            candidates.append(cfg.rotation_motor)
        candidates.extend(cfg.motors)
        for m in candidates:
            if not m.centering_enabled:
                continue
            if not m.pv.strip():
                continue
            specs.append(
                CenteringMotorSpec(
                    shorthand=m.shorthand,
                    description=m.description,
                    pv=m.pv.strip(),
                    precision=m.precision,
                )
            )
        return specs

    def _subscribe_monitors(self, specs: list[CenteringMotorSpec]) -> None:
        for spec in specs:
            rbv = _rbv_pv(spec.pv)
            self._rbv_to_setpoint[rbv] = spec.pv
            try:
                camonitor(rbv, callback=self._on_rbv_change)
                self._monitored_rbvs.append(rbv)
            except Exception as exc:
                _log.warning("Failed to camonitor %s: %s", rbv, exc)

    def _prime_initial_values(self, specs: list[CenteringMotorSpec]) -> None:
        """Push initial readbacks so rows show a value before the first monitor event."""

        def _worker() -> None:
            for spec in specs:
                value: float | None
                try:
                    raw = caget(_rbv_pv(spec.pv))
                    value = float(raw) if raw is not None else None
                except Exception:
                    value = None
                wx.CallAfter(self._view.update_centering_value, spec.pv, value)

        threading.Thread(target=_worker, daemon=True, name="centering-prime").start()

    def _clear_monitors(self) -> None:
        for pv in self._monitored_rbvs:
            try:
                camonitor_clear(pv)
            except Exception:
                pass
        self._monitored_rbvs.clear()
        self._rbv_to_setpoint.clear()

    def _on_rbv_change(self, pvname: str = "", value=None, **_: object) -> None:
        setpoint = self._rbv_to_setpoint.get(pvname)
        if setpoint is None:
            return
        try:
            numeric: float | None = float(value) if value is not None else None
        except (TypeError, ValueError):
            numeric = None
        wx.CallAfter(self._view.update_centering_value, setpoint, numeric)

    def _on_jog_minus(self, spec: CenteringMotorSpec) -> None:
        self._jog(spec, sign=-1.0)

    def _on_jog_plus(self, spec: CenteringMotorSpec) -> None:
        self._jog(spec, sign=+1.0)

    def _jog(self, spec: CenteringMotorSpec, sign: float) -> None:
        step_mm = self._view.step_mm
        if step_mm <= 0:
            return
        delta = sign * step_mm
        setpoint = _val_pv(spec.pv)
        readback = _rbv_pv(spec.pv)

        def _worker() -> None:
            try:
                current = caget(readback)
                if current is None:
                    current = caget(setpoint)
                if current is None:
                    return
                target = float(current) + delta
                caput(setpoint, target, wait=False)
            except Exception as exc:
                _log.warning("Jog failed for %s: %s", spec.pv, exc)

        threading.Thread(target=_worker, daemon=True, name=f"jog-{spec.shorthand or spec.pv}").start()
