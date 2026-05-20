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
    FG_PRIMARY,
    FG_SECONDARY,
    SEP_COLOUR,
    scaled_font,
)
from crystalsweep.ui.view.custom.widgets import DarkCombo, DarkTextCtrl, FlatButton, MUTED_SCHEME

__all__ = ["CollectionSettingsView"]

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
        self._on_add_point_cb: Callable[[], None] | None = None
        self._on_update_selected_cb: Callable[[], None] | None = None

        self._rotation_shorthand: str = ""

        self._build_layout()
        self._refresh_visibility("still")

    def _build_layout(self) -> None:
        label_font = scaled_font(12)
        section_font = scaled_font(13, weight=wx.FONTWEIGHT_BOLD)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.AddSpacer(6)

        section_lbl = wx.StaticText(self, label="Collection Settings")
        section_lbl.SetFont(section_font)
        section_lbl.SetForegroundColour(FG_PRIMARY)
        section_lbl.SetBackgroundColour(BG_CARD)
        outer.Add(section_lbl, 0, wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(6)

        sep_top = wx.Panel(self, size=(-1, 1))
        sep_top.SetBackgroundColour(SEP_COLOUR)
        outer.Add(sep_top, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        outer.AddSpacer(6)

        outer.Add(self._make_row_type(label_font), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(4)

        outer.Add(self._make_row_rotation(label_font), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(4)

        outer.Add(self._make_row_step(label_font), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(8)

        sep_bot = wx.Panel(self, size=(-1, 1))
        sep_bot.SetBackgroundColour(SEP_COLOUR)
        outer.Add(sep_bot, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        outer.AddSpacer(6)

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

    def _make_row_type(self, label_font: wx.Font) -> wx.Sizer:
        row = wx.BoxSizer(wx.HORIZONTAL)
        lbl = self._field_label("Type", label_font)
        lbl.SetMinSize((70, -1))
        self._type_combo = DarkCombo(
            self,
            choices=list(SCAN_TYPES),
            selection=0,
            choice_colours=_TYPE_COLOURS,
        )
        self._type_combo.Bind(wx.EVT_CHOICE, self._on_type_choice)
        exp_lbl = self._field_label("Exp. (s)", label_font)
        self._exposure_ctrl = DarkTextCtrl(self, value="1.0", parent_bg=BG_CARD)
        self._exposure_ctrl.set_restrict_to_float(True)
        self._exposure_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_exposure_enter)
        self._exposure_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_exposure_enter)
        row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(6)
        row.Add(self._type_combo, 1, wx.EXPAND)
        row.AddSpacer(10)
        row.Add(exp_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(6)
        row.Add(self._exposure_ctrl, 1, wx.EXPAND)
        return row

    def _make_row_rotation(self, label_font: wx.Font) -> wx.Sizer:
        self._rotation_row = wx.BoxSizer(wx.HORIZONTAL)
        self._rot_start_lbl = self._field_label("Start", label_font)
        self._rot_start_ctrl = DarkTextCtrl(self, value="0.0", parent_bg=BG_CARD)
        self._rot_start_ctrl.set_restrict_to_float(True)
        self._rot_start_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_rot_start_enter)
        self._rot_start_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_rot_start_enter)
        self._rot_end_lbl = self._field_label("End", label_font)
        self._rot_end_ctrl = DarkTextCtrl(self, value="180.0", parent_bg=BG_CARD)
        self._rot_end_ctrl.set_restrict_to_float(True)
        self._rot_end_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_rot_end_enter)
        self._rot_end_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_rot_end_enter)
        self._rot_range_lbl = self._field_label("Range", label_font)
        self._rot_range_ctrl = DarkTextCtrl(self, value="180.0", parent_bg=BG_CARD)
        self._rot_range_ctrl.set_restrict_to_float(True)
        self._rot_range_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_rot_range_enter)
        self._rot_range_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_rot_range_enter)
        self._rotation_row.Add(self._rot_start_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        self._rotation_row.AddSpacer(4)
        self._rotation_row.Add(self._rot_start_ctrl, 1, wx.EXPAND)
        self._rotation_row.AddSpacer(6)
        self._rotation_row.Add(self._rot_end_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        self._rotation_row.AddSpacer(4)
        self._rotation_row.Add(self._rot_end_ctrl, 1, wx.EXPAND)
        self._rotation_row.AddSpacer(6)
        self._rotation_row.Add(self._rot_range_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        self._rotation_row.AddSpacer(4)
        self._rotation_row.Add(self._rot_range_ctrl, 1, wx.EXPAND)
        return self._rotation_row

    def _make_row_step(self, label_font: wx.Font) -> wx.Sizer:
        self._step_row = wx.BoxSizer(wx.HORIZONTAL)
        lbl = self._field_label("Step (°)", label_font)
        lbl.SetMinSize((70, -1))
        self._step_ctrl = DarkTextCtrl(self, value="1.0", parent_bg=BG_CARD)
        self._step_ctrl.set_restrict_to_float(True)
        self._step_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_step_enter)
        self._step_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_step_enter)
        self._step_row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        self._step_row.AddSpacer(6)
        self._step_row.Add(self._step_ctrl, 1, wx.EXPAND)
        return self._step_row

    def _refresh_visibility(self, scan_type: ScanType) -> None:
        show_rotation = scan_type in ("wide", "step")
        show_step = scan_type == "step"

        for item in self._rotation_row.GetChildren():
            w = item.GetWindow()
            if w:
                w.Show(show_rotation)

        for item in self._step_row.GetChildren():
            w = item.GetWindow()
            if w:
                w.Show(show_step)

        self._update_rotation_labels(scan_type)
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

    def set_scan_type(self, scan_type: ScanType) -> None:
        if scan_type in SCAN_TYPES:
            self._type_combo.SetSelection(list(SCAN_TYPES).index(scan_type))
            self._refresh_visibility(scan_type)

    def set_exposure(self, value: float) -> None:
        self._exposure_ctrl.SetValue(f"{value}")

    def set_rotation_start(self, value: float) -> None:
        self._rot_start_ctrl.SetValue(f"{value}")

    def set_rotation_end(self, value: float) -> None:
        self._rot_end_ctrl.SetValue(f"{value}")

    def set_rotation_range(self, value: float) -> None:
        self._rot_range_ctrl.SetValue(f"{value}")

    def set_step_size(self, value: float) -> None:
        self._step_ctrl.SetValue(f"{value}")

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

    def _on_add_clicked(self) -> None:
        if self._on_add_point_cb is not None:
            self._on_add_point_cb()

    def _on_update_selected_clicked(self) -> None:
        if self._on_update_selected_cb is not None:
            self._on_update_selected_cb()

    def _fire_float(self, ctrl: DarkTextCtrl, cb: Callable[[float], None] | None) -> None:
        if cb is None:
            return
        try:
            cb(float(ctrl.GetValue()))
        except ValueError:
            pass
