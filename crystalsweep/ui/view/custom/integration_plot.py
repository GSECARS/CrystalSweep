#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/integration_plot.py
# ----------------------------------------------------------------------------------
# Purpose:
# 1D azimuthal integration profile plot with pan/zoom, unit selection, and
# calibration status overlay.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import math
from typing import Callable

import numpy as np
import wx

from crystalsweep.ui.view.custom.icons import draw_folder
from crystalsweep.ui.view.custom.theme import LIVE_H, LIVE_W, PONI_LOADED, PONI_MISSING
from crystalsweep.ui.view.custom.widgets import LiveToggle

__all__ = ["IntegrationPlot"]

_UNIT_KEYS = ["2th_deg", "d_A", "q_A^-1"]
_UNIT_LABELS = ["2\u03b8", "d (\u212b)", "Q (\u212b\u207b\u00b9)"]

_ICON_SIZE = 20
_BTN_HOVER = wx.Colour(50, 50, 55)
_BTN_PRESS = wx.Colour(70, 70, 78)
_UNIT_BTN_W = 44
_UNIT_BTN_H = 22
_UNIT_BTN_GAP = 4
_UNIT_FG = wx.Colour(180, 180, 190)
_UNIT_FG_ACTIVE = wx.Colour(72, 199, 116)
_UNIT_BG = wx.Colour(28, 28, 32)
_UNIT_BG_HOVER = wx.Colour(45, 45, 50)
_UNIT_BG_ACTIVE = wx.Colour(30, 55, 38)
_UNIT_BORDER = wx.Colour(55, 55, 62)
_UNIT_BORDER_ACTIVE = wx.Colour(72, 199, 116)


