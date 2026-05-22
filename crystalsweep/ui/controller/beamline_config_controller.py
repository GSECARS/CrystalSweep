#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/controller/beamline_config_controller.py
# ----------------------------------------------------------------------------------
# Purpose:
# Controller bridging the beamline configuration model and the four modal
# configuration dialogs (General, Detectors, Controllers, Positioners) plus
# File-menu load / save / save-as actions.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
import threading
from typing import Callable

import wx

from crystalsweep.model import BeamlineConfig, MainModel
from crystalsweep.ui.view import (
    ControllersConfigDialog,
    DetectorsConfigDialog,
    GeneralConfigDialog,
    MainView,
    PositionersConfigDialog,
)

__all__ = ["BeamlineConfigController"]

_log = logging.getLogger(__name__)


class BeamlineConfigController:
    """Bridges the beamline configuration model and the four config dialogs."""

    def __init__(
        self,
        model: MainModel,
        view: MainView,
        on_config_applied: Callable[[BeamlineConfig], None] | None = None,
    ) -> None:
        self._model = model
        self._view = view
        self._on_config_applied = on_config_applied

        self._general_dlg: GeneralConfigDialog | None = None
        self._detectors_dlg: DetectorsConfigDialog | None = None
        self._controllers_dlg: ControllersConfigDialog | None = None
        self._positioners_dlg: PositionersConfigDialog | None = None

        self._view.bind_open_general(self.open_general)
        self._view.bind_open_detectors(self.open_detectors)
        self._view.bind_open_controllers(self.open_controllers)
        self._view.bind_open_positioners(self.open_positioners)
        self._view.bind_load_config(self.load_config)
        self._view.bind_save_config(self.save_config)
        self._view.bind_save_config_as(self.save_config_as)

    def has_active_config(self) -> bool:
        return self._model.beamline.has_active

    def load_config(self) -> None:
        names = self._model.beamline.list_config_names()
        if not names:
            wx.MessageBox("No configurations found. Create one via Save config as.", "No configurations", wx.OK | wx.ICON_INFORMATION)
            return
        with wx.SingleChoiceDialog(self._view, "Select a configuration to load:", "Load configuration", names) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            name = dlg.GetStringSelection()
        self._switch_to(name)

    def save_config(self) -> None:
        cfg = self._model.beamline.active
        if not cfg.name:
            self.save_config_as()
            return
        self._save(self._build_updated_config(cfg.name))

    def save_config_as(self) -> None:
        with wx.TextEntryDialog(self._view, "Configuration name (e.g. 2026-2):", "Save configuration as") as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            name = dlg.GetValue().strip()
        if not name:
            return
        self._save(self._build_updated_config(name))

    def open_general(self) -> None:
        if self._general_dlg is None:
            self._general_dlg = GeneralConfigDialog(self._view)
            self._general_dlg.config_panel.bind_save(self.save_config)
            self._general_dlg.Bind(wx.EVT_CLOSE, lambda e: self._hide_dialog(self._general_dlg, e))

        self._general_dlg.config_panel.load_config(self._model.beamline.active)
        self._show(self._general_dlg)

    def open_detectors(self) -> None:
        if self._detectors_dlg is None:
            self._detectors_dlg = DetectorsConfigDialog(self._view)
            self._detectors_dlg.config_panel.bind_save(self.save_config)
            self._detectors_dlg.Bind(wx.EVT_CLOSE, lambda e: self._hide_dialog(self._detectors_dlg, e))

        self._detectors_dlg.config_panel.load_config(self._model.beamline.active)
        self._show(self._detectors_dlg)

    def open_controllers(self) -> None:
        if self._controllers_dlg is None:
            self._controllers_dlg = ControllersConfigDialog(self._view)
            self._controllers_dlg.config_panel.bind_save(self.save_config)
            self._controllers_dlg.Bind(wx.EVT_CLOSE, lambda e: self._hide_dialog(self._controllers_dlg, e))

        self._controllers_dlg.config_panel.load_config(self._model.beamline.active)
        self._show(self._controllers_dlg)

    def open_positioners(self) -> None:
        if self._positioners_dlg is None:
            self._positioners_dlg = PositionersConfigDialog(self._view)
            self._positioners_dlg.config_panel.bind_save(self.save_config)
            self._positioners_dlg.Bind(wx.EVT_CLOSE, lambda e: self._hide_dialog(self._positioners_dlg, e))

        cfg = self._model.beamline.active
        panel = self._positioners_dlg.config_panel
        panel.set_controller_names(
            [c.name for c in cfg.controllers if c.name],
            {c.name: c.type for c in cfg.controllers if c.name},
        )
        panel.load_config(cfg)
        self._show(self._positioners_dlg)

    def _show(self, dlg: wx.Dialog) -> None:
        dlg.Show()
        dlg.Raise()

    @staticmethod
    def _hide_dialog(dlg: wx.Dialog | None, event: wx.CloseEvent) -> None:
        if dlg is not None:
            dlg.Hide()
        event.Veto() if event.CanVeto() else event.Skip()

    def _apply(self, cfg: BeamlineConfig) -> None:
        self._model.beamline.remember_active(cfg.name)
        self._view.set_active_config_name(cfg.name)
        if self._on_config_applied is not None:
            self._on_config_applied(cfg)

    def _reload_all_open(self, cfg: BeamlineConfig) -> None:
        if self._general_dlg is not None:
            self._general_dlg.config_panel.load_config(cfg)
        if self._detectors_dlg is not None:
            self._detectors_dlg.config_panel.load_config(cfg)
        if self._controllers_dlg is not None:
            self._controllers_dlg.config_panel.load_config(cfg)
        if self._positioners_dlg is not None:
            p = self._positioners_dlg.config_panel
            p.set_controller_names(
                [c.name for c in cfg.controllers if c.name],
                {c.name: c.type for c in cfg.controllers if c.name},
            )
            p.load_config(cfg)

    def _switch_to(self, name: str) -> None:
        try:
            cfg = self._model.beamline.load(name)
        except Exception as exc:
            _log.exception("Failed to load beamline config %s", name)
            wx.MessageBox(f"Failed to load configuration '{name}':\n{exc}", "Error", wx.OK | wx.ICON_ERROR)
            return
        self._reload_all_open(cfg)
        self._apply(cfg)

    def _build_updated_config(self, name: str) -> BeamlineConfig:
        """Merge edits from all open panels into a single BeamlineConfig."""
        base = self._model.beamline.active

        beamline = self._general_dlg.config_panel.beamline_name() if self._general_dlg else base.beamline

        if self._detectors_dlg:
            detectors, active_detector = self._detectors_dlg.config_panel.collect_detectors()
        else:
            detectors, active_detector = base.detectors, base.active_detector

        controllers = self._controllers_dlg.config_panel.collect_controllers() if self._controllers_dlg else base.controllers

        if self._positioners_dlg:
            rotation_motor = self._positioners_dlg.config_panel.collect_rotation_motor()
            motors = self._positioners_dlg.config_panel.collect_motors()
        else:
            rotation_motor, motors = base.rotation_motor, base.motors

        return BeamlineConfig(
            name=name,
            beamline=beamline,
            rotation_motor=rotation_motor,
            detectors=detectors,
            active_detector=active_detector,
            controllers=controllers,
            motors=motors,
        )

    def _save(self, config: BeamlineConfig) -> None:
        if not config.detectors:
            self._set_status_all("At least one detector is required.", error=True)
            return

        if config.rotation_motor is None or not config.rotation_motor.pv.strip():
            self._set_status_all("Rotation stage PV is required.", error=True)
            return

        shorthands = [m.shorthand for m in config.motors if m.shorthand]
        if len(shorthands) != len(set(shorthands)):
            self._set_status_all("Motor shorthands must be unique.", error=True)
            return

        all_motors = [config.rotation_motor] + list(config.motors) if config.rotation_motor else list(config.motors)
        pvs = [m.pv.strip() for m in all_motors if m.pv.strip()]

        def _check_pvs() -> None:
            offline = [pv for pv in pvs if not self._model.epics.is_online(pv)]
            if offline:
                wx.CallAfter(self._set_status_all, f"Warning: PV(s) unreachable: {', '.join(offline)}", True)

        threading.Thread(target=_check_pvs, daemon=True).start()

        try:
            path = self._model.beamline.save(config)
        except Exception as exc:
            _log.exception("Failed to save beamline config %s", config.name)
            self._set_status_all(f"Save failed: {exc}", error=True)
            return

        if config.controllers:
            self._model.controllers.apply_config(config.controllers)

        self._reload_all_open(config)
        self._set_status_all(f"Saved to {path}.")
        self._apply(config)

    def _set_status_all(self, text: str, error: bool = False) -> None:
        for dlg in (self._general_dlg, self._detectors_dlg, self._controllers_dlg, self._positioners_dlg):
            if dlg is not None:
                dlg.config_panel.set_status(text, error)
