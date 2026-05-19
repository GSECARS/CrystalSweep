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

import wx

from crystalsweep.model import MainModel
from crystalsweep.ui.controller.ad_viewer_controller import ADViewerController
from crystalsweep.ui.controller.beamline_config_controller import BeamlineConfigController
from crystalsweep.ui.controller.collection_table_controller import CollectionTableController
from crystalsweep.ui.controller.file_settings_controller import FileSettingsController
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
        self._collection_controller = CollectionTableController(model=self._model, view=self._view.collection_table)
        self._ad_viewer_controller = ADViewerController(model=self._model, view=self._view)
        self._beamline_config_controller = BeamlineConfigController(
            model=self._model,
            view=self._view,
            on_config_applied=self._on_config_applied,
        )

    def _on_config_applied(self, cfg) -> None:
        self._ad_viewer_controller.resubscribe_detector()
        self._collection_controller.on_config_applied(cfg)

    def run(self) -> None:
        """Starts the main application loop."""
        self._view.display_window()
        if not self._beamline_config_controller.has_active_config():
            wx.CallAfter(self._beamline_config_controller.open_dialog)
        self._app.MainLoop()
