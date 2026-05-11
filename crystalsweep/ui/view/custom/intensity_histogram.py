#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/intensity_histogram.py
# ----------------------------------------------------------------------------------
# Purpose:
# Intensity histogram widget for image contrast control.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from typing import Callable

import numpy as np
import wx
from vispy.color import get_colormap

from crystalsweep.ui.view.custom.colormaps import CUSTOM_COLORMAPS
from crystalsweep.ui.view.custom.histogram_utils import compute_histogram_data

__all__ = ["IntensityHistogramWidget"]


class IntensityHistogramWidget(wx.Panel):
    """Horizontal intensity histogram + colorbar strip with draggable contrast handles."""

    _ML = 30
    _MR = 10
    _MT = 6
    _GRADIENT_H = 12
    _GRADIENT_GAP = 4
    _MB = 10
    _HANDLE_R = 6
    _HIT_RADIUS = 10

    def __init__(self, parent: wx.Window, colormap: str = "gray", on_levels_changed: Callable | None = None) -> None:
        super().__init__(parent)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetMinSize((-1, 64))

        self._colormap = colormap
        self._min_val = 1.0
        self._max_val = 255.0
        self._level_min = 1.0
        self._level_max = 255.0
        self._bin_centers: np.ndarray | None = None
        self._log_counts: np.ndarray | None = None
        self._gradient_bitmap: wx.Bitmap | None = None
        self._gradient_bitmap_width: int = 0
        self._dragging: str | None = None
        self._drag_start_x: float = 0.0
        self._drag_start_min: float = 0.0
        self._drag_start_max: float = 0.0
        self._on_levels_changed = on_levels_changed

        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, self._on_size)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_mouse_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_mouse_up)
        self.Bind(wx.EVT_MOTION, self._on_mouse_move)

    def set_colormap(self, colormap: str) -> None:
        self._colormap = colormap
        self._gradient_bitmap = None
        self.Refresh()

    def set_data(self, image: np.ndarray, auto_scale: bool = False) -> None:
        if image is None or image.size == 0:
            return
        raw_min = float(image.min())
        raw_max = float(image.max())
        new_min = max(raw_min, -1.0)
        new_max = raw_max if raw_max > new_min else new_min + 1.0
        self._bin_centers, self._log_counts = compute_histogram_data(image)
        if auto_scale or self._level_min >= self._level_max:
            self._min_val = new_min
            self._max_val = new_max
            self._level_min = self._min_val
            self._level_max = self._max_val
        else:
            self._min_val = min(self._min_val, new_min)
            self._max_val = max(self._max_val, new_max)
        self.Refresh()

    def set_levels(self, min_val: float, max_val: float) -> None:
        self._level_min = min_val
        self._level_max = max_val
        self.Refresh()

    def get_levels(self) -> tuple[float, float]:
        return self._level_min, self._level_max

    def set_range(self, min_val: float, max_val: float) -> None:
        self._min_val = max(min_val, -1.0)
        self._max_val = max_val if max_val > self._min_val else self._min_val + 1.0
        self.Refresh()

    def _plot_rect(self) -> tuple[int, int, int, int]:
        w, h = self.GetSize()
        pb = h - self._MB - self._GRADIENT_H - self._GRADIENT_GAP
        return self._ML, self._MT, max(1, w - self._ML - self._MR), max(1, pb - self._MT)

    def _gradient_rect(self) -> tuple[int, int, int, int]:
        w, h = self.GetSize()
        y = h - self._MB - self._GRADIENT_H
        return self._ML, y, max(1, w - self._ML - self._MR), self._GRADIENT_H

    def _val_to_x(self, value: float) -> float:
        pl, _, pw, _ = self._plot_rect()
        log_min = np.log1p(max(self._min_val, 0.0))
        log_max = np.log1p(max(self._max_val, 0.0))
        if log_max == log_min:
            return pl + pw / 2.0
        t = max(0.0, min(1.0, (np.log1p(max(value, 0.0)) - log_min) / (log_max - log_min)))
        return pl + t * pw

    def _x_to_val(self, x: float) -> float:
        pl, _, pw, _ = self._plot_rect()
        log_min = np.log1p(max(self._min_val, 0.0))
        log_max = np.log1p(max(self._max_val, 0.0))
        t = max(0.0, min(1.0, (x - pl) / pw))
        return np.expm1(log_min + t * (log_max - log_min))

    def _build_gradient_bitmap(self, w: int, h: int) -> wx.Bitmap:
        cmap = CUSTOM_COLORMAPS.get(self._colormap) or get_colormap(self._colormap)
        ts = np.linspace(0.0, 1.0, max(w, 1))
        rgba = cmap[ts].rgba
        rgb = (np.clip(rgba[:, :3], 0.0, 1.0) * 255).astype(np.uint8)
        data = np.ascontiguousarray(np.repeat(rgb[:, np.newaxis, :], h, axis=1).transpose(1, 0, 2))
        return wx.Bitmap.FromBuffer(w, h, data.tobytes())

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return

        w, h = self.GetSize()
        pl, pt, pw, ph = self._plot_rect()
        gx, gy, gw, gh = self._gradient_rect()

        _BG = wx.Colour(0, 0, 0)
        _HIST_LINE = wx.Colour(99, 179, 237)
        _HIST_FILL = wx.Colour(99, 179, 237, 35)
        _REGION_FILL = wx.Colour(99, 179, 237, 45)
        _REGION_HOVER = wx.Colour(130, 200, 255, 70)
        _HANDLE_MIN = wx.Colour(252, 110, 81)
        _HANDLE_MAX = wx.Colour(72, 199, 116)
        _BAR_BORDER = wx.Colour(55, 55, 60)

        gc.SetBrush(wx.Brush(_BG))
        gc.DrawRectangle(0, 0, w, h)

        bmp_w, bmp_h = int(gw), int(gh)
        if bmp_w > 0 and bmp_h > 0:
            if self._gradient_bitmap is None or self._gradient_bitmap_width != bmp_w:
                self._gradient_bitmap = self._build_gradient_bitmap(bmp_w, bmp_h)
                self._gradient_bitmap_width = bmp_w
            gc.DrawBitmap(self._gradient_bitmap, gx, gy, bmp_w, bmp_h)

        gc.SetPen(wx.Pen(_BAR_BORDER, 1))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.DrawRectangle(gx, gy, gw, gh)

        if self._bin_centers is not None and self._log_counts is not None and len(self._bin_centers) > 1:
            log_min = np.log1p(max(self._min_val, 0.0))
            log_max = np.log1p(max(self._max_val, 0.0))
            log_range = log_max - log_min or 1.0
            count_range = (self._log_counts.max() - self._log_counts.min()) or 1.0
            count_min = self._log_counts.min()

            pts = [(pl + max(0.0, min(1.0, (bc - log_min) / log_range)) * pw, pt + ph - (lc - count_min) / count_range * ph) for bc, lc in zip(self._bin_centers, self._log_counts)]

            fill = gc.CreatePath()
            fill.MoveToPoint(pts[0][0], pt + ph)
            for px, py in pts:
                fill.AddLineToPoint(px, py)
            fill.AddLineToPoint(pts[-1][0], pt + ph)
            fill.CloseSubpath()
            gc.SetBrush(wx.Brush(_HIST_FILL))
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.FillPath(fill)

            line = gc.CreatePath()
            line.MoveToPoint(pts[0][0], pts[0][1])
            for px, py in pts[1:]:
                line.AddLineToPoint(px, py)
            gc.SetPen(wx.Pen(_HIST_LINE, 1))
            gc.SetBrush(wx.TRANSPARENT_BRUSH)
            gc.StrokePath(line)

        min_x = self._val_to_x(self._level_min)
        max_x = self._val_to_x(self._level_max)
        rw = max(min_x, max_x) - min(min_x, max_x)
        if rw > 0:
            fill = _REGION_HOVER if self._dragging == "region" else _REGION_FILL
            gc.SetBrush(wx.Brush(fill))
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.DrawRectangle(min(min_x, max_x), pt, rw, ph + gh)

        for x, col in ((min_x, _HANDLE_MIN), (max_x, _HANDLE_MAX)):
            gc.SetPen(wx.Pen(col, 1))
            gc.StrokeLine(x, pt, x, gy + gh)
            r = self._HANDLE_R
            gc.SetBrush(wx.Brush(col))
            gc.SetPen(wx.Pen(wx.Colour(18, 18, 18), 1))
            gc.DrawEllipse(x - r, gy + gh // 2 - r, r * 2, r * 2)

        font = wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)

        def _fmt(v: float) -> str:
            if v == 0:
                return "0"
            if abs(v) >= 10000 or (abs(v) < 0.01 and v != 0):
                return f"{v:.2e}"
            return f"{int(v):,}" if v == int(v) else f"{v:.1f}"

        for x, col, val in ((min_x, _HANDLE_MIN, self._level_min), (max_x, _HANDLE_MAX, self._level_max)):
            gc.SetFont(font, col)
            lbl = _fmt(val)
            tw, _ = gc.GetTextExtent(lbl)
            gc.DrawText(lbl, x - tw / 2, gy + gh + 2)

    def _on_mouse_down(self, event: wx.MouseEvent) -> None:
        x = event.GetX()
        min_x = self._val_to_x(self._level_min)
        max_x = self._val_to_x(self._level_max)
        if abs(x - min_x) < self._HIT_RADIUS:
            self._dragging = "min"
            self.CaptureMouse()
        elif abs(x - max_x) < self._HIT_RADIUS:
            self._dragging = "max"
            self.CaptureMouse()
        elif min(min_x, max_x) <= x <= max(min_x, max_x):
            self._dragging = "region"
            self._drag_start_x = x
            self._drag_start_min = self._level_min
            self._drag_start_max = self._level_max
            self.CaptureMouse()

    def _on_mouse_up(self, event: wx.MouseEvent) -> None:
        if self._dragging and self.HasCapture():
            self.ReleaseMouse()
        self._dragging = None
        self.Refresh()

    def _on_mouse_move(self, event: wx.MouseEvent) -> None:
        if not self._dragging:
            return
        x = event.GetX()
        if self._dragging == "region":
            delta = x - self._drag_start_x
            new_min = self._x_to_val(self._val_to_x(self._drag_start_min) + delta)
            log_span = np.log1p(max(self._drag_start_max, 0.0)) - np.log1p(max(self._drag_start_min, 0.0))
            log_dmin = np.log1p(max(self._min_val, 0.0))
            log_dmax = np.log1p(max(self._max_val, 0.0))
            lmin = np.log1p(max(new_min, 0.0))
            lmax = lmin + log_span
            if lmin < log_dmin:
                lmin, lmax = log_dmin, log_dmin + log_span
            if lmax > log_dmax:
                lmax, lmin = log_dmax, log_dmax - log_span
            self._level_min = np.expm1(lmin)
            self._level_max = np.expm1(lmax)
        else:
            value = max(self._min_val, min(self._max_val, self._x_to_val(x)))
            if self._dragging == "min" and value < self._level_max:
                self._level_min = value
            elif self._dragging == "max" and value > self._level_min:
                self._level_max = value
        self.Refresh()
        if self._on_levels_changed:
            self._on_levels_changed(self._level_min, self._level_max)

    def _on_size(self, event: wx.SizeEvent) -> None:
        self._gradient_bitmap = None
        self.Refresh()
        event.Skip()
