#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/widgets.py
# ----------------------------------------------------------------------------------
# Purpose:
# Reusable custom wx controls shared across view panels.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import wx
from wxutils import FlatLabel, FlatMenuBar, FlatPanel as _FlatPanel, SectionDivider

from crystalsweep.ui.view.custom.theme import app_theme

__all__ = ["CrystalMenuBar", "FlatPanel", "ThemedSectionDivider"]


class FlatPanel(_FlatPanel):
    """FlatPanel that reports app_theme.background via GetBackgroundColour().

    wxutils FlatPanel paints its background from the active theme but never
    calls SetBackgroundColour(), so child widgets that query
    GetParent().GetBackgroundColour() receive the system default instead of
    the theme color. Overriding GetBackgroundColour() fixes checkboxes,
    text fields, and other flat widgets parented to this panel.
    """

    def GetBackgroundColour(self) -> wx.Colour:
        return app_theme.background


class ThemedSectionDivider(SectionDivider):
    """SectionDivider that pulls fg and line colors from app_theme at paint time.

    SectionDivider caches colors at init and relies on darkdetect to update
    them. On Windows, darkdetect does not fire reliably at startup so the
    divider can be stuck in light-mode colors. Overriding _resolve_colors to
    read from app_theme and calling it at the start of every paint ensures the
    colors are always current regardless of OS detection timing.
    """

    def _resolve_colors(self, is_dark=None) -> None:
        self._fg = app_theme.foreground
        self._line = app_theme.bright_black

    def _on_paint(self, event: wx.PaintEvent) -> None:
        self._resolve_colors()
        super()._on_paint(event)


class CrystalMenuBar(FlatMenuBar):
    """CS-specific menu bar. Adds EPICS status and config name indicators."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, height=28)
        self._config_prefix = FlatLabel(self, label="")
        self._config_name = FlatLabel(self, label="", fg=app_theme.blue)
        self._epics_prefix = FlatLabel(self, label="")
        self._epics_value = FlatLabel(self, label="")
        self._sizer.AddStretchSpacer(1)
        self._sizer.Add(self._epics_prefix, 0, wx.ALIGN_CENTER_VERTICAL)
        self._sizer.Add(self._epics_value, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)
        self._sizer.Add(self._config_prefix, 0, wx.ALIGN_CENTER_VERTICAL)
        self._sizer.Add(self._config_name, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)

    def set_config_name(self, name: str) -> None:
        self._config_prefix.SetLabel("Active config: ")
        self._config_name.SetLabel(name)
        self.Layout()

    def set_epics_status(self, online: bool) -> None:
        self._epics_prefix.SetLabel("EPICS: ")
        self._epics_value.SetLabel("Online" if online else "Offline")
        self._epics_value._custom_fg = app_theme.green if online else app_theme.red
        self._epics_value.Refresh()
        self.Layout()
