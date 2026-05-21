#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/collection_table_view.py
# ----------------------------------------------------------------------------------
# Purpose:
# Collection-points table panel with a fully custom-painted dark scrollbar and
# per-row selection checkbox.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from typing import Callable

import wx

from crystalsweep.model.collection_model import SCAN_TYPES, CollectionPoint, ScanType
from crystalsweep.model.validation import MotorPositionValidator
from crystalsweep.ui.view.custom.theme import ACCENT, BG_CARD, BG_ELEVATED, BG_SURFACE, FG_PRIMARY, SEP_COLOUR, scaled_font
from crystalsweep.ui.view.custom.widgets import DANGER_SCHEME, MUTED_SCHEME, DarkCombo, DarkScrollBar, DarkTextCtrl, FlatButton

__all__ = ["CollectionTableView"]

_TYPE_COLOURS: dict[str, wx.Colour] = {"still": wx.Colour(99, 179, 237), "step": wx.Colour(72, 199, 116), "wide": wx.Colour(246, 173, 85)}

_ROW_H = 28
_HEADER_H = 32
_CHECK_W = 32
_EXT_W = 90
_TYPE_W = 76
_REMOVE_W = 28
_GET_W = 46
_MOVE_W = 50
_MOTOR_W = 78
_ROT_W = 76
_STEP_W = 68
_TIME_W = 68
_BORDER = wx.Colour(50, 50, 56)
_ROW_ALT = wx.Colour(32, 32, 36)
_HEADER_BG = wx.Colour(22, 22, 26)
_CELL_PAD = 6

_SB_W = 8

_BOX_S = 14
_BOX_R = 3
_CHECK_FG = wx.Colour(72, 199, 116)
_CHECK_BG = wx.Colour(38, 38, 42)
_CHECK_BORDER = wx.Colour(80, 80, 92)


