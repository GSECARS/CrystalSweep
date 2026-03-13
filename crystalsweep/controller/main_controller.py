#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/controller/main_controller.py
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

import wx

from crystalsweep.view import MainView

__all__ = ["MainController"]


class MainController:
    """Implements the main controller for the CrystalSweep application. Helps to bridge the gap between the model and view components."""

    def __init__(self, version: str) -> None:
        """Initializes the main controller."""
        # Create the core app and views
        self._app = wx.App(False)
        self._view = MainView(version=version)

    def run(self) -> None:
        """Starts the main application loop."""
        self._view.display_window()
        self._app.MainLoop()
