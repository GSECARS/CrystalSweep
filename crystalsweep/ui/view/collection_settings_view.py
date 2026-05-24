#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/collection_settings_view.py
# ----------------------------------------------------------------------------------
# Purpose:
# Collection settings panel placed between file settings and the collection table.
# Shows a scan-type dropdown and dynamically shows/hides the relevant input fields:
#   still  -> exposure (s)
#   wide   -> exposure + rotation start / end / range (labelled with shorthand)
#   step   -> exposure + rotation start / end / range + step size (deg)
# An "Add point" button appends the current settings as a new collection row.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from typing import Callable

import wx

from crystalsweep.model.collection_model import SCAN_TYPES, ScanType
from crystalsweep.ui.view.custom.theme import (
    BG_CARD,
    BG_ELEVATED,
    BG_SURFACE,
    FG_PRIMARY,
    FG_SECONDARY,
    SEP_COLOUR,
    scaled_font,
)
from crystalsweep.ui.view.custom.widgets import DarkCombo, DarkTextCtrl, DarkToggle, FlatButton, MUTED_SCHEME

__all__ = ["CollectionSettingsView"]

_MAP_PRESETS: tuple[tuple[int, int], ...] = (
    (5, 1),
    (10, 1),
    (20, 1),
    (20, 2),
    (30, 2),
    (50, 5),
)

_TABLE_ROW_H   = 28
_TABLE_HDR_H   = 26
_TABLE_BORDER  = wx.Colour(50, 50, 56)
_TABLE_HDR_BG  = wx.Colour(22, 22, 26)
_TABLE_ROW_ALT = wx.Colour(32, 32, 36)
_BOX_S         = 12
_BOX_R         = 3
_CHECK_FG      = wx.Colour(72, 199, 116)
_CHECK_BG      = wx.Colour(38, 38, 42)
_CHECK_BORDER  = wx.Colour(80, 80, 92)
_CHECK_W       = 26
_PAD           = 5


def _draw_checkbox(gc: wx.GraphicsContext, cx: int, cy: int, checked: bool, grayed: bool = False) -> None:
    r = wx.Rect(cx - _BOX_S // 2, cy - _BOX_S // 2, _BOX_S, _BOX_S)
    if grayed:
        fill = wx.Colour(55, 55, 60)
        border = wx.Colour(70, 70, 78)
    elif checked:
        fill = _CHECK_FG
        border = _CHECK_FG
    else:
        fill = _CHECK_BG
        border = _CHECK_BORDER
    gc.SetBrush(wx.Brush(fill))
    gc.SetPen(wx.Pen(border, 1))
    gc.DrawRoundedRectangle(r.x, r.y, r.width, r.height, _BOX_R)
    if checked and not grayed:
        gc.SetPen(wx.Pen(wx.Colour(255, 255, 255), 1))
        x, y = r.x, r.y
        s = _BOX_S
        gc.StrokeLines([
            wx.Point2D(x + s * 0.2, y + s * 0.5),
            wx.Point2D(x + s * 0.42, y + s * 0.72),
            wx.Point2D(x + s * 0.8, y + s * 0.28),
        ])


class _MapHeaderRow(wx.Panel):
    """Painted header for the map axes table."""

    _LABELS = ("", "Motor", "Start", "End", "Step", "#Pts")

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, size=(-1, _TABLE_HDR_H), style=wx.BORDER_NONE)
        self.SetBackgroundColour(_TABLE_HDR_BG)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, lambda _e: self.Refresh())

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(_TABLE_HDR_BG))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        widths = _col_widths(w)
        font = scaled_font(12, weight=wx.FONTWEIGHT_BOLD)
        gc.SetFont(font, FG_SECONDARY)
        gc.SetPen(wx.Pen(_TABLE_BORDER, 1))
        x = 0
        for i, (label, cw) in enumerate(zip(self._LABELS, widths)):
            if label:
                tw, th = gc.GetTextExtent(label)
                gc.DrawText(label, x + (cw - tw) / 2, (h - th) / 2)
            if i < len(widths) - 1:
                gc.StrokeLine(x + cw, 0, x + cw, h)
            x += cw
        gc.SetPen(wx.Pen(_TABLE_BORDER, 1))
        gc.StrokeLine(0, h - 1, w, h - 1)


