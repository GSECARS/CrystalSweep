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

        # Initialize the AD Viewer controller
        self._ad_viewer_controller = ADViewerController(model=self._model, view=self._view)

    def run(self) -> None:
        """Starts the main application loop."""
        self._view.display_window()
        self._app.MainLoop()
