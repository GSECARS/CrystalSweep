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

from crystalsweep.ui.view.ad_viewer_view import ADViewerView
from crystalsweep.ui.view.collect_view import CollectView
from crystalsweep.ui.view.collection_settings_view import CollectionSettingsView
from crystalsweep.ui.view.collection_table_view import CollectionTableView
from crystalsweep.ui.view.custom.theme import BG_CARD, BG_SURFACE, SEP_COLOUR
from crystalsweep.ui.view.custom.widgets import DarkConfirmDialog, DarkMenuBar, SectionDivider, ThemedSplitter
from crystalsweep.ui.view.file_settings_view import FileSettingsView

__all__ = ["MainView"]

_LEFT_PANEL_W = 340


class MainView(wx.Frame):
    """Implements the main view for the CrystalSweep application."""

    def __init__(self, version: str) -> None:
        """Initializes the main view."""
        super(MainView, self).__init__(None, wx.ID_ANY)

        self._version = version
        self._open_general_cb: Callable[[], None] | None = None
        self._open_detectors_cb: Callable[[], None] | None = None
        self._open_controllers_cb: Callable[[], None] | None = None
        self._open_positioners_cb: Callable[[], None] | None = None
        self._load_config_cb: Callable[[], None] | None = None
        self._save_config_cb: Callable[[], None] | None = None
        self._save_config_as_cb: Callable[[], None] | None = None
        self._abort_cb: Callable[[], None] | None = None

        self._collecting = False
        self._splitter = ThemedSplitter(self)
        self._splitter.SetSashGravity(0.0)
        self._splitter.SetMinimumPaneSize(180)

        self._left_panel = wx.Panel(self._splitter)
        self._left_panel.SetBackgroundColour(BG_CARD)

        self.file_settings = FileSettingsView(self._left_panel)
        self.collection_settings = CollectionSettingsView(self._left_panel)
        self.collection_table = CollectionTableView(self._left_panel)
        self.collect = CollectView(self._left_panel)

        _sep = lambda: wx.Panel(self._left_panel, size=(-1, 1))

        collect_sep = _sep()
        collect_sep.SetBackgroundColour(SEP_COLOUR)

        left_sizer = wx.BoxSizer(wx.VERTICAL)
        left_sizer.Add(SectionDivider(self._left_panel, "File Settings"), 0, wx.EXPAND)
        left_sizer.Add(self.file_settings, 0, wx.EXPAND)
        left_sizer.AddSpacer(25)
        left_sizer.Add(SectionDivider(self._left_panel, "Collection Settings"), 0, wx.EXPAND)
        left_sizer.Add(self.collection_settings, 0, wx.EXPAND)
        left_sizer.AddSpacer(25)
        left_sizer.Add(SectionDivider(self._left_panel, "Collection Points"), 0, wx.EXPAND)
        left_sizer.Add(self.collection_table, 1, wx.EXPAND)
        left_sizer.Add(collect_sep, 0, wx.EXPAND)
        left_sizer.Add(self.collect, 0, wx.EXPAND)
        self._left_panel.SetSizer(left_sizer)

        self.ad_viewer = ADViewerView(self._splitter)

        self._splitter.SplitVertically(self._left_panel, self.ad_viewer, _LEFT_PANEL_W)
        self._splitter.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGING, self._on_sash_changing)
        self.collection_table.bind_min_width_changed(self._on_table_min_width_changed)
        self._update_left_min_size()

        self._menu_bar = self._build_menu_bar()
        self.Bind(wx.EVT_CLOSE, self._close_event_handler)
        self._configure_main_window()

    def display_window(self) -> None:
        """Displays the main window of the application."""
        self.Show(True)
        wx.CallAfter(self._set_initial_sash)

    def bind_open_general(self, callback: Callable[[], None]) -> None:
        self._open_general_cb = callback

    def bind_open_detectors(self, callback: Callable[[], None]) -> None:
        self._open_detectors_cb = callback

    def bind_open_controllers(self, callback: Callable[[], None]) -> None:
        self._open_controllers_cb = callback

    def bind_open_positioners(self, callback: Callable[[], None]) -> None:
        self._open_positioners_cb = callback

    def set_active_config_name(self, name: str) -> None:
        if self._menu_bar is not None:
            self._menu_bar.set_config_name(name)

    def set_ui_collecting(self, collecting: bool) -> None:
        self._collecting = collecting
        if self._menu_bar is not None:
            self._menu_bar.Enable(not collecting)
        self.file_settings.set_enabled(not collecting)
        self.collection_settings.set_enabled(not collecting)
        self.collect.set_collecting(collecting)

    def bind_load_config(self, callback: Callable[[], None]) -> None:
        self._load_config_cb = callback

    def bind_save_config(self, callback: Callable[[], None]) -> None:
        self._save_config_cb = callback

    def bind_save_config_as(self, callback: Callable[[], None]) -> None:
        self._save_config_as_cb = callback

    def bind_abort(self, callback: Callable[[], None]) -> None:
        self._abort_cb = callback

    def _build_menu_bar(self) -> DarkMenuBar | None:
        if sys.platform == "darwin":
            menu_bar = wx.MenuBar()

            file_menu = wx.Menu()
            load_item = file_menu.Append(wx.ID_ANY, "Load config\tCtrl+O")
            save_item = file_menu.Append(wx.ID_SAVE, "Save config\tCtrl+S")
            save_as_item = file_menu.Append(wx.ID_SAVEAS, "Save config as\tCtrl+Shift+S")
            file_menu.AppendSeparator()
            exit_item = file_menu.Append(wx.ID_EXIT, "Exit\tCtrl+Q")
            menu_bar.Append(file_menu, "&File")

            general_menu = wx.Menu()
            general_item = general_menu.Append(wx.ID_ANY, "General\tCtrl+1")
            menu_bar.Append(general_menu, "&General")

            detectors_menu = wx.Menu()
            detectors_item = detectors_menu.Append(wx.ID_ANY, "Detectors\tCtrl+2")
            menu_bar.Append(detectors_menu, "&Detectors")

            controllers_menu = wx.Menu()
            controllers_item = controllers_menu.Append(wx.ID_ANY, "Controllers\tCtrl+3")
            menu_bar.Append(controllers_menu, "C&ontrollers")

            positioners_menu = wx.Menu()
            positioners_item = positioners_menu.Append(wx.ID_ANY, "Positioners\tCtrl+4")
            menu_bar.Append(positioners_menu, "&Positioners")

            self.SetMenuBar(menu_bar)
            self.Bind(wx.EVT_MENU, lambda _e: self._fire(self._load_config_cb), load_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._fire(self._save_config_cb), save_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._fire(self._save_config_as_cb), save_as_item)
            self.Bind(wx.EVT_MENU, lambda _e: self.Close(), exit_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._fire(self._open_general_cb), general_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._fire(self._open_detectors_cb), detectors_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._fire(self._open_controllers_cb), controllers_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._fire(self._open_positioners_cb), positioners_item)
            return None

        bar = DarkMenuBar(self)
        bar.append_menu(
            title="File",
            items=["Load config", "Save config", "Save config as", None, "Exit"],
            shortcuts=["Ctrl+O", "Ctrl+S", "Ctrl+Shift+S", None, "Ctrl+Q"],
            callbacks=[
                lambda: self._fire(self._load_config_cb),
                lambda: self._fire(self._save_config_cb),
                lambda: self._fire(self._save_config_as_cb),
                None,
                self._on_exit,
            ],
        )
        bar.append_action("General", lambda: self._fire(self._open_general_cb))
        bar.append_action("Detectors", lambda: self._fire(self._open_detectors_cb))
        bar.append_action("Controllers", lambda: self._fire(self._open_controllers_cb))
        bar.append_action("Positioners", lambda: self._fire(self._open_positioners_cb))

        accel = wx.AcceleratorTable(
            [
                wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("Q"), wx.ID_EXIT),
            ]
        )
        self.SetAcceleratorTable(accel)
        self.Bind(wx.EVT_MENU, lambda _e: self.Close(), id=wx.ID_EXIT)
        return bar

    @staticmethod
    def _fire(cb: Callable[[], None] | None) -> None:
        if cb is not None:
            cb()

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
        self.SetSize(1600, 900)
        self.SetMinSize((800, 520))

    def _update_left_min_size(self) -> None:
        min_w = self.collection_table.min_content_width
        self._left_panel.SetMinSize((min_w, -1))
        self._splitter.SetMinimumPaneSize(min_w)

    def _on_table_min_width_changed(self, min_w: int) -> None:
        self._left_panel.SetMinSize((min_w, -1))
        self._splitter.SetMinimumPaneSize(min_w)
        cur = self._splitter.GetSashPosition()
        if cur < min_w:
            self._splitter.SetSashPosition(min_w)

    def _on_sash_changing(self, event: wx.SplitterEvent) -> None:
        min_w = self._left_panel.GetMinSize().width
        if min_w > 0 and event.GetSashPosition() < min_w:
            event.SetSashPosition(min_w)

    def _set_initial_sash(self) -> None:
        min_w = self._left_panel.GetMinSize().width
        w = self._splitter.GetClientSize().width
        pos = max(min_w, w // 2) if w > 0 else min_w
        self._splitter.SetSashPosition(pos)
        self._splitter._reposition_overlay()

    def _close_event_handler(self, event: wx.CloseEvent) -> None:
        """Runs when trying to close the main window."""
        if self._collecting:
            result = DarkConfirmDialog(self, "Collection is in progress. Abort and close?", "Collection in Progress").ShowModal()
            if result == wx.ID_YES:
                self._fire(self._abort_cb)
                event.Skip()
            else:
                event.Veto()
            return
        result = DarkConfirmDialog(self, "Are you sure you want to close the application?", "Close Application").ShowModal()
        event.Skip() if result == wx.ID_YES else event.Veto()
