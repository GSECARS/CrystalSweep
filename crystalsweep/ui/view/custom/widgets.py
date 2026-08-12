#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/widgets.py
# ----------------------------------------------------------------------------------
# Purpose:
# Reusable dark-themed custom wx controls shared across view panels.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import wx
from wxutils import FlatMenuBar

from crystalsweep.ui.view.custom.theme import (
    ACCENT,
    DANGER,
    FG_SECONDARY,
    MENU_BAR_SCHEME,
    PONI_LOADED,
)

__all__ = ["CrystalMenuBar"]


class CrystalMenuBar(FlatMenuBar):
    """CS-specific menu bar. Adds EPICS status and config name indicators."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, height=28, scheme=MENU_BAR_SCHEME)
        bg = MENU_BAR_SCHEME[0]
        self._config_prefix = wx.StaticText(self, label="")
        self._config_prefix.SetBackgroundColour(bg)
        self._config_prefix.SetForegroundColour(FG_SECONDARY)
        self._config_name = wx.StaticText(self, label="")
        self._config_name.SetBackgroundColour(bg)
        self._config_name.SetForegroundColour(ACCENT)
        self._epics_prefix = wx.StaticText(self, label="")
        self._epics_prefix.SetBackgroundColour(bg)
        self._epics_prefix.SetForegroundColour(FG_SECONDARY)
        self._epics_value = wx.StaticText(self, label="")
        self._epics_value.SetBackgroundColour(bg)
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
        self._epics_value.SetForegroundColour(PONI_LOADED if online else DANGER)
        self._epics_value.Refresh()
        self.Layout()
