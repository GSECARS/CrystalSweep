#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/integration_plot.py
# ----------------------------------------------------------------------------------
# Purpose:
# 1D azimuthal integration profile plot with pan/zoom, unit selection, and
# calibration status overlay.  The curve area is rendered via a VisPy
# SceneCanvas embedded inside the margins; axes, labels and button overlays
# are drawn with wx.GraphicsContext on the outer wx.Panel.
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
from vispy import scene

from crystalsweep.ui.view.custom.icons import draw_folder
from crystalsweep.ui.view.custom.theme import LIVE_H, LIVE_W, PONI_LOADED, PONI_MISSING, scaled_font
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
    """1D azimuthal integration profile plot.

    Axes, labels and button overlays are painted with wx.GraphicsContext.
    The curve and fill area are rendered by a VisPy SceneCanvas that sits
    inside the plot margins.
    """

    _ML = 82
    _MR = 14
    _MT = 30
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

    _C_CURVE = (99 / 255, 179 / 255, 237 / 255, 1.0)
    _C_CURVE_FILL = (99 / 255, 179 / 255, 237 / 255, 30 / 255)
    _C_SEL = (99 / 255, 179 / 255, 237 / 255, 0.7)
    _C_EMPTY = (80 / 255, 80 / 255, 90 / 255, 1.0)

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

        self._canvas = scene.SceneCanvas(
            keys=None,
            parent=self,
            app="wx",
            vsync=True,
            bgcolor=(6 / 255, 6 / 255, 8 / 255, 1.0),
            config={"double_buffer": True, "depth_size": 0, "stencil_size": 0},
        )
        self._view = self._canvas.central_widget.add_view()
        self._view.camera = scene.PanZoomCamera(aspect=None)
        self._view.camera.interactive = False

        self._curve_line = scene.visuals.Line(
            pos=np.array([[0, 0], [1, 1]], dtype=np.float32),
            color=self._C_CURVE,
            width=1.5,
            method="agg",
            parent=self._view.scene,
        )
        self._curve_line.visible = False

        self._fill_mesh = scene.visuals.Mesh(
            vertices=np.zeros((4, 2), dtype=np.float32),
            faces=np.array([[0, 1, 2], [0, 2, 3]], dtype=np.uint32),
            color=self._C_CURVE_FILL,
            parent=self._view.scene,
        )
        self._fill_mesh.visible = False

        self._sel_line = scene.visuals.Line(
            pos=np.array([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]], dtype=np.float32),
            color=self._C_SEL,
            width=1,
            method="agg",
            connect="strip",
            parent=self._view.scene,
        )
        self._sel_line.visible = False

        self._canvas.native.Hide()

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

        self._canvas.native.Bind(wx.EVT_MOUSEWHEEL, self._on_mouse_wheel)
        self._canvas.native.Bind(wx.EVT_LEFT_DOWN, self._on_mouse_down)
        self._canvas.native.Bind(wx.EVT_LEFT_UP, self._on_mouse_up)
        self._canvas.native.Bind(wx.EVT_MOTION, self._on_canvas_mouse_move)
        self._canvas.native.Bind(wx.EVT_LEAVE_WINDOW, self._on_canvas_leave)
        self._canvas.native.Bind(wx.EVT_RIGHT_DCLICK, self._on_right_dclick)

        wx.CallAfter(self._reposition_children)

    def set_poni_info(self, text: str, success: bool) -> None:
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
        self._reposition_children()
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
        self._rebuild_visuals()
        self.Refresh()

    def clear(self) -> None:
        self._xs = None
        self._ys = None
        self._x_label = "Pixel"
        self._zoom_x_min = self._zoom_x_max = self._zoom_y_min = self._zoom_y_max = None
        self._rebuild_visuals()
        self.Refresh()

    def _reposition_children(self) -> None:
        W, H = self.GetSize()
        pw = W - self._ML - self._MR
        ph = H - self._MT - self._MB
        self._canvas.native.SetPosition((self._ML, self._MT))
        self._canvas.native.SetSize((max(1, pw), max(1, ph)))
        self._canvas.native.Lower()
        x = W - LIVE_W - self._BTN_PAD
        y = self._MT + max(0, (H - self._MT - self._MB - LIVE_H) // 2)
        self._live_toggle.SetPosition(wx.Point(x, y))
        self._live_toggle.Raise()

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

    def _rebuild_visuals(self) -> None:
        ranges = self._data_ranges()
        has_data = ranges is not None and self._xs is not None and self._ys is not None

        self._curve_line.visible = has_data
        self._fill_mesh.visible = has_data
        self._canvas.native.Show(has_data)

        if not has_data:
            self._canvas.update()
            return

        xs, ys = self._xs, self._ys
        x_min, x_max, y_min, y_max = ranges

        pts = np.column_stack([xs, ys]).astype(np.float32)
        self._curve_line.set_data(pos=pts)

        n = len(xs)
        verts = np.empty((2 * n, 2), dtype=np.float32)
        verts[:n, 0] = xs
        verts[:n, 1] = ys
        verts[n:, 0] = xs
        verts[n:, 1] = y_min
        faces = np.empty((2 * (n - 1), 3), dtype=np.uint32)
        for i in range(n - 1):
            faces[2 * i] = [i, i + 1, n + i]
            faces[2 * i + 1] = [i + 1, n + i + 1, n + i]
        self._fill_mesh.set_data(vertices=verts, faces=faces, color=self._C_CURVE_FILL)

        self._sync_camera()

    def _sync_camera(self) -> None:
        ranges = self._data_ranges()
        if ranges is None:
            return
        x_min, x_max, y_min, y_max = ranges
        self._view.camera.set_range(x=(x_min, x_max), y=(y_min, y_max), margin=0)
        self._canvas.update()

    def _btn_rect_for(self, W: int, H: int) -> wx.Rect:
        return wx.Rect(W - self._BTN_W - self._BTN_PAD, H - self._BTN_H - self._BTN_PAD, self._BTN_W, self._BTN_H)

    def _unit_btn_at(self, pt: wx.Point) -> int:
        for i, r in enumerate(self._unit_btn_rects):
            if r.Contains(pt):
                return i
        return -1

    def _canvas_pt_to_panel(self, cx: int, cy: int) -> wx.Point:
        return wx.Point(cx + self._ML, cy + self._MT)

    def _panel_pt_in_plot(self, pt: wx.Point) -> bool:
        W, H = self.GetSize()
        return self._ML <= pt.x <= W - self._MR and self._MT <= pt.y <= H - self._MB

    def _panel_pt_to_data(self, pt: wx.Point) -> tuple[float, float] | None:
        ranges = self._data_ranges()
        if ranges is None:
            return None
        W, H = self.GetSize()
        pw = W - self._ML - self._MR
        ph = H - self._MT - self._MB
        if pw <= 0 or ph <= 0:
            return None
        x_min, x_max, y_min, y_max = ranges
        dx = x_min + (pt.x - self._ML) / pw * (x_max - x_min)
        dy = y_max - (pt.y - self._MT) / ph * (y_max - y_min)
        return dx, dy

    def _canvas_pt_to_data(self, cx: int, cy: int) -> tuple[float, float] | None:
        cw, ch = self._canvas.native.GetSize()
        ranges = self._data_ranges()
        if ranges is None:
            return None
        if cw <= 0 or ch <= 0:
            return None
        x_min, x_max, y_min, y_max = ranges
        dx = x_min + cx / cw * (x_max - x_min)
        dy = y_max - cy / ch * (y_max - y_min)
        return dx, dy

    def _update_sel_box(self) -> None:
        if self._drag_start is None or self._drag_end is None:
            self._sel_line.visible = False
            self._canvas.update()
            return
        ranges = self._data_ranges()
        if ranges is None:
            self._sel_line.visible = False
            self._canvas.update()
            return
        W, H = self.GetSize()
        pw = W - self._ML - self._MR
        ph = H - self._MT - self._MB
        x_min, x_max, y_min, y_max = ranges

        s, e = self._drag_start, self._drag_end
        cx0 = max(0, min(pw, s.x - self._ML))
        cx1 = max(0, min(pw, e.x - self._ML))
        cy0 = max(0, min(ph, s.y - self._MT))
        cy1 = max(0, min(ph, e.y - self._MT))
        sx = sorted([cx0, cx1])
        sy = sorted([cy0, cy1])
        if sx[1] - sx[0] <= 1 or sy[1] - sy[0] <= 1:
            self._sel_line.visible = False
            self._canvas.update()
            return
        dx0 = x_min + sx[0] / pw * (x_max - x_min)
        dx1 = x_min + sx[1] / pw * (x_max - x_min)
        dy0 = y_max - sy[1] / ph * (y_max - y_min)
        dy1 = y_max - sy[0] / ph * (y_max - y_min)
        pos = np.array([[dx0, dy0], [dx1, dy0], [dx1, dy1], [dx0, dy1], [dx0, dy0]], dtype=np.float32)
        self._sel_line.set_data(pos=pos)
        self._sel_line.visible = True
        self._canvas.update()

    def _on_mouse_wheel(self, event: wx.MouseEvent) -> None:
        if self._xs is None or len(self._xs) < 2:
            event.Skip()
            return
        W, H = self.GetSize()
        pw, ph = W - self._ML - self._MR, H - self._MT - self._MB
        raw_pt = event.GetPosition()
        obj = event.GetEventObject()
        if obj is self._canvas.native:
            pt = self._canvas_pt_to_panel(raw_pt.x, raw_pt.y)
        else:
            pt = raw_pt
        if not (self._ML <= pt.x <= self._ML + pw and self._MT <= pt.y <= self._MT + ph):
            event.Skip()
            return
        ranges = self._data_ranges()
        if ranges is None:
            event.Skip()
            return
        x_min, x_max, y_min, y_max = ranges
        factor = 1.15 ** (-event.GetWheelRotation() / 120.0)
        mx = x_min + (pt.x - self._ML) / pw * (x_max - x_min)
        my = y_max - (pt.y - self._MT) / ph * (y_max - y_min)
        self._zoom_x_min = mx + (x_min - mx) * factor
        self._zoom_x_max = mx + (x_max - mx) * factor
        self._zoom_y_min = my + (y_min - my) * factor
        self._zoom_y_max = my + (y_max - my) * factor
        self._sync_camera()
        self.Refresh()
        event.Skip()

    def _on_right_dclick(self, event: wx.MouseEvent) -> None:
        self._zoom_x_min = self._zoom_x_max = self._zoom_y_min = self._zoom_y_max = None
        if self._xs is not None:
            self._sync_camera()
        self.Refresh()
        event.Skip()

    def _on_mouse_move(self, event: wx.MouseEvent) -> None:
        self._handle_mouse_move(event.GetPosition(), event)

    def _on_canvas_mouse_move(self, event: wx.MouseEvent) -> None:
        pt = self._canvas_pt_to_panel(event.GetPosition().x, event.GetPosition().y)
        self._handle_mouse_move(pt, event)

    def _handle_mouse_move(self, pt: wx.Point, event: wx.MouseEvent) -> None:
        W, H = self.GetSize()

        if self._drag_start is not None:
            self._drag_end = pt
            self._update_sel_box()
            self.Refresh()
            event.Skip()
            return

        if self._panning and self._pan_last_pt is not None:
            ranges = self._data_ranges()
            if ranges is not None:
                pw = W - self._ML - self._MR
                ph = H - self._MT - self._MB
                x_min, x_max, y_min, y_max = ranges
                dx = (pt.x - self._pan_last_pt.x) / pw * (x_max - x_min)
                dy = (pt.y - self._pan_last_pt.y) / ph * (y_max - y_min)
                self._zoom_x_min = x_min - dx
                self._zoom_x_max = x_max - dx
                self._zoom_y_min = y_min + dy
                self._zoom_y_max = y_max + dy
                self._pan_last_pt = pt
                self._sync_camera()
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
        pw = W - self._ML - self._MR
        ph = H - self._MT - self._MB
        if ranges is not None and self._ML <= pt.x <= self._ML + pw and self._MT <= pt.y <= self._MT + ph:
            x_min, x_max, y_min, y_max = ranges
            new_x = x_min + (pt.x - self._ML) / pw * (x_max - x_min)
            new_y = y_max - (pt.y - self._MT) / ph * (y_max - y_min)
        else:
            new_x, new_y = None, None

        if new_x != self._hover_data_x or new_y != self._hover_data_y:
            self._hover_data_x = new_x
            self._hover_data_y = new_y
            self.Refresh()
        event.Skip()

    def _on_leave(self, event: wx.MouseEvent) -> None:
        self._clear_hover_state()
        event.Skip()

    def _on_canvas_leave(self, event: wx.MouseEvent) -> None:
        self._clear_hover_state()
        event.Skip()

    def _clear_hover_state(self) -> None:
        changed = (
            self._btn_hovered
            or self._btn_pressed
            or self._unit_btn_hovered != -1
            or self._hover_data_x is not None
        )
        self._btn_hovered = False
        self._btn_pressed = False
        self._unit_btn_hovered = -1
        self._unit_btn_pressed = -1
        self._hover_data_x = None
        self._hover_data_y = None
        self._panning = False
        self._pan_last_pt = None
        self._drag_start = None
        self._drag_end = None
        self._sel_line.visible = False
        self._canvas.update()
        if changed:
            self.Refresh()

    def _on_mouse_down(self, event: wx.MouseEvent) -> None:
        raw_pt = event.GetPosition()
        obj = event.GetEventObject()
        if obj is self._canvas.native:
            pt = self._canvas_pt_to_panel(raw_pt.x, raw_pt.y)
        else:
            pt = raw_pt
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
        if self._xs is not None and self._panel_pt_in_plot(pt):
            self._drag_start = self._drag_end = pt
        event.Skip()

    def _on_mouse_up(self, event: wx.MouseEvent) -> None:
        if self._panning:
            self._panning = False
            self._pan_last_pt = None
            event.Skip()
            return
        if self._drag_start is not None:
            raw_pt = event.GetPosition()
            obj = event.GetEventObject()
            if obj is self._canvas.native:
                end = self._canvas_pt_to_panel(raw_pt.x, raw_pt.y)
            else:
                end = raw_pt
            start = self._drag_start
            self._drag_start = self._drag_end = None
            self._sel_line.visible = False
            self._canvas.update()
            ranges = self._data_ranges()
            if ranges is not None:
                W, H = self.GetSize()
                pw = W - self._ML - self._MR
                ph = H - self._MT - self._MB
                x_min, x_max, y_min, y_max = ranges
                sx = sorted([start.x, end.x])
                sy = sorted([start.y, end.y])
                if sx[1] - sx[0] > 4 and sy[1] - sy[0] > 4:
                    self._zoom_x_min = x_min + (sx[0] - self._ML) / pw * (x_max - x_min)
                    self._zoom_x_max = x_min + (sx[1] - self._ML) / pw * (x_max - x_min)
                    self._zoom_y_min = y_max - (sy[1] - self._MT) / ph * (y_max - y_min)
                    self._zoom_y_max = y_max - (sy[0] - self._MT) / ph * (y_max - y_min)
                    self._sync_camera()
            self.Refresh()
            event.Skip()
            return

        raw_pt = event.GetPosition()
        obj = event.GetEventObject()
        if obj is self._canvas.native:
            pt = self._canvas_pt_to_panel(raw_pt.x, raw_pt.y)
        else:
            pt = raw_pt
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
        self._reposition_children()
        if self._xs is not None:
            self._sync_camera()
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
        gc.DrawRectangle(0, 0, ml, H)
        gc.DrawRectangle(ml, 0, pw, mt)
        gc.DrawRectangle(ml, mt + ph, pw, mb)
        gc.DrawRectangle(ml + pw, 0, mr, H)

        gc.SetPen(wx.Pen(self._BORDER, 1))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.StrokeLine(ml, mt + ph, ml + pw, mt + ph)
        gc.StrokeLine(ml, mt, ml, mt + ph)

        font_small = scaled_font(10, weight=wx.FONTWEIGHT_BOLD)
        ranges = self._data_ranges()

        if ranges is None:
            gc.SetBrush(wx.Brush(self._PLOT_BG))
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.DrawRectangle(ml, mt, pw, ph)
            gc.SetFont(scaled_font(13, weight=wx.FONTWEIGHT_BOLD), self._EMPTY_TEXT)
            msg = "Draw an ROI on the image to see the integration profile"
            tw, th = gc.GetTextExtent(msg)
            gc.DrawText(msg, ml + pw / 2 - tw / 2, mt + ph / 2 - th / 2)
        else:
            x_min, x_max, y_min, y_max = ranges

            gc.SetFont(font_small, self._TICK_LABEL)
            for i in range(5):
                t = i / 4
                y_val = y_min + t * (y_max - y_min)
                py = mt + ph - t * ph
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
                px = ml + t * pw
                gc.SetPen(wx.Pen(self._BORDER, 1))
                gc.StrokeLine(px, mt + ph, px, mt + ph + 3)
                lbl = f"{x_val:.4g}"
                tw, _ = gc.GetTextExtent(lbl)
                gc.DrawText(lbl, px - tw / 2, mt + ph + 5)

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

        self._draw_poni_overlay(gc, W, H)
        if self._calibrated:
            self._draw_unit_buttons(gc, W, H)

    def _draw_unit_buttons(self, gc: wx.GraphicsContext, W: int, H: int) -> None:
        total_w = len(_UNIT_KEYS) * _UNIT_BTN_W + (len(_UNIT_KEYS) - 1) * _UNIT_BTN_GAP
        start_x = W - self._MR - total_w
        self._unit_btn_rects = []
        font = scaled_font(9, weight=wx.FONTWEIGHT_BOLD)
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

        font = scaled_font(11, style=wx.FONTSTYLE_ITALIC)
        gc.SetFont(font, self._poni_colour)
        tw, th = gc.GetTextExtent(self._poni_text)
        gc.DrawText(self._poni_text, br.x - tw - self._BTN_PAD, br.y + (br.height - th) / 2)

        info_font = scaled_font(11, weight=wx.FONTWEIGHT_BOLD)
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