class _RowsViewport(wx.Panel):
    """Clipping panel — scrolls by repositioning the inner rows panel."""

    def __init__(self, parent: wx.Window, on_scroll_changed: Callable[[float, float], None]) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self.SetBackgroundColour(BG_CARD)

        self._on_scroll_changed = on_scroll_changed
        self._scroll_offset: int = 0

        self._rows_panel = wx.Panel(self, style=wx.BORDER_NONE)
        self._rows_panel.SetBackgroundColour(BG_CARD)
        self._rows_sizer = wx.BoxSizer(wx.VERTICAL)
        self._rows_panel.SetSizer(self._rows_sizer)

        self.Bind(wx.EVT_SIZE, self._on_size)
        self.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel)
        self._rows_panel.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel)

    @property
    def rows_sizer(self) -> wx.BoxSizer:
        return self._rows_sizer

    @property
    def rows_panel(self) -> wx.Panel:
        return self._rows_panel

    def total_height(self) -> int:
        return self._rows_panel.GetBestSize().height

    def viewport_height(self) -> int:
        return self.GetClientSize().height

    def scroll_to(self, fraction: float) -> None:
        total = self.total_height()
        vh = self.viewport_height()
        self._scroll_offset = int(fraction * max(0, total - vh))
        self._apply_offset()

    def refresh_layout(self) -> None:
        self._rows_panel.Layout()
        self._rows_panel.SetSize(self.GetClientSize().width, max(self.total_height(), self.viewport_height()))
        self._apply_offset()

    def _apply_offset(self) -> None:
        w = self.GetClientSize().width
        total = self.total_height()
        vh = self.viewport_height()
        max_offset = max(0, total - vh)
        self._scroll_offset = max(0, min(self._scroll_offset, max_offset))
        self._rows_panel.SetPosition((0, -self._scroll_offset))
        self._rows_panel.SetSize(w, max(total, vh))
        self._notify_scroll()

    def _notify_scroll(self) -> None:
        total = self.total_height()
        vh = self.viewport_height()
        if total <= vh:
            self._on_scroll_changed(0.0, 1.0)
        else:
            self._on_scroll_changed(self._scroll_offset / (total - vh), vh / total)

    def _on_size(self, event: wx.SizeEvent) -> None:
        self._apply_offset()
        event.Skip()

    def _on_wheel(self, event: wx.MouseEvent) -> None:
        self._scroll_offset = max(0, self._scroll_offset - event.GetWheelRotation() // event.GetWheelDelta() * _ROW_H)
        self._apply_offset()
        event.Skip()


def _draw_checkbox(gc: wx.GraphicsContext, r: wx.Rect, checked: bool) -> None:
    """Paint a themed checkbox inside the given rect."""
    if checked:
        gc.SetBrush(wx.Brush(_CHECK_FG))
        gc.SetPen(wx.Pen(_CHECK_FG, 1))
        gc.DrawRoundedRectangle(r.x, r.y, r.width, r.height, _BOX_R)
        gc.SetPen(wx.Pen(wx.Colour(18, 18, 18), 2))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        path = gc.CreatePath()
        path.MoveToPoint(r.x + 3, r.y + r.height / 2)
        path.AddLineToPoint(r.x + r.width * 0.42, r.y + r.height - 3.5)
        path.AddLineToPoint(r.x + r.width - 3, r.y + 3)
        gc.StrokePath(path)
    else:
        gc.SetBrush(wx.Brush(_CHECK_BG))
        gc.SetPen(wx.Pen(_CHECK_BORDER, 1))
        gc.DrawRoundedRectangle(r.x, r.y, r.width, r.height, _BOX_R)


class _CollectionRow(wx.Panel):
    """One editable row with checkbox and data controls positioned flush inside each cell."""

    def __init__(
        self,
        parent: wx.Window,
        point: CollectionPoint,
        motor_shorthands: list[str],
        motor_precisions: dict[str, int],
        rotation_precision: int,
        col_widths: list[int],
        on_label_changed: Callable[[str], None],
        on_motor_changed: Callable[[str, str], None],
        on_type_changed: Callable[[ScanType], None],
        on_rotation_start_changed: Callable[[str], None],
        on_rotation_end_changed: Callable[[str], None],
        on_step_changed: Callable[[str], None],
        on_time_changed: Callable[[str], None],
        on_selection_changed: Callable[[bool], None],
        on_remove: Callable[[], None],
    ) -> None:
        super().__init__(parent, size=(-1, _ROW_H), style=wx.BORDER_NONE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(BG_CARD)

        self._on_label_changed = on_label_changed
        self._on_motor_changed = on_motor_changed
        self._on_type_changed = on_type_changed
        self._on_selection_changed = on_selection_changed
        self._col_widths = col_widths
        self._selected = point.selected
        self._motor_precisions = motor_precisions

        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, self._on_size)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_click)

        inner_h = _ROW_H - 8

        def _text(value: str, on_commit: Callable[[str], None]) -> DarkTextCtrl:
            ctrl = DarkTextCtrl(self, value=value)
            ctrl.SetMinSize((-1, inner_h))
            handler = self._make_commit(ctrl, on_commit)
            ctrl.Bind(wx.EVT_KILL_FOCUS, handler)
            ctrl.Bind(wx.EVT_TEXT_ENTER, handler)
            return ctrl

        self._label_ctrl = _text(point.label, on_label_changed)

        self._motor_ctrls: dict[str, DarkTextCtrl] = {}
        for shorthand in motor_shorthands:
            precision = motor_precisions.get(shorthand, 4)
            ctrl = _text(point.motor_positions.get(shorthand, ""), self._make_motor_commit_fn(shorthand))
            ctrl.set_restrict_to_float(True)
            ctrl.set_validator(self._make_motor_validator(precision))
            self._motor_ctrls[shorthand] = ctrl

        self._get_btn: FlatButton | None = None
        self._move_btn: FlatButton | None = None
        if motor_shorthands:
            self._get_btn = FlatButton(self, "Get", color_scheme=MUTED_SCHEME)
            self._get_btn.SetMinSize((-1, inner_h))
            self._get_btn.SetToolTip("Get current motor positions")
            self._move_btn = FlatButton(self, "Move", color_scheme=MUTED_SCHEME)
            self._move_btn.SetMinSize((-1, inner_h))
            self._move_btn.SetToolTip("Move motors to stored positions")

        self._type_combo = DarkCombo(self, choices=list(SCAN_TYPES), choice_colours=_TYPE_COLOURS)
        if point.scan_type in SCAN_TYPES:
            self._type_combo.SetSelection(list(SCAN_TYPES).index(point.scan_type))
        self._type_combo.SetMinSize((-1, inner_h))
        self._type_combo.Bind(wx.EVT_CHOICE, self._on_type_commit)

        self._rot_start_ctrl = _text(point.rotation_start, on_rotation_start_changed)
        self._rot_start_ctrl.set_restrict_to_float(True)
        self._rot_start_ctrl.set_validator(self._make_motor_validator(rotation_precision))

        self._rot_end_ctrl = _text(point.rotation_end, on_rotation_end_changed)
        self._rot_end_ctrl.set_restrict_to_float(True)
        self._rot_end_ctrl.set_validator(self._make_motor_validator(rotation_precision))

        self._step_ctrl = _text(point.step, on_step_changed)
        self._step_ctrl.set_restrict_to_float(True)
        self._step_ctrl.set_validator(self._make_motor_validator(4))

        self._time_ctrl = _text(point.time, on_time_changed)
        self._time_ctrl.set_restrict_to_float(True)
        self._time_ctrl.set_validator(self._make_motor_validator(4))

        self._remove_btn_panel = wx.Panel(self, style=wx.BORDER_NONE)
        self._remove_btn_panel.SetBackgroundColour(BG_CARD)
        self._remove_btn = FlatButton(self._remove_btn_panel, "×", color_scheme=DANGER_SCHEME)
        self._remove_btn.SetMinSize((inner_h + 8, inner_h))
        self._remove_btn.SetToolTip("Remove row")
        self._remove_btn.set_action(on_remove)
        _btn_sizer = wx.BoxSizer(wx.VERTICAL)
        _btn_sizer.AddStretchSpacer()
        _btn_sizer.Add(self._remove_btn, 0, wx.ALIGN_CENTER_HORIZONTAL)
        _btn_sizer.AddStretchSpacer()
        self._remove_btn_panel.SetSizer(_btn_sizer)

        self._apply_scan_type_state(point.scan_type)
        self._reposition()

    def SetBackgroundColour(self, colour: wx.Colour) -> bool:
        result = super().SetBackgroundColour(colour)
        if hasattr(self, "_remove_btn_panel"):
            self._remove_btn_panel.SetBackgroundColour(colour)
        return result

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.Refresh()

    def refresh_from_point(self, point: "CollectionPoint") -> None:
        if point.scan_type in SCAN_TYPES:
            self._type_combo.SetSelection(list(SCAN_TYPES).index(point.scan_type))
        self._time_ctrl.SetValue(point.time)
        self._rot_start_ctrl.SetValue(point.rotation_start)
        self._rot_end_ctrl.SetValue(point.rotation_end)
        self._step_ctrl.SetValue(point.step)
        self._apply_scan_type_state(point.scan_type)

    def update_col_widths(self, col_widths: list[int]) -> None:
        self._col_widths = col_widths
        self._reposition()

    def get_label(self) -> str:
        return self._label_ctrl.GetValue().strip()

    def get_motor_value(self, shorthand: str) -> str:
        ctrl = self._motor_ctrls.get(shorthand)
        return ctrl.GetValue().strip() if ctrl else ""

    def get_scan_type(self) -> ScanType:
        sel = self._type_combo.GetStringSelection()
        return sel if sel in SCAN_TYPES else "still"

    def _checkbox_rect(self) -> wx.Rect:
        cw = self._col_widths[0]
        return wx.Rect((cw - _BOX_S) // 2, (_ROW_H - _BOX_S) // 2, _BOX_S, _BOX_S)

    def _reposition(self) -> None:
        x = self._col_widths[0]
        y_off = 4

        def _place(ctrl: wx.Window, w: int) -> None:
            nonlocal x
            ctrl.SetSize(x + _CELL_PAD, y_off, w - 2 * _CELL_PAD, _ROW_H - 2 * y_off)
            x += w

        _place(self._label_ctrl, self._col_widths[1])

        for i, ctrl in enumerate(self._motor_ctrls.values(), start=2):
            _place(ctrl, self._col_widths[i])

        n = len(self._motor_ctrls)
        extra = 0
        if self._get_btn is not None and self._move_btn is not None:
            _place(self._get_btn, self._col_widths[n + 2])
            _place(self._move_btn, self._col_widths[n + 3])
            extra = 2
        _place(self._type_combo, self._col_widths[n + 2 + extra])
        _place(self._rot_start_ctrl, self._col_widths[n + 3 + extra])
        _place(self._rot_end_ctrl, self._col_widths[n + 4 + extra])
        _place(self._step_ctrl, self._col_widths[n + 5 + extra])
        _place(self._time_ctrl, self._col_widths[n + 6 + extra])
        cw = self._col_widths[n + 7 + extra]
        self._remove_btn_panel.SetSize(x, 0, cw, _ROW_H)
        self._remove_btn_panel.Layout()

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()

        gc.SetBrush(wx.Brush(self.GetBackgroundColour()))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)

        _draw_checkbox(gc, self._checkbox_rect(), self._selected)

        gc.SetPen(wx.Pen(_BORDER, 1))
        gc.StrokeLine(0, h - 1, w, h - 1)
        x = 0
        for cw in self._col_widths[:-1]:
            x += cw
            gc.StrokeLine(x, 0, x, h)

    def _on_click(self, event: wx.MouseEvent) -> None:
        if self._checkbox_rect().Contains(event.GetPosition()):
            self._selected = not self._selected
            self.Refresh()
            self._on_selection_changed(self._selected)
        else:
            event.Skip()

    def _on_size(self, event: wx.SizeEvent) -> None:
        self._reposition()
        self.Refresh()
        event.Skip()

    def _apply_scan_type_state(self, scan_type: ScanType) -> None:
        still = scan_type == "still"
        wide = scan_type == "wide"
        self._rot_start_ctrl.set_disabled(still)
        self._rot_end_ctrl.set_disabled(still)
        self._step_ctrl.set_disabled(still or wide)

    def _on_type_commit(self, value: str) -> None:
        if value in SCAN_TYPES:
            self._apply_scan_type_state(value)
            self._on_type_changed(value)

    @staticmethod
    def _make_commit(ctrl: DarkTextCtrl, callback: Callable[[str], None]) -> Callable[[wx.Event], None]:
        def _handler(event: wx.Event) -> None:
            callback(ctrl.GetValue().strip())
            event.Skip()

        return _handler

    def _make_motor_commit_fn(self, shorthand: str) -> Callable[[str], None]:
        def _cb(value: str) -> None:
            self._on_motor_changed(shorthand, value)

        return _cb

    @staticmethod
    def _make_motor_validator(precision: int) -> Callable[[str], str]:
        def _validate(raw: str) -> str:
            if raw == "":
                return ""
            return MotorPositionValidator(raw, precision).formatted

        return _validate


