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
from crystalsweep.ui.view.collection_table_view import CollectionTableView
from crystalsweep.ui.view.custom.theme import BG_SURFACE

__all__ = ["MainView"]

_LEFT_PANEL_W = 340
_SASH_W = 4


class MainView(wx.Frame):
    """Implements the main view for the CrystalSweep application."""

    def __init__(self, version: str) -> None:
        """Initializes the main view."""
        super(MainView, self).__init__(None, wx.ID_ANY)

        self._version = version
        self._open_config_cb: Callable[[], None] | None = None

        self._splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        self._splitter.SetSashGravity(0.0)
        self._splitter.SetMinimumPaneSize(180)

        self.collection_table = CollectionTableView(self._splitter)
        self.ad_viewer = ADViewerView(self._splitter)

        self._splitter.SplitVertically(self.collection_table, self.ad_viewer, _LEFT_PANEL_W)
        self._splitter.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGING, self._on_sash_changing)

        self._build_menu_bar()
        self.Bind(wx.EVT_CLOSE, self._close_event_handler)
        self._configure_main_window()

    def display_window(self) -> None:
        """Displays the main window of the application."""
        self.Show(True)
        wx.CallAfter(self._set_initial_sash)

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

        self._splitter.SetBackgroundColour(wx.Colour(45, 45, 48))

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self._splitter, 1, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)
        self.SetSize(1200, 700)
        self.SetMinSize((800, 520))

    def _on_sash_changing(self, event: wx.SplitterEvent) -> None:
        min_w = self.collection_table.GetMinSize().width
        if min_w > 0 and event.GetSashPosition() < min_w:
            event.SetSashPosition(min_w)

    def _set_initial_sash(self) -> None:
        w = self._splitter.GetClientSize().width
        if w > 0:
            self._splitter.SetSashPosition(w // 2)

    def _close_event_handler(self, event: wx.CloseEvent) -> None:
        """Runs when trying to close the main window."""
        style = wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        result = Popup(self, "Are you sure you want to close the application?", "Close Application", style=style)
        event.Skip() if result == wx.ID_YES else event.Veto()
