#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/settings_popup.py
# ----------------------------------------------------------------------------------
# Purpose:
# Image settings popup panel (colormap, contrast, auto-scale, filter gaps, reset).
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from typing import Callable

import wx

from crystalsweep.ui.view.custom.colormaps import COLORMAP_NAMES
from crystalsweep.ui.view.custom.theme import FG_SECONDARY, POPUP_BG, POPUP_FG, SEP_COLOUR, scaled_font
from crystalsweep.ui.view.custom.widgets import DarkCombo, DarkTextCtrl, DarkToggle, FlatButton

__all__ = ["ImageSettingsPopup"]


class ImageSettingsPopup(wx.Frame):
    """Borderless settings popup that dismisses when focus is lost."""

    def __init__(
        self,
        parent: wx.Window,
        colormap: str,
        auto_scale: bool,
        filter_gaps: bool,
        contrast_min: float,
        contrast_max: float,
        on_colormap_changed: Callable[[str], None],
        on_auto_scale_changed: Callable[[bool], None],
        on_filter_gaps_changed: Callable[[bool], None],
        on_levels_changed: Callable[[float, float], None],
        on_reset_view: Callable[[], None],
    ) -> None:
        super().__init__(
            parent,
            style=wx.FRAME_NO_TASKBAR | wx.NO_BORDER | wx.FRAME_FLOAT_ON_PARENT | wx.STAY_ON_TOP,
        )
        self._on_colormap_changed = on_colormap_changed
        self._on_auto_scale_changed = on_auto_scale_changed
        self._on_filter_gaps_changed = on_filter_gaps_changed
        self._on_levels_changed = on_levels_changed
        self._on_reset_view = on_reset_view

        self.SetBackgroundColour(SEP_COLOUR)

        panel = wx.Panel(self)
        panel.SetBackgroundColour(POPUP_BG)
        panel.SetForegroundColour(POPUP_FG)

        sizer = wx.BoxSizer(wx.VERTICAL)
        self._build_section(panel, sizer, colormap, auto_scale, filter_gaps, contrast_min, contrast_max)
        sizer.AddSpacer(10)
        panel.SetSizer(sizer)
        sizer.Fit(panel)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 0, wx.EXPAND | wx.ALL, 1)
        self.SetSizer(outer)
        self.Fit()

        self.Bind(wx.EVT_KILL_FOCUS, lambda e: e.Skip())
        self.Bind(wx.EVT_ACTIVATE, self._on_activate)

    def Popup(self) -> None:
        self.Show()
        self.Raise()

    def Position(self, pt: wx.Point, size: tuple) -> None:
        self.SetPosition(pt)

    def _on_activate(self, event: wx.ActivateEvent) -> None:
        if not event.GetActive():
            self.Hide()
            self.Destroy()
        event.Skip()

    def _build_section(
        self,
        parent: wx.Panel,
        sizer: wx.BoxSizer,
        colormap: str,
        auto_scale: bool,
        filter_gaps: bool,
        contrast_min: float,
        contrast_max: float,
    ) -> None:
        font = scaled_font(12)

        def _lbl(text: str) -> wx.StaticText:
            w = wx.StaticText(parent, label=text)
            w.SetBackgroundColour(POPUP_BG)
            w.SetForegroundColour(FG_SECONDARY)
            w.SetFont(font)
            return w

        cmap_row = wx.BoxSizer(wx.HORIZONTAL)
        cmap_row.Add(_lbl("Colormap"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self._cmap_choice = DarkCombo(parent, choices=COLORMAP_NAMES)
        if colormap in COLORMAP_NAMES:
            self._cmap_choice.SetSelection(COLORMAP_NAMES.index(colormap))
        self._cmap_choice.Bind(wx.EVT_CHOICE, self._evt_colormap)
        cmap_row.Add(self._cmap_choice, 1, wx.EXPAND)
        sizer.Add(cmap_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        levels_row = wx.BoxSizer(wx.HORIZONTAL)
        levels_row.Add(_lbl("Min"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self._min_ctrl = DarkTextCtrl(parent, value=f"{contrast_min:.4g}")
        self._min_ctrl.Bind(wx.EVT_KEY_DOWN, self._evt_levels_key)
        self._min_ctrl.Bind(wx.EVT_KILL_FOCUS, self._evt_levels)
        levels_row.Add(self._min_ctrl, 1, wx.EXPAND | wx.RIGHT, 8)
        levels_row.Add(_lbl("Max"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self._max_ctrl = DarkTextCtrl(parent, value=f"{contrast_max:.4g}")
        self._max_ctrl.Bind(wx.EVT_KEY_DOWN, self._evt_levels_key)
        self._max_ctrl.Bind(wx.EVT_KILL_FOCUS, self._evt_levels)
        levels_row.Add(self._max_ctrl, 1, wx.EXPAND)
        sizer.Add(levels_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self._auto_scale_cb = DarkToggle(parent, label="Auto-scale contrast", value=auto_scale)
        self._auto_scale_cb.Bind(wx.EVT_CHECKBOX, self._evt_auto_scale)
        sizer.Add(self._auto_scale_cb, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self._filter_gaps_cb = DarkToggle(parent, label="Filter gaps (zeros)", value=filter_gaps)
        self._filter_gaps_cb.Bind(wx.EVT_CHECKBOX, self._evt_filter_gaps)
        sizer.Add(self._filter_gaps_cb, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        reset_btn = FlatButton(parent, label="Reset View")
        reset_btn.set_action(self._evt_reset_view)
        sizer.Add(reset_btn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

    def _evt_colormap(self, colormap: str) -> None:
        self._on_colormap_changed(colormap)

    def _evt_auto_scale(self, value: bool) -> None:
        self._on_auto_scale_changed(value)

    def _evt_filter_gaps(self, value: bool) -> None:
        self._on_filter_gaps_changed(value)

    def _evt_levels_key(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._evt_levels(event)
        else:
            event.Skip()

    def _evt_levels(self, event: wx.Event) -> None:
        try:
            lo, hi = float(self._min_ctrl.GetValue()), float(self._max_ctrl.GetValue())
            if lo < hi:
                self._on_levels_changed(lo, hi)
        except ValueError:
            pass
        event.Skip()

    def _evt_reset_view(self) -> None:
        self._on_reset_view()
        self.Hide()
        self.Destroy()
