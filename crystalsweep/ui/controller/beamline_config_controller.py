#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/controller/beamline_config_controller.py
# ----------------------------------------------------------------------------------
# Purpose:
# Controller bridging the beamline configuration model and a modal configuration
# dialog opened from the File menu.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
from typing import Callable

import wx

from crystalsweep.model import BeamlineConfig, MainModel
from crystalsweep.ui.view import BeamlineConfigDialog, BeamlineConfigView, MainView

__all__ = ["BeamlineConfigController"]

_log = logging.getLogger(__name__)


class BeamlineConfigController:
    """Bridges the beamline configuration model and the modal config dialog."""

    def __init__(
        self,
        model: MainModel,
        view: MainView,
        on_config_applied: Callable[[BeamlineConfig], None] | None = None,
    ) -> None:
        self._model = model
        self._view = view
        self._on_config_applied = on_config_applied
        self._dialog: BeamlineConfigDialog | None = None

        self._view.bind_open_configuration(self.open_dialog)

    def has_active_config(self) -> bool:
        return self._model.beamline.has_active

    def open_dialog(self) -> None:
        """Show the configuration dialog (creating it lazily)."""
        if self._dialog is None:
            self._dialog = BeamlineConfigDialog(self._view)
            self._wire_panel(self._dialog.config_panel)
            self._dialog.Bind(wx.EVT_CLOSE, self._on_dialog_close)

        self._refresh_choices(active=self._model.beamline.active.name)
        self._dialog.config_panel.load_config(self._model.beamline.active)
        if not self._model.beamline.has_active:
            available = self._model.beamline.list_config_names()
            if available:
                self._dialog.config_panel.set_status(
                    "No active configuration. Pick one above or create a new one.",
                )
            else:
                self._dialog.config_panel.set_status(
                    "No configurations found. Click 'New' to create your first one.",
                )
        self._dialog.Show()
        self._dialog.Raise()

    def _wire_panel(self, panel: BeamlineConfigView) -> None:
        panel.bind_active_config_changed(self._on_active_changed)
        panel.bind_create(self._on_create)
        panel.bind_save(self._on_save)

    def _refresh_choices(self, active: str | None = None) -> None:
        if self._dialog is None:
            return
        names = self._model.beamline.list_config_names()
        self._dialog.config_panel.set_available_configs(names, active=active)

    def _on_dialog_close(self, event: wx.CloseEvent) -> None:
        # Hide instead of destroying so the dialog state is reused next time it is opened.
        if self._dialog is not None:
            self._dialog.Hide()
        event.Veto() if event.CanVeto() else event.Skip()

    def _apply(self, cfg: BeamlineConfig) -> None:
        self._model.beamline.remember_active(cfg.name)
        if self._on_config_applied is not None:
            self._on_config_applied(cfg)

    def _on_active_changed(self, name: str) -> None:
        try:
            cfg = self._model.beamline.load(name)
        except Exception as exc:
            _log.exception("Failed to load beamline config %s", name)
            wx.MessageBox(f"Failed to load configuration '{name}':\n{exc}", "Error", wx.OK | wx.ICON_ERROR)
            return

        if self._dialog is not None:
            self._dialog.config_panel.load_config(cfg)
            self._dialog.config_panel.set_status(f"Loaded '{name}'.")
        self._apply(cfg)

    def _on_create(self, name: str) -> None:
        if self._model.beamline.exists(name):
            wx.MessageBox(f"A configuration named '{name}' already exists.", "Already exists", wx.OK | wx.ICON_WARNING)
            return
        try:
            cfg = self._model.beamline.create_blank(name)
        except Exception as exc:
            _log.exception("Failed to create beamline config %s", name)
            wx.MessageBox(f"Failed to create configuration '{name}':\n{exc}", "Error", wx.OK | wx.ICON_ERROR)
            return
        self._refresh_choices(active=name)
        if self._dialog is not None:
            self._dialog.config_panel.load_config(cfg)
            self._dialog.config_panel.set_status(f"Created '{name}'.")
        self._apply(cfg)

    def _on_save(self, config: BeamlineConfig) -> None:
        if self._dialog is None:
            return
        panel = self._dialog.config_panel

        if not config.name:
            panel.set_status("No configuration selected. Use 'New' to create one.", error=True)
            return

        shorthands = [m.shorthand for m in config.motors if m.shorthand]
        if len(shorthands) != len(set(shorthands)):
            panel.set_status("Motor shorthands must be unique.", error=True)
            return

        try:
            path = self._model.beamline.save(config)
        except Exception as exc:
            _log.exception("Failed to save beamline config %s", config.name)
            panel.set_status(f"Save failed: {exc}", error=True)
            return

        self._refresh_choices(active=config.name)
        panel.set_status(f"Saved to {path}.")
        self._apply(config)