class _HeaderRow(wx.Panel):
    """Custom-painted header with column labels, bottom border, and a select-all checkbox."""

    def __init__(
        self,
        parent: wx.Window,
        motor_shorthands: list[str],
        rotation_shorthand: str,
        col_widths: list[int],
        on_select_all: Callable[[bool], None],
    ) -> None:
        super().__init__(parent, size=(-1, _HEADER_H), style=wx.BORDER_NONE)
        self.SetBackgroundColour(_HEADER_BG)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self._col_widths = col_widths
        self._labels = self._build_labels(motor_shorthands, rotation_shorthand)
        self._all_selected = False
        self._on_select_all = on_select_all
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_click)

    def update_col_widths(self, motor_shorthands: list[str], rotation_shorthand: str, col_widths: list[int]) -> None:
        self._col_widths = col_widths
        self._labels = self._build_labels(motor_shorthands, rotation_shorthand)
        self.Refresh()

    def set_all_selected(self, selected: bool) -> None:
        self._all_selected = selected
        self.Refresh()

    @staticmethod
    def _build_labels(motor_shorthands: list[str], rotation_shorthand: str) -> list[str]:
        rot = rotation_shorthand.capitalize() if rotation_shorthand else "Rot"
        motor_action_labels = ["Get", "Move"] if motor_shorthands else []
        return ["", "Ext."] + [s.capitalize() for s in motor_shorthands] + motor_action_labels + ["Type", f"{rot} Start", f"{rot} End", "Step", "Time", ""]

    def _checkbox_rect(self) -> wx.Rect:
        cw = self._col_widths[0]
        return wx.Rect((cw - _BOX_S) // 2, (_HEADER_H - _BOX_S) // 2, _BOX_S, _BOX_S)

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()

        gc.SetBrush(wx.Brush(_HEADER_BG))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)

        _draw_checkbox(gc, self._checkbox_rect(), self._all_selected)

        font = scaled_font(13, weight=wx.FONTWEIGHT_BOLD)
        gc.SetFont(font, ACCENT)

        x = 0
        gc.SetPen(wx.Pen(_BORDER, 1))
        for i, (label, cw) in enumerate(zip(self._labels, self._col_widths)):
            if label:
                tw, th = gc.GetTextExtent(label)
                gc.DrawText(label, x + (cw - tw) / 2, (h - th) / 2)
            if i < len(self._col_widths) - 1:
                gc.StrokeLine(x + cw, 0, x + cw, h)
            x += cw

        gc.StrokeLine(0, h - 1, w, h - 1)

    def _on_click(self, event: wx.MouseEvent) -> None:
        if self._checkbox_rect().Contains(event.GetPosition()):
            self._all_selected = not self._all_selected
            self.Refresh()
            self._on_select_all(self._all_selected)
        else:
            event.Skip()