class _MapDataRow(wx.Panel):
    """One painted data row in the map axes table with inline controls."""

    def __init__(
        self,
        parent: wx.Window,
        bg: wx.Colour,
        row_index: int,
    ) -> None:
        super().__init__(parent, size=(-1, _TABLE_ROW_H), style=wx.BORDER_NONE)
        self.SetBackgroundColour(bg)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self._row_index = row_index
        self._optional = row_index > 0
        self._enabled = not self._optional

        self.motor_combo = DarkCombo(self, choices=[], selection=0)
        self.start_ctrl = DarkTextCtrl(self, value="0.0", parent_bg=bg)
        self.start_ctrl.set_restrict_to_float(True)
        self.end_ctrl = DarkTextCtrl(self, value="1.0", parent_bg=bg)
        self.end_ctrl.set_restrict_to_float(True)
        self.step_ctrl = DarkTextCtrl(self, value="0.1", parent_bg=bg)
        self.step_ctrl.set_restrict_to_float(True)
        self.points_ctrl = DarkTextCtrl(self, value="11", parent_bg=bg)

        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, self._on_size)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_click)

        self._reposition()
        self._apply_enabled()

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(self.GetBackgroundColour()))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        cx = _CHECK_W // 2
        cy = h // 2
        _draw_checkbox(gc, cx, cy, self._enabled, grayed=not self._optional)
        gc.SetPen(wx.Pen(_TABLE_BORDER, 1))
        gc.StrokeLine(0, h - 1, w, h - 1)
        widths = _col_widths(w)
        x = 0
        for i, cw in enumerate(widths[:-1]):
            x += cw
            gc.StrokeLine(x, 0, x, h)

    def _on_size(self, event: wx.SizeEvent) -> None:
        self._reposition()
        self.Refresh()
        event.Skip()

    def _on_click(self, event: wx.MouseEvent) -> None:
        if not self._optional:
            return
        if event.GetX() < _CHECK_W:
            self._enabled = not self._enabled
            self._apply_enabled()
            self.Refresh()
            wx.PostEvent(self, wx.CommandEvent(wx.EVT_CHECKBOX.typeId, self.GetId()))
        event.Skip()

    def _reposition(self) -> None:
        w, _ = self.GetClientSize()
        if w <= 0:
            return
        widths = _col_widths(w)
        ctrl_h = _TABLE_ROW_H - 8
        y = 4
        x = widths[0]
        for ctrl, cw in zip(
            (self.motor_combo, self.start_ctrl, self.end_ctrl, self.step_ctrl, self.points_ctrl),
            widths[1:],
        ):
            ctrl.SetSize(x + _PAD, y, cw - _PAD * 2, ctrl_h)
            x += cw

    def _apply_enabled(self) -> None:
        for ctrl in (self.motor_combo, self.start_ctrl, self.end_ctrl, self.step_ctrl, self.points_ctrl):
            ctrl.Enable(self._enabled)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, value: bool) -> None:
        if not self._optional:
            return
        self._enabled = value
        self._apply_enabled()
        self.Refresh()

    def set_choices(self, choices: list[str]) -> None:
        self.motor_combo.SetChoices(choices)

    def set_motor(self, shorthand: str) -> None:
        choices = self.motor_combo._choices
        if shorthand in choices:
            self.motor_combo.SetSelection(choices.index(shorthand))

    def get_motor(self) -> str:
        return self.motor_combo.GetStringSelection()


