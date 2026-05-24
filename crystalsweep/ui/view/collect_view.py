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
    ACCENT,
    BG_CARD,
    BG_ELEVATED,
    DANGER,
    DANGER_HOVER,
    DANGER_PRESS,
    FG_PRIMARY,
    FG_SECONDARY,
    PONI_LOADED,
    scaled_font,
)
from crystalsweep.ui.view.custom.widgets import DarkToggle, FlatButton

__all__ = ["CollectView"]

_COLLECT_SCHEME = (
    wx.Colour(30, 100, 60),
    wx.Colour(40, 130, 80),
    wx.Colour(20, 75, 45),
    wx.Colour(200, 255, 220),
    wx.Colour(200, 255, 220),
)
_ABORT_SCHEME = (DANGER, DANGER_HOVER, DANGER_PRESS, FG_PRIMARY, FG_PRIMARY)

_BAR_H = 28


def _format_hms(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class _ProgressBar(wx.Panel):
    """Custom-painted progress bar with point/frame text overlay."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, size=(-1, _BAR_H), style=wx.BORDER_NONE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(BG_CARD)
        self._fraction: float = 0.0
        self._point_text: str = ""
        self._frame_text: str = ""
        self._elapsed_text: str = ""
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, lambda _e: self.Refresh())

    def update(
        self,
        point: int,
        total_points: int,
        frame: int = 0,
        total_frames: int = 0,
        point_fraction: float | None = None,
    ) -> None:
        if point_fraction is not None:
            self._fraction = max(0.0, min(1.0, point_fraction))
        else:
            completed_points = point - 1
            inner = frame / total_frames if total_frames > 1 else 0.0
            self._fraction = max(0.0, min(1.0, (completed_points + inner) / total_points if total_points > 0 else 0.0))
        self._point_text = f"Point {point}/{total_points}"
        self._frame_text = f"  Frame {frame}/{total_frames}" if total_frames > 1 else ""
        self.Refresh()

    def set_elapsed(self, elapsed_seconds: float) -> None:
        self._elapsed_text = _format_hms(elapsed_seconds)
        self.Refresh()

    def clear_elapsed(self) -> None:
        self._elapsed_text = ""
        self.Refresh()

    def reset(self) -> None:
        self._fraction = 0.0
        self._point_text = ""
        self._frame_text = ""
        self._elapsed_text = ""
        self.Refresh()

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        r = 4

        gc.SetBrush(wx.Brush(BG_ELEVATED))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRoundedRectangle(0, 0, w, h, r)

        fill_w = int(w * self._fraction)
        if fill_w > 0:
            gc.SetBrush(wx.Brush(ACCENT))
            gc.DrawRoundedRectangle(0, 0, fill_w, h, r)

        if self._point_text:
            font = scaled_font(11, weight=wx.FONTWEIGHT_BOLD)
            full_text = self._point_text + self._frame_text
            gc.SetFont(font, wx.Colour(255, 255, 255))
            tw, th = gc.GetTextExtent(full_text)
            tx = (w - tw) / 2
            ty = (h - th) / 2

            if self._frame_text:
                pt_w, _ = gc.GetTextExtent(self._point_text)
                gc.SetFont(font, wx.Colour(255, 255, 255))
                gc.DrawText(self._point_text, tx, ty)
                gc.SetFont(scaled_font(11), wx.Colour(200, 230, 255))
                gc.DrawText(self._frame_text, tx + pt_w, ty)
            else:
                gc.DrawText(self._point_text, tx, ty)

        if self._elapsed_text:
            efont = scaled_font(11)
            gc.SetFont(efont, wx.Colour(200, 230, 255))
            ew, eh = gc.GetTextExtent(self._elapsed_text)
            pad = 6
            gc.DrawText(self._elapsed_text, w - ew - pad, (h - eh) / 2)


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

        self._progress_bar = _ProgressBar(self)

        self._collect_btn = FlatButton(self, "Collect", color_scheme=_COLLECT_SCHEME)
        self._collect_btn.SetMinSize((120, 42))
        self._collect_btn.set_action(self._on_btn_clicked)

        self._test_mode_toggle = DarkToggle(self, "Test mode")
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

    def set_status(self, text: str, colour: wx.Colour | None = None) -> None:
        self._status_label.SetLabel(text)
        self._status_label.SetForegroundColour(colour if colour is not None else FG_SECONDARY)
        self._status_label.Refresh()

    def set_collecting(self, collecting: bool) -> None:
        self._collecting = collecting
        self._test_mode_toggle.SetLocked(collecting)
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
        self._progress_bar.update(point, total_points, frame, total_frames, point_fraction)

    def set_eta(self, total_seconds: float) -> None:
        self._eta_label.SetLabel(f"Estimated Time: {_format_hms(total_seconds)}")
        self._eta_label.Refresh()

    def clear_eta(self) -> None:
        self._eta_label.SetLabel("")
        self._eta_label.Refresh()

    def set_elapsed(self, elapsed_seconds: float) -> None:
        self._progress_bar.set_elapsed(elapsed_seconds)

    def clear_elapsed(self) -> None:
        self._progress_bar.clear_elapsed()

    def reset_progress(self) -> None:
        self._progress_bar.reset()
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

    def _on_btn_clicked(self) -> None:
        if self._collecting:
            if self._on_abort_cb is not None:
                self._on_abort_cb()
        else:
            if self._on_collect_cb is not None:
                self._on_collect_cb()
