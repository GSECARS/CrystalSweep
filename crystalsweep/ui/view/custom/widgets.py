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
from wxutils import FlatMenuBar

from crystalsweep.ui.view.custom.theme import app_theme

__all__ = ["CrystalMenuBar"]


class CrystalMenuBar(FlatMenuBar):
    """CS-specific menu bar. Adds EPICS status and config name indicators."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, height=28)
        self._config_prefix = wx.StaticText(self, label="")
        self._config_name = wx.StaticText(self, label="")
        self._epics_prefix = wx.StaticText(self, label="")
        self._epics_value = wx.StaticText(self, label="")
        self._config_name.SetForegroundColour(app_theme.blue)
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
        self._epics_value.SetForegroundColour(app_theme.green if online else app_theme.red)
        self._epics_value.Refresh()
        self.Layout()