class CollectionTableView(wx.Panel):
    """Editable collection-points table with a traditional grid look."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self.SetBackgroundColour(BG_SURFACE)

        self._motor_shorthands: list[str] = []
        self._motor_precisions: dict[str, int] = {}
        self._rotation_precision: int = 4
        self._rotation_shorthand: str = ""
        self._rows: list[_CollectionRow] = []

        self._on_add_cb: Callable[[], None] | None = None
        self._on_clear_cb: Callable[[], None] | None = None
        self._on_delete_selected_cb: Callable[[], None] | None = None
        self._on_label_cb: Callable[[int, str], None] | None = None
        self._on_motor_cb: Callable[[int, str, str], None] | None = None
        self._on_type_cb: Callable[[int, ScanType], None] | None = None
        self._on_rotation_start_cb: Callable[[int, str], None] | None = None
        self._on_rotation_end_cb: Callable[[int, str], None] | None = None
        self._on_step_cb: Callable[[int, str], None] | None = None
        self._on_time_cb: Callable[[int, str], None] | None = None
        self._on_selection_cb: Callable[[int, bool], None] | None = None
        self._on_remove_cb: Callable[[int], None] | None = None

        self._build_layout()
        self.SetMinSize((self._min_content_width(), -1))
        self.Bind(wx.EVT_SIZE, self._on_size)

    def _min_content_width(self) -> int:
        n_motor = len(self._motor_shorthands)
        motor_cols = _MOTOR_W * n_motor + (_GET_W + _MOVE_W if n_motor else 0)
        return _CHECK_W + _EXT_W + motor_cols + _TYPE_W + _ROT_W + _ROT_W + _STEP_W + _TIME_W + _REMOVE_W + _SB_W

    def _col_widths(self) -> list[int]:
        total = self.GetClientSize().width - _SB_W
        n_motor = len(self._motor_shorthands)
        motor_cols = _MOTOR_W * n_motor + (_GET_W + _MOVE_W if n_motor else 0)
        fixed = _CHECK_W + motor_cols + _TYPE_W + _ROT_W + _ROT_W + _STEP_W + _TIME_W + _REMOVE_W
        ext_w = max(_EXT_W, total - fixed)
        motor_action_cols = [_GET_W, _MOVE_W] if n_motor else []
        return [_CHECK_W, ext_w] + [_MOTOR_W] * n_motor + motor_action_cols + [_TYPE_W, _ROT_W, _ROT_W, _STEP_W, _TIME_W, _REMOVE_W]

    def _build_layout(self) -> None:
        title_lbl = wx.StaticText(self, label="Collection Points")
        title_lbl.SetForegroundColour(FG_PRIMARY)
        title_lbl.SetFont(scaled_font(13, weight=wx.FONTWEIGHT_BOLD))
        title_lbl.SetBackgroundColour(BG_SURFACE)

        self._delete_selected_btn = FlatButton(self, "Delete selected", color_scheme=DANGER_SCHEME)
        self._delete_selected_btn.SetMinSize((100, 22))
        self._delete_selected_btn.set_action(self._on_delete_selected_clicked)

        self._clear_btn = FlatButton(self, "Clear all", color_scheme=DANGER_SCHEME)
        self._clear_btn.SetMinSize((70, 22))
        self._clear_btn.set_action(self._on_clear_clicked)

        title_row = wx.BoxSizer(wx.HORIZONTAL)
        title_row.Add(title_lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.TOP | wx.BOTTOM, 8)
        title_row.AddStretchSpacer()
        title_row.Add(self._delete_selected_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.TOP | wx.BOTTOM, 4)
        title_row.Add(self._clear_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.TOP | wx.BOTTOM, 4)

        title_sep = wx.Panel(self, size=(-1, 1))
        title_sep.SetBackgroundColour(SEP_COLOUR)

        self._header = _HeaderRow(
            self,
            self._motor_shorthands,
            self._rotation_shorthand,
            self._col_widths(),
            on_select_all=self._on_select_all,
        )

        header_border = wx.Panel(self, size=(-1, 1))
        header_border.SetBackgroundColour(_BORDER)

        self._scrollbar = DarkScrollBar(self, on_scroll=self._on_sb_scroll)
        self._viewport = _RowsViewport(self, on_scroll_changed=self._on_scroll_changed)
        self._scrollbar.SetBackgroundColour(BG_ELEVATED)

        scroll_row = wx.BoxSizer(wx.HORIZONTAL)
        scroll_row.Add(self._viewport, 1, wx.EXPAND)
        scroll_row.Add(self._scrollbar, 0, wx.EXPAND)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(title_row, 0, wx.EXPAND)
        outer.Add(title_sep, 0, wx.EXPAND)
        outer.Add(self._header, 0, wx.EXPAND)
        outer.Add(header_border, 0, wx.EXPAND)
        outer.Add(scroll_row, 1, wx.EXPAND)
        self.SetSizer(outer)

    def set_columns(self, motor_shorthands: list[str], rotation_shorthand: str = "", motor_precisions: dict[str, int] | None = None, rotation_precision: int = 4) -> None:
        self._motor_shorthands = list(motor_shorthands)
        self._motor_precisions = motor_precisions or {}
        self._rotation_precision = rotation_precision
        self._rotation_shorthand = rotation_shorthand
        self.SetMinSize((self._min_content_width(), -1))
        widths = self._col_widths()
        self._header.update_col_widths(self._motor_shorthands, self._rotation_shorthand, widths)

        for row in self._rows:
            self._viewport.rows_sizer.Detach(row)
            row.Destroy()
        self._rows.clear()
        self._viewport.refresh_layout()
        self.Layout()

    def add_row(self, point: CollectionPoint) -> None:
        index = len(self._rows)
        bg = BG_CARD if index % 2 == 0 else _ROW_ALT
        row = _CollectionRow(
            self._viewport.rows_panel,
            point,
            self._motor_shorthands,
            self._motor_precisions,
            self._rotation_precision,
            self._col_widths(),
            on_label_changed=self._make_label_cb(index),
            on_motor_changed=self._make_motor_cb(index),
            on_type_changed=self._make_type_cb(index),
            on_rotation_start_changed=self._make_rot_start_cb(index),
            on_rotation_end_changed=self._make_rot_end_cb(index),
            on_step_changed=self._make_step_cb(index),
            on_time_changed=self._make_time_cb(index),
            on_selection_changed=self._make_selection_cb(index),
            on_remove=self._make_remove_cb(index),
        )
        row.SetBackgroundColour(bg)
        self._viewport.rows_sizer.Add(row, 0, wx.EXPAND)
        self._rows.append(row)
        self._viewport.refresh_layout()
        self._viewport.scroll_to(1.0)

    def remove_row(self, index: int) -> None:
        if not (0 <= index < len(self._rows)):
            return
        row = self._rows.pop(index)
        self._viewport.rows_sizer.Detach(row)
        row.Destroy()
        self._restripe()
        self._viewport.refresh_layout()
        self._rebind_rows()

    def refresh_row(self, index: int, point: CollectionPoint) -> None:
        if 0 <= index < len(self._rows):
            self._rows[index].refresh_from_point(point)

    def set_row_selected(self, index: int, selected: bool) -> None:
        if 0 <= index < len(self._rows):
            self._rows[index].set_selected(selected)

    def bind_add(self, callback: Callable[[], None]) -> None:
        self._on_add_cb = callback

    def bind_clear(self, callback: Callable[[], None]) -> None:
        self._on_clear_cb = callback

    def bind_delete_selected(self, callback: Callable[[], None]) -> None:
        self._on_delete_selected_cb = callback

    def bind_label_changed(self, callback: Callable[[int, str], None]) -> None:
        self._on_label_cb = callback

    def bind_motor_changed(self, callback: Callable[[int, str, str], None]) -> None:
        self._on_motor_cb = callback

    def bind_type_changed(self, callback: Callable[[int, ScanType], None]) -> None:
        self._on_type_cb = callback

    def bind_rotation_start_changed(self, callback: Callable[[int, str], None]) -> None:
        self._on_rotation_start_cb = callback

    def bind_rotation_end_changed(self, callback: Callable[[int, str], None]) -> None:
        self._on_rotation_end_cb = callback

    def bind_step_changed(self, callback: Callable[[int, str], None]) -> None:
        self._on_step_cb = callback

    def bind_time_changed(self, callback: Callable[[int, str], None]) -> None:
        self._on_time_cb = callback

    def bind_selection_changed(self, callback: Callable[[int, bool], None]) -> None:
        self._on_selection_cb = callback

    def bind_remove(self, callback: Callable[[int], None]) -> None:
        self._on_remove_cb = callback

    def _on_add_clicked(self) -> None:
        if self._on_add_cb is not None:
            self._on_add_cb()

    def _on_clear_clicked(self) -> None:
        if self._on_clear_cb is not None:
            self._on_clear_cb()

    def _on_delete_selected_clicked(self) -> None:
        if self._on_delete_selected_cb is not None:
            self._on_delete_selected_cb()

    def _on_select_all(self, selected: bool) -> None:
        for i, row in enumerate(self._rows):
            row.set_selected(selected)
            if self._on_selection_cb is not None:
                self._on_selection_cb(i, selected)

    def _on_sb_scroll(self, fraction: float) -> None:
        self._viewport.scroll_to(fraction)

    def _on_scroll_changed(self, pos: float, size: float) -> None:
        self._scrollbar.update(pos, size)

    def _on_size(self, event: wx.SizeEvent) -> None:
        widths = self._col_widths()
        self._header.update_col_widths(self._motor_shorthands, self._rotation_shorthand, widths)
        for row in self._rows:
            row.update_col_widths(widths)
        event.Skip()

    def _restripe(self) -> None:
        for i, row in enumerate(self._rows):
            row.SetBackgroundColour(BG_CARD if i % 2 == 0 else _ROW_ALT)
            row.Refresh()

    def _make_label_cb(self, index: int) -> Callable[[str], None]:
        def _cb(label: str) -> None:
            if self._on_label_cb is not None:
                self._on_label_cb(index, label)

        return _cb

    def _make_motor_cb(self, index: int) -> Callable[[str, str], None]:
        def _cb(shorthand: str, value: str) -> None:
            if self._on_motor_cb is not None:
                self._on_motor_cb(index, shorthand, value)

        return _cb

    def _make_type_cb(self, index: int) -> Callable[[ScanType], None]:
        def _cb(scan_type: ScanType) -> None:
            if self._on_type_cb is not None:
                self._on_type_cb(index, scan_type)

        return _cb

    def _make_rot_start_cb(self, index: int) -> Callable[[str], None]:
        def _cb(value: str) -> None:
            if self._on_rotation_start_cb is not None:
                self._on_rotation_start_cb(index, value)

        return _cb

    def _make_rot_end_cb(self, index: int) -> Callable[[str], None]:
        def _cb(value: str) -> None:
            if self._on_rotation_end_cb is not None:
                self._on_rotation_end_cb(index, value)

        return _cb

    def _make_step_cb(self, index: int) -> Callable[[str], None]:
        def _cb(value: str) -> None:
            if self._on_step_cb is not None:
                self._on_step_cb(index, value)

        return _cb

    def _make_time_cb(self, index: int) -> Callable[[str], None]:
        def _cb(value: str) -> None:
            if self._on_time_cb is not None:
                self._on_time_cb(index, value)

        return _cb

    def _make_selection_cb(self, index: int) -> Callable[[bool], None]:
        def _cb(selected: bool) -> None:
            if self._on_selection_cb is not None:
                self._on_selection_cb(index, selected)
            self._sync_header_checkbox()

        return _cb

    def _make_remove_cb(self, index: int) -> Callable[[], None]:
        def _cb() -> None:
            if self._on_remove_cb is not None:
                self._on_remove_cb(index)

        return _cb

    def _sync_header_checkbox(self) -> None:
        all_checked = bool(self._rows) and all(row._selected for row in self._rows)
        self._header.set_all_selected(all_checked)

    def _rebind_rows(self) -> None:
        for i, row in enumerate(self._rows):
            row._on_label_changed = self._make_label_cb(i)
            row._on_motor_changed = self._make_motor_cb(i)
            row._on_type_changed = self._make_type_cb(i)
            row._on_selection_changed = self._make_selection_cb(i)
            rot_start = self._make_rot_start_cb(i)
            rot_end = self._make_rot_end_cb(i)
            step = self._make_step_cb(i)
            time = self._make_time_cb(i)
            row._rot_start_ctrl.Bind(wx.EVT_KILL_FOCUS, _CollectionRow._make_commit(row._rot_start_ctrl, rot_start))
            row._rot_end_ctrl.Bind(wx.EVT_KILL_FOCUS, _CollectionRow._make_commit(row._rot_end_ctrl, rot_end))
            row._step_ctrl.Bind(wx.EVT_KILL_FOCUS, _CollectionRow._make_commit(row._step_ctrl, step))
            row._time_ctrl.Bind(wx.EVT_KILL_FOCUS, _CollectionRow._make_commit(row._time_ctrl, time))
            row._remove_btn.set_action(self._make_remove_cb(i))
