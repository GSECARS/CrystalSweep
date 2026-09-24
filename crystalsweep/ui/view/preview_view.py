#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/preview_view.py
# ----------------------------------------------------------------------------------
# Purpose:
# Preview tab inside the Single-Crystal Centering Tools section.
# Provides a Start/Stop preview button, step-size input, live motor jog rows,
# and a combined Original/Current/Best positions table.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from typing import Callable

import wx
from wxutils import FlatButton, FlatIconButton, FlatTextCtrl, StatusField, draw_chevron_left, draw_chevron_right

from crystalsweep.ui.view.custom.theme import app_theme
from crystalsweep.ui.view.custom.widgets import FlatLabel, FlatPanel
from crystalsweep.utils import MotorPositionValidator

__all__ = ["CenteringMotorSpec", "PreviewView"]


class CenteringMotorSpec:
    """Lightweight description of a centering-enabled motor for PreviewView."""

    __slots__ = ("shorthand", "description", "pv", "precision")

    def __init__(self, shorthand: str, description: str, pv: str, precision: int) -> None:
        self.shorthand = shorthand
        self.description = description
        self.pv = pv
        self.precision = precision


def _stop_scheme():
    return (app_theme.red, app_theme.bright_red, app_theme.red, app_theme.foreground, app_theme.foreground)


_STEP_PRECISION = 4
_UM_PER_MM = 1000.0

_P_ROW_H = 26
_P_HEADER_H = 30
_P_MOTOR_W = 108
_P_VAL_W = 90
_P_GO_W = 32
_P_GO_H = 18
_P_BORDER = wx.Colour(50, 50, 56)
_P_CELL_PAD = 6

_COL_ORIG = 0
_COL_CURR = 1
_COL_BEST = 2


