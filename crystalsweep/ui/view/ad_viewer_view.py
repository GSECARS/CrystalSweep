#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/ad_viewer_view.py
# ----------------------------------------------------------------------------------
# Purpose:
# AD Viewer panel: wires the image canvas, histogram, and integration plot into
# a single panel and exposes a clean bind/update API for the controller.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import sys
from pathlib import Path
from typing import Callable, Protocol

import numpy as np
import wx

from crystalsweep.ui.view.custom import IconButton, ImageCanvas, ImageSettingsPopup, IntegrationPlot, IntensityHistogramWidget, LiveToggle
from crystalsweep.ui.view.custom.icons import draw_chevron_left, draw_chevron_right, draw_cog, draw_folder
from crystalsweep.ui.view.custom.theme import BG_SURFACE, PONI_LOADED, PONI_MISSING
from crystalsweep.ui.view.custom.widgets import DarkTextCtrl

__all__ = ["ADViewerView"]

type RoiCoords = tuple[int, int, int, int]
type IntegrationSettings = tuple[int, str]

_DEFAULT_COLORMAP: str = "grays"
_DEFAULT_NPT: int = 1_000
_INTEGRATION_UNITS: list[str] = ["2th_deg", "d_A", "q_A^-1"]


class _FileLoadCallback(Protocol):
    def __call__(self, filepath: Path) -> None: ...


class _RoiChangedCallback(Protocol):
    def __call__(self, x1: int | None, y1: int | None, x2: int | None, y2: int | None) -> None: ...


class _FrameNavCallback(Protocol):
    def __call__(self, index: int) -> None: ...


