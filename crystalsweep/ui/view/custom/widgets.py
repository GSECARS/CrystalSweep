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

from typing import Callable

import wx

from wxutils import FlatButton, FlatToggleButton, FlatMenuBar
from crystalsweep.ui.view.custom.theme import (
    ACCENT,
    ACCENT_HOVER,
    BG_CARD,
    BG_ELEVATED,
    BG_SURFACE,
    BTN_DISABLED,
    btn_font,
    BTN_HOVER_BG,
    BTN_PRESS_BG,
    DANGER,
    DANGER_HOVER,
    DANGER_PRESS,
    DANGER_SCHEME,
    DEFAULT_SCHEME,
    DISABLED_BG,
    DISABLED_FG,
    FG_PRIMARY,
    FG_SECONDARY,
    LIVE_H,
    LIVE_SCHEME,
    LIVE_W,
    MENU_BAR_SCHEME,
    PONI_LOADED,
    POPUP_BG,
    POPUP_BTN_BG,
    POPUP_BTN_HOVER,
    POPUP_BTN_PRESS,
    SEP_COLOUR,
    scaled_font,
)

__all__ = [
    "CrystalMenuBar",
    "LiveToggle",
]

class LiveToggle(FlatToggleButton):
    """Vertical LIVE toggle button. Gray when off, matte red when on.

    Thin CS wrapper around FlatToggleButton — preserves the vertical
    character-by-character label layout specific to the beamline UI.
    """

    def __init__(self, parent: wx.Window, live: bool = False, tooltip: str = "Toggle live updates") -> None:
        super().__init__(
            parent,
            label="LIVE",
            value=live,
            toggle_scheme=LIVE_SCHEME,
            size=wx.Size(LIVE_W, LIVE_H),
        )
        if tooltip:
            self.SetToolTip(tooltip)

    def set_live(self, live: bool) -> None:
        self.SetValue(live)

    def set_hovered(self, hovered: bool) -> None:
        if hovered != self._hovered:
            self._hovered = hovered
            self.Refresh()

    def set_toggled_callback(self, cb: Callable[[bool], None]) -> None:
        self.SetAction(lambda _e: cb(self.GetValue()))

    @property
    def is_live(self) -> bool:
        return self.GetValue()

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()

        gc.SetBrush(wx.Brush(BG_SURFACE))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)

        colour = (self._on_hover if self._hovered else self._on) if self._value else (self._off_hover if self._hovered else self._off)
        gc.SetPen(wx.Pen(colour, 1))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.DrawRoundedRectangle(1, 1, w - 2, h - 2, self._corner_radius)

        font = scaled_font(10, weight=wx.FONTWEIGHT_BOLD)
        gc.SetFont(font, colour)
        _, ch_h = gc.GetTextExtent("L")
        y = (h - (4 * ch_h + 6)) / 2
        for ch in "LIVE":
            tw, th = gc.GetTextExtent(ch)
            gc.DrawText(ch, (w - tw) / 2, y)
            y += th + 2


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
