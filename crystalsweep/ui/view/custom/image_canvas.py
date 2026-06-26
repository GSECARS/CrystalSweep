#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/image_canvas.py
# ----------------------------------------------------------------------------------
# Purpose:
# Hardware-accelerated image viewer widget using VisPy with pan/zoom, ROI
# selection, line ROI, and pixel info overlay.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import time
from typing import Callable

import numpy as np
import vispy
import wx

# Force vispy onto the PyOpenGL-backed bridge (`glplus`)
vispy.use(app="wx", gl="glplus")

from vispy import scene  # noqa: E402

from wxmplot.colors import lookup_colormap

__all__ = ["ImageCanvas"]

# Integer dtypes the GPU can sample natively via vispy's Image visual
_GPU_NATIVE_INT_DTYPES = (np.uint8, np.uint16, np.uint32, np.int8, np.int16, np.int32)

# Largest integer downsampling factor we'll ever apply to a live frame.
_MAX_LIVE_BIN = 4


BIN_METHOD_NONE = "none"
BIN_METHOD_STRIDE = "stride"
BIN_METHOD_MEAN = "mean"
BIN_METHODS = (BIN_METHOD_NONE, BIN_METHOD_STRIDE, BIN_METHOD_MEAN)


def _bin_stride(image: np.ndarray, n: int) -> np.ndarray:
    """Zero-copy stride decimation: `image[::n, ::n]`. Fastest possible reduction with slight anti-aliasing"""
    if n <= 1:
        return image
    return image[::n, ::n]