class _CenteringRow(FlatPanel):
    """One row in the centering motors column: [label] [<] [live RBV] [>]."""

    _ARROW_SIZE = 20
    _ROW_H = 28
    _VALUE_W = 90

    def __init__(self, parent: wx.Window, spec: CenteringMotorSpec) -> None:
        super().__init__(parent)
        self.SetMinSize((-1, self._ROW_H))
        self.spec = spec
        self._precision = max(0, int(spec.precision))

        label_text = spec.description or spec.shorthand or spec.pv
        self._label = FlatLabel(self, label=label_text)
        self._label.SetFont(app_theme.scaled_font(12, weight=wx.FONTWEIGHT_BOLD))

        self._left_btn = FlatIconButton(self, draw_chevron_left, icon_size=self._ARROW_SIZE, tooltip=f"Move {label_text} - step")
        self._left_btn.Bind(wx.EVT_BUTTON, lambda _e: self._fire(self._on_left_cb))

        self._right_btn = FlatIconButton(self, draw_chevron_right, icon_size=self._ARROW_SIZE, tooltip=f"Move {label_text} + step")
        self._right_btn.Bind(wx.EVT_BUTTON, lambda _e: self._fire(self._on_right_cb))

        self._value_box = StatusField(self, height=self._ROW_H)
        self._value_box.SetMinSize((self._VALUE_W, self._ROW_H))
        self._value_box.SetMaxSize((self._VALUE_W, self._ROW_H))
        self._value_box.SetValue("—")

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self._label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        sizer.AddStretchSpacer(1)
        sizer.Add(self._left_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self._value_box, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 6)
        sizer.Add(self._right_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        self.SetSizer(sizer)

        self._on_left_cb: Callable[[CenteringMotorSpec], None] | None = None
        self._on_right_cb: Callable[[CenteringMotorSpec], None] | None = None

    def bind_left(self, callback: Callable[[CenteringMotorSpec], None]) -> None:
        self._on_left_cb = callback

    def bind_right(self, callback: Callable[[CenteringMotorSpec], None]) -> None:
        self._on_right_cb = callback

    def set_enabled(self, enabled: bool) -> None:
        self._left_btn.Enable(enabled)
        self._right_btn.Enable(enabled)

    def set_value(self, value: float | None) -> None:
        if value is None:
            text = "—"
        else:
            try:
                text = f"{float(value):.{self._precision}f}"
            except (TypeError, ValueError):
                text = "—"
        self._value_box.SetValue(text)

    def _fire(self, cb: Callable[[CenteringMotorSpec], None] | None) -> None:
        if cb is not None:
            cb(self.spec)


class _PosTableRow(wx.Panel):
    """One painted row in the positions table: motor label + Original/Current/Best values."""

    def __init__(
        self,
        parent: wx.Window,
        label: str,
        precision: int,
        col_widths: list[int],
        alt_bg: bool,
        is_max: bool = False,
    ) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self.SetMinSize((-1, _P_ROW_H))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self._label = label
        self._precision = max(0, int(precision))
        self._col_widths = col_widths
        self._is_max = is_max
        self._alt_bg = alt_bg
        self._values: list[float | None] = [None, None, None]
        self._curr_colour: wx.Colour = app_theme.foreground
        self._best_colour: wx.Colour = app_theme.foreground
        self.Bind(wx.EVT_PAINT, self._on_paint)

    def set_value(self, col: int, value: float | None) -> None:
        self._values[col] = value
        self.Refresh()

    def set_curr_colour(self, colour: wx.Colour) -> None:
        self._curr_colour = colour
        self.Refresh()

    def set_best_colour(self, colour: wx.Colour) -> None:
        self._best_colour = colour
        self.Refresh()

    def update_col_widths(self, col_widths: list[int]) -> None:
        self._col_widths = col_widths
        self.Refresh()

    def _fmt(self, col: int) -> str:
        value = self._values[col]
        if value is None:
            return "—"
        try:
            v = float(value)
            return f"{v:.4g}" if self._is_max else f"{v:.{self._precision}f}"
        except (TypeError, ValueError):
            return "—"

    def _on_paint(self, _: wx.PaintEvent) -> None:
        w, h = self.GetClientSize()
        if w <= 0 or h <= 0:
            return
        try:
            dc = wx.AutoBufferedPaintDC(self)
            gc = wx.GraphicsContext.Create(dc)
        except Exception:
            return
        if gc is None:
            return

        bg = app_theme.black if self._alt_bg else app_theme.background
        gc.SetBrush(wx.Brush(bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)

        weight = wx.FONTWEIGHT_BOLD if self._is_max else wx.FONTWEIGHT_NORMAL
        font = app_theme.scaled_font(12, weight=weight)

        texts = [self._label, self._fmt(_COL_ORIG), self._fmt(_COL_CURR), self._fmt(_COL_BEST)]
        colours = [app_theme.foreground, app_theme.foreground, self._curr_colour, self._best_colour]

        x = 0
        for i, (text, cw, colour) in enumerate(zip(texts, self._col_widths, colours)):
            gc.SetFont(font, colour)
            tw, th = gc.GetTextExtent(text)
            text_x = x + _P_CELL_PAD if i == 0 else x + (cw - tw) / 2
            gc.DrawText(text, text_x, (h - th) / 2)
            x += cw

        gc.SetPen(wx.Pen(_P_BORDER, 1))
        gc.StrokeLine(0, h - 1, w, h - 1)
        x = 0
        for cw in self._col_widths[:-1]:
            x += cw
            gc.StrokeLine(x, 0, x, h)


class _PosTableHeader(FlatPanel):
    """Painted header for the positions table: column labels + Go buttons."""

    def __init__(self, parent: wx.Window, col_widths: list[int]) -> None:
        super().__init__(parent, size=(-1, _P_HEADER_H))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self._col_widths = col_widths

        self._go_orig = FlatButton(self, "Go", font=app_theme.btn_font())
        self._go_orig.SetMinSize((_P_GO_W, _P_GO_H))
        self._go_orig.Enable(False)

        self._go_curr = FlatButton(self, "Go", font=app_theme.btn_font())
        self._go_curr.SetMinSize((_P_GO_W, _P_GO_H))
        self._go_curr.Enable(False)

        self._go_best = FlatButton(self, "Go", font=app_theme.btn_font())
        self._go_best.SetMinSize((_P_GO_W, _P_GO_H))
        self._go_best.Enable(False)

        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, self._on_size)
        self._reposition()

    def update_col_widths(self, col_widths: list[int]) -> None:
        self._col_widths = col_widths
        self._reposition()
        self.Refresh()

    def set_go_enabled(self, col: int, enabled: bool) -> None:
        [self._go_orig, self._go_curr, self._go_best][col].Enable(enabled)

    def _reposition(self) -> None:
        if len(self._col_widths) < 4:
            return
        h = self.GetClientSize().height or _P_HEADER_H
        btn_y = (h - _P_GO_H) // 2
        x = self._col_widths[0]
        for btn, cw in zip([self._go_orig, self._go_curr, self._go_best], self._col_widths[1:]):
            btn.SetSize(x + cw - _P_GO_W - 2, btn_y, _P_GO_W, _P_GO_H)
            x += cw

    def _on_size(self, event: wx.SizeEvent) -> None:
        self._reposition()
        event.Skip()

    def _on_paint(self, _: wx.PaintEvent) -> None:
        w, h = self.GetClientSize()
        if w <= 0 or h <= 0:
            return
        try:
            dc = wx.AutoBufferedPaintDC(self)
            gc = wx.GraphicsContext.Create(dc)
        except Exception:
            return
        if gc is None:
            return

        gc.SetBrush(wx.Brush(app_theme.background))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)

        font = app_theme.scaled_font(12, weight=wx.FONTWEIGHT_BOLD)
        gc.SetFont(font, app_theme.foreground)

        labels = ("Motor", "Original", "Current", "Best")
        x = 0
        for i, (label, cw) in enumerate(zip(labels, self._col_widths)):
            avail_w = (cw - _P_GO_W - 4) if i > 0 else cw
            tw, th = gc.GetTextExtent(label)
            gc.DrawText(label, x + max(_P_CELL_PAD, (avail_w - tw) / 2), (h - th) / 2)
            x += cw

        gc.SetPen(wx.Pen(_P_BORDER, 1))
        x = 0
        for cw in self._col_widths[:-1]:
            x += cw
            gc.StrokeLine(x, 0, x, h)
        gc.StrokeLine(0, h - 1, w, h - 1)


