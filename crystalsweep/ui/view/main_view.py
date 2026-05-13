#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/main_view.py
# ----------------------------------------------------------------------------------
# Purpose:
# This file is used to implement the main view for the CrystalSweep application.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from typing import Callable

import wx
from wxutils import Popup

from crystalsweep.ui.view.ad_viewer_view import ADViewerView
from crystalsweep.ui.view.custom.theme import BG_SURFACE

__all__ = ["MainView"]


class MainView(wx.Frame):
    """Implements the main view for the CrystalSweep application."""

    def __init__(self, version: str) -> None:
        """Initializes the main view."""
        super(MainView, self).__init__(None, wx.ID_ANY)

        self._version = version
        self._open_config_cb: Callable[[], None] | None = None

        self.ad_viewer = ADViewerView(self)

        self._build_menu_bar()

        self.Bind(wx.EVT_CLOSE, self._close_event_handler)

        self._configure_main_window()

    def display_window(self) -> None:
        """Displays the main window of the application."""
        self.Show(True)

    def bind_open_configuration(self, callback: Callable[[], None]) -> None:
        """Set the handler invoked when File -> Configuration is selected."""
        self._open_config_cb = callback

    def _build_menu_bar(self) -> None:
        menu_bar = wx.MenuBar()

        file_menu = wx.Menu()
        config_item = file_menu.Append(wx.ID_ANY, "Configuration\tCtrl+,", "Edit beamline configuration")
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, "Exit\tCtrl+Q", "Close the application")

        menu_bar.Append(file_menu, "&File")
        self.SetMenuBar(menu_bar)

        self.Bind(wx.EVT_MENU, self._on_open_configuration, config_item)
        self.Bind(wx.EVT_MENU, lambda _e: self.Close(), exit_item)

    def _on_open_configuration(self, _event: wx.CommandEvent) -> None:
        if self._open_config_cb is not None:
            self._open_config_cb()

    def _configure_main_window(self) -> None:
        """Configures the main wx Frame of the application."""
        self.SetTitle(f"CrystalSweep - {self._version}")
        self.SetBackgroundColour(BG_SURFACE)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self.ad_viewer, 1, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)
        self.SetSize(800, 600)
        self.SetMinSize((500, 520))

    def _close_event_handler(self, event: wx.CloseEvent) -> None:
        """Runs when trying to close the main window."""
        style = wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        result = Popup(self, "Are you sure you want to close the application?", "Close Application", style=style)
        event.Skip() if result == wx.ID_YES else event.Veto()