def _bin_mean(image: np.ndarray, n: int) -> np.ndarray:
    """Block mean binning: reshape to (h/n, n, w/n, n[, c]) then average. Full anti-aliasing downsampling."""
    if n <= 1:
        return image
    h, w = image.shape[:2]
    h2 = (h // n) * n
    w2 = (w // n) * n
    if h2 == 0 or w2 == 0:
        return image
    cropped = image[:h2, :w2]
    if cropped.ndim == 2:
        view = cropped.reshape(h2 // n, n, w2 // n, n)
        return view.mean(axis=(1, 3), dtype=np.float32).astype(image.dtype, copy=False)
    c = cropped.shape[2]
    view = cropped.reshape(h2 // n, n, w2 // n, n, c)
    return view.mean(axis=(1, 3), dtype=np.float32).astype(image.dtype, copy=False)


def _bin_for_display(image: np.ndarray, n: int, method: str) -> np.ndarray:
    """Downsample image by integer factor n using the selected method."""
    if n <= 1:
        return image
    if method == BIN_METHOD_MEAN:
        return _bin_mean(image, n)
    return _bin_stride(image, n)


class ImageCanvas(wx.Panel):
    """Hardware-accelerated image viewer using VisPy."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)

        self._canvas = scene.SceneCanvas(
            keys=None,
            parent=self,
            app="wx",
            vsync=True,
            config={"samples": 0, "double_buffer": True, "depth_size": 0, "stencil_size": 0},
        )
        self._view = self._canvas.central_widget.add_view()
        self._view.camera = scene.PanZoomCamera(aspect=1)
        self._view.camera.flip = (0, 1, 0)
        self._view.camera.interactive = False

        self._image_visual = scene.visuals.Image(
            np.zeros((512, 512), dtype=np.float32),
            parent=self._view.scene,
            cmap="grays",
            clim="auto",
        )

        self._raw_image: np.ndarray | None = None
        self._colormap = "grays"
        self._first_image = True
        self._auto_scale = True
        self._filter_gaps = False
        self._min_value = 0.0
        self._max_value = 255.0
        self._data_min = 0.0
        self._data_max = 255.0

        # Redraw only the latest pending frame
        self._pending_image: np.ndarray | None = None
        self._redraw_interval_ms: int = 16  # ~60 Hz cap
        self._redraw_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_redraw_tick, self._redraw_timer)

        # Live-display binning method with default of none so the GPU always receives the full-resolution frame
        self._bin_method: str = BIN_METHOD_NONE

        self._panning = False
        self._last_mouse_pos: tuple[int, int] | None = None

        self._roi_selecting = False
        self._roi_start: tuple[int, int] | None = None
        self._roi_img_coords: tuple[int, int, int, int] | None = None
        self._roi_dragging = False
        self._roi_drag_start_img: tuple[float, float] | None = None
        self._roi_drag_orig_coords: tuple[int, int, int, int] | None = None
        self._on_roi_changed: Callable | None = None
        self._on_roi_cleared: Callable | None = None

        self._line_start_img: tuple[float, float] | None = None
        self._line_end_img: tuple[float, float] | None = None
        self._line_coords: tuple[int, int, int, int] | None = None
        self._on_line_changed: Callable | None = None

        self._d_spacing_func: Callable | None = None
        self._two_theta_func: Callable | None = None
        self._overlay_motion_callback: Callable[[int, int], None] | None = None
        self._last_pixel_info_text: str = ""
        self._last_pixel_info_time: float = 0.0
        self._pixel_info_min_interval: float = 1.0 / 60.0

        self._roi_line = scene.visuals.Line(
            pos=np.array([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]], dtype=np.float32),
            color=(99 / 255, 179 / 255, 237 / 255, 180 / 255),
            width=2,
            method="gl",
            parent=self._view.scene,
        )
        self._roi_line.visible = False

        self._line_visual = scene.visuals.Line(
            pos=np.array([[0, 0], [1, 1]], dtype=np.float32),
            color=(237 / 255, 179 / 255, 99 / 255, 200 / 255),
            width=2,
            method="gl",
            parent=self._view.scene,
        )
        self._line_visual.visible = False

        self._line_start_marker = scene.visuals.Markers(parent=self._view.scene)
        self._line_start_marker.set_data(
            pos=np.array([[0, 0, 0]], dtype=np.float32),
            face_color=(0, 0, 0, 0),
            edge_color=(0, 0, 0, 0),
            size=1,
        )
        self._line_start_marker.visible = False

        self._pixel_info_text = scene.visuals.Text(
            text="",
            color=(72 / 255, 199 / 255, 116 / 255, 1.0),
            font_size=8,
            bold=True,
            anchor_x="left",
            anchor_y="top",
            parent=self._canvas.scene,
        )
        self._pixel_info_text.visible = False

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self._canvas.native, 1, wx.EXPAND)
        self.SetSizer(sizer)
        self._canvas.show()

        self._canvas.native.Bind(wx.EVT_MOUSEWHEEL, self._on_mouse_wheel)
        self._canvas.native.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)
        self._canvas.native.Bind(wx.EVT_LEFT_UP, self._on_left_up)
        self._canvas.native.Bind(wx.EVT_MOTION, self._on_mouse_move)
        self._canvas.native.Bind(wx.EVT_RIGHT_DCLICK, self._on_right_dclick)

    def set_colormap(self, colormap: str) -> None:
        self._colormap = colormap
        self._image_visual.cmap = lookup_colormap(colormap)
        self._canvas.update()

    def set_image(self, image: np.ndarray) -> None:
        """Stash image as the latest pending frame and use the redraw timer to push it to the GPU."""
        if image is None or image.size == 0:
            return
        self._pending_image = image
        if not self._redraw_timer.IsRunning():
            self._redraw_timer.StartOnce(self._redraw_interval_ms)

    def _on_redraw_tick(self, _: wx.TimerEvent) -> None:
        """Apply the latest pending frame and re-arm if more arrived."""
        image = self._pending_image
        self._pending_image = None
        if image is not None:
            self._apply_image(image)
        # If a fresh frame arrived while we were uploading, schedule another tick rather than blocking on it inline.
        if self._pending_image is not None:
            self._redraw_timer.StartOnce(self._redraw_interval_ms)

    def _apply_image(self, image: np.ndarray) -> None:
        is_rgb = image.ndim == 3 and image.shape[2] in (3, 4)
        if is_rgb and image.shape[2] == 4:
            image = image[:, :, :3]

        # Always cache the full-res frame for pixel-info, ROI sums, etc.
        if image.dtype.type in _GPU_NATIVE_INT_DTYPES:
            full_res = image if image.flags.c_contiguous else np.ascontiguousarray(image)
        else:
            # Float / unknown dtype: still need to sanitize NaNs/Infs once.
            full_res = np.nan_to_num(image.astype(np.float32, copy=False), nan=0.0, posinf=0.0, neginf=0.0, copy=False)
        self._raw_image = full_res

        bin_factor = self._pick_live_bin_factor(full_res.shape[:2])
        gpu_image = _bin_for_display(full_res, bin_factor, self._bin_method)
        if not gpu_image.flags.c_contiguous:
            gpu_image = np.ascontiguousarray(gpu_image)

        if self._auto_scale:
            self._min_value, self._max_value = self._compute_auto_clim(gpu_image)
            self._data_min, self._data_max = self._min_value, self._max_value
            self._image_visual.clim = (self._min_value, self._max_value)

        self._image_visual.set_data(gpu_image)
        if self._first_image:
            self.reset_view()
            self._first_image = False
        self._canvas.update()

    def _pick_live_bin_factor(self, image_hw: tuple[int, int]) -> int:
        """Pick the smallest integer bin factor (1..N) such that the binned image still has at least as many pixels as the canvas, on the limiting axis."""

        if self._bin_method == BIN_METHOD_NONE:
            return 1
        cw, ch = self._canvas.size
        if cw <= 0 or ch <= 0:
            return 1
        ih, iw = image_hw
        ratio = max(iw / cw, ih / ch)
        if ratio <= 1.0:
            return 1
        return min(_MAX_LIVE_BIN, int(ratio))

    def set_contrast(self, min_val: float, max_val: float) -> None:
        self._auto_scale = False
        self._min_value = min_val
        self._max_value = max_val
        self._image_visual.clim = (min_val, max_val)
        self._canvas.update()

    def set_auto_scale(self, enabled: bool) -> None:
        self._auto_scale = enabled
        if enabled and self._raw_image is not None:
            self._min_value, self._max_value = self._compute_auto_clim(self._raw_image)
            self._image_visual.clim = (self._min_value, self._max_value)
            self._canvas.update()

    def set_filter_gaps(self, enabled: bool) -> None:
        self._filter_gaps = enabled
        if self._auto_scale and self._raw_image is not None:
            self.set_auto_scale(True)

    def set_bin_method(self, method: str) -> None:
        """Switch the live downsampling method. Use one of ``BIN_METHODS``."""
        if method not in BIN_METHODS:
            raise ValueError(f"Unknown bin method: {method!r}; expected one of {BIN_METHODS}")
        self._bin_method = method
        if self._raw_image is not None:
            self._apply_image(self._raw_image)

    @property
    def bin_method(self) -> str:
        """Current live downsampling method."""
        return self._bin_method

    def get_data_range(self) -> tuple[float, float]:
        return self._data_min, self._data_max

    def get_contrast_range(self) -> tuple[float, float]:
        return self._min_value, self._max_value

    def reset_view(self) -> None:
        if self._raw_image is not None:
            h, w = self._raw_image.shape[:2]
            self._view.camera.set_range(x=(0, w), y=(0, h))
        self._roi_img_coords = None
        self._roi_line.visible = False
        self._hide_line_visual()
        self._canvas.update()

    def get_roi_coords(self) -> tuple[int, int, int, int] | None:
        return self._roi_img_coords

    def get_line_coords(self) -> tuple[int, int, int, int] | None:
        return self._line_coords

    def set_roi_changed_callback(self, callback: Callable) -> None:
        self._on_roi_changed = callback

    def set_roi_cleared_callback(self, callback: Callable) -> None:
        self._on_roi_cleared = callback

    def set_line_changed_callback(self, callback: Callable) -> None:
        self._on_line_changed = callback

    def set_d_spacing_func(self, func: Callable | None) -> None:
        self._d_spacing_func = func

    def set_two_theta_func(self, func: Callable | None) -> None:
        self._two_theta_func = func

    def set_overlay_motion_callback(self, callback: Callable[[int, int], None] | None) -> None:
        self._overlay_motion_callback = callback

    @property
    def native(self) -> wx.Window:
        return self._canvas.native

    # Stride so the auto-clim estimator never touches more than ~256k pixels.
    _AUTO_CLIM_SAMPLE_BUDGET = 256_000

    def _compute_auto_clim(self, img: np.ndarray) -> tuple[float, float]:
        """Cheap, sampled min/max (or 1-99 percentile) estimator."""
        flat = img.reshape(-1)
        step = max(1, flat.size // self._AUTO_CLIM_SAMPLE_BUDGET)
        sample = flat[::step]
        if self._filter_gaps:
            nonzero = sample[sample > 0]
            n = nonzero.size
            if n >= 3:
                k_lo = min(max(int(n * 0.01), 0), n - 1)
                k_hi = min(max(int(n * 0.99), k_lo + 1), n - 1)
                part = np.partition(nonzero, (k_lo, k_hi))
                return float(part[k_lo]), float(part[k_hi])
            if n > 0:
                return float(nonzero.min()), float(nonzero.max())
        return float(sample.min()), float(sample.max())

    def _screen_to_image(self, sx: int, sy: int) -> tuple[float, float] | None:
        if self._raw_image is None:
            return None
        tr = self._image_visual.transforms.get_transform("canvas", "visual")
        img_pos = tr.map((sx, sy))
        return float(img_pos[0]), float(img_pos[1])

    def _is_inside_roi(self, ix: float, iy: float) -> bool:
        if self._roi_img_coords is None:
            return False
        x1, y1, x2, y2 = self._roi_img_coords
        return x1 <= ix <= x2 and y1 <= iy <= y2

    def _set_roi_visual(self, x1: float, y1: float, x2: float, y2: float) -> None:
        pts = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2], [x1, y1]], dtype=np.float32)
        self._roi_line.set_data(pos=pts)
        self._roi_line.visible = True
        self._canvas.update()

    def _set_line_visual(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self._line_visual.set_data(pos=np.array([[x1, y1], [x2, y2]], dtype=np.float32))
        self._line_visual.visible = True
        self._canvas.update()

    def _set_line_start_marker(self, x: float, y: float) -> None:
        self._line_start_marker.set_data(
            pos=np.array([[x, y, 0]], dtype=np.float32),
            face_color=(237 / 255, 179 / 255, 99 / 255, 1.0),
            edge_color=(237 / 255, 179 / 255, 99 / 255, 1.0),
            size=8,
        )
        self._line_start_marker.visible = True
        self._canvas.update()

    def _hide_line_visual(self) -> None:
        self._line_visual.visible = False
        self._line_start_marker.visible = False
        self._line_start_img = None
        self._line_end_img = None
        self._line_coords = None

    def _update_pixel_info(self, sx: int, sy: int) -> None:
        now = time.perf_counter()
        if now - self._last_pixel_info_time < self._pixel_info_min_interval:
            return
        self._last_pixel_info_time = now
        img_pos = self._screen_to_image(sx, sy)
        if img_pos is None or self._raw_image is None:
            if self._pixel_info_text.visible:
                self._pixel_info_text.visible = False
                self._last_pixel_info_text = ""
                self._canvas.update()
            return
        ix, iy = int(img_pos[0]), int(img_pos[1])
        h, w = self._raw_image.shape[:2]
        if 0 <= ix < w and 0 <= iy < h:
            pixel = self._raw_image[iy, ix]
            _, canvas_h = self._canvas.size
            intensity = float(np.mean(pixel)) if self._raw_image.ndim == 3 else float(pixel)
            text = f"x: {ix}  y: {iy}  I: {intensity:.4g}"
            if self._d_spacing_func is not None:
                d = self._d_spacing_func(ix, iy)
                if d is not None:
                    text += f"  d: {d:.4g} \u212b"
            if self._two_theta_func is not None:
                tth = self._two_theta_func(ix, iy)
                if tth is not None:
                    text += f"  2\u03b8: {tth:.4g}\u00b0"
            if text != self._last_pixel_info_text:
                self._pixel_info_text.text = text
                self._pixel_info_text.pos = (8, canvas_h - 20)
                self._pixel_info_text.visible = True
                self._last_pixel_info_text = text
                self._canvas.update()
        elif self._pixel_info_text.visible:
            self._pixel_info_text.visible = False
            self._last_pixel_info_text = ""
            self._canvas.update()

    def _on_mouse_wheel(self, event: wx.MouseEvent) -> None:
        if event.GetWheelRotation() == 0:
            return
        zoom = 1.1 ** (-event.GetWheelRotation() / 120.0)
        before = self._screen_to_image(event.GetX(), event.GetY())
        self._view.camera.zoom(zoom)
        if before is not None:
            after = self._screen_to_image(event.GetX(), event.GetY())
            if after is not None:
                self._view.camera.pan((before[0] - after[0], before[1] - after[1]))
        self._canvas.update()

    def _on_left_down(self, event: wx.MouseEvent) -> None:
        if event.ShiftDown():
            self._panning = True
            self._last_mouse_pos = (event.GetX(), event.GetY())
        elif event.AltDown():
            img_pos = self._screen_to_image(event.GetX(), event.GetY())
            if img_pos is not None:
                if self._line_start_img is None:
                    self._line_start_img = img_pos
                    self._roi_line.visible = False
                    self._roi_img_coords = None
                    self._set_line_start_marker(*img_pos)
                else:
                    x1, y1 = int(round(self._line_start_img[0])), int(round(self._line_start_img[1]))
                    x2, y2 = int(round(img_pos[0])), int(round(img_pos[1]))
                    self._line_start_img = None
                    self._line_end_img = img_pos
                    self._line_coords = (x1, y1, x2, y2)
                    self._line_start_marker.visible = False
                    self._set_line_visual(x1, y1, x2, y2)
                    if self._on_line_changed:
                        self._on_line_changed(x1, y1, x2, y2)
        else:
            self._line_start_img = None
            self._line_end_img = None
            self._line_coords = None
            self._hide_line_visual()
            img_pos = self._screen_to_image(event.GetX(), event.GetY())
            if img_pos is not None and self._is_inside_roi(*img_pos):
                self._roi_dragging = True
                self._roi_drag_start_img = img_pos
                self._roi_drag_orig_coords = self._roi_img_coords
            else:
                self._roi_selecting = True
                self._roi_start = (event.GetX(), event.GetY())
                self._roi_img_coords = None
                self._roi_line.visible = False
                self._canvas.update()
        event.Skip()

    def _on_left_up(self, event: wx.MouseEvent) -> None:
        if self._roi_dragging:
            self._roi_dragging = False
            self._roi_drag_start_img = None
            self._roi_drag_orig_coords = None
            if self._on_roi_changed and self._roi_img_coords is not None:
                self._on_roi_changed(*self._roi_img_coords)
            self._canvas.update()
            event.Skip()
            return

        if self._roi_selecting and self._roi_start is not None:
            start_img = self._screen_to_image(*self._roi_start)
            end_img = self._screen_to_image(event.GetX(), event.GetY())
            if start_img is not None and end_img is not None:
                x1 = int(min(start_img[0], end_img[0]))
                y1 = int(min(start_img[1], end_img[1]))
                x2 = int(max(start_img[0], end_img[0]))
                y2 = int(max(start_img[1], end_img[1]))
                if x2 > x1 and y2 > y1:
                    self._roi_img_coords = (x1, y1, x2, y2)
                    self._set_roi_visual(x1, y1, x2, y2)
                    if self._on_roi_changed:
                        self._on_roi_changed(x1, y1, x2, y2)
                else:
                    self._roi_line.visible = False
            else:
                self._roi_line.visible = False

        self._roi_selecting = False
        self._roi_start = None
        self._panning = False
        self._last_mouse_pos = None
        self._canvas.update()
        event.Skip()

    def _on_mouse_move(self, event: wx.MouseEvent) -> None:
        if self._panning and self._last_mouse_pos:
            dx = event.GetX() - self._last_mouse_pos[0]
            dy = event.GetY() - self._last_mouse_pos[1]
            self._view.camera.pan((-dx, -dy))
            self._canvas.update()
            self._last_mouse_pos = (event.GetX(), event.GetY())
        elif self._roi_dragging and self._roi_drag_start_img is not None:
            cur = self._screen_to_image(event.GetX(), event.GetY())
            if cur is not None and self._roi_drag_orig_coords is not None:
                dx = cur[0] - self._roi_drag_start_img[0]
                dy = cur[1] - self._roi_drag_start_img[1]
                ox1, oy1, ox2, oy2 = self._roi_drag_orig_coords
                if self._raw_image is not None:
                    h, w = self._raw_image.shape[:2]
                    rw, rh = ox2 - ox1, oy2 - oy1
                    nx1 = max(0, min(int(ox1 + dx), w - rw))
                    ny1 = max(0, min(int(oy1 + dy), h - rh))
                    nx2, ny2 = nx1 + rw, ny1 + rh
                else:
                    nx1, ny1 = int(ox1 + dx), int(oy1 + dy)
                    nx2, ny2 = int(ox2 + dx), int(oy2 + dy)
                self._roi_img_coords = (nx1, ny1, nx2, ny2)
                self._set_roi_visual(nx1, ny1, nx2, ny2)
        elif self._roi_selecting and self._roi_start is not None:
            start_img = self._screen_to_image(*self._roi_start)
            end_img = self._screen_to_image(event.GetX(), event.GetY())
            if start_img is not None and end_img is not None:
                x1 = min(start_img[0], end_img[0])
                y1 = min(start_img[1], end_img[1])
                x2 = max(start_img[0], end_img[0])
                y2 = max(start_img[1], end_img[1])
                if x2 > x1 and y2 > y1:
                    self._set_roi_visual(x1, y1, x2, y2)
        elif self._line_start_img is not None and event.AltDown():
            img_pos = self._screen_to_image(event.GetX(), event.GetY())
            if img_pos is not None:
                self._set_line_visual(self._line_start_img[0], self._line_start_img[1], img_pos[0], img_pos[1])
        else:
            img_pos = self._screen_to_image(event.GetX(), event.GetY())
            cursor = wx.CURSOR_SIZING if (img_pos is not None and self._is_inside_roi(*img_pos)) else wx.CURSOR_DEFAULT
            self._canvas.native.SetCursor(wx.Cursor(cursor))

        self._update_pixel_info(event.GetX(), event.GetY())
        if self._overlay_motion_callback is not None:
            screen_pt = self._canvas.native.ClientToScreen(wx.Point(event.GetX(), event.GetY()))
            panel_pt = self.GetParent().ScreenToClient(screen_pt)
            self._overlay_motion_callback(panel_pt.x, panel_pt.y)
        event.Skip()

    def _on_right_dclick(self, event: wx.MouseEvent) -> None:
        if self._raw_image is not None:
            h, w = self._raw_image.shape[:2]
            self._view.camera.set_range(x=(0, w), y=(0, h))
        self._roi_img_coords = None
        self._roi_line.visible = False
        self._hide_line_visual()
        self._canvas.update()
        if self._on_roi_cleared:
            self._on_roi_cleared()
        event.Skip()