class _PositionsTable(FlatPanel):
    """Read-only table: Motor | Original | Current | Best, with Go buttons in the header."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)

        self._motor_keys: list[str] = []
        self._motor_rows: dict[str, _PosTableRow] = {}
        self._max_row: _PosTableRow | None = None
        self._orig_max: float | None = None

        self._on_go_original_cb: Callable[[str | None], None] | None = None
        self._on_go_current_cb: Callable[[str | None], None] | None = None
        self._on_go_best_cb: Callable[[str | None], None] | None = None
        self._on_height_needed_cb: Callable[[int], None] | None = None

        self._header = _PosTableHeader(self, self._col_widths())
        self._header._go_orig.SetAction(lambda _e=None: self._on_go_original_cb and self._on_go_original_cb(None))
        self._header._go_curr.SetAction(lambda _e=None: self._on_go_current_cb and self._on_go_current_cb(None))
        self._header._go_best.SetAction(lambda _e=None: self._on_go_best_cb and self._on_go_best_cb(None))

        self._header_border = FlatPanel(self)
        self._header_border.SetBackgroundColour(_P_BORDER)
        self._header_border.SetMinSize((-1, 1))
        self._header_border.SetMaxSize((-1, 1))

        self._rows_panel = FlatPanel(self)
        self._rows_sizer = wx.BoxSizer(wx.VERTICAL)
        self._rows_panel.SetSizer(self._rows_sizer)

        self._empty_label = FlatLabel(self, label="No preview snapshot yet.")
        self._empty_label.SetFont(app_theme.scaled_font(12, style=wx.FONTSTYLE_ITALIC))

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(self._header, 0, wx.EXPAND)
        outer.Add(self._header_border, 0, wx.EXPAND)
        outer.Add(self._rows_panel, 0, wx.EXPAND)
        outer.Add(self._empty_label, 0, wx.TOP, 6)
        self.SetSizer(outer)

        self.Bind(wx.EVT_SIZE, self._on_size)

    def bind_go_original(self, callback: Callable[[str | None], None]) -> None:
        self._on_go_original_cb = callback

    def bind_go_current(self, callback: Callable[[str | None], None]) -> None:
        self._on_go_current_cb = callback

    def bind_go_best(self, callback: Callable[[str | None], None]) -> None:
        self._on_go_best_cb = callback

    def bind_height_needed_changed(self, callback: Callable[[int], None]) -> None:
        self._on_height_needed_cb = callback

    def set_original_all(self, positions: list[tuple[str, str, float | None, int]], max_intensity: float | None) -> None:
        """Rebuild all rows from *positions* and populate the Original column."""
        self._clear_rows()
        widths = self._col_widths()
        for key, label, value, precision in positions:
            if not key.strip():
                continue
            row = _PosTableRow(self._rows_panel, label or key, precision, widths, alt_bg=False)
            row.set_value(_COL_ORIG, value)
            self._rows_sizer.Add(row, 0, wx.EXPAND)
            self._motor_rows[key] = row
            self._motor_keys.append(key)

        if self._motor_keys:
            self._max_row = _PosTableRow(self._rows_panel, "Max intensity", 0, widths, alt_bg=False, is_max=True)
            self._max_row.set_value(_COL_ORIG, max_intensity)
            self._rows_sizer.Add(self._max_row, 0, wx.EXPAND)
            self._orig_max = max_intensity

        has_data = bool(self._motor_keys)
        self._empty_label.Show(not has_data)
        self._header.set_go_enabled(_COL_ORIG, has_data)
        self._rows_panel.Show(has_data)
        self._rows_panel.Layout()
        self.Layout()

        n_rows = len(self._motor_keys) + (1 if self._motor_keys else 0)
        table_h = _P_HEADER_H + 1 + n_rows * _P_ROW_H
        if self._on_height_needed_cb:
            self._on_height_needed_cb(table_h)

    def clear_original(self) -> None:
        self.set_original_all([], None)

    def set_current_all(
        self,
        positions: list[tuple[str, str, float | None, int]],
        max_intensity: float | None,
        orig_max: float | None,
    ) -> None:
        """Populate the Current column values."""
        if orig_max is not None:
            self._orig_max = orig_max
        for key, _label, value, _prec in positions:
            row = self._motor_rows.get(key)
            if row is None:
                continue
            try:
                row.set_value(_COL_CURR, value)
            except RuntimeError:
                self._motor_rows.pop(key, None)
        if self._max_row is not None:
            try:
                self._max_row.set_value(_COL_CURR, max_intensity)
                self._max_row.set_curr_colour(self._max_colour(max_intensity))
            except RuntimeError:
                self._max_row = None
        self._header.set_go_enabled(_COL_CURR, bool(positions))

    def clear_current(self) -> None:
        for row in self._motor_rows.values():
            try:
                row.set_value(_COL_CURR, None)
            except RuntimeError:
                pass
        if self._max_row is not None:
            try:
                self._max_row.set_value(_COL_CURR, None)
                self._max_row.set_curr_colour(app_theme.foreground)
            except RuntimeError:
                self._max_row = None
        self._header.set_go_enabled(_COL_CURR, False)

    def update_current(self, key: str, value: float | None) -> None:
        row = self._motor_rows.get(key)
        if row is None:
            return
        try:
            row.set_value(_COL_CURR, value)
        except RuntimeError:
            self._motor_rows.pop(key, None)

    def update_current_max(self, value: float | None) -> None:
        if self._max_row is None:
            return
        try:
            self._max_row.set_value(_COL_CURR, value)
            self._max_row.set_curr_colour(self._max_colour(value))
        except RuntimeError:
            self._max_row = None

    def set_best_all(self, positions: list[tuple[str, str, float | None, int]], max_intensity: float | None) -> None:
        """Populate the Best column values."""
        for key, _label, value, _prec in positions:
            row = self._motor_rows.get(key)
            if row is None:
                continue
            try:
                row.set_value(_COL_BEST, value)
            except RuntimeError:
                self._motor_rows.pop(key, None)
        if self._max_row is not None:
            try:
                self._max_row.set_value(_COL_BEST, max_intensity)
                self._max_row.set_best_colour(self._max_colour(max_intensity))
            except RuntimeError:
                self._max_row = None
        self._header.set_go_enabled(_COL_BEST, bool(positions))

    def clear_best(self) -> None:
        for row in self._motor_rows.values():
            try:
                row.set_value(_COL_BEST, None)
            except RuntimeError:
                pass
        if self._max_row is not None:
            try:
                self._max_row.set_value(_COL_BEST, None)
                self._max_row.set_best_colour(app_theme.foreground)
            except RuntimeError:
                self._max_row = None
        self._header.set_go_enabled(_COL_BEST, False)

    def update_best(self, key: str, value: float | None) -> None:
        row = self._motor_rows.get(key)
        if row is None:
            return
        try:
            row.set_value(_COL_BEST, value)
        except RuntimeError:
            self._motor_rows.pop(key, None)

    def update_best_max(self, value: float | None) -> None:
        if self._max_row is None:
            return
        try:
            self._max_row.set_value(_COL_BEST, value)
            self._max_row.set_best_colour(self._max_colour(value))
        except RuntimeError:
            self._max_row = None

    def _max_colour(self, value: float | None) -> wx.Colour:
        orig = self._orig_max
        if value is None or orig is None:
            return app_theme.foreground
        if value > orig:
            return app_theme.green
        if value < orig:
            return app_theme.red
        return app_theme.foreground

    def _col_widths(self) -> list[int]:
        w = self.GetClientSize().width
        if w <= _P_MOTOR_W:
            w = _P_MOTOR_W + _P_VAL_W * 3
        remaining = w - _P_MOTOR_W
        val_w = remaining // 3
        last_w = remaining - val_w * 2
        return [_P_MOTOR_W, val_w, val_w, last_w]

    def _on_size(self, event: wx.SizeEvent) -> None:
        widths = self._col_widths()
        self._header.update_col_widths(widths)
        for row in list(self._motor_rows.values()):
            try:
                row.update_col_widths(widths)
            except RuntimeError:
                pass
        if self._max_row is not None:
            try:
                self._max_row.update_col_widths(widths)
            except RuntimeError:
                self._max_row = None
        event.Skip()

    def _clear_rows(self) -> None:
        for row in list(self._motor_rows.values()):
            self._rows_sizer.Detach(row)
            row.Destroy()
        self._motor_rows.clear()
        self._motor_keys.clear()
        if self._max_row is not None:
            self._rows_sizer.Detach(self._max_row)
            self._max_row.Destroy()
            self._max_row = None
        self._orig_max = None
        self._header.set_go_enabled(_COL_ORIG, False)
        self._header.set_go_enabled(_COL_CURR, False)
        self._header.set_go_enabled(_COL_BEST, False)
        self._rows_panel.Layout()


class PreviewView(FlatPanel):
    """Preview tab: Start/Stop button, step-size input, motor jog rows, and positions table."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)

        self._on_start_cb: Callable[[], None] | None = None
        self._on_stop_cb: Callable[[], None] | None = None
        self._on_step_changed_cb: Callable[[float], None] | None = None
        self._on_jog_minus_cb: Callable[[CenteringMotorSpec], None] | None = None
        self._on_jog_plus_cb: Callable[[CenteringMotorSpec], None] | None = None
        self._on_auto_optimize_cb: Callable[[], None] | None = None
        self._on_height_needed_cb: Callable[[int], None] | None = None
        self._centering_col_h: int = 0
        self._table_h: int = 0
        self._previewing = False
        self._step_mm: float = 0.001

        self._centering_rows: dict[str, _CenteringRow] = {}

        self._toggle_btn = FlatButton(self, "Start Preview", font=app_theme.btn_font())
        self._toggle_btn.SetMinSize((-1, 36))
        self._toggle_btn.SetAction(self._on_toggle_clicked)

        self._centering_panel, self._centering_sizer, self._centering_empty_label = self._build_centering_column()
        self._positions_table = _PositionsTable(self)
        self._positions_table.bind_height_needed_changed(self._on_table_height_changed)
        self._auto_optimize_panel = self._build_auto_optimize_panel()

        right_col = wx.BoxSizer(wx.VERTICAL)
        right_col.Add(self._toggle_btn, 0, wx.EXPAND | wx.BOTTOM, 8)
        right_col.Add(self._auto_optimize_panel, 0, wx.EXPAND)

        cols = wx.BoxSizer(wx.HORIZONTAL)
        cols.Add(self._positions_table, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)
        cols.AddSpacer(12)
        cols.Add(self._centering_panel, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)
        cols.AddSpacer(12)
        cols.Add(right_col, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)
        self.SetSizer(cols)

    def bind_start(self, callback: Callable[[], None]) -> None:
        self._on_start_cb = callback

    def bind_stop(self, callback: Callable[[], None]) -> None:
        self._on_stop_cb = callback

    def bind_step_changed(self, callback: Callable[[float], None]) -> None:
        self._on_step_changed_cb = callback

    def bind_jog_minus(self, callback: Callable[["CenteringMotorSpec"], None]) -> None:
        self._on_jog_minus_cb = callback
        for row in self._centering_rows.values():
            row.bind_left(callback)

    def bind_jog_plus(self, callback: Callable[["CenteringMotorSpec"], None]) -> None:
        self._on_jog_plus_cb = callback
        for row in self._centering_rows.values():
            row.bind_right(callback)

    def bind_auto_optimize(self, callback: Callable[[], None]) -> None:
        self._on_auto_optimize_cb = callback

    def bind_go_original(self, callback: Callable[[str | None], None]) -> None:
        self._positions_table.bind_go_original(callback)

    def bind_go_current(self, callback: Callable[[str | None], None]) -> None:
        self._positions_table.bind_go_current(callback)

    def bind_go_best(self, callback: Callable[[str | None], None]) -> None:
        self._positions_table.bind_go_best(callback)

    def bind_height_needed_changed(self, callback: Callable[[int], None]) -> None:
        self._on_height_needed_cb = callback

    def _on_table_height_changed(self, table_h: int) -> None:
        self._table_h = table_h
        self._emit_height_needed()

    def _emit_height_needed(self) -> None:
        _right_col_h = 108
        needed = max(self._centering_col_h, self._table_h, _right_col_h) + 16
        if self._on_height_needed_cb:
            self._on_height_needed_cb(needed)

    @property
    def auto_optimize_range(self) -> float | None:
        """Read the Range field in raw motor units (mm, deg, ...), or None if empty/invalid."""
        return self._parse_positive_float(self._auto_range_ctrl.GetValue())

    @property
    def auto_optimize_step(self) -> float | None:
        """Read the Step field in raw motor units (mm, deg, ...), or None if empty/invalid."""
        return self._parse_positive_float(self._auto_step_ctrl.GetValue())

    def set_auto_optimize_enabled(self, enabled: bool) -> None:
        self._auto_optimize_btn.Enable(enabled)

    def set_auto_optimize_running(self, running: bool) -> None:
        if running:
            self._auto_optimize_btn.SetLabel("Stop Optimize")
            self._auto_optimize_btn.SetColorScheme(_stop_scheme())
        else:
            self._auto_optimize_btn.SetLabel("Auto Optimize")
            self._auto_optimize_btn.SetColorScheme(None)

    @staticmethod
    def _parse_positive_float(raw: str) -> float | None:
        raw = (raw or "").strip()
        if not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            return None
        if value <= 0:
            return None
        return value

    def _on_auto_optimize_clicked(self, _e=None) -> None:
        if self._on_auto_optimize_cb is not None:
            self._on_auto_optimize_cb()

    def set_centering_motors(self, specs: list["CenteringMotorSpec"]) -> None:
        """Replace the centering rows with one row per spec; preserves jog bindings."""
        old_rows = list(self._centering_rows.values())
        self._centering_rows.clear()
        for row in old_rows:
            self._centering_sizer.Detach(row)
            row.Destroy()

        if not specs:
            self._centering_empty_label.Show()
            self._centering_panel.Layout()
            self._centering_col_h = 0
            self._emit_height_needed()
            return

        self._centering_empty_label.Hide()
        for spec in specs:
            if not spec.pv.strip():
                continue
            row = _CenteringRow(self._centering_panel, spec)
            if self._on_jog_minus_cb is not None:
                row.bind_left(self._on_jog_minus_cb)
            if self._on_jog_plus_cb is not None:
                row.bind_right(self._on_jog_plus_cb)
            self._centering_rows[spec.pv] = row
            self._centering_sizer.Add(row, 0, wx.EXPAND | wx.BOTTOM, 4)
        self._centering_panel.Layout()

        n = len(self._centering_rows)
        self._centering_col_h = 39 + n * (_CenteringRow._ROW_H + 4)
        self._emit_height_needed()

    def update_centering_value(self, pv: str, value: float | None) -> None:
        """Push a new live readback value into the row identified by *pv*."""
        row = self._centering_rows.get(pv)
        if row is None:
            return
        try:
            row.set_value(value)
        except RuntimeError:
            # Row's C++ widget was destroyed between the camonitor callback
            # being queued and processed; safe to ignore.
            self._centering_rows.pop(pv, None)

    def centering_specs(self) -> list["CenteringMotorSpec"]:
        return [row.spec for row in self._centering_rows.values()]

    @property
    def step_mm(self) -> float:
        return self._step_mm

    @property
    def step_um(self) -> float:
        return self._step_mm * _UM_PER_MM

    @property
    def is_previewing(self) -> bool:
        return self._previewing

    def set_previewing(self, previewing: bool) -> None:
        self._previewing = previewing
        if previewing:
            self._toggle_btn.SetLabel("Stop Preview")
            self._toggle_btn.SetColorScheme(_stop_scheme())
        else:
            self._toggle_btn.SetLabel("Start Preview")
            self._toggle_btn.SetColorScheme(None)
        for row in self._centering_rows.values():
            row.set_enabled(previewing)

    def set_collecting(self, collecting: bool) -> None:
        self._toggle_btn.Enable(not collecting)
        for row in self._centering_rows.values():
            row.set_enabled(self._previewing and not collecting)

    def set_original_positions(
        self,
        positions: list[tuple[str, str, float | None, int]],
        max_intensity: float | None,
    ) -> None:
        self._positions_table.set_original_all(positions, max_intensity)

    def clear_original_positions(self) -> None:
        self._positions_table.clear_original()

    def set_current_positions(
        self,
        positions: list[tuple[str, str, float | None, int]],
        max_intensity: float | None,
        original_max_intensity: float | None,
    ) -> None:
        self._positions_table.set_current_all(positions, max_intensity, original_max_intensity)

    def clear_current_positions(self) -> None:
        self._positions_table.clear_current()

    def update_current_position(self, pv: str, value: float | None) -> None:
        self._positions_table.update_current(pv, value)

    def update_current_max_intensity(self, value: float | None) -> None:
        self._positions_table.update_current_max(value)

    def set_best_positions(
        self,
        positions: list[tuple[str, str, float | None, int]],
        max_intensity: float | None,
    ) -> None:
        self._positions_table.set_best_all(positions, max_intensity)

    def clear_best_positions(self) -> None:
        self._positions_table.clear_best()

    def update_best_position(self, key: str, value: float | None) -> None:
        self._positions_table.update_best(key, value)

    def update_best_max_intensity(self, value: float | None) -> None:
        self._positions_table.update_best_max(value)

    def _build_centering_column(self) -> tuple[FlatPanel, wx.BoxSizer, FlatLabel]:
        panel = FlatPanel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        step_label = FlatLabel(panel, label="Step Size")
        step_label.SetFont(app_theme.scaled_font(12, weight=wx.FONTWEIGHT_BOLD))

        self._custom_ctrl = FlatTextCtrl(
            panel,
            value=self._format_mm(self._step_mm),
            placeholder="mm",
            centered=True,
        )
        self._custom_ctrl.SetMinSize((_CenteringRow._VALUE_W, 28))
        self._custom_ctrl.SetMaxSize((_CenteringRow._VALUE_W, _CenteringRow._ROW_H))
        self._custom_ctrl.SetRestrictToFloat(True)
        self._custom_ctrl.SetValidator(self._validate_custom_step)
        self._custom_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_custom_committed)
        self._custom_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_custom_committed)

        header_row = wx.BoxSizer(wx.HORIZONTAL)
        header_row.Add(step_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        header_row.AddStretchSpacer(1)
        header_row.AddSpacer(_CenteringRow._ARROW_SIZE + 8)
        header_row.Add(self._custom_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 6)
        header_row.AddSpacer(_CenteringRow._ARROW_SIZE + 8)
        sizer.Add(header_row, 0, wx.EXPAND | wx.BOTTOM, 4)

        sep = FlatPanel(panel)
        sep.SetBackgroundColour(app_theme.bright_black)
        sep.SetMinSize((-1, 1))
        sep.SetMaxSize((-1, 1))
        sizer.Add(sep, 0, wx.EXPAND | wx.BOTTOM, 6)

        empty_label = FlatLabel(panel, label="No motors flagged for centering.")
        empty_label.SetFont(app_theme.scaled_font(12, style=wx.FONTSTYLE_ITALIC))
        sizer.Add(empty_label, 0)

        panel.SetSizer(sizer)
        return panel, sizer, empty_label

    def _build_auto_optimize_panel(self) -> FlatPanel:
        panel = FlatPanel(self)

        self._auto_optimize_btn = FlatButton(panel, "Auto Optimize", font=app_theme.btn_font())
        self._auto_optimize_btn.SetMinSize((-1, 30))
        self._auto_optimize_btn.SetAction(self._on_auto_optimize_clicked)

        range_lbl = FlatLabel(panel, label="Range")
        range_lbl.SetFont(app_theme.scaled_font(12))
        self._auto_range_ctrl = FlatTextCtrl(panel, value="0.005", placeholder="", centered=True)
        self._auto_range_ctrl.SetRestrictToFloat(True)
        self._auto_range_ctrl.SetMinSize((70, 28))

        step_lbl = FlatLabel(panel, label="Step")
        step_lbl.SetFont(app_theme.scaled_font(12))
        self._auto_step_ctrl = FlatTextCtrl(panel, value="0.001", placeholder="", centered=True)
        self._auto_step_ctrl.SetRestrictToFloat(True)
        self._auto_step_ctrl.SetMinSize((70, 28))

        inputs_row = wx.BoxSizer(wx.HORIZONTAL)
        inputs_row.Add(range_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        inputs_row.Add(self._auto_range_ctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 6)
        inputs_row.AddSpacer(10)
        inputs_row.Add(step_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        inputs_row.Add(self._auto_step_ctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 6)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self._auto_optimize_btn, 0, wx.EXPAND | wx.BOTTOM, 6)
        sizer.Add(inputs_row, 0, wx.EXPAND)
        panel.SetSizer(sizer)
        return panel

    @staticmethod
    def _format_mm(value_mm: float) -> str:
        return MotorPositionValidator(f"{value_mm:.{_STEP_PRECISION}f}", _STEP_PRECISION).formatted

    @staticmethod
    def _validate_custom_step(raw: str) -> str:
        if raw == "":
            return ""
        return MotorPositionValidator(raw, _STEP_PRECISION).formatted

    def _on_custom_committed(self, event: wx.Event) -> None:
        event.Skip()
        raw = self._custom_ctrl.GetValue()
        if not raw:
            return
        try:
            value = float(raw)
        except ValueError:
            return
        self._step_mm = value
        if self._on_step_changed_cb is not None:
            self._on_step_changed_cb(value)

    def _on_toggle_clicked(self, _e=None) -> None:
        if self._previewing:
            if self._on_stop_cb is not None:
                self._on_stop_cb()
        else:
            if self._on_start_cb is not None:
                self._on_start_cb()
