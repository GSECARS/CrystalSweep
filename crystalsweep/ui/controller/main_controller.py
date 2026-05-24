#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/controller/main_controller.py
# ----------------------------------------------------------------------------------
# Purpose:
# This file is used to implement the main controller for the CrystalSweep
# application.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import sys
import threading

import wx

from crystalsweep.model import MainModel
from crystalsweep.model.beamline_config_model import BeamlineConfig
from crystalsweep.ui.controller.ad_viewer_controller import ADViewerController
from crystalsweep.ui.controller.beamline_config_controller import BeamlineConfigController
from crystalsweep.ui.controller.collect_controller import CollectController
from crystalsweep.ui.controller.collection_settings_controller import CollectionSettingsController
from crystalsweep.ui.controller.collection_table_controller import CollectionTableController
from crystalsweep.ui.controller.file_settings_controller import FileSettingsController
from crystalsweep.ui.controller.script_editor_controller import ScriptEditorController
from crystalsweep.ui.view import MainView

__all__ = ["MainController"]


class MainController:
    """Implements the main controller for the CrystalSweep application. Helps to bridge the gap between the model and view components."""

    def __init__(self, version: str) -> None:
        """Initializes the main controller."""
        if sys.platform == "win32":
            try:
                wx.App.SetDPIAwareness(wx.DPI_AWARENESS_CTX_PER_MONITOR_AWARE_V2)
            except AttributeError:
                import ctypes

                ctypes.windll.shcore.SetProcessDpiAwareness(2)

        self._app = wx.App(False)
        self._model = MainModel()
        self._view = MainView(version=version)

        self._file_settings_controller = FileSettingsController(model=self._model, view=self._view)
        self._collection_settings_controller = CollectionSettingsController(model=self._model, view=self._view)
        self._collection_controller = CollectionTableController(model=self._model, view=self._view.collection_table)
        self._collect_controller = CollectController(model=self._model, view=self._view)
        self._collect_controller.bind_collecting_changed(self._on_collecting_changed)
        self._collection_controller.add_points_changed_listener(self._collect_controller.refresh_eta)
        self._collection_settings_controller.add_points_changed_listener(self._collect_controller.refresh_eta)
        self._ad_viewer_controller = ADViewerController(model=self._model, view=self._view)
        self._beamline_config_controller = BeamlineConfigController(
            model=self._model,
            view=self._view,
            on_config_applied=self._on_config_applied,
        )
        self._script_editor_controller = ScriptEditorController(
            model=self._model.scripts,
            view=self._view,
        )

    def _on_collecting_changed(self, collecting: bool) -> None:
        self._view.set_ui_collecting(collecting)
        self._beamline_config_controller.set_collecting(collecting)

    def _on_config_applied(self, cfg: BeamlineConfig) -> None:
        self._ad_viewer_controller.resubscribe_detector()
        self._collection_controller.on_config_applied(cfg)
        self._collection_settings_controller.on_config_applied()
        self._file_settings_controller.sync_from_detector()
        self._file_settings_controller.push_to_detector()
        self._check_epics_status(cfg)

    def _check_epics_status(self, cfg: BeamlineConfig | None = None) -> None:
        if cfg is None:
            cfg = self._model.beamline.active

        def _worker() -> None:
            pvs: list[str] = []
            if cfg.rotation_motor and cfg.rotation_motor.pv.strip():
                pvs.append(cfg.rotation_motor.pv.strip())
            det = cfg.active_detector_config
            if det and det.pv_prefix.strip():
                prefix = det.pv_prefix.strip()
                if not prefix.endswith(":"):
                    prefix += ":"
                pvs.append(f"{prefix}cam1:Acquire")
            for motor in cfg.motors:
                if motor.pv.strip():
                    pvs.append(motor.pv.strip())
            online = all(self._model.epics.is_online(pv) for pv in pvs) if pvs else True
            wx.CallAfter(self._view.set_epics_online, online)

        threading.Thread(target=_worker, daemon=True, name="epics-check").start()

    def run(self) -> None:
        """Starts the main application loop."""
        self._view.display_window()
        if self._beamline_config_controller.has_active_config():
            self._view.set_active_config_name(self._model.beamline.active.name)
            self._check_epics_status()
        else:
            wx.CallAfter(self._beamline_config_controller.open_general)
        self._app.MainLoop()
