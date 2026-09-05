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
from epicsapps.pva_adviewer.ad_viewer_view import ADViewerView
from wxutils import FlatConfirmDialog, FlatLabel, FlatSplitter, FlatTabbedPanel

from crystalsweep.assets import LOGO_PNG
from crystalsweep.ui.view.collect_view import CollectView
from crystalsweep.ui.view.collection_settings_view import CollectionSettingsView
from crystalsweep.ui.view.collection_table_view import CollectionTableView
from crystalsweep.ui.view.custom.theme import app_theme
from crystalsweep.ui.view.custom.widgets import CrystalMenuBar, FlatPanel, ThemedSectionDivider
from crystalsweep.ui.view.file_settings_view import FileSettingsView
from crystalsweep.ui.view.preview_view import PreviewView

__all__ = ["MainView"]

_LEFT_PANEL_W = 340


class MainView(wx.Frame):
    """Implements the main view for the CrystalSweep application."""

    def __init__(self, version: str) -> None:
        """Initializes the main view."""
        super(MainView, self).__init__(None, wx.ID_ANY)
        self.SetBackgroundColour(app_theme.background)

        self._version = version
        self._open_general_cb: Callable[[], None] | None = None
        self._open_crysalis_cb: Callable[[], None] | None = None
        self._open_detectors_cb: Callable[[], None] | None = None
        self._open_controllers_cb: Callable[[], None] | None = None
        self._open_positioners_cb: Callable[[], None] | None = None
        self._open_scripts_cb: Callable[[], None] | None = None
        self._load_config_cb: Callable[[], None] | None = None
        self._save_config_cb: Callable[[], None] | None = None
        self._save_config_as_cb: Callable[[], None] | None = None
        self._abort_cb: Callable[[], None] | None = None

        self._collecting = False
        self._splitter = FlatSplitter(self)
        self._splitter.SetSashGravity(0.0)
        self._splitter.SetMinimumPaneSize(180)

        self._left_panel = FlatPanel(self._splitter)

        self.file_settings = FileSettingsView(self._left_panel)
        self.collection_settings = CollectionSettingsView(self._left_panel)
        self.collection_table = CollectionTableView(self._left_panel)
        self.collect = CollectView(self._left_panel)

        def _sep() -> FlatPanel:
            return FlatPanel(self._left_panel, size=(-1, 1))

        collect_sep = _sep()
        collect_sep.SetBackgroundColour(app_theme.bright_black)

        left_sizer = wx.BoxSizer(wx.VERTICAL)
        left_sizer.Add(ThemedSectionDivider(self._left_panel, "File Settings"), 0, wx.EXPAND)
        left_sizer.Add(self.file_settings, 0, wx.EXPAND)
        left_sizer.AddSpacer(12)
        left_sizer.Add(ThemedSectionDivider(self._left_panel, "Collection Settings"), 0, wx.EXPAND)
        left_sizer.Add(self.collection_settings, 0, wx.EXPAND)
        left_sizer.AddSpacer(12)
        left_sizer.Add(ThemedSectionDivider(self._left_panel, "Collection Points"), 0, wx.EXPAND)
        left_sizer.Add(self.collection_table, 1, wx.EXPAND)
        left_sizer.AddSpacer(12)
        self._centering_divider = ThemedSectionDivider(self._left_panel, "Single-Crystal Centering Tools")
        left_sizer.Add(self._centering_divider, 0, wx.EXPAND)
        self.centering_tabs = self._build_centering_tabs()
        left_sizer.Add(self.centering_tabs, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        self._centering_spacer = left_sizer.AddSpacer(8)
        left_sizer.Add(collect_sep, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
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

    def bind_open_crysalis(self, callback: Callable[[], None]) -> None:
        self._open_crysalis_cb = callback

    def bind_open_detectors(self, callback: Callable[[], None]) -> None:
        self._open_detectors_cb = callback

    def bind_open_controllers(self, callback: Callable[[], None]) -> None:
        self._open_controllers_cb = callback

    def bind_open_positioners(self, callback: Callable[[], None]) -> None:
        self._open_positioners_cb = callback

    def set_centering_tools_visible(self, visible: bool) -> None:
        self._centering_divider.Show(visible)
        self.centering_tabs.Show(visible)
        self._centering_spacer.Show(visible)
        self._left_panel.Layout()

    def set_active_config_name(self, name: str) -> None:
        if self._menu_bar is not None:
            self._menu_bar.set_config_name(name)

    def set_epics_online(self, online: bool) -> None:
        if self._menu_bar is not None:
            self._menu_bar.set_epics_status(online)
        self.collect.set_collect_enabled(online)

    def set_ui_collecting(self, collecting: bool) -> None:
        self._collecting = collecting
        if self._menu_bar is not None:
            self._menu_bar.Enable(not collecting)
        self.file_settings.set_enabled(not collecting)
        self.collection_settings.set_enabled(not collecting)
        self.collect.set_collecting(collecting)
        self.collection_table.set_collecting(collecting)
        self.preview.set_collecting(collecting)

    def bind_load_config(self, callback: Callable[[], None]) -> None:
        self._load_config_cb = callback

    def bind_save_config(self, callback: Callable[[], None]) -> None:
        self._save_config_cb = callback

    def bind_save_config_as(self, callback: Callable[[], None]) -> None:
        self._save_config_as_cb = callback

    def bind_open_scripts(self, callback: Callable[[], None]) -> None:
        self._open_scripts_cb = callback

    def bind_abort(self, callback: Callable[[], None]) -> None:
        self._abort_cb = callback

    def _build_centering_tabs(self) -> FlatTabbedPanel:
        tabs = FlatTabbedPanel(self._left_panel)
        tabs.SetMinSize((-1, 150))

        self.preview = PreviewView(tabs)

        xrd_page = FlatPanel(tabs)
        xrd_label = FlatLabel(xrd_page, label="Coming soon")
        xrd_label.SetFont(app_theme.scaled_font(12, style=wx.FONTSTYLE_ITALIC))
        xrd_sizer = wx.BoxSizer(wx.VERTICAL)
        xrd_sizer.AddStretchSpacer(1)
        xrd_row = wx.BoxSizer(wx.HORIZONTAL)
        xrd_row.AddStretchSpacer(1)
        xrd_row.Add(xrd_label, 0, wx.ALIGN_CENTER_VERTICAL)
        xrd_row.AddStretchSpacer(1)
        xrd_sizer.Add(xrd_row, 0, wx.EXPAND)
        xrd_sizer.AddStretchSpacer(1)
        xrd_page.SetSizer(xrd_sizer)

        tabs.AddPage("Preview", self.preview)
        tabs.AddPage("XRD centering", xrd_page)
        return tabs

    def _build_menu_bar(self) -> CrystalMenuBar | None:
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

            crysalis_menu = wx.Menu()
            crysalis_item = crysalis_menu.Append(wx.ID_ANY, "CrysAlis\tCtrl+2")
            menu_bar.Append(crysalis_menu, "&CrysAlis")

            detectors_menu = wx.Menu()
            detectors_item = detectors_menu.Append(wx.ID_ANY, "Detectors\tCtrl+3")
            menu_bar.Append(detectors_menu, "&Detectors")

            controllers_menu = wx.Menu()
            controllers_item = controllers_menu.Append(wx.ID_ANY, "Controllers\tCtrl+4")
            menu_bar.Append(controllers_menu, "C&ontrollers")

            positioners_menu = wx.Menu()
            positioners_item = positioners_menu.Append(wx.ID_ANY, "Positioners\tCtrl+5")
            menu_bar.Append(positioners_menu, "&Positioners")

            self.SetMenuBar(menu_bar)
            self.Bind(wx.EVT_MENU, lambda _e: self._fire(self._load_config_cb), load_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._fire(self._save_config_cb), save_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._fire(self._save_config_as_cb), save_as_item)
            self.Bind(wx.EVT_MENU, lambda _e: self.Close(), exit_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._fire(self._open_general_cb), general_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._fire(self._open_crysalis_cb), crysalis_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._fire(self._open_detectors_cb), detectors_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._fire(self._open_controllers_cb), controllers_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._fire(self._open_positioners_cb), positioners_item)
            return None

        bar = CrystalMenuBar(self)
        bar.AppendMenu(
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
        bar.AppendAction("General", lambda: self._fire(self._open_general_cb))
        bar.AppendAction("CrysAlis", lambda: self._fire(self._open_crysalis_cb))
        bar.AppendAction("Detectors", lambda: self._fire(self._open_detectors_cb))
        bar.AppendAction("Controllers", lambda: self._fire(self._open_controllers_cb))
        bar.AppendAction("Positioners", lambda: self._fire(self._open_positioners_cb))
        bar.AppendAction("Scripts", lambda: self._fire(self._open_scripts_cb))

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
        self._apply_app_icon()

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        if self._menu_bar is not None:
            main_sizer.Add(self._menu_bar, 0, wx.EXPAND)
        main_sizer.Add(self._splitter, 1, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)
        self.SetSize(1600, 900)
        self.SetMinSize((800, 520))

    def _apply_app_icon(self) -> None:
        """Sets the window/taskbar icon from the bundled PNG logo."""
        logo = LOGO_PNG
        if not logo.is_file():
            return
        image = wx.Image(str(logo), wx.BITMAP_TYPE_PNG)
        if not image.IsOk():
            return
        bundle = wx.IconBundle()
        for size in (16, 24, 32, 48, 64, 128, 256):
            scaled = image.Scale(size, size, wx.IMAGE_QUALITY_HIGH)
            icon = wx.Icon()
            icon.CopyFromBitmap(wx.Bitmap(scaled))
            bundle.AddIcon(icon)
        self.SetIcons(bundle)

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
            result = FlatConfirmDialog(
                self, "Collection is in progress. Abort and close?", "Collection in Progress", yes_scheme=app_theme.danger_scheme()
            ).ShowModal()
            if result == wx.ID_YES:
                self._fire(self._abort_cb)
                event.Skip()
            else:
                event.Veto()
            return
        result = FlatConfirmDialog(
            self, "Are you sure you want to close the application?", "Close Application", yes_scheme=app_theme.danger_scheme()
        ).ShowModal()
        event.Skip() if result == wx.ID_YES else event.Veto()
