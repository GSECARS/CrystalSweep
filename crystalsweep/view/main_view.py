#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/view/main_view.py
# ----------------------------------------------------------------------------------
# Purpose:
# This file is used to implement the main view for the CrystalSweep application.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import wx
from wxutils import Popup

__all__ = ["MainView"]


class MainView(wx.Frame):
    """Implements the main view for the CrystalSweep application."""

    def __init__(self, version: str) -> None:
        """Initializes the main view."""
        super(MainView, self).__init__(None, wx.ID_ANY)

        self._version = version

        # Bind events to the close event handler
        self.Bind(wx.EVT_CLOSE, self._close_event_handler)

        # Configure the main window
        self._configure_main_window()

    def display_window(self) -> None:
        """Displays the main window of the application."""
        self.Show(True)

    def _configure_main_window(self) -> None:
        """Configures the main wx Frame of the application."""
        # Set the window title
        self.SetTitle(f"CrystalSweep - {self._version}")

    def _close_event_handler(self, event: wx.CloseEvent) -> None:
        """Runs when trying to close the main window."""
        style = wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        result = Popup(self, "Are you sure you want to close the application?", "Close Application", style=style)
        event.Skip() if result == wx.ID_YES else event.Veto()