class ADViewerView(wx.Panel):
    """AD Viewer panel – renders detector images and exposes a clean API for the controller."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)

        self._current_frame: np.ndarray | None = None
        self._live_updates: bool = True
        self._auto_scale: bool = True
        self._filter_gaps: bool = True
        self._current_colormap: str = _DEFAULT_COLORMAP
        self._current_npt: int = _DEFAULT_NPT
        self._current_unit: str = _INTEGRATION_UNITS[0]
        self._poni_label_text: str = "No calibration loaded"
        self._poni_label_colour: wx.Colour = PONI_MISSING

        self._load_file_cb: _FileLoadCallback | None = None
        self._load_poni_cb: _FileLoadCallback | None = None
        self._integration_changed_cb: Callable[[], None] | None = None
        self._roi_live_integration_cb: Callable[[bool], None] | None = None
        self._line_changed_cb: Callable | None = None
        self._frame_nav_cb: _FrameNavCallback | None = None
        self._current_frame_index: int = 0
        self._total_frames: int = 0

        self._build_layout()

    def _build_layout(self) -> None:
        self._intensity_histogram = IntensityHistogramWidget(self, on_levels_changed=self._on_histogram_levels_changed)
        self._integration_plot = IntegrationPlot(self)

        self.SetBackgroundColour(BG_SURFACE)

        self._canvas_panel = wx.Panel(self)
        self._canvas_panel.SetBackgroundColour(BG_SURFACE)
        self._image_canvas = ImageCanvas(self._canvas_panel)

        # Parent overlay buttons to the VisPy native widget so they render above it on Windows
        overlay_parent = self._image_canvas.native

        self._load_file_btn = IconButton(overlay_parent, draw_folder, tooltip="Load image file")
        self._load_file_btn.Bind(wx.EVT_BUTTON, lambda _: self._trigger_load_file())

        self._prev_btn = IconButton(overlay_parent, draw_chevron_left, tooltip="Previous frame")
        self._prev_btn.Bind(wx.EVT_BUTTON, self._on_prev_frame)
        self._prev_btn.Hide()

        self._next_btn = IconButton(overlay_parent, draw_chevron_right, tooltip="Next frame")
        self._next_btn.Bind(wx.EVT_BUTTON, self._on_next_frame)
        self._next_btn.Hide()

        self._frame_ctrl = DarkTextCtrl(overlay_parent, value="0")
        self._frame_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_frame_ctrl_enter)
        self._frame_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_frame_ctrl_enter)
        self._frame_ctrl.Hide()

        self._settings_btn = IconButton(overlay_parent, draw_cog, tooltip="Image settings")
        self._settings_btn.Bind(wx.EVT_BUTTON, self._on_settings_btn)

        self._live_toggle = LiveToggle(overlay_parent, live=self._live_updates)
        self._live_toggle.set_toggled_callback(self._apply_live_updates)

        canvas_sizer = wx.BoxSizer(wx.VERTICAL)
        canvas_sizer.Add(self._image_canvas, 1, wx.EXPAND)
        self._canvas_panel.SetSizer(canvas_sizer)
        self._canvas_panel.SetMinSize((-1, 200))

        # Track size changes on the native VisPy widget so overlays reposition whenever the canvas resizes
        overlay_parent.Bind(wx.EVT_SIZE, self._on_overlay_parent_size)
        overlay_parent.Bind(wx.EVT_MOTION, self._on_canvas_panel_motion)
        overlay_parent.Bind(wx.EVT_LEAVE_WINDOW, self._on_canvas_panel_leave)

        inner = wx.BoxSizer(wx.VERTICAL)
        inner.Add(self._intensity_histogram, 0, wx.EXPAND)
        inner.Add(self._canvas_panel, 3, wx.EXPAND)
        inner.Add(self._integration_plot, 1, wx.EXPAND)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(inner, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(sizer)

        self._image_canvas.set_roi_cleared_callback(self._on_roi_or_line_cleared)
        self._integration_plot.set_load_poni_callback(self._trigger_load_poni)
        self._integration_plot.set_unit_changed_callback(self._on_unit_changed)
        self._integration_plot.set_live_integration_callback(self._on_roi_live_integration_toggled)
        self._image_canvas.set_overlay_motion_callback(self._on_canvas_panel_motion_xy)
        self._image_canvas.set_filter_gaps(self._filter_gaps)

        self._reposition_overlay_buttons()

    def bind_load_file(self, callback: _FileLoadCallback) -> None:
        self._load_file_cb = callback

    def bind_load_poni(self, callback: _FileLoadCallback) -> None:
        self._load_poni_cb = callback

    def bind_integration_settings_changed(self, callback: Callable[[], None]) -> None:
        self._integration_changed_cb = callback

    def bind_roi_changed(self, callback: _RoiChangedCallback) -> None:
        self._image_canvas.set_roi_changed_callback(callback)

    def bind_line_changed(self, callback: Callable) -> None:
        self._line_changed_cb = callback
        self._image_canvas.set_line_changed_callback(callback)

    def bind_frame_navigation(self, callback: _FrameNavCallback) -> None:
        self._frame_nav_cb = callback

    def bind_roi_live_integration(self, callback: Callable[[bool], None]) -> None:
        self._roi_live_integration_cb = callback
        self._integration_plot.set_live_integration_callback(callback)

    @property
    def is_roi_live_integration(self) -> bool:
        return self._integration_plot.is_live_integration

    @property
    def current_frame(self) -> np.ndarray | None:
        return self._current_frame

    def update_frame(self, frame: np.ndarray) -> None:
        if frame is None or frame.size == 0 or not self._live_updates:
            return
        self.display_frame(frame)

    def display_frame(self, frame: np.ndarray) -> None:
        self._current_frame = frame
        self._image_canvas.set_image(frame)
        self._intensity_histogram.set_data(frame, auto_scale=False)
        lo, hi = self._image_canvas.get_contrast_range()
        self._intensity_histogram.set_levels(lo, hi)

    def set_live_updates(self, enabled: bool) -> None:
        self._live_updates = enabled
        self._live_toggle.set_live(enabled)

    def set_poni_label(self, text: str, *, success: bool = True) -> None:
        self._poni_label_text = text
        self._poni_label_colour = PONI_LOADED if success else PONI_MISSING
        self._integration_plot.set_poni_info(text, success=success)
        self._integration_plot.set_calibrated(success)

    def set_d_spacing_func(self, func: Callable | None) -> None:
        self._image_canvas.set_d_spacing_func(func)

    def set_two_theta_func(self, func: Callable | None) -> None:
        self._image_canvas.set_two_theta_func(func)

    def get_integration_settings(self) -> IntegrationSettings:
        return self._current_npt, self._current_unit

    def get_roi_coords(self) -> RoiCoords | None:
        return self._image_canvas.get_roi_coords()

    def get_line_coords(self) -> RoiCoords | None:
        return self._image_canvas.get_line_coords()

    def set_integration_data(self, xs: np.ndarray, ys: np.ndarray, x_label: str) -> None:
        self._integration_plot.set_data(xs, ys, x_label=x_label)

    def clear_integration_plot(self) -> None:
        self._integration_plot.clear()

    def set_frame_navigation(self, total_frames: int, current_index: int = 0) -> None:
        self._total_frames = total_frames
        self._current_frame_index = current_index
        visible = total_frames > 1 and not self._live_updates
        self._prev_btn.Show(visible)
        self._next_btn.Show(visible)
        self._frame_ctrl.Show(visible)
        if visible:
            self._frame_ctrl.SetValue(str(current_index))
        self._reposition_overlay_buttons()

    def _on_roi_or_line_cleared(self) -> None:
        self._integration_plot.clear()

    def _on_unit_changed(self, unit: str) -> None:
        self._current_unit = unit
        self._integration_plot.set_active_unit(unit)
        if self._integration_changed_cb is not None:
            self._integration_changed_cb()

    def _on_roi_live_integration_toggled(self, enabled: bool) -> None:
        if self._roi_live_integration_cb is not None:
            self._roi_live_integration_cb(enabled)

    def _on_histogram_levels_changed(self, min_val: float, max_val: float) -> None:
        self._auto_scale = False
        self._image_canvas.set_contrast(min_val, max_val)

    def _on_overlay_parent_size(self, event: wx.SizeEvent) -> None:
        event.Skip()
        self._reposition_overlay_buttons()

    def _reposition_overlay_buttons(self) -> None:
        # Coordinates are now relative to the native VisPy widget (overlay parent)
        panel_w, _ = self._image_canvas.native.GetClientSize()
        cog_sz = self._settings_btn.GetBestSize()
        x = panel_w - cog_sz.width - 4
        self._settings_btn.SetPosition(wx.Point(x, 4))
        self._settings_btn.Raise()

        lw, _lh = self._live_toggle.GetSize()
        self._live_toggle.SetPosition(wx.Point(x + (cog_sz.width - lw) // 2, 4 + cog_sz.height + 4))
        self._live_toggle.Raise()

        load_sz = self._load_file_btn.GetBestSize()
        x -= load_sz.width + 4
        self._load_file_btn.SetPosition(wx.Point(x, 4))
        self._load_file_btn.Raise()

        if self._total_frames > 1:
            next_sz = self._next_btn.GetBestSize()
            x -= next_sz.width + 2
            self._next_btn.SetPosition(wx.Point(x, 4))
            self._next_btn.Raise()

            ctrl_w, ctrl_h = self._frame_ctrl.GetSize()
            x -= ctrl_w + 2
            self._frame_ctrl.SetPosition(wx.Point(x, 4 + (next_sz.height - ctrl_h) // 2))
            self._frame_ctrl.Raise()

            prev_sz = self._prev_btn.GetBestSize()
            x -= prev_sz.width + 2
            self._prev_btn.SetPosition(wx.Point(x, 4))
            self._prev_btn.Raise()

    def _overlay_buttons(self) -> list:
        btns = [self._load_file_btn, self._settings_btn, self._live_toggle]
        if self._total_frames > 1:
            btns += [self._prev_btn, self._next_btn]
        return btns

    def _update_overlay_hover(self, pt: wx.Point) -> None:
        for btn in self._overlay_buttons():
            if not btn.IsShown():
                continue
            pos = btn.GetPosition()
            sz = btn.GetSize()
            btn.set_hovered(wx.Rect(pos.x, pos.y, sz.width, sz.height).Contains(pt))

    def _on_canvas_panel_motion(self, event: wx.MouseEvent) -> None:
        self._update_overlay_hover(event.GetPosition())
        event.Skip()

    def _on_canvas_panel_motion_xy(self, x: int, y: int) -> None:
        self._update_overlay_hover(wx.Point(x, y))

    def _on_canvas_panel_leave(self, event: wx.MouseEvent) -> None:
        pos = wx.GetMousePosition()
        for btn in self._overlay_buttons():
            if not btn.GetScreenRect().Contains(pos):
                btn.set_hovered(False)
        event.Skip()

    def _on_settings_btn(self, event: wx.CommandEvent) -> None:
        lo, hi = self._image_canvas.get_contrast_range()
        popup = ImageSettingsPopup(
            self,
            colormap=self._current_colormap,
            auto_scale=self._auto_scale,
            filter_gaps=self._filter_gaps,
            contrast_min=lo,
            contrast_max=hi,
            on_colormap_changed=self._apply_colormap,
            on_auto_scale_changed=self._apply_auto_scale,
            on_filter_gaps_changed=self._apply_filter_gaps,
            on_levels_changed=self._on_histogram_levels_changed,
            on_reset_view=self._apply_reset_view,
        )
        btn_sz = self._settings_btn.GetSize()
        popup_w, _ = popup.GetSize()
        pos = self._settings_btn.ClientToScreen(wx.Point(btn_sz.width - popup_w, btn_sz.height))
        popup.Position(pos, (0, 0))
        popup.Popup()

    def _on_prev_frame(self, event: wx.CommandEvent) -> None:
        if self._current_frame_index > 0:
            self._navigate_to(self._current_frame_index - 1)

    def _on_next_frame(self, event: wx.CommandEvent) -> None:
        if self._current_frame_index < self._total_frames - 1:
            self._navigate_to(self._current_frame_index + 1)

    def _on_frame_ctrl_enter(self, event: wx.Event) -> None:
        try:
            index = max(0, min(int(self._frame_ctrl.GetValue()), self._total_frames - 1))
        except ValueError:
            self._frame_ctrl.SetValue(str(self._current_frame_index))
            event.Skip()
            return
        self._navigate_to(index)
        event.Skip()

    def _navigate_to(self, index: int) -> None:
        self._current_frame_index = index
        self._frame_ctrl.SetValue(str(index))
        if self._frame_nav_cb is not None:
            self._frame_nav_cb(index)

    def _apply_colormap(self, colormap: str) -> None:
        self._current_colormap = colormap
        self._image_canvas.set_colormap(colormap)
        self._intensity_histogram.set_colormap(colormap)

    def _apply_auto_scale(self, enabled: bool) -> None:
        self._auto_scale = enabled
        self._image_canvas.set_auto_scale(enabled)
        if self._current_frame is not None:
            self._intensity_histogram.set_data(self._current_frame, auto_scale=False)
            lo, hi = self._image_canvas.get_contrast_range()
            self._intensity_histogram.set_levels(lo, hi)

    def _apply_filter_gaps(self, enabled: bool) -> None:
        self._filter_gaps = enabled
        self._image_canvas.set_filter_gaps(enabled)
        if self._current_frame is not None:
            self._intensity_histogram.set_data(self._current_frame, auto_scale=False)
            lo, hi = self._image_canvas.get_contrast_range()
            self._intensity_histogram.set_levels(lo, hi)

    def _apply_live_updates(self, enabled: bool) -> None:
        self._live_updates = enabled
        if enabled:
            self._prev_btn.Hide()
            self._next_btn.Hide()
            self._frame_ctrl.Hide()
            self._reposition_overlay_buttons()

    def _apply_reset_view(self) -> None:
        self._image_canvas.reset_view()
        self._integration_plot.clear()

    def _trigger_load_file(self) -> None:
        with wx.FileDialog(
            self,
            "Open image file",
            wildcard="HDF5 files (*.h5;*.hdf5)|*.h5;*.hdf5" + ("|All files (*.*)|*.*" if sys.platform == "win32" else ""),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            filepath = Path(dlg.GetPath())
        if self._load_file_cb is not None:
            self._load_file_cb(filepath)

    def _trigger_load_poni(self) -> None:
        with wx.FileDialog(
            self,
            "Open .poni calibration file",
            wildcard="PONI files (*.poni)|*.poni" + ("|All files (*.*)|*.*" if sys.platform == "win32" else ""),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            poni_path = Path(dlg.GetPath())
        if self._load_poni_cb is not None:
            self._load_poni_cb(poni_path)