def _col_widths(total_w: int) -> list[int]:
    """Return pixel widths for [checkbox, motor, start, end, step, #pts] columns."""
    remaining = max(0, total_w - _CHECK_W)
    motor_w = max(60, remaining * 3 // 10)
    field_w = max(30, (remaining - motor_w) // 4)
    last_w = remaining - motor_w - field_w * 3
    return [_CHECK_W, motor_w, field_w, field_w, field_w, last_w]


class _MapTable(wx.Panel):
    """Compact two-row table for map axes, styled like the collection table."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self.SetBackgroundColour(BG_CARD)

        self._header = _MapHeaderRow(self)
        self.row1 = _MapDataRow(self, BG_CARD, row_index=0)
        self.row2 = _MapDataRow(self, _TABLE_ROW_ALT, row_index=1)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self._header, 0, wx.EXPAND)
        sizer.Add(self.row1, 0, wx.EXPAND)
        sizer.Add(self.row2, 0, wx.EXPAND)
        self.SetSizer(sizer)

_TYPE_COLOURS: dict[str, wx.Colour] = {
    "still": wx.Colour(99, 179, 237),
    "step": wx.Colour(72, 199, 116),
    "wide": wx.Colour(246, 173, 85),
}


class CollectionSettingsView(wx.Panel):
    """Collection settings panel: scan type selector and dynamic parameter fields."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.SetBackgroundColour(BG_CARD)

        self._on_scan_type_changed_cb: Callable[[ScanType], None] | None = None
        self._on_exposure_changed_cb: Callable[[float], None] | None = None
        self._on_rotation_start_changed_cb: Callable[[float], None] | None = None
        self._on_rotation_end_changed_cb: Callable[[float], None] | None = None
        self._on_rotation_range_changed_cb: Callable[[float], None] | None = None
        self._on_step_size_changed_cb: Callable[[float], None] | None = None
        self._on_map_changed_cb: Callable[[bool], None] | None = None
        self._on_wide_flip_changed_cb: Callable[[bool], None] | None = None
        self._on_map_motor_changed_cb: Callable[[str], None] | None = None
        self._on_map_start_changed_cb: Callable[[float], None] | None = None
        self._on_map_end_changed_cb: Callable[[float], None] | None = None
        self._on_map_step_changed_cb: Callable[[float], None] | None = None
        self._on_map_points_changed_cb: Callable[[int], None] | None = None
        self._on_map2_enabled_changed_cb: Callable[[bool], None] | None = None
        self._on_map2_motor_changed_cb: Callable[[str], None] | None = None
        self._on_map2_start_changed_cb: Callable[[float], None] | None = None
        self._on_map2_end_changed_cb: Callable[[float], None] | None = None
        self._on_map2_step_changed_cb: Callable[[float], None] | None = None
        self._on_map2_points_changed_cb: Callable[[int], None] | None = None
        self._on_add_point_cb: Callable[[], None] | None = None
        self._on_update_selected_cb: Callable[[], None] | None = None

        self._rotation_shorthand: str = ""

        self._build_layout()
        self._refresh_visibility("still")

    def _build_layout(self) -> None:
        label_font = scaled_font(12)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.AddSpacer(2)

        outer.Add(self._make_row_all(label_font), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(4)

        outer.Add(self._make_map_table(), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self._map_table.Hide()
        self._flip_toggle.Hide()

        outer.Add(self._make_map_presets(label_font), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 10)
        self._map_presets_panel.Hide()
        outer.AddSpacer(8)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self._add_btn = FlatButton(self, "+ Add point")
        self._add_btn.SetMinSize((-1, 28))
        self._add_btn.set_action(self._on_add_clicked)
        self._update_selected_btn = FlatButton(self, "Update selected", color_scheme=MUTED_SCHEME)
        self._update_selected_btn.SetMinSize((-1, 28))
        self._update_selected_btn.set_action(self._on_update_selected_clicked)
        btn_row.Add(self._add_btn, 1, wx.EXPAND | wx.RIGHT, 4)
        btn_row.Add(self._update_selected_btn, 1, wx.EXPAND)
        outer.Add(btn_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(6)

        self.SetSizer(outer)

    def _field_label(self, text: str, font: wx.Font) -> wx.StaticText:
        lbl = wx.StaticText(self, label=text)
        lbl.SetFont(font)
        lbl.SetForegroundColour(FG_SECONDARY)
        lbl.SetBackgroundColour(BG_CARD)
        return lbl

    def _make_row_all(self, label_font: wx.Font) -> wx.Sizer:
        row = wx.BoxSizer(wx.HORIZONTAL)

        type_lbl = self._field_label("Type", label_font)
        self._type_combo = DarkCombo(
            self,
            choices=list(SCAN_TYPES),
            selection=0,
            choice_colours=_TYPE_COLOURS,
        )
        self._type_combo.Bind(wx.EVT_CHOICE, self._on_type_choice)
        row.Add(type_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(6)
        row.Add(self._type_combo, 2, wx.EXPAND)
        row.AddSpacer(8)

        exp_lbl = self._field_label("Exp. (s)", label_font)
        self._exposure_ctrl = DarkTextCtrl(self, value="1.0", parent_bg=BG_CARD)
        self._exposure_ctrl.set_restrict_to_float(True)
        self._exposure_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_exposure_enter)
        self._exposure_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_exposure_enter)
        row.Add(exp_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(4)
        row.Add(self._exposure_ctrl, 2, wx.EXPAND)
        row.AddSpacer(8)

        self._rot_start_lbl = self._field_label("Start", label_font)
        self._rot_start_ctrl = DarkTextCtrl(self, value="0.0", parent_bg=BG_CARD)
        self._rot_start_ctrl.set_restrict_to_float(True)
        self._rot_start_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_rot_start_enter)
        self._rot_start_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_rot_start_enter)
        row.Add(self._rot_start_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(4)
        row.Add(self._rot_start_ctrl, 2, wx.EXPAND)
        row.AddSpacer(8)

        self._rot_end_lbl = self._field_label("End", label_font)
        self._rot_end_ctrl = DarkTextCtrl(self, value="180.0", parent_bg=BG_CARD)
        self._rot_end_ctrl.set_restrict_to_float(True)
        self._rot_end_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_rot_end_enter)
        self._rot_end_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_rot_end_enter)
        row.Add(self._rot_end_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(4)
        row.Add(self._rot_end_ctrl, 2, wx.EXPAND)
        row.AddSpacer(8)

        self._rot_range_lbl = self._field_label("Range", label_font)
        self._rot_range_ctrl = DarkTextCtrl(self, value="180.0", parent_bg=BG_CARD)
        self._rot_range_ctrl.set_restrict_to_float(True)
        self._rot_range_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_rot_range_enter)
        self._rot_range_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_rot_range_enter)
        row.Add(self._rot_range_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(4)
        row.Add(self._rot_range_ctrl, 2, wx.EXPAND)
        row.AddSpacer(8)

        self._step_lbl = self._field_label("Step (°)", label_font)
        self._step_ctrl = DarkTextCtrl(self, value="1.0", parent_bg=BG_CARD)
        self._step_ctrl.set_restrict_to_float(True)
        self._step_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_step_enter)
        self._step_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_step_enter)
        row.Add(self._step_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(4)
        row.Add(self._step_ctrl, 2, wx.EXPAND)
        row.AddSpacer(8)

        self._map_toggle = DarkToggle(self, "Map")
        self._map_toggle.SetBackgroundColour(BG_CARD)
        self._map_toggle.Bind(wx.EVT_CHECKBOX, self._on_map_toggle_changed)
        row.Add(self._map_toggle, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(8)

        self._flip_toggle = DarkToggle(self, "Flip", value=True)
        self._flip_toggle.SetBackgroundColour(BG_CARD)
        self._flip_toggle.Bind(wx.EVT_CHECKBOX, self._on_flip_toggle_changed)
        row.Add(self._flip_toggle, 0, wx.ALIGN_CENTER_VERTICAL)

        self._scan_row = row
        return row

    def _make_map_presets(self, label_font: wx.Font) -> wx.Window:
        self._map_presets_panel = wx.Panel(self)
        self._map_presets_panel.SetBackgroundColour(BG_CARD)
        lbl = wx.StaticText(self._map_presets_panel, label="Presets")
        lbl.SetFont(label_font)
        lbl.SetForegroundColour(FG_SECONDARY)
        lbl.SetBackgroundColour(BG_CARD)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        for size_um, step_um in _MAP_PRESETS:
            pts = size_um // step_um + 1
            label = f"{size_um}×{size_um} / {step_um}µm"
            btn = FlatButton(self._map_presets_panel, label, color_scheme=MUTED_SCHEME)
            btn.SetMinSize((-1, 22))
            btn.set_action(lambda s=size_um, st=step_um, p=pts: self._apply_map_preset(s, st, p))
            row.Add(btn, 1, wx.EXPAND | wx.RIGHT, 4)
        self._map_presets_panel.SetSizer(row)
        return self._map_presets_panel

    def _apply_map_preset(self, size_um: int, step_um: int, points: int) -> None:
        half = size_um / 2.0
        for row in (self._map_table.row1, self._map_table.row2):
            row.start_ctrl.SetValue(f"{-half:.1f}")
            row.end_ctrl.SetValue(f"{half:.1f}")
            row.step_ctrl.SetValue(f"{step_um:.1f}")
            row.points_ctrl.SetValue(str(points))
        if self._on_map_start_changed_cb:
            self._on_map_start_changed_cb(-half)
        if self._on_map_end_changed_cb:
            self._on_map_end_changed_cb(half)
        if self._on_map_step_changed_cb:
            self._on_map_step_changed_cb(float(step_um))
        if self._on_map_points_changed_cb:
            self._on_map_points_changed_cb(points)
        if self._on_map2_start_changed_cb:
            self._on_map2_start_changed_cb(-half)
        if self._on_map2_end_changed_cb:
            self._on_map2_end_changed_cb(half)
        if self._on_map2_step_changed_cb:
            self._on_map2_step_changed_cb(float(step_um))
        if self._on_map2_points_changed_cb:
            self._on_map2_points_changed_cb(points)

    def _make_map_table(self) -> wx.Window:
        self._map_table = _MapTable(self)
        r1, r2 = self._map_table.row1, self._map_table.row2
        r1.motor_combo.Bind(wx.EVT_CHOICE, self._on_map1_motor_choice)
        r1.start_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_map_start_enter)
        r1.start_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_map_start_enter)
        r1.end_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_map_end_enter)
        r1.end_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_map_end_enter)
        r1.step_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_map_step_enter)
        r1.step_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_map_step_enter)
        r1.points_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_map_points_enter)
        r1.points_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_map_points_enter)
        r2.Bind(wx.EVT_CHECKBOX, self._on_map2_enable_changed)
        r2.motor_combo.Bind(wx.EVT_CHOICE, self._on_map2_motor_choice)
        r2.start_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_map2_start_enter)
        r2.start_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_map2_start_enter)
        r2.end_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_map2_end_enter)
        r2.end_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_map2_end_enter)
        r2.step_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_map2_step_enter)
        r2.step_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_map2_step_enter)
        r2.points_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_map2_points_enter)
        r2.points_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_map2_points_enter)
        return self._map_table

    def _refresh_visibility(self, scan_type: ScanType) -> None:
        show_rotation = scan_type in ("wide", "step")
        show_step = scan_type == "step"

        for w in (self._rot_start_lbl, self._rot_start_ctrl,
                  self._rot_end_lbl, self._rot_end_ctrl,
                  self._rot_range_lbl, self._rot_range_ctrl):
            w.Show(show_rotation)

        self._step_lbl.Show(show_step)
        self._step_ctrl.Show(show_step)

        self._update_rotation_labels(scan_type)
        self._refresh_map_row()
        self._refresh_flip_visibility(scan_type)
        self.Layout()
        self.GetParent().Layout()

    def _refresh_flip_visibility(self, scan_type: ScanType | None = None) -> None:
        if scan_type is None:
            scan_type = SCAN_TYPES[self._type_combo._selection]
        show = self._map_toggle.GetValue() and scan_type == "wide"
        self._flip_toggle.Show(show)
        self.Layout()
        self.GetParent().Layout()

    def _refresh_map_row(self) -> None:
        show = self._map_toggle.GetValue()
        self._map_table.Show(show)
        self._map_presets_panel.Show(show)
        self._add_btn.SetLabel("+ Add map points" if show else "+ Add point")
        self._refresh_flip_visibility()
        self.Layout()
        self.GetParent().Layout()

    def _update_rotation_labels(self, scan_type: ScanType) -> None:
        prefix = self._rotation_shorthand.capitalize() if self._rotation_shorthand else "Rot"
        self._rot_start_lbl.SetLabel(f"{prefix} start")
        self._rot_end_lbl.SetLabel(f"{prefix} end")
        self._rot_range_lbl.SetLabel(f"{prefix} range")

    def set_rotation_shorthand(self, shorthand: str) -> None:
        self._rotation_shorthand = shorthand
        current_type = SCAN_TYPES[self._type_combo._selection]
        self._update_rotation_labels(current_type)

    def set_enabled(self, enabled: bool) -> None:
        for ctrl in (
            self._type_combo, self._exposure_ctrl,
            self._rot_start_ctrl, self._rot_end_ctrl, self._rot_range_ctrl,
            self._step_ctrl, self._add_btn, self._update_selected_btn,
        ):
            ctrl.Enable(enabled)
        self._map_toggle.SetLocked(not enabled)
        self._flip_toggle.SetLocked(not enabled)

    def set_scan_type(self, scan_type: ScanType) -> None:
        if scan_type in SCAN_TYPES:
            self._type_combo.SetSelection(list(SCAN_TYPES).index(scan_type))
            self._refresh_visibility(scan_type)

    def set_exposure(self, value: float) -> None:
        self._exposure_ctrl.SetValue(f"{value}")

    def set_map(self, value: bool) -> None:
        self._map_toggle.SetValue(value)

    def set_wide_flip(self, value: bool) -> None:
        self._flip_toggle.SetValue(value)

    def set_rotation_start(self, value: float) -> None:
        self._rot_start_ctrl.SetValue(f"{value}")

    def set_rotation_end(self, value: float) -> None:
        self._rot_end_ctrl.SetValue(f"{value}")

    def set_rotation_range(self, value: float) -> None:
        self._rot_range_ctrl.SetValue(f"{value}")

    def set_step_size(self, value: float) -> None:
        self._step_ctrl.SetValue(f"{value}")

    def set_map_motors(self, motor_names: list[str]) -> None:
        self._map_table.row1.set_choices(motor_names)
        selected1 = self._map_table.row1.get_motor()
        self._map_table.row2.set_choices([m for m in motor_names if m != selected1])

    def set_map_motor(self, shorthand: str) -> None:
        self._map_table.row1.set_motor(shorthand)
        selected1 = self._map_table.row1.get_motor()
        all_choices = self._map_table.row1.motor_combo._choices
        self._map_table.row2.set_choices([m for m in all_choices if m != selected1])

    def set_map_start(self, value: float) -> None:
        self._map_table.row1.start_ctrl.SetValue(f"{value}")

    def set_map_end(self, value: float) -> None:
        self._map_table.row1.end_ctrl.SetValue(f"{value}")

    def set_map_step(self, value: float) -> None:
        self._map_table.row1.step_ctrl.SetValue(f"{value}")

    def set_map_points(self, value: int) -> None:
        self._map_table.row1.points_ctrl.SetValue(str(value))

    def set_map2_enabled(self, value: bool) -> None:
        self._map_table.row2.set_enabled(value)

    def set_map2_motor(self, shorthand: str) -> None:
        self._map_table.row2.set_motor(shorthand)

    def set_map2_start(self, value: float) -> None:
        self._map_table.row2.start_ctrl.SetValue(f"{value}")

    def set_map2_end(self, value: float) -> None:
        self._map_table.row2.end_ctrl.SetValue(f"{value}")

    def set_map2_step(self, value: float) -> None:
        self._map_table.row2.step_ctrl.SetValue(f"{value}")

    def set_map2_points(self, value: int) -> None:
        self._map_table.row2.points_ctrl.SetValue(str(value))

    def bind_scan_type_changed(self, callback: Callable[[ScanType], None]) -> None:
        self._on_scan_type_changed_cb = callback

    def bind_exposure_changed(self, callback: Callable[[float], None]) -> None:
        self._on_exposure_changed_cb = callback

    def bind_rotation_start_changed(self, callback: Callable[[float], None]) -> None:
        self._on_rotation_start_changed_cb = callback

    def bind_rotation_end_changed(self, callback: Callable[[float], None]) -> None:
        self._on_rotation_end_changed_cb = callback

    def bind_rotation_range_changed(self, callback: Callable[[float], None]) -> None:
        self._on_rotation_range_changed_cb = callback

    def bind_step_size_changed(self, callback: Callable[[float], None]) -> None:
        self._on_step_size_changed_cb = callback

    def bind_map_changed(self, callback: Callable[[bool], None]) -> None:
        self._on_map_changed_cb = callback

    def bind_wide_flip_changed(self, callback: Callable[[bool], None]) -> None:
        self._on_wide_flip_changed_cb = callback

    def bind_map_motor_changed(self, callback: Callable[[str], None]) -> None:
        self._on_map_motor_changed_cb = callback

    def bind_map_start_changed(self, callback: Callable[[float], None]) -> None:
        self._on_map_start_changed_cb = callback

    def bind_map_end_changed(self, callback: Callable[[float], None]) -> None:
        self._on_map_end_changed_cb = callback

    def bind_map_step_changed(self, callback: Callable[[float], None]) -> None:
        self._on_map_step_changed_cb = callback

    def bind_map_points_changed(self, callback: Callable[[int], None]) -> None:
        self._on_map_points_changed_cb = callback

    def bind_map2_enabled_changed(self, callback: Callable[[bool], None]) -> None:
        self._on_map2_enabled_changed_cb = callback

    def bind_map2_motor_changed(self, callback: Callable[[str], None]) -> None:
        self._on_map2_motor_changed_cb = callback

    def bind_map2_start_changed(self, callback: Callable[[float], None]) -> None:
        self._on_map2_start_changed_cb = callback

    def bind_map2_end_changed(self, callback: Callable[[float], None]) -> None:
        self._on_map2_end_changed_cb = callback

    def bind_map2_step_changed(self, callback: Callable[[float], None]) -> None:
        self._on_map2_step_changed_cb = callback

    def bind_map2_points_changed(self, callback: Callable[[int], None]) -> None:
        self._on_map2_points_changed_cb = callback

    def bind_add_point(self, callback: Callable[[], None]) -> None:
        self._on_add_point_cb = callback

    def bind_update_selected(self, callback: Callable[[], None]) -> None:
        self._on_update_selected_cb = callback

    def _on_type_choice(self, value: str) -> None:
        scan_type: ScanType = value if value in SCAN_TYPES else "still"
        self._refresh_visibility(scan_type)
        if self._on_scan_type_changed_cb is not None:
            self._on_scan_type_changed_cb(scan_type)

    def _on_exposure_enter(self, event: wx.Event) -> None:
        self._fire_float(self._exposure_ctrl, self._on_exposure_changed_cb)
        event.Skip()

    def _on_rot_start_enter(self, event: wx.Event) -> None:
        self._fire_float(self._rot_start_ctrl, self._on_rotation_start_changed_cb)
        event.Skip()

    def _on_rot_end_enter(self, event: wx.Event) -> None:
        self._fire_float(self._rot_end_ctrl, self._on_rotation_end_changed_cb)
        event.Skip()

    def _on_rot_range_enter(self, event: wx.Event) -> None:
        self._fire_float(self._rot_range_ctrl, self._on_rotation_range_changed_cb)
        event.Skip()

    def _on_step_enter(self, event: wx.Event) -> None:
        self._fire_float(self._step_ctrl, self._on_step_size_changed_cb)
        event.Skip()

    def _on_map_toggle_changed(self, event: wx.Event) -> None:
        value = self._map_toggle.GetValue()
        self._fire(self._on_map_changed_cb, value)
        self._refresh_map_row()

    def _on_flip_toggle_changed(self, event: wx.Event) -> None:
        self._fire(self._on_wide_flip_changed_cb, self._flip_toggle.GetValue())

    def _on_map1_motor_choice(self, value: str) -> None:
        self._fire(self._on_map_motor_changed_cb, value)
        all_choices = self._map_table.row1.motor_combo._choices
        map2_choices = [m for m in all_choices if m != value]
        current2 = self._map_table.row2.get_motor()
        self._map_table.row2.set_choices(map2_choices)
        if current2 and current2 in map2_choices:
            self._map_table.row2.set_motor(current2)

    def _on_map_start_enter(self, event: wx.Event) -> None:
        self._fire_float(self._map_table.row1.start_ctrl, self._on_map_start_changed_cb)
        event.Skip()

    def _on_map_end_enter(self, event: wx.Event) -> None:
        self._fire_float(self._map_table.row1.end_ctrl, self._on_map_end_changed_cb)
        event.Skip()

    def _on_map_step_enter(self, event: wx.Event) -> None:
        self._fire_float(self._map_table.row1.step_ctrl, self._on_map_step_changed_cb)
        event.Skip()

    def _on_map_points_enter(self, event: wx.Event) -> None:
        if self._on_map_points_changed_cb is None:
            event.Skip()
            return
        try:
            self._on_map_points_changed_cb(int(self._map_table.row1.points_ctrl.GetValue()))
        except ValueError:
            pass
        event.Skip()

    def _on_map2_enable_changed(self, event: wx.Event) -> None:
        self._fire(self._on_map2_enabled_changed_cb, self._map_table.row2.enabled)

    def _on_map2_motor_choice(self, value: str) -> None:
        self._fire(self._on_map2_motor_changed_cb, value)

    def _on_map2_start_enter(self, event: wx.Event) -> None:
        self._fire_float(self._map_table.row2.start_ctrl, self._on_map2_start_changed_cb)
        event.Skip()

    def _on_map2_end_enter(self, event: wx.Event) -> None:
        self._fire_float(self._map_table.row2.end_ctrl, self._on_map2_end_changed_cb)
        event.Skip()

    def _on_map2_step_enter(self, event: wx.Event) -> None:
        self._fire_float(self._map_table.row2.step_ctrl, self._on_map2_step_changed_cb)
        event.Skip()

    def _on_map2_points_enter(self, event: wx.Event) -> None:
        if self._on_map2_points_changed_cb is None:
            event.Skip()
            return
        try:
            self._on_map2_points_changed_cb(int(self._map_table.row2.points_ctrl.GetValue()))
        except ValueError:
            pass
        event.Skip()

    def _on_add_clicked(self) -> None:
        if self._on_add_point_cb is not None:
            self._on_add_point_cb()

    def _on_update_selected_clicked(self) -> None:
        if self._on_update_selected_cb is not None:
            self._on_update_selected_cb()

    def _fire(self, cb, value=None) -> None:
        if cb is None:
            return
        if value is None:
            cb()
        else:
            cb(value)

    def _fire_float(self, ctrl: DarkTextCtrl, cb: Callable[[float], None] | None) -> None:
        if cb is None:
            return
        try:
            cb(float(ctrl.GetValue()))
        except ValueError:
            pass
