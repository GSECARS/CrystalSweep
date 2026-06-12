#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/preview_view.py
# ----------------------------------------------------------------------------------
# Purpose:
# Preview tab inside the Single-Crystal Centering Tools section.
# Provides a Start/Stop preview button and step-size selection (predefined or
# custom), arranged in the first of four columns.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from typing import Callable

import wx

from crystalsweep.model.validation import MotorPositionValidator
from crystalsweep.ui.view.custom.icons import draw_chevron_left, draw_chevron_right
from crystalsweep.ui.view.custom.theme import (
    BG_CARD,
    DANGER,
    DANGER_HOVER,
    DANGER_PRESS,
    FG_PRIMARY,
    FG_SECONDARY,
    POPUP_BTN_BG,
    POPUP_BTN_HOVER,
    POPUP_BTN_PRESS,
    SEP_COLOUR,
    scaled_font,
)
from crystalsweep.ui.view.custom.widgets import DEFAULT_SCHEME, DarkTextCtrl, FlatButton, IconButton, ReadbackBox

__all__ = ["CenteringMotorSpec", "PreviewView"]


class CenteringMotorSpec:
    """Lightweight description of a centering-enabled motor for PreviewView."""

    __slots__ = ("shorthand", "description", "pv", "precision")

    def __init__(self, shorthand: str, description: str, pv: str, precision: int) -> None:
        self.shorthand = shorthand
        self.description = description
        self.pv = pv
        self.precision = precision

_START_SCHEME = DEFAULT_SCHEME
_STOP_SCHEME = (DANGER, DANGER_HOVER, DANGER_PRESS, FG_PRIMARY, FG_PRIMARY)

_STEP_BTN_IDLE = POPUP_BTN_BG
_STEP_BTN_HOVER = POPUP_BTN_HOVER
_STEP_BTN_PRESS = POPUP_BTN_PRESS

_STEP_PRECISION = 4
_UM_PER_MM = 1000.0
_PREDEFINED_STEPS_UM: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0)


class _StepButton(wx.Control):
    """Flat preset button. Click invokes its action; no toggled state."""

    def __init__(self, parent: wx.Window, label: str) -> None:
        super().__init__(parent, style=wx.BORDER_NONE | wx.WANTS_CHARS)
        self._label = label
        self._hovered = False
        self._pressed = False
        self._action: Callable[[], None] | None = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetMinSize((-1, 28))
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, lambda e: (self.Refresh(), e.Skip()))
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_press)
        self.Bind(wx.EVT_LEFT_UP, self._on_release)

    def set_action(self, callback: Callable[[], None]) -> None:
        self._action = callback

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(self.GetParent().GetBackgroundColour()))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        if self._pressed:
            bg = _STEP_BTN_PRESS
        elif self._hovered:
            bg = _STEP_BTN_HOVER
        else:
            bg = _STEP_BTN_IDLE
        gc.SetBrush(wx.Brush(bg))
        gc.DrawRoundedRectangle(0, 0, w, h, 4)
        font = scaled_font(12)
        gc.SetFont(font, FG_PRIMARY)
        tw, th = gc.GetTextExtent(self._label)
        gc.DrawText(self._label, (w - tw) / 2, (h - th) / 2)

    def _on_enter(self, event: wx.MouseEvent) -> None:
        self._hovered = True
        self.Refresh()
        event.Skip()

    def _on_leave(self, event: wx.MouseEvent) -> None:
        self._hovered = False
        self._pressed = False
        self.Refresh()
        event.Skip()

    def _on_press(self, event: wx.MouseEvent) -> None:
        self._pressed = True
        self.Refresh()
        event.Skip()

    def _on_release(self, event: wx.MouseEvent) -> None:
        was_pressed = self._pressed
        self._pressed = False
        self.Refresh()
        event.Skip()
        if was_pressed and self._action is not None:
            wx.CallAfter(self._action)


