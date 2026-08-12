#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/collect_view.py
# ----------------------------------------------------------------------------------
# Purpose:
# Bottom-of-left-panel collect section: status label, progress bar with inline
# point/frame text, and a Collect button that becomes Abort while collecting.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from typing import Callable

import wx

from crystalsweep.ui.view.custom.theme import (
    BG_CARD,
    DANGER,
    DANGER_HOVER,
    DANGER_PRESS,
    FG_PRIMARY,
    FG_SECONDARY,
    PONI_LOADED,
    scaled_font,
)
from crystalsweep.ui.view.custom.theme import BTN_DISABLED, btn_font, TOGGLE_SCHEME, PROGRESS_SCHEME
from wxutils import FlatButton, FlatCheckBox, FlatProgressBar

__all__ = ["CollectView"]

_COLLECT_SCHEME = (
    wx.Colour(30, 100, 60),
    wx.Colour(40, 130, 80),
    wx.Colour(20, 75, 45),
    wx.Colour(200, 255, 220),
    wx.Colour(200, 255, 220),
)
_ABORT_SCHEME = (DANGER, DANGER_HOVER, DANGER_PRESS, FG_PRIMARY, FG_PRIMARY)


class CollectView(wx.Panel):
    """Status + progress bar (left) and collect/abort button (right)."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.SetBackgroundColour(BG_CARD)

        self._on_collect_cb: Callable[[], None] | None = None
        self._on_abort_cb: Callable[[], None] | None = None
        self._collecting = False

        self._status_label = wx.StaticText(self, label="Ready")
        self._status_label.SetFont(scaled_font(13, weight=wx.FONTWEIGHT_BOLD))
        self._status_label.SetForegroundColour(FG_SECONDARY)
        self._status_label.SetBackgroundColour(BG_CARD)

        self._progress_bar = FlatProgressBar(self, progress_scheme=PROGRESS_SCHEME)

        self._collect_btn = FlatButton(self, "Collect", color_scheme=_COLLECT_SCHEME, disabled_scheme=BTN_DISABLED, font=btn_font())
        self._collect_btn.SetMinSize((120, 42))
        self._collect_btn.SetAction(self._on_btn_clicked)

        self._test_mode_toggle = FlatCheckBox(self, "Test mode", check_scheme=TOGGLE_SCHEME, disabled_scheme=BTN_DISABLED)
        self._test_mode_toggle.SetBackgroundColour(BG_CARD)

        self._eta_label = wx.StaticText(self, label="")
        self._eta_label.SetFont(scaled_font(11))
        self._eta_label.SetForegroundColour(FG_SECONDARY)
        self._eta_label.SetBackgroundColour(BG_CARD)

        top_row = wx.BoxSizer(wx.HORIZONTAL)
        top_row.Add(self._status_label, 0, wx.ALIGN_CENTER_VERTICAL)
        top_row.AddStretchSpacer()
        top_row.Add(self._test_mode_toggle, 0, wx.ALIGN_CENTER_VERTICAL)

        left = wx.BoxSizer(wx.VERTICAL)
        left.Add(top_row, 0, wx.EXPAND | wx.TOP, 8)
        left.AddSpacer(2)
        left.Add(self._eta_label, 0)
        left.AddSpacer(4)
        left.Add(self._progress_bar, 0, wx.EXPAND | wx.BOTTOM, 8)

        outer = wx.BoxSizer(wx.HORIZONTAL)
        outer.AddSpacer(10)
        outer.Add(left, 1, wx.EXPAND)
        outer.AddSpacer(8)
        outer.Add(self._collect_btn, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)
        outer.AddSpacer(10)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(outer, 1, wx.EXPAND)
        self.SetSizer(sizer)

    def bind_collect(self, callback: Callable[[], None]) -> None:
        self._on_collect_cb = callback

    def bind_abort(self, callback: Callable[[], None]) -> None:
        self._on_abort_cb = callback

    @property
    def test_mode(self) -> bool:
        return self._test_mode_toggle.GetValue()

    def set_collect_enabled(self, enabled: bool) -> None:
        if not self._collecting:
            self._collect_btn.Enable(enabled)

    def set_status(self, text: str, colour: wx.Colour | None = None) -> None:
        self._status_label.SetLabel(text)
        self._status_label.SetForegroundColour(colour if colour is not None else FG_SECONDARY)
        self._status_label.Refresh()

    def set_collecting(self, collecting: bool) -> None:
        self._collecting = collecting
        self._test_mode_toggle.Enable(not collecting)
        if collecting:
            self._collect_btn.SetLabel("Abort")
            self._collect_btn._idle_bg = _ABORT_SCHEME[0]
            self._collect_btn._hover_bg = _ABORT_SCHEME[1]
            self._collect_btn._press_bg = _ABORT_SCHEME[2]
            self._collect_btn._idle_fg = _ABORT_SCHEME[3]
            self._collect_btn._hover_fg = _ABORT_SCHEME[4]
        else:
            self._collect_btn.SetLabel("Collect")
            self._collect_btn._idle_bg = _COLLECT_SCHEME[0]
            self._collect_btn._hover_bg = _COLLECT_SCHEME[1]
            self._collect_btn._press_bg = _COLLECT_SCHEME[2]
            self._collect_btn._idle_fg = _COLLECT_SCHEME[3]
            self._collect_btn._hover_fg = _COLLECT_SCHEME[4]
        self._collect_btn.Refresh()

    def set_progress(
        self,
        point: int,
        total_points: int,
        frame: int = 0,
        total_frames: int = 0,
        point_fraction: float | None = None,
    ) -> None:
        if point_fraction is not None:
            fraction = max(0.0, min(1.0, point_fraction))
        else:
            completed = point - 1
            inner = frame / total_frames if total_frames > 1 else 0.0
            fraction = max(0.0, min(1.0, (completed + inner) / total_points if total_points > 0 else 0.0))
        label = f"Point {point}/{total_points}"
        sublabel = f"  Frame {frame}/{total_frames}" if total_frames > 1 else ""
        self._progress_bar.Update(fraction, label, sublabel)

    def set_eta(self, total_seconds: float) -> None:
        s = int(total_seconds)
        h, rem = divmod(s, 3600)
        m, s = divmod(rem, 60)
        self._eta_label.SetLabel(f"Estimated Time: {h:02d}:{m:02d}:{s:02d}")
        self._eta_label.Refresh()

    def clear_eta(self) -> None:
        self._eta_label.SetLabel("")
        self._eta_label.Refresh()

    def set_elapsed(self, elapsed_seconds: float) -> None:
        self._progress_bar.SetElapsed(elapsed_seconds)

    def clear_elapsed(self) -> None:
        self._progress_bar.ClearElapsed()

    def reset_progress(self) -> None:
        self._progress_bar.Reset()
        self.clear_eta()

    def set_status_collecting(self) -> None:
        self.set_status("Collecting…", PONI_LOADED)
        self.set_collecting(True)

    def set_status_ready(self) -> None:
        self.set_status("Ready", FG_SECONDARY)
        self.set_collecting(False)
        self.reset_progress()

    def set_status_error(self, message: str) -> None:
        self.set_status(message, DANGER)
        self.set_collecting(False)

    def _on_btn_clicked(self, _e=None) -> None:
        if self._collecting:
            if self._on_abort_cb is not None:
                self._on_abort_cb()
        else:
            if self._on_collect_cb is not None:
                self._on_collect_cb()