class IntegrationPlot(wx.Panel):
    """1D azimuthal integration profile plot."""

    _ML = 82
    _MR = 14
    _MT = 14
    _MB = 50
    _BTN_W = _ICON_SIZE + 8
    _BTN_H = _ICON_SIZE + 8
    _BTN_PAD = 6

    _BG = wx.Colour(0, 0, 0)
    _PLOT_BG = wx.Colour(6, 6, 8)
    _BORDER = wx.Colour(50, 50, 55)
    _CURVE = wx.Colour(99, 179, 237)
    _CURVE_FILL = wx.Colour(99, 179, 237, 30)
    _AXIS_LABEL = wx.Colour(140, 140, 150)
    _TICK_LABEL = wx.Colour(110, 110, 120)
    _EMPTY_TEXT = wx.Colour(80, 80, 90)

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.SetMinSize((-1, 160))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(wx.Colour(0, 0, 0))

        self._xs: np.ndarray | None = None
        self._ys: np.ndarray | None = None
        self._x_label: str = "Pixel"

        self._poni_text: str = "No calibration loaded"
        self._poni_colour: wx.Colour = PONI_MISSING
        self._load_poni_cb: Callable[[], None] | None = None
        self._calibrated: bool = False

        self._active_unit: str = _UNIT_KEYS[0]
        self._unit_changed_cb: Callable[[str], None] | None = None
        self._unit_btn_rects: list[wx.Rect] = []
        self._unit_btn_hovered: int = -1
        self._unit_btn_pressed: int = -1

        self._btn_hovered: bool = False
        self._btn_pressed: bool = False
        self._btn_rect: wx.Rect = wx.Rect(0, 0, 0, 0)

        self._hover_data_x: float | None = None
        self._hover_data_y: float | None = None

        self._zoom_x_min: float | None = None
        self._zoom_x_max: float | None = None
        self._zoom_y_min: float | None = None
        self._zoom_y_max: float | None = None
        self._panning: bool = False
        self._pan_last_pt: wx.Point | None = None
        self._drag_start: wx.Point | None = None
        self._drag_end: wx.Point | None = None

        self._live_toggle = LiveToggle(self, live=False, tooltip="Toggle live ROI integration")
        self._live_toggle.Hide()

        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, self._on_size)
        self.Bind(wx.EVT_MOTION, self._on_mouse_move)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_mouse_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_mouse_up)
        self.Bind(wx.EVT_MOUSEWHEEL, self._on_mouse_wheel)
        self.Bind(wx.EVT_RIGHT_DCLICK, self._on_right_dclick)

        self._reposition_live_toggle()

    def set_poni_info(self, text: str, *, success: bool) -> None:
        self._poni_text = text
        self._poni_colour = PONI_LOADED if success else PONI_MISSING
        self.Refresh()

    def set_load_poni_callback(self, callback: Callable[[], None]) -> None:
        self._load_poni_cb = callback

    def set_unit_changed_callback(self, callback: Callable[[str], None]) -> None:
        self._unit_changed_cb = callback

    def set_live_integration_callback(self, callback: Callable[[bool], None]) -> None:
        self._live_toggle.set_toggled_callback(callback)

    @property
    def is_live_integration(self) -> bool:
        return self._live_toggle.is_live

    def set_calibrated(self, calibrated: bool) -> None:
        self._calibrated = calibrated
        if calibrated:
            self._live_toggle.Show()
        else:
            self._live_toggle.set_live(False)
            self._live_toggle.Hide()
        self._reposition_live_toggle()
        self.Refresh()

    def set_active_unit(self, unit: str) -> None:
        if unit in _UNIT_KEYS:
            self._active_unit = unit
            self.Refresh()

    def set_data(self, xs: np.ndarray, ys: np.ndarray, x_label: str = "Pixel") -> None:
        self._xs = xs
        self._ys = ys
        self._x_label = x_label
        self._zoom_x_min = self._zoom_x_max = self._zoom_y_min = self._zoom_y_max = None
        self.Refresh()

    def clear(self) -> None:
        self._xs = None
        self._ys = None
        self._x_label = "Pixel"
        self.Refresh()

    def _reposition_live_toggle(self) -> None:
        W, H = self.GetSize()
        x = W - LIVE_W - self._BTN_PAD
        y = self._MT + max(0, (H - self._MT - self._MB - LIVE_H) // 2)
        self._live_toggle.SetPosition(wx.Point(x, y))

    def _data_ranges(self) -> tuple[float, float, float, float] | None:
        if self._xs is None or self._ys is None or len(self._xs) < 2:
            return None
        x_min = self._zoom_x_min if self._zoom_x_min is not None else float(self._xs[0])
        x_max = self._zoom_x_max if self._zoom_x_max is not None else float(self._xs[-1])
        y_min = self._zoom_y_min if self._zoom_y_min is not None else float(self._ys.min())
        y_max = self._zoom_y_max if self._zoom_y_max is not None else float(self._ys.max())
        if x_max == x_min:
            x_max = x_min + 1
        if y_max == y_min:
            y_max = y_min + 1
        return x_min, x_max, y_min, y_max

    def _btn_rect_for(self, W: int, H: int) -> wx.Rect:
        return wx.Rect(W - self._BTN_W - self._BTN_PAD, H - self._BTN_H - self._BTN_PAD, self._BTN_W, self._BTN_H)

    def _unit_btn_at(self, pt: wx.Point) -> int:
        for i, r in enumerate(self._unit_btn_rects):
            if r.Contains(pt):
                return i
        return -1

    def _in_plot(self, pt: wx.Point) -> bool:
        W, H = self.GetSize()
        return self._ML <= pt.x <= W - self._MR and self._MT <= pt.y <= H - self._MB

    def _on_mouse_wheel(self, event: wx.MouseEvent) -> None:
        if self._xs is None or len(self._xs) < 2:
            event.Skip()
            return
        W, H = self.GetSize()
        ml, mr, mt, mb = self._ML, self._MR, self._MT, self._MB
        pw, ph = W - ml - mr, H - mt - mb
        pt = event.GetPosition()
        if not (ml <= pt.x <= ml + pw and mt <= pt.y <= mt + ph):
            event.Skip()
            return
        ranges = self._data_ranges()
        if ranges is None:
            event.Skip()
            return
        x_min, x_max, y_min, y_max = ranges
        factor = 1.15 ** (-event.GetWheelRotation() / 120.0)
        mx = x_min + (pt.x - ml) / pw * (x_max - x_min)
        my = y_max - (pt.y - mt) / ph * (y_max - y_min)
        self._zoom_x_min = mx + (x_min - mx) * factor
        self._zoom_x_max = mx + (x_max - mx) * factor
        self._zoom_y_min = my + (y_min - my) * factor
        self._zoom_y_max = my + (y_max - my) * factor
        self.Refresh()
        event.Skip()

    def _on_right_dclick(self, event: wx.MouseEvent) -> None:
        self._zoom_x_min = self._zoom_x_max = self._zoom_y_min = self._zoom_y_max = None
        self.Refresh()
        event.Skip()

    def _on_mouse_move(self, event: wx.MouseEvent) -> None:
        pt = event.GetPosition()
        W, H = self.GetSize()

        if self._drag_start is not None:
            self._drag_end = pt
            self.Refresh()
            event.Skip()
            return

        if self._panning and self._pan_last_pt is not None:
            ranges = self._data_ranges()
            if ranges is not None:
                ml, mr, mt, mb = self._ML, self._MR, self._MT, self._MB
                pw, ph = W - ml - mr, H - mt - mb
                x_min, x_max, y_min, y_max = ranges
                dx = (pt.x - self._pan_last_pt.x) / pw * (x_max - x_min)
                dy = (pt.y - self._pan_last_pt.y) / ph * (y_max - y_min)
                self._zoom_x_min = x_min - dx
                self._zoom_x_max = x_max - dx
                self._zoom_y_min = y_min + dy
                self._zoom_y_max = y_max + dy
                self._pan_last_pt = pt
                self.Refresh()
            event.Skip()
            return

        inside_btn = self._btn_rect_for(W, H).Contains(pt)
        if inside_btn != self._btn_hovered:
            self._btn_hovered = inside_btn
            self.Refresh()

        if self._calibrated:
            idx = self._unit_btn_at(pt)
            if idx != self._unit_btn_hovered:
                self._unit_btn_hovered = idx
                self.Refresh()

        ranges = self._data_ranges()
        ml, mr, mt, mb = self._ML, self._MR, self._MT, self._MB
        pw, ph = W - ml - mr, H - mt - mb
        if ranges is not None and ml <= pt.x <= ml + pw and mt <= pt.y <= mt + ph:
            x_min, x_max, y_min, y_max = ranges
            new_x = x_min + (pt.x - ml) / pw * (x_max - x_min)
            new_y = y_max - (pt.y - mt) / ph * (y_max - y_min)
        else:
            new_x, new_y = None, None

        if new_x != self._hover_data_x or new_y != self._hover_data_y:
            self._hover_data_x = new_x
            self._hover_data_y = new_y
            self.Refresh()
        event.Skip()

    def _on_leave(self, event: wx.MouseEvent) -> None:
        changed = self._btn_hovered or self._btn_pressed or self._unit_btn_hovered != -1 or self._hover_data_x is not None
        self._btn_hovered = self._btn_pressed = False
        self._unit_btn_hovered = self._unit_btn_pressed = -1
        self._hover_data_x = self._hover_data_y = None
        self._panning = False
        self._pan_last_pt = self._drag_start = self._drag_end = None
        if changed:
            self.Refresh()
        event.Skip()

    def _on_mouse_down(self, event: wx.MouseEvent) -> None:
        pt = event.GetPosition()
        W, H = self.GetSize()
        if event.ShiftDown() and self._xs is not None:
            self._panning = True
            self._pan_last_pt = pt
            event.Skip()
            return
        if self._btn_rect_for(W, H).Contains(pt):
            self._btn_pressed = True
            self.Refresh()
            event.Skip()
            return
        if self._calibrated:
            idx = self._unit_btn_at(pt)
            if idx != -1:
                self._unit_btn_pressed = idx
                self.Refresh()
                event.Skip()
                return
        if self._xs is not None and self._in_plot(pt):
            self._drag_start = self._drag_end = pt
        event.Skip()

    def _on_mouse_up(self, event: wx.MouseEvent) -> None:
        if self._panning:
            self._panning = False
            self._pan_last_pt = None
            event.Skip()
            return
        if self._drag_start is not None:
            start, end = self._drag_start, event.GetPosition()
            self._drag_start = self._drag_end = None
            self.Refresh()
            ranges = self._data_ranges()
            if ranges is not None:
                W, H = self.GetSize()
                ml, mr, mt, mb = self._ML, self._MR, self._MT, self._MB
                pw, ph = W - ml - mr, H - mt - mb
                x_min, x_max, y_min, y_max = ranges
                sx = sorted([start.x, end.x])
                sy = sorted([start.y, end.y])
                if sx[1] - sx[0] > 4 and sy[1] - sy[0] > 4:
                    self._zoom_x_min = x_min + (sx[0] - ml) / pw * (x_max - x_min)
                    self._zoom_x_max = x_min + (sx[1] - ml) / pw * (x_max - x_min)
                    self._zoom_y_min = y_max - (sy[1] - mt) / ph * (y_max - y_min)
                    self._zoom_y_max = y_max - (sy[0] - mt) / ph * (y_max - y_min)
                    self.Refresh()
            event.Skip()
            return

        pt = event.GetPosition()
        W, H = self.GetSize()
        was_btn = self._btn_pressed
        was_unit = self._unit_btn_pressed
        self._btn_pressed = False
        self._unit_btn_pressed = -1
        self.Refresh()
        if was_btn and self._btn_rect_for(W, H).Contains(pt) and self._load_poni_cb is not None:
            self._load_poni_cb()
        if was_unit != -1 and self._unit_btn_at(pt) == was_unit:
            self._active_unit = _UNIT_KEYS[was_unit]
            if self._unit_changed_cb is not None:
                self._unit_changed_cb(self._active_unit)
        event.Skip()

    def _on_size(self, event: wx.SizeEvent) -> None:
        self._reposition_live_toggle()
        self.Refresh()
        event.Skip()

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        dc.DestroyClippingRegion()
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return

        W, H = self.GetSize()
        ml, mr, mt, mb = self._ML, self._MR, self._MT, self._MB
        pw, ph = W - ml - mr, H - mt - mb

        gc.SetBrush(wx.Brush(self._BG))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, W, H)

        gc.SetBrush(wx.Brush(self._PLOT_BG))
        gc.DrawRectangle(ml, mt, pw, ph)

        gc.SetPen(wx.Pen(self._BORDER, 1))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.StrokeLine(ml, mt + ph, ml + pw, mt + ph)
        gc.StrokeLine(ml, mt, ml, mt + ph)

        font_small = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        ranges = self._data_ranges()

        if ranges is None:
            gc.SetFont(wx.Font(13, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD), self._EMPTY_TEXT)
            msg = "Draw an ROI on the image to see the integration profile"
            tw, th = gc.GetTextExtent(msg)
            gc.DrawText(msg, ml + pw / 2 - tw / 2, mt + ph / 2 - th / 2)
        else:
            xs, ys = self._xs, self._ys
            x_min, x_max, y_min, y_max = ranges

            def to_px(x, y):
                return (ml + (x - x_min) / (x_max - x_min) * pw, mt + ph - (y - y_min) / (y_max - y_min) * ph)

            gc.SetFont(font_small, self._TICK_LABEL)
            for i in range(5):
                t = i / 4
                y_val = y_min + t * (y_max - y_min)
                _, py = to_px(x_min, y_val)
                av = abs(y_val)
                if av == 0:
                    lbl = "0"
                elif av >= 1e6 or (0 < av < 0.01):
                    lbl = f"{y_val:.2e}"
                elif av >= 1000:
                    lbl = f"{y_val:,.0f}"
                elif av >= 10:
                    lbl = f"{y_val:.1f}"
                else:
                    lbl = f"{y_val:.3f}"
                tw, th = gc.GetTextExtent(lbl)
                gc.DrawText(lbl, ml - tw - 4, py - th / 2)

            for i in range(5):
                t = i / 4
                x_val = x_min + t * (x_max - x_min)
                px, _ = to_px(x_val, y_min)
                gc.SetPen(wx.Pen(self._BORDER, 1))
                gc.StrokeLine(px, mt + ph, px, mt + ph + 3)
                lbl = f"{x_val:.4g}"
                tw, _ = gc.GetTextExtent(lbl)
                gc.DrawText(lbl, px - tw / 2, mt + ph + 5)

            dc.SetClippingRegion(ml, mt, pw, ph)
            pts = [to_px(x, y) for x, y in zip(xs, ys)]

            fill = gc.CreatePath()
            fill.MoveToPoint(pts[0][0], mt + ph)
            for px, py in pts:
                fill.AddLineToPoint(px, py)
            fill.AddLineToPoint(pts[-1][0], mt + ph)
            fill.CloseSubpath()
            gc.SetBrush(wx.Brush(self._CURVE_FILL))
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.FillPath(fill)

            line = gc.CreatePath()
            line.MoveToPoint(pts[0][0], pts[0][1])
            for px, py in pts[1:]:
                line.AddLineToPoint(px, py)
            gc.SetPen(wx.Pen(self._CURVE, 1))
            gc.SetBrush(wx.TRANSPARENT_BRUSH)
            gc.StrokePath(line)

            dc.DestroyClippingRegion()

            gc.SetFont(font_small, self._AXIS_LABEL)
            x_lw, _ = gc.GetTextExtent(self._x_label)
            gc.DrawText(self._x_label, ml + pw / 2 - x_lw / 2, H - mb + 20)

            y_lbl = "Intensity"
            y_lw, y_lh = gc.GetTextExtent(y_lbl)
            gc.PushState()
            gc.Translate(y_lh, mt + ph / 2 + y_lw / 2)
            gc.Rotate(-math.pi / 2)
            gc.DrawText(y_lbl, 0, 0)
            gc.PopState()

        if self._drag_start is not None and self._drag_end is not None:
            sx = sorted([self._drag_start.x, self._drag_end.x])
            sy = sorted([self._drag_start.y, self._drag_end.y])
            rw, rh = sx[1] - sx[0], sy[1] - sy[0]
            if rw > 1 and rh > 1:
                gc.SetBrush(wx.Brush(wx.Colour(99, 179, 237, 30)))
                gc.SetPen(wx.Pen(wx.Colour(99, 179, 237, 180), 1))
                gc.DrawRectangle(sx[0], sy[0], rw, rh)

        self._draw_poni_overlay(gc, W, H)
        if self._calibrated:
            self._draw_unit_buttons(gc, W, H)

    def _draw_unit_buttons(self, gc: wx.GraphicsContext, W: int, H: int) -> None:
        total_w = len(_UNIT_KEYS) * _UNIT_BTN_W + (len(_UNIT_KEYS) - 1) * _UNIT_BTN_GAP
        start_x = W - self._MR - total_w
        self._unit_btn_rects = []
        font = wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        for i, (key, label) in enumerate(zip(_UNIT_KEYS, _UNIT_LABELS)):
            x = start_x + i * (_UNIT_BTN_W + _UNIT_BTN_GAP)
            r = wx.Rect(x, 2, _UNIT_BTN_W, _UNIT_BTN_H)
            self._unit_btn_rects.append(r)
            active = key == self._active_unit
            if i == self._unit_btn_pressed:
                bg, border, fg = _BTN_PRESS, _UNIT_BORDER_ACTIVE if active else _UNIT_BORDER, _UNIT_FG_ACTIVE if active else _UNIT_FG
            elif active:
                bg, border, fg = _UNIT_BG_ACTIVE, _UNIT_BORDER_ACTIVE, _UNIT_FG_ACTIVE
            elif i == self._unit_btn_hovered:
                bg, border, fg = _UNIT_BG_HOVER, _UNIT_BORDER, _UNIT_FG
            else:
                bg, border, fg = _UNIT_BG, _UNIT_BORDER, _UNIT_FG
            gc.SetBrush(wx.Brush(bg))
            gc.SetPen(wx.Pen(border, 1))
            gc.DrawRoundedRectangle(r.x, r.y, r.width, r.height, 3)
            gc.SetFont(font, fg)
            tw, th = gc.GetTextExtent(label)
            gc.DrawText(label, r.x + (r.width - tw) / 2, r.y + (r.height - th) / 2)

    def _draw_poni_overlay(self, gc: wx.GraphicsContext, W: int, H: int) -> None:
        br = self._btn_rect_for(W, H)
        self._btn_rect = br
        bg = _BTN_PRESS if self._btn_pressed else (_BTN_HOVER if self._btn_hovered else wx.Colour(0, 0, 0))
        gc.SetBrush(wx.Brush(bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRoundedRectangle(br.x, br.y, br.width, br.height, 4)
        gc.SetAntialiasMode(wx.ANTIALIAS_DEFAULT)
        off = (br.width - _ICON_SIZE) / 2
        gc.PushState()
        gc.Translate(br.x + off, br.y + off)
        draw_folder(gc, _ICON_SIZE)
        gc.PopState()

        font = wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL)
        gc.SetFont(font, self._poni_colour)
        tw, th = gc.GetTextExtent(self._poni_text)
        gc.DrawText(self._poni_text, br.x - tw - self._BTN_PAD, br.y + (br.height - th) / 2)

        info_font = wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        gc.SetFont(info_font, wx.Colour(72, 199, 116))
        x = self._BTN_PAD
        if self._ys is not None:
            lbl = f"max: {float(self._ys.max()):.4g}"
            lw, lh = gc.GetTextExtent(lbl)
            gc.DrawText(lbl, x, br.y + (br.height - lh) / 2)
            x += lw + 16
        if self._hover_data_x is not None and self._hover_data_y is not None:
            coord = f"{self._x_label}: {self._hover_data_x:.4g}   I: {self._hover_data_y:.4g}"
            _, ch = gc.GetTextExtent(coord)
            gc.DrawText(coord, x, br.y + (br.height - ch) / 2)