class _CenteringRow(wx.Panel):
    """One row in the centering motors column: [label] [<] [live RBV] [>]."""

    _ARROW_SIZE = 20
    _ROW_H = 28
    _VALUE_W = 90

    def __init__(self, parent: wx.Window, spec: CenteringMotorSpec) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self.SetBackgroundColour(BG_CARD)
        self.SetMinSize((-1, self._ROW_H))
        self.spec = spec
        self._precision = max(0, int(spec.precision))

        label_text = spec.description or spec.shorthand or spec.pv
        self._label = wx.StaticText(self, label=label_text)
        self._label.SetFont(scaled_font(12, weight=wx.FONTWEIGHT_BOLD))
        self._label.SetForegroundColour(FG_SECONDARY)
        self._label.SetBackgroundColour(BG_CARD)

        self._left_btn = IconButton(self, draw_chevron_left, size=self._ARROW_SIZE, tooltip=f"Move {label_text} − step", bg=BG_CARD)
        self._left_btn.Bind(wx.EVT_BUTTON, lambda _e: self._fire(self._on_left_cb))

        self._right_btn = IconButton(self, draw_chevron_right, size=self._ARROW_SIZE, tooltip=f"Move {label_text} + step", bg=BG_CARD)
        self._right_btn.Bind(wx.EVT_BUTTON, lambda _e: self._fire(self._on_right_cb))

        self._value_box = ReadbackBox(self, height=self._ROW_H)
        self._value_box.SetMinSize((self._VALUE_W, self._ROW_H))
        self._value_box.SetMaxSize((self._VALUE_W, self._ROW_H))
        self._value_box.set_text("—")

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
        self._value_box.set_text(text)

    def _fire(self, cb: Callable[[CenteringMotorSpec], None] | None) -> None:
        if cb is not None:
            cb(self.spec)


