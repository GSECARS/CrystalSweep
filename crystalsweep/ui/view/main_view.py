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

import sys
from typing import Callable

import wx
from wxutils import Popup

from crystalsweep.ui.view.ad_viewer_view import ADViewerView
from crystalsweep.ui.view.collection_table_view import CollectionTableView
from crystalsweep.ui.view.custom.theme import BG_CARD, BG_SURFACE
from crystalsweep.ui.view.custom.widgets import DarkMenuBar, ThemedSplitter
from crystalsweep.ui.view.file_settings_view import FileSettingsView

__all__ = ["MainView"]

_LEFT_PANEL_W = 340


class MainView(wx.Frame):
    """Implements the main view for the CrystalSweep application."""

    def __init__(self, version: str) -> None:
        """Initializes the main view."""
        super(MainView, self).__init__(None, wx.ID_ANY)

        self._version = version
        self._open_config_cb: Callable[[], None] | None = None

        self._splitter = ThemedSplitter(self)
        self._splitter.SetSashGravity(0.0)
        self._splitter.SetMinimumPaneSize(180)

        self._left_panel = wx.Panel(self._splitter)
        self._left_panel.SetBackgroundColour(BG_CARD)

        self.file_settings = FileSettingsView(self._left_panel)
        self.collection_table = CollectionTableView(self._left_panel)

        left_sizer = wx.BoxSizer(wx.VERTICAL)
        left_sizer.Add(self.file_settings, 0, wx.EXPAND)
        left_sizer.Add(self.collection_table, 1, wx.EXPAND)
        self._left_panel.SetSizer(left_sizer)

        self.ad_viewer = ADViewerView(self._splitter)

        self._splitter.SplitVertically(self._left_panel, self.ad_viewer, _LEFT_PANEL_W)
        self._splitter.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGING, self._on_sash_changing)

        self._menu_bar = self._build_menu_bar()
        self.Bind(wx.EVT_CLOSE, self._close_event_handler)
        self._configure_main_window()

    def display_window(self) -> None:
        """Displays the main window of the application."""
        self.Show(True)
        wx.CallAfter(self._set_initial_sash)

    def bind_open_configuration(self, callback: Callable[[], None]) -> None:
        """Set the handler invoked when File -> Configuration is selected."""
        self._open_config_cb = callback

    def _build_menu_bar(self) -> DarkMenuBar | None:
        if sys.platform == "darwin":
            menu_bar = wx.MenuBar()
            file_menu = wx.Menu()
            config_item = file_menu.Append(wx.ID_ANY, "Configuration\tCtrl+,", "Edit beamline configuration")
            file_menu.AppendSeparator()
            exit_item = file_menu.Append(wx.ID_EXIT, "Exit\tCtrl+Q", "Close the application")
            menu_bar.Append(file_menu, "&File")
            self.SetMenuBar(menu_bar)
            self.Bind(wx.EVT_MENU, self._on_open_configuration, config_item)
            self.Bind(wx.EVT_MENU, lambda _e: self.Close(), exit_item)
            return None

        bar = DarkMenuBar(self)
        bar.append_menu(
            title="File",
            items=["Configuration", None, "Exit"],
            shortcuts=["Ctrl+,", None, "Ctrl+Q"],
            callbacks=[self._on_open_configuration, None, self._on_exit],
        )
        accel = wx.AcceleratorTable([
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord(","), wx.ID_ANY),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("Q"), wx.ID_EXIT),
        ])
        self.SetAcceleratorTable(accel)
        self.Bind(wx.EVT_MENU, lambda _e: self._on_open_configuration(), id=wx.ID_ANY)
        self.Bind(wx.EVT_MENU, lambda _e: self.Close(), id=wx.ID_EXIT)
        return bar

    def _on_open_configuration(self, _event: wx.CommandEvent | None = None) -> None:
        if self._open_config_cb is not None:
            self._open_config_cb()

    def _on_exit(self) -> None:
        self.Close()

    def _configure_main_window(self) -> None:
        """Configures the main wx Frame of the application."""
        self.SetTitle(f"CrystalSweep - {self._version}")
        self.SetBackgroundColour(BG_SURFACE)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        if self._menu_bar is not None:
            main_sizer.Add(self._menu_bar, 0, wx.EXPAND)
        main_sizer.Add(self._splitter, 1, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)
        self.SetSize(1200, 700)
        self.SetMinSize((800, 520))

    def _on_sash_changing(self, event: wx.SplitterEvent) -> None:
        min_w = self._left_panel.GetMinSize().width
        if min_w > 0 and event.GetSashPosition() < min_w:
            event.SetSashPosition(min_w)

    def _set_initial_sash(self) -> None:
        w = self._splitter.GetClientSize().width
        if w > 0:
            self._splitter.SetSashPosition(w // 2)
        self._splitter._reposition_overlay()

    def _close_event_handler(self, event: wx.CloseEvent) -> None:
        """Runs when trying to close the main window."""
        style = wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        result = Popup(self, "Are you sure you want to close the application?", "Close Application", style=style)
        event.Skip() if result == wx.ID_YES else event.Veto()
