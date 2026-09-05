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
_PREDEFINED_STEPS_UM: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0)


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

        self._left_btn = FlatIconButton(self, draw_chevron_left, icon_size=self._ARROW_SIZE, tooltip=f"Move {label_text} − step")
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


class PreviewView(FlatPanel):
    """Preview tab: Start/Stop button and step-size selector in column 1."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)

        self._on_start_cb: Callable[[], None] | None = None
        self._on_stop_cb: Callable[[], None] | None = None
        self._on_step_changed_cb: Callable[[float], None] | None = None
        self._on_jog_minus_cb: Callable[[CenteringMotorSpec], None] | None = None
        self._on_jog_plus_cb: Callable[[CenteringMotorSpec], None] | None = None
        self._on_auto_optimize_cb: Callable[[], None] | None = None
        self._on_go_original_cb: Callable[[str | None], None] | None = None
        self._on_go_current_cb: Callable[[str | None], None] | None = None
        self._on_go_best_cb: Callable[[str | None], None] | None = None
        self._previewing = False
        self._step_mm: float = _PREDEFINED_STEPS_UM[0] / _UM_PER_MM

        self._centering_rows: dict[str, _CenteringRow] = {}

        self._column1 = self._build_column1()
        self._centering_panel, self._centering_sizer, self._centering_empty_label = self._build_centering_column()
        (
            self._originals_panel,
            self._originals_sizer,
            self._originals_empty_label,
        ) = self._build_originals_column()
        (
            self._currents_panel,
            self._currents_sizer,
            self._currents_empty_label,
        ) = self._build_currents_column()
        (
            self._bests_panel,
            self._bests_sizer,
            self._bests_empty_label,
        ) = self._build_bests_column()

        self._auto_optimize_panel = self._build_auto_optimize_panel()

        originals_stack = wx.BoxSizer(wx.VERTICAL)
        originals_stack.Add(self._originals_panel, 0, wx.EXPAND)
        originals_stack.AddSpacer(12)
        originals_stack.Add(self._bests_panel, 0, wx.EXPAND)

        currents_stack = wx.BoxSizer(wx.VERTICAL)
        currents_stack.Add(self._currents_panel, 0, wx.EXPAND)
        currents_stack.AddSpacer(12)
        currents_stack.Add(self._auto_optimize_panel, 0, wx.EXPAND)

        cols = wx.BoxSizer(wx.HORIZONTAL)
        cols.Add(self._column1, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)
        cols.AddSpacer(12)
        cols.Add(self._centering_panel, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)
        cols.AddSpacer(12)
        cols.Add(originals_stack, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)
        cols.AddSpacer(12)
        cols.Add(currents_stack, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)
        self.SetSizer(cols)

        self._original_rows: list[wx.Window] = []
        self._current_pair_rows: list[wx.Window] = []
        self._current_motor_rows: dict[str, tuple[FlatPanel, FlatLabel, int]] = {}
        self._current_max_row: FlatPanel | None = None
        self._current_max_value: FlatLabel | None = None
        self._original_max_intensity: float | None = None
        self._best_pair_rows: list[wx.Window] = []
        self._best_motor_rows: dict[str, tuple[FlatPanel, FlatLabel, int]] = {}
        self._best_max_row: FlatPanel | None = None
        self._best_max_value: FlatLabel | None = None

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
        self._on_go_original_cb = callback

    def bind_go_current(self, callback: Callable[[str | None], None]) -> None:
        self._on_go_current_cb = callback

    def bind_go_best(self, callback: Callable[[str | None], None]) -> None:
        self._on_go_best_cb = callback

    @property
    def auto_optimize_range(self) -> float | None:
        """Read the Range field in raw motor units (mm, deg, …), or None if empty/invalid."""
        return self._parse_positive_float(self._auto_range_ctrl.GetValue())

    @property
    def auto_optimize_step(self) -> float | None:
        """Read the Step field in raw motor units (mm, deg, …), or None if empty/invalid."""
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

    def _build_column1(self) -> wx.BoxSizer:
        col = wx.BoxSizer(wx.VERTICAL)

        preset_btn_size = 30
        preset_gap = 4
        num_presets = len(_PREDEFINED_STEPS_UM)
        presets_total_w = preset_btn_size * num_presets + preset_gap * (num_presets - 1)

        self._toggle_btn = FlatButton(self, "Start Preview", font=app_theme.btn_font())
        self._toggle_btn.SetMinSize((presets_total_w, 36))
        self._toggle_btn.SetMaxSize((presets_total_w, -1))
        self._toggle_btn.SetAction(self._on_toggle_clicked)
        col.Add(self._toggle_btn, 1, wx.EXPAND | wx.BOTTOM, 10)

        sep = FlatPanel(self, size=(presets_total_w, 1))
        sep.SetBackgroundColour(app_theme.bright_black)
        sep.SetMinSize((presets_total_w, 1))
        sep.SetMaxSize((presets_total_w, 1))
        col.Add(sep)
        col.AddSpacer(12)

        step_label = FlatLabel(self, label="Step Size")
        step_label.SetFont(app_theme.scaled_font(12, weight=wx.FONTWEIGHT_BOLD))
        step_label.SetMinSize((presets_total_w, -1))
        step_label.SetMaxSize((presets_total_w, -1))
        col.Add(step_label, 0, wx.ALIGN_CENTRE_HORIZONTAL | wx.BOTTOM, 4)

        preset_row = wx.BoxSizer(wx.HORIZONTAL)
        for i, value_um in enumerate(_PREDEFINED_STEPS_UM):
            btn = FlatButton(self, self._format_um_label(value_um))
            btn.SetToolTip(f"Set step to {self._format_um_label(value_um)} um")
            btn.SetMinSize((preset_btn_size, preset_btn_size))
            btn.SetMaxSize((preset_btn_size, preset_btn_size))
            btn.SetAction(lambda v=value_um / _UM_PER_MM: self._apply_preset(v))
            preset_row.Add(btn, 0, wx.LEFT if i > 0 else 0, preset_gap)
        col.Add(preset_row, 0)

        self._custom_ctrl = FlatTextCtrl(
            self,
            value=self._format_mm(self._step_mm),
            placeholder="mm",
            centered=True,
        )
        self._custom_ctrl.SetMinSize((presets_total_w, 28))
        self._custom_ctrl.SetMaxSize((presets_total_w, 28))
        self._custom_ctrl.SetRestrictToFloat(True)
        self._custom_ctrl.SetValidator(self._validate_custom_step)
        self._custom_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_custom_committed)
        self._custom_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_custom_committed)
        col.Add(self._custom_ctrl, 0, wx.TOP, 6)

        return col

    def _build_centering_column(self) -> tuple[FlatPanel, wx.BoxSizer, FlatLabel]:
        panel = FlatPanel(self)

        sizer = wx.BoxSizer(wx.VERTICAL)

        empty_label = FlatLabel(panel, label="No motors flagged for centering.")
        empty_label.SetFont(app_theme.scaled_font(12, style=wx.FONTSTYLE_ITALIC))
        sizer.Add(empty_label, 0)

        panel.SetSizer(sizer)
        return panel, sizer, empty_label

    def _build_originals_column(self) -> tuple[FlatPanel, wx.BoxSizer, FlatLabel]:
        panel = FlatPanel(self)

        sizer = wx.BoxSizer(wx.VERTICAL)

        header_row = wx.BoxSizer(wx.HORIZONTAL)
        header = FlatLabel(panel, label="Original Positions")
        header.SetFont(app_theme.scaled_font(12, weight=wx.FONTWEIGHT_BOLD))
        self._originals_go_btn = FlatButton(panel, "Go", font=app_theme.btn_font())
        self._originals_go_btn.SetMinSize((36, 22))
        self._originals_go_btn.Enable(False)
        header_row.Add(header, 0, wx.ALIGN_CENTER_VERTICAL)
        header_row.Add(self._originals_go_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        sizer.Add(header_row, 0, wx.BOTTOM, 6)

        empty_label = FlatLabel(panel, label="No preview snapshot yet.")
        empty_label.SetFont(app_theme.scaled_font(12, style=wx.FONTSTYLE_ITALIC))
        sizer.Add(empty_label, 0)

        panel.SetSizer(sizer)
        return panel, sizer, empty_label

    def set_original_positions(
        self,
        positions: list[tuple[str, str, float | None, int]],
        max_intensity: float | None,
    ) -> None:
        """Replace the Original Positions list."""
        for row in self._original_rows:
            self._originals_sizer.Detach(row)
            row.Destroy()
        self._original_rows.clear()

        if not positions:
            self._originals_empty_label.Show()
            self._originals_go_btn.Enable(False)
            self._originals_panel.Layout()
            self.Layout()
            return

        self._originals_empty_label.Hide()
        on_go_all = self._make_go_invoker("original", None)
        self._originals_go_btn.SetAction(lambda: on_go_all())
        self._originals_go_btn.Enable(True)

        self._add_motor_pair_rows(self._originals_panel, self._originals_sizer, positions, self._original_rows, None)

        max_text = f"{max_intensity:.4g}" if max_intensity is not None else "—"
        row, _, _ = self._make_snapshot_row(self._originals_panel, "Max intensity", max_text, None)
        self._originals_sizer.Add(row, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 2)
        self._original_rows.append(row)

        self._originals_panel.Layout()
        self.Layout()

    def _make_go_invoker(self, column: str, key: str | None) -> Callable[[], None]:
        def _invoke() -> None:
            if column == "original":
                cb = self._on_go_original_cb
            elif column == "current":
                cb = self._on_go_current_cb
            elif column == "best":
                cb = self._on_go_best_cb
            else:
                return
            if cb is not None:
                cb(key)

        return _invoke

    def clear_original_positions(self) -> None:
        self.set_original_positions([], None)

    def _make_snapshot_row(
        self,
        parent: wx.Window,
        label_text: str,
        value_text: str,
        on_go: Callable[[], None] | None,
    ) -> tuple[FlatPanel, FlatLabel, FlatButton | None]:
        row = FlatPanel(parent)

        label = FlatLabel(row, label=label_text)
        label.SetFont(app_theme.scaled_font(12))

        value = FlatLabel(row, label=value_text)
        value.SetFont(app_theme.scaled_font(12, weight=wx.FONTWEIGHT_BOLD))

        go_btn: FlatButton | None = None
        s = wx.BoxSizer(wx.HORIZONTAL)
        s.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
        s.AddStretchSpacer(1)
        s.Add(value, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        row.SetSizer(s)
        return row, value, go_btn

    def _add_motor_pair_rows(
        self,
        parent: FlatPanel,
        sizer: wx.BoxSizer,
        items: list[tuple[str, str, float | None, int]],
        container_list: list[wx.Window],
        key_map: dict[str, tuple[FlatPanel, FlatLabel, int]] | None,
    ) -> None:
        """Add motor items to *sizer* two per line. Pair containers go into *container_list*.
        If *key_map* is provided, maps each item key → (cell_panel, value_label, precision)."""
        it = iter(items)
        for left in it:
            right = next(it, None)

            pair = FlatPanel(parent)
            pair.SetBackgroundColour(app_theme.black)
            pair_sizer = wx.BoxSizer(wx.HORIZONTAL)

            l_key, l_label, l_value, l_prec = left
            l_cell, l_val_lbl, _ = self._make_snapshot_row(pair, l_label, self._format_original_position(l_value, l_prec), None)
            pair_sizer.Add(l_cell, 1, wx.EXPAND)
            if key_map is not None:
                key_map[l_key] = (l_cell, l_val_lbl, l_prec)

            if right is not None:
                r_key, r_label, r_value, r_prec = right
                r_cell, r_val_lbl, _ = self._make_snapshot_row(pair, r_label, self._format_original_position(r_value, r_prec), None)
                pair_sizer.AddSpacer(12)
                pair_sizer.Add(r_cell, 1, wx.EXPAND)
                if key_map is not None:
                    key_map[r_key] = (r_cell, r_val_lbl, r_prec)

            pair.SetSizer(pair_sizer)
            sizer.Add(pair, 0, wx.EXPAND | wx.BOTTOM, 2)
            container_list.append(pair)

    @staticmethod
    def _format_original_position(value: float | None, precision: int) -> str:
        if value is None:
            return "—"
        prec = max(0, int(precision))
        try:
            return f"{float(value):.{prec}f}"
        except (TypeError, ValueError):
            return "—"

    def _build_currents_column(self) -> tuple[FlatPanel, wx.BoxSizer, FlatLabel]:
        return self._build_snapshot_column("Current Positions", "_currents_go_btn")

    def _build_bests_column(self) -> tuple[FlatPanel, wx.BoxSizer, FlatLabel]:
        return self._build_snapshot_column("Best Positions", "_bests_go_btn")

    def _build_snapshot_column(self, title: str, go_btn_attr: str) -> tuple[FlatPanel, wx.BoxSizer, FlatLabel]:
        panel = FlatPanel(self)

        sizer = wx.BoxSizer(wx.VERTICAL)

        header_row = wx.BoxSizer(wx.HORIZONTAL)
        header = FlatLabel(panel, label=title)
        header.SetFont(app_theme.scaled_font(12, weight=wx.FONTWEIGHT_BOLD))
        go_btn = FlatButton(panel, "Go", font=app_theme.btn_font())
        go_btn.SetMinSize((36, 22))
        go_btn.Enable(False)
        setattr(self, go_btn_attr, go_btn)
        header_row.Add(header, 0, wx.ALIGN_CENTER_VERTICAL)
        header_row.Add(go_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        sizer.Add(header_row, 0, wx.BOTTOM, 6)

        empty_label = FlatLabel(panel, label="No preview snapshot yet.")
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

    def set_current_positions(
        self,
        positions: list[tuple[str, str, float | None, int]],
        max_intensity: float | None,
        original_max_intensity: float | None,
    ) -> None:
        """Replace the Current Positions list."""
        self._original_max_intensity = original_max_intensity

        for pair in self._current_pair_rows:
            self._currents_sizer.Detach(pair)
            pair.Destroy()
        self._current_pair_rows.clear()
        self._current_motor_rows.clear()
        if self._current_max_row is not None:
            self._currents_sizer.Detach(self._current_max_row)
            self._current_max_row.Destroy()
            self._current_max_row = None
            self._current_max_value = None

        if not positions:
            self._currents_empty_label.Show()
            self._currents_go_btn.Enable(False)
            self._currents_panel.Layout()
            self.Layout()
            return

        self._currents_empty_label.Hide()
        on_go_all = self._make_go_invoker("current", None)
        self._currents_go_btn.SetAction(lambda: on_go_all())
        self._currents_go_btn.Enable(True)

        self._add_motor_pair_rows(
            self._currents_panel,
            self._currents_sizer,
            positions,
            self._current_pair_rows,
            self._current_motor_rows,
        )

        max_text = self._format_max(max_intensity)
        row, value_label, _ = self._make_snapshot_row(self._currents_panel, "Max intensity", max_text, None)
        self._currents_sizer.Add(row, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 2)
        self._current_max_row = row
        self._current_max_value = value_label
        self._apply_max_colour(max_intensity)

        self._currents_panel.Layout()
        self.Layout()

    def clear_current_positions(self) -> None:
        self.set_current_positions([], None, None)

    def update_current_position(self, key: str, value: float | None) -> None:
        """Update a single current motor row in place by its PV key."""
        entry = self._current_motor_rows.get(key)
        if entry is None:
            return
        _row, value_label, precision = entry
        try:
            value_label.SetLabel(self._format_original_position(value, precision))
        except RuntimeError:
            # Widget was destroyed (e.g. teardown raced with a wx.CallAfter).
            self._current_motor_rows.pop(key, None)

    def update_current_max_intensity(self, value: float | None) -> None:
        """Update the live ROI max row and recolour it relative to the original."""
        if self._current_max_value is None:
            return
        try:
            self._current_max_value.SetLabel(self._format_max(value))
        except RuntimeError:
            self._current_max_value = None
            self._current_max_row = None
            return
        self._apply_max_colour(value)

    def set_best_positions(
        self,
        positions: list[tuple[str, str, float | None, int]],
        max_intensity: float | None,
    ) -> None:
        """Replace the Best Positions list. *max_intensity* is the running best ROI max."""
        for pair in self._best_pair_rows:
            self._bests_sizer.Detach(pair)
            pair.Destroy()
        self._best_pair_rows.clear()
        self._best_motor_rows.clear()
        if self._best_max_row is not None:
            self._bests_sizer.Detach(self._best_max_row)
            self._best_max_row.Destroy()
            self._best_max_row = None
            self._best_max_value = None

        if not positions:
            self._bests_empty_label.Show()
            self._bests_go_btn.Enable(False)
            self._bests_panel.Layout()
            self.Layout()
            return

        self._bests_empty_label.Hide()
        on_go_all = self._make_go_invoker("best", None)
        self._bests_go_btn.SetAction(lambda: on_go_all())
        self._bests_go_btn.Enable(True)

        self._add_motor_pair_rows(
            self._bests_panel,
            self._bests_sizer,
            positions,
            self._best_pair_rows,
            self._best_motor_rows,
        )

        row, value_label, _ = self._make_snapshot_row(self._bests_panel, "Max intensity", self._format_max(max_intensity), None)
        self._bests_sizer.Add(row, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 2)
        self._best_max_row = row
        self._best_max_value = value_label
        self._colour_max_label(self._best_max_value, max_intensity)

        self._bests_panel.Layout()
        self.Layout()

    def clear_best_positions(self) -> None:
        self.set_best_positions([], None)

    def update_best_position(self, key: str, value: float | None) -> None:
        entry = self._best_motor_rows.get(key)
        if entry is None:
            return
        _row, value_label, precision = entry
        try:
            value_label.SetLabel(self._format_original_position(value, precision))
        except RuntimeError:
            self._best_motor_rows.pop(key, None)

    def update_best_max_intensity(self, value: float | None) -> None:
        if self._best_max_value is None:
            return
        try:
            self._best_max_value.SetLabel(self._format_max(value))
        except RuntimeError:
            self._best_max_value = None
            self._best_max_row = None
            return
        if self._colour_max_label(self._best_max_value, value) is None:
            self._best_max_value = None
            self._best_max_row = None

    def _apply_max_colour(self, value: float | None) -> None:
        self._colour_max_label(self._current_max_value, value)
        if self._current_max_value is None:
            self._current_max_row = None

    def _colour_max_label(self, label: FlatLabel | None, value: float | None) -> FlatLabel | None:
        """Apply red/green/neutral colour relative to ``self._original_max_intensity``."""
        if label is None:
            return None
        original = self._original_max_intensity
        if value is None or original is None:
            colour = app_theme.foreground
        elif value < original:
            colour = app_theme.red
        elif value > original:
            colour = app_theme.green
        else:
            colour = app_theme.foreground
        try:
            label.SetForegroundColour(colour)
            label.Refresh()
        except RuntimeError:
            return None
        return label

    @staticmethod
    def _format_max(value: float | None) -> str:
        if value is None:
            return "—"
        try:
            return f"{float(value):.4g}"
        except (TypeError, ValueError):
            return "—"

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

    def _on_toggle_clicked(self, _e=None) -> None:
        if self._previewing:
            if self._on_stop_cb is not None:
                self._on_stop_cb()
        else:
            if self._on_start_cb is not None:
                self._on_start_cb()