class PreviewView(wx.Panel):
    """Preview tab: Start/Stop button and step-size selector in column 1."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self.SetBackgroundColour(BG_CARD)

        self._on_start_cb: Callable[[], None] | None = None
        self._on_stop_cb: Callable[[], None] | None = None
        self._on_step_changed_cb: Callable[[float], None] | None = None
        self._on_jog_minus_cb: Callable[[CenteringMotorSpec], None] | None = None
        self._on_jog_plus_cb: Callable[[CenteringMotorSpec], None] | None = None
        self._previewing = False
        self._step_mm: float = _PREDEFINED_STEPS_UM[0] / _UM_PER_MM

        self._centering_rows: dict[str, _CenteringRow] = {}

        self._column1 = self._build_column1()
        self._centering_panel, self._centering_sizer, self._centering_empty_label = self._build_centering_column()
        self._column3 = self._build_placeholder_column()
        self._column4 = self._build_placeholder_column()

        cols = wx.BoxSizer(wx.HORIZONTAL)
        cols.Add(self._column1, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)
        cols.AddSpacer(12)
        cols.Add(self._centering_panel, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)
        cols.AddSpacer(12)
        cols.Add(self._column3, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)
        cols.AddSpacer(12)
        cols.Add(self._column4, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)
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
            return

        self._centering_empty_label.Hide()
        for spec in specs:
            if not spec.pv.strip():
                continue
            row = _CenteringRow(self._centering_panel, spec)
            row.SetBackgroundColour(BG_CARD)
            if self._on_jog_minus_cb is not None:
                row.bind_left(self._on_jog_minus_cb)
            if self._on_jog_plus_cb is not None:
                row.bind_right(self._on_jog_plus_cb)
            self._centering_rows[spec.pv] = row
            self._centering_sizer.Add(row, 0, wx.EXPAND | wx.BOTTOM, 4)
        self._centering_panel.Layout()

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
            self._toggle_btn._idle_bg = _STOP_SCHEME[0]
            self._toggle_btn._hover_bg = _STOP_SCHEME[1]
            self._toggle_btn._press_bg = _STOP_SCHEME[2]
            self._toggle_btn._idle_fg = _STOP_SCHEME[3]
            self._toggle_btn._hover_fg = _STOP_SCHEME[4]
        else:
            self._toggle_btn.SetLabel("Start Preview")
            self._toggle_btn._idle_bg = _START_SCHEME[0]
            self._toggle_btn._hover_bg = _START_SCHEME[1]
            self._toggle_btn._press_bg = _START_SCHEME[2]
            self._toggle_btn._idle_fg = _START_SCHEME[3]
            self._toggle_btn._hover_fg = _START_SCHEME[4]
        self._toggle_btn.Refresh()
        for row in self._centering_rows.values():
            row.set_enabled(previewing)

    def _build_column1(self) -> wx.BoxSizer:
        col = wx.BoxSizer(wx.VERTICAL)

        preset_btn_size = 30
        preset_gap = 4
        num_presets = len(_PREDEFINED_STEPS_UM)
        presets_total_w = preset_btn_size * num_presets + preset_gap * (num_presets - 1)

        self._toggle_btn = FlatButton(self, "Start Preview", color_scheme=_START_SCHEME)
        self._toggle_btn.SetMinSize((presets_total_w, 36))
        self._toggle_btn.SetMaxSize((presets_total_w, -1))
        self._toggle_btn.set_action(self._on_toggle_clicked)
        col.Add(self._toggle_btn, 1, wx.EXPAND | wx.BOTTOM, 10)

        sep = wx.Panel(self, size=(presets_total_w, 1))
        sep.SetBackgroundColour(SEP_COLOUR)
        sep.SetMinSize((presets_total_w, 1))
        sep.SetMaxSize((presets_total_w, 1))
        col.Add(sep)
        col.AddSpacer(12)

        step_label = wx.StaticText(self, label="Step Size", style=wx.ALIGN_CENTRE_HORIZONTAL)
        step_label.SetFont(scaled_font(11, weight=wx.FONTWEIGHT_BOLD))
        step_label.SetForegroundColour(FG_SECONDARY)
        step_label.SetBackgroundColour(BG_CARD)
        step_label.SetMinSize((presets_total_w, -1))
        step_label.SetMaxSize((presets_total_w, -1))
        col.Add(step_label, 0, wx.BOTTOM, 4)

        preset_row = wx.BoxSizer(wx.HORIZONTAL)
        for i, value_um in enumerate(_PREDEFINED_STEPS_UM):
            btn = _StepButton(self, self._format_um_label(value_um))
            btn.SetToolTip(f"Set step to {self._format_um_label(value_um)} um")
            btn.SetMinSize((preset_btn_size, preset_btn_size))
            btn.SetMaxSize((preset_btn_size, preset_btn_size))
            btn.set_action(lambda v=value_um / _UM_PER_MM: self._apply_preset(v))
            preset_row.Add(btn, 0, wx.LEFT if i > 0 else 0, preset_gap)
        col.Add(preset_row, 0)

        self._custom_ctrl = DarkTextCtrl(
            self,
            value=self._format_mm(self._step_mm),
            placeholder="mm",
            parent_bg=BG_CARD,
            centered=True,
        )
        self._custom_ctrl.SetMinSize((presets_total_w, 28))
        self._custom_ctrl.SetMaxSize((presets_total_w, 28))
        self._custom_ctrl.set_restrict_to_float(True)
        self._custom_ctrl.set_validator(self._validate_custom_step)
        self._custom_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_custom_committed)
        self._custom_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_custom_committed)
        col.Add(self._custom_ctrl, 0, wx.TOP, 6)

        return col

    def _build_centering_column(self) -> tuple[wx.Panel, wx.BoxSizer, wx.StaticText]:
        panel = wx.Panel(self, style=wx.BORDER_NONE)
        panel.SetBackgroundColour(BG_CARD)

        sizer = wx.BoxSizer(wx.VERTICAL)

        empty_label = wx.StaticText(panel, label="No motors flagged for centering.")
        empty_label.SetFont(scaled_font(11, style=wx.FONTSTYLE_ITALIC))
        empty_label.SetForegroundColour(FG_SECONDARY)
        empty_label.SetBackgroundColour(BG_CARD)
        sizer.Add(empty_label, 0)

        panel.SetSizer(sizer)
        return panel, sizer, empty_label

    def _build_placeholder_column(self) -> wx.BoxSizer:
        return wx.BoxSizer(wx.VERTICAL)

    @staticmethod
    def _format_um_label(value_um: float) -> str:
        if value_um == int(value_um):
            return f"{int(value_um)}"
        return f"{value_um:g}"

    @staticmethod
    def _format_mm(value_mm: float) -> str:
        return MotorPositionValidator(f"{value_mm:.{_STEP_PRECISION}f}", _STEP_PRECISION).formatted

    @staticmethod
    def _validate_custom_step(raw: str) -> str:
        if raw == "":
            return ""
        return MotorPositionValidator(raw, _STEP_PRECISION).formatted

    def _apply_preset(self, value_mm: float) -> None:
        self._custom_ctrl.SetValue(self._format_mm(value_mm))
        self._step_mm = value_mm
        if self._on_step_changed_cb is not None:
            self._on_step_changed_cb(value_mm)

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

    def _on_toggle_clicked(self) -> None:
        if self._previewing:
            if self._on_stop_cb is not None:
                self._on_stop_cb()
        else:
            if self._on_start_cb is not None:
                self._on_start_cb()
