#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/collection_table_view.py
# ----------------------------------------------------------------------------------
# Purpose:
# Collection-points table panel with a fully custom-painted dark scrollbar and
# per-row selection checkbox.
#
# The table is virtualized: regardless of how many points are added, only a
# small pool of `_CollectionRow` widgets is realized (enough to fill the
# viewport plus a small over-scan buffer). As the user scrolls, pooled rows
# are re-bound to different points instead of being created/destroyed. This
# keeps the number of native (HWND/GDI) handles bounded and avoids Windows
# GDI exhaustion when the table contains hundreds or thousands of map points.
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
from crystalsweep.ui.view.custom.theme import ACCENT, BG_CARD, BG_ELEVATED, BG_SURFACE, DANGER, FG_PRIMARY, FG_SECONDARY, SEP_COLOUR, scaled_font
from crystalsweep.ui.view.custom.widgets import DANGER_SCHEME, MUTED_SCHEME, DarkCombo, DarkScrollBar, DarkTextCtrl, DarkToggle, FlatButton

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

# Extra rows realized above/below the viewport so partially-visible rows are ready
# before they scroll into view (smoother wheel scrolling without flicker).
_OVERSCAN_ROWS = 2


class _RowsViewport(wx.Panel):
    """Clipping panel that hosts the pooled row widgets.

    The viewport does not own a sizer for the rows; rows are positioned
    absolutely inside ``_rows_panel`` by the owning :class:`CollectionTableView`
    so that the same small set of widgets can be re-used as the user scrolls.
    """

    def __init__(self, parent: wx.Window, on_scroll_changed: Callable[[float, float], None], on_repopulate: Callable[[], None]) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self.SetBackgroundColour(BG_CARD)

        self._on_scroll_changed = on_scroll_changed
        self._on_repopulate = on_repopulate
        self._scroll_offset: int = 0
        self._virtual_height: int = 0

        self._rows_panel = wx.Panel(self, style=wx.BORDER_NONE)
        self._rows_panel.SetBackgroundColour(BG_CARD)

        self.Bind(wx.EVT_SIZE, self._on_size)
        self.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel)
        self._rows_panel.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel)

    @property
    def rows_panel(self) -> wx.Panel:
        return self._rows_panel

    @property
    def scroll_offset(self) -> int:
        return self._scroll_offset

    def set_virtual_height(self, height: int) -> None:
        self._virtual_height = max(0, height)
        self._clamp_offset()
        self._resize_rows_panel()
        self._on_repopulate()
        self._notify_scroll()

    def total_height(self) -> int:
        return self._virtual_height

    def viewport_height(self) -> int:
        return self.GetClientSize().height

    def scroll_to(self, fraction: float) -> None:
        total = self._virtual_height
        vh = self.viewport_height()
        self._scroll_offset = int(fraction * max(0, total - vh))
        self._clamp_offset()
        self._on_repopulate()
        self._notify_scroll()

    def scroll_by_pixels(self, delta: int) -> None:
        self._scroll_offset += delta
        self._clamp_offset()
        self._on_repopulate()
        self._notify_scroll()

    def ensure_visible(self, top: int, bottom: int) -> None:
        vh = self.viewport_height()
        if top < self._scroll_offset:
            self._scroll_offset = top
        elif bottom > self._scroll_offset + vh:
            self._scroll_offset = bottom - vh
        self._clamp_offset()
        self._on_repopulate()
        self._notify_scroll()

    def _clamp_offset(self) -> None:
        max_offset = max(0, self._virtual_height - self.viewport_height())
        self._scroll_offset = max(0, min(self._scroll_offset, max_offset))

    def _resize_rows_panel(self) -> None:
        w = self.GetClientSize().width
        h = max(self._virtual_height, self.viewport_height())
        self._rows_panel.SetSize(0, 0, w, h)

    def _notify_scroll(self) -> None:
        total = self._virtual_height
        vh = self.viewport_height()
        if total <= vh:
            self._on_scroll_changed(0.0, 1.0)
        else:
            self._on_scroll_changed(self._scroll_offset / (total - vh), vh / total)

    def _on_size(self, event: wx.SizeEvent) -> None:
        self._clamp_offset()
        self._resize_rows_panel()
        self._on_repopulate()
        self._notify_scroll()
        event.Skip()

    def _on_wheel(self, event: wx.MouseEvent) -> None:
        delta = -event.GetWheelRotation() // event.GetWheelDelta() * _ROW_H
        self.scroll_by_pixels(delta)
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


class _RowDispatcher:
    """Look-up table the pooled rows use to forward edits to the owning view.

    Each pool row carries its current logical ``data_idx``. When the user edits
    a cell, the row calls into this dispatcher with that ``data_idx``; the
    dispatcher then forwards to whichever ``on_*`` callback the view has
    registered, passing the correct point index. This avoids capturing the
    index in a closure (which would go stale when the row is re-bound).
    """

    def __init__(self) -> None:
        self.on_label: Callable[[int, str], None] | None = None
        self.on_motor: Callable[[int, str, str], None] | None = None
        self.on_type: Callable[[int, ScanType], None] | None = None
        self.on_rot_start: Callable[[int, str], None] | None = None
        self.on_rot_end: Callable[[int, str], None] | None = None
        self.on_step: Callable[[int, str], None] | None = None
        self.on_time: Callable[[int, str], None] | None = None
        self.on_selection: Callable[[int, bool], None] | None = None
        self.on_remove: Callable[[int], None] | None = None
        self.on_get: Callable[[int], None] | None = None
        self.on_move: Callable[[int], None] | None = None


class _CollectionRow(wx.Panel):
    """One editable row with checkbox and data controls positioned flush inside each cell.

    Rows are pooled and re-bound to different points via :meth:`bind_to` as the
    user scrolls; they do not own a reference to ``CollectionPoint`` and they
    do not capture an index in any closure. The row reports edits through a
    shared :class:`_RowDispatcher`, passing its current ``data_idx``.
    """

    def __init__(
        self,
        parent: wx.Window,
        motor_shorthands: list[str],
        motor_precisions: dict[str, int],
        rotation_precision: int,
        col_widths: list[int],
        dispatcher: _RowDispatcher,
    ) -> None:
        super().__init__(parent, size=(-1, _ROW_H), style=wx.BORDER_NONE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(BG_CARD)

        self._dispatcher = dispatcher
        self._data_idx: int = -1
        self._col_widths = col_widths
        self._selected = False
        self._motor_precisions = motor_precisions
        self._collecting = False
        self._active = False
        self._limit_error = False
        self._label_enabled = True

        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, self._on_size)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_click)

        inner_h = _ROW_H - 8

        def _text(value: str, commit_attr: str) -> DarkTextCtrl:
            ctrl = DarkTextCtrl(self, value=value)
            ctrl.SetMinSize((-1, inner_h))
            handler = self._make_commit_handler(ctrl, commit_attr)
            ctrl.Bind(wx.EVT_KILL_FOCUS, handler)
            ctrl.Bind(wx.EVT_TEXT_ENTER, handler)
            return ctrl

        self._label_ctrl = _text("", "_dispatch_label")

        self._motor_shorthands = list(motor_shorthands)
        self._motor_ctrls: dict[str, DarkTextCtrl] = {}
        for shorthand in motor_shorthands:
            precision = motor_precisions.get(shorthand, 4)
            ctrl = DarkTextCtrl(self, value="")
            ctrl.SetMinSize((-1, inner_h))
            handler = self._make_motor_commit_handler(ctrl, shorthand)
            ctrl.Bind(wx.EVT_KILL_FOCUS, handler)
            ctrl.Bind(wx.EVT_TEXT_ENTER, handler)
            ctrl.set_restrict_to_float(True)
            ctrl.set_validator(self._make_motor_validator(precision))
            self._motor_ctrls[shorthand] = ctrl

        self._get_btn: FlatButton | None = None
        self._move_btn: FlatButton | None = None
        if motor_shorthands:
            self._get_btn = FlatButton(self, "Get", color_scheme=MUTED_SCHEME)
            self._get_btn.SetMinSize((-1, inner_h))
            self._get_btn.SetToolTip("Get current motor positions")
            self._get_btn.set_action(self._dispatch_get)
            self._move_btn = FlatButton(self, "Move", color_scheme=MUTED_SCHEME)
            self._move_btn.SetMinSize((-1, inner_h))
            self._move_btn.SetToolTip("Move motors to stored positions")
            self._move_btn.set_action(self._dispatch_move)

        self._type_combo = DarkCombo(self, choices=list(SCAN_TYPES), choice_colours=_TYPE_COLOURS)
        self._type_combo.SetMinSize((-1, inner_h))
        self._type_combo.Bind(wx.EVT_CHOICE, self._on_type_commit)

        self._rot_start_ctrl = _text("", "_dispatch_rot_start")
        self._rot_start_ctrl.set_restrict_to_float(True)
        self._rot_start_ctrl.set_validator(self._make_motor_validator(rotation_precision))

        self._rot_end_ctrl = _text("", "_dispatch_rot_end")
        self._rot_end_ctrl.set_restrict_to_float(True)
        self._rot_end_ctrl.set_validator(self._make_motor_validator(rotation_precision))

        self._step_ctrl = _text("", "_dispatch_step")
        self._step_ctrl.set_restrict_to_float(True)
        self._step_ctrl.set_validator(self._make_motor_validator(4))

        self._time_ctrl = _text("", "_dispatch_time")
        self._time_ctrl.set_restrict_to_float(True)
        self._time_ctrl.set_validator(self._make_motor_validator(4))

        self._remove_btn_panel = wx.Panel(self, style=wx.BORDER_NONE)
        self._remove_btn_panel.SetBackgroundColour(BG_CARD)
        self._remove_btn_panel.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self._remove_btn_panel.Bind(wx.EVT_PAINT, self._on_remove_panel_paint)
        self._remove_btn = FlatButton(self._remove_btn_panel, "×", color_scheme=DANGER_SCHEME)
        self._remove_btn.SetMinSize((inner_h, inner_h))
        self._remove_btn.SetToolTip("Remove row")
        self._remove_btn.set_action(self._dispatch_remove)
        _btn_sizer = wx.BoxSizer(wx.VERTICAL)
        _btn_sizer.AddStretchSpacer()
        _btn_sizer.Add(self._remove_btn, 0, wx.ALIGN_CENTER_HORIZONTAL)
        _btn_sizer.AddStretchSpacer()
        self._remove_btn_panel.SetSizer(_btn_sizer)

        self._reposition()
        self.Hide()

    # ---------------- Pooled rebind ----------------

    def bind_to(
        self,
        data_idx: int,
        point: CollectionPoint,
        bg: wx.Colour,
        selected: bool,
        active: bool,
        limit_error: bool,
        field_errors: tuple[dict[str, bool], bool, bool],
        collecting: bool,
        label_enabled: bool,
    ) -> None:
        """Re-bind this pooled row to a new logical data row."""
        self._data_idx = data_idx
        self._selected = selected
        self._active = active
        self._limit_error = limit_error
        self._collecting = collecting
        self._label_enabled = label_enabled

        if self.GetBackgroundColour() != bg:
            self.SetBackgroundColour(bg)

        # Programmatic value swap. DarkTextCtrl.SetValue updates the displayed
        # text without firing EVT_TEXT_ENTER / EVT_KILL_FOCUS, so the commit
        # handlers (which would otherwise echo the swapped value back into the
        # model) do not run.
        self._label_ctrl.SetValue(point.label)
        for shorthand, ctrl in self._motor_ctrls.items():
            ctrl.SetValue(point.motor_positions.get(shorthand, ""))
        if point.scan_type in SCAN_TYPES:
            self._type_combo.SetSelection(list(SCAN_TYPES).index(point.scan_type))
        self._rot_start_ctrl.SetValue(point.rotation_start)
        self._rot_end_ctrl.SetValue(point.rotation_end)
        self._step_ctrl.SetValue(point.step)
        self._time_ctrl.SetValue(point.time)

        # Per-field limit error highlighting
        motor_errors, rot_start_error, rot_end_error = field_errors
        for shorthand, ctrl in self._motor_ctrls.items():
            ctrl.set_limit_error(motor_errors.get(shorthand, False))
        self._rot_start_ctrl.set_limit_error(rot_start_error)
        self._rot_end_ctrl.set_limit_error(rot_end_error)

        self._apply_enabled_states(point.scan_type)
        self.Refresh()
        self._remove_btn_panel.Refresh()

    def clear_binding(self) -> None:
        """Mark the pooled row as unused (hidden, no data index)."""
        self._data_idx = -1
        self.Hide()

    @property
    def data_idx(self) -> int:
        return self._data_idx

    # ---------------- Dispatchers ----------------

    def _dispatch_label(self, value: str) -> None:
        if self._data_idx >= 0 and self._dispatcher.on_label is not None:
            self._dispatcher.on_label(self._data_idx, value)

    def _dispatch_motor(self, shorthand: str, value: str) -> None:
        if self._data_idx >= 0 and self._dispatcher.on_motor is not None:
            self._dispatcher.on_motor(self._data_idx, shorthand, value)

    def _dispatch_type(self, value: ScanType) -> None:
        if self._data_idx >= 0 and self._dispatcher.on_type is not None:
            self._dispatcher.on_type(self._data_idx, value)

    def _dispatch_rot_start(self, value: str) -> None:
        if self._data_idx >= 0 and self._dispatcher.on_rot_start is not None:
            self._dispatcher.on_rot_start(self._data_idx, value)

    def _dispatch_rot_end(self, value: str) -> None:
        if self._data_idx >= 0 and self._dispatcher.on_rot_end is not None:
            self._dispatcher.on_rot_end(self._data_idx, value)

    def _dispatch_step(self, value: str) -> None:
        if self._data_idx >= 0 and self._dispatcher.on_step is not None:
            self._dispatcher.on_step(self._data_idx, value)

    def _dispatch_time(self, value: str) -> None:
        if self._data_idx >= 0 and self._dispatcher.on_time is not None:
            self._dispatcher.on_time(self._data_idx, value)

    def _dispatch_selection(self, selected: bool) -> None:
        if self._data_idx >= 0 and self._dispatcher.on_selection is not None:
            self._dispatcher.on_selection(self._data_idx, selected)

    def _dispatch_remove(self) -> None:
        if self._data_idx >= 0 and self._dispatcher.on_remove is not None:
            self._dispatcher.on_remove(self._data_idx)

    def _dispatch_get(self) -> None:
        if self._data_idx >= 0 and self._dispatcher.on_get is not None:
            self._dispatcher.on_get(self._data_idx)

    def _dispatch_move(self) -> None:
        if self._data_idx >= 0 and self._dispatcher.on_move is not None:
            self._dispatcher.on_move(self._data_idx)

    # ---------------- Painting / layout ----------------

    def SetBackgroundColour(self, colour: wx.Colour) -> bool:
        result = super().SetBackgroundColour(colour)
        if hasattr(self, "_remove_btn_panel"):
            self._remove_btn_panel.SetBackgroundColour(colour)
        return result

    def update_col_widths(self, col_widths: list[int]) -> None:
        self._col_widths = col_widths
        self._reposition()

    def update_motor_values(self, values: dict[str, str]) -> None:
        for shorthand, value in values.items():
            ctrl = self._motor_ctrls.get(shorthand)
            if ctrl is not None:
                ctrl.SetValue(value)

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

        if self._limit_error:
            gc.SetPen(wx.Pen(DANGER, 2))
            gc.SetBrush(wx.TRANSPARENT_BRUSH)
            gc.StrokeLine(1, 1, w, 1)
            gc.StrokeLine(1, h - 2, w, h - 2)
            gc.StrokeLine(1, 1, 1, h - 2)
        elif self._active:
            gc.SetPen(wx.Pen(ACCENT, 2))
            gc.SetBrush(wx.TRANSPARENT_BRUSH)
            gc.StrokeLine(1, 1, w, 1)
            gc.StrokeLine(1, h - 2, w, h - 2)
            gc.StrokeLine(1, 1, 1, h - 2)

    def _on_remove_panel_paint(self, _: wx.PaintEvent) -> None:
        w, h = self._remove_btn_panel.GetClientSize()
        if w <= 0 or h <= 0:
            return
        try:
            dc = wx.AutoBufferedPaintDC(self._remove_btn_panel)
            gc = wx.GraphicsContext.Create(dc)
        except Exception:
            return
        if gc is None:
            return
        gc.SetBrush(wx.Brush(self._remove_btn_panel.GetBackgroundColour()))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        if self._limit_error:
            gc.SetPen(wx.Pen(DANGER, 2))
            gc.SetBrush(wx.TRANSPARENT_BRUSH)
            gc.StrokeLine(w - 1, 1, w - 1, h - 1)
            gc.StrokeLine(0, 1, w - 1, 1)
            gc.StrokeLine(0, h - 2, w - 1, h - 2)
        elif self._active:
            gc.SetPen(wx.Pen(ACCENT, 2))
            gc.SetBrush(wx.TRANSPARENT_BRUSH)
            gc.StrokeLine(w - 1, 1, w - 1, h - 1)
            gc.StrokeLine(0, 1, w - 1, 1)
            gc.StrokeLine(0, h - 2, w - 1, h - 2)

    def _on_click(self, event: wx.MouseEvent) -> None:
        if self._collecting:
            return
        if self._checkbox_rect().Contains(event.GetPosition()):
            self._selected = not self._selected
            self.Refresh()
            self._dispatch_selection(self._selected)
        else:
            event.Skip()

    def _on_size(self, event: wx.SizeEvent) -> None:
        self._reposition()
        self.Refresh()
        event.Skip()

    def _apply_enabled_states(self, scan_type: ScanType) -> None:
        disabled = self._collecting
        self._label_ctrl.set_disabled(disabled or not self._label_enabled)
        for ctrl in self._motor_ctrls.values():
            ctrl.set_disabled(disabled)
        if self._get_btn is not None:
            self._get_btn.Enable(not disabled)
        if self._move_btn is not None:
            self._move_btn.Enable(not disabled and not self._limit_error)
        self._type_combo.Enable(not disabled)
        still = scan_type == "still"
        wide = scan_type == "wide"
        if disabled:
            self._rot_start_ctrl.set_disabled(True)
            self._rot_end_ctrl.set_disabled(True)
            self._step_ctrl.set_disabled(True)
            self._time_ctrl.set_disabled(True)
        else:
            self._rot_start_ctrl.set_disabled(still)
            self._rot_end_ctrl.set_disabled(still)
            self._step_ctrl.set_disabled(still or wide)
            self._time_ctrl.set_disabled(False)
        self._remove_btn.Enable(not disabled)

    def _on_type_commit(self, value: str) -> None:
        if value in SCAN_TYPES:
            self._apply_enabled_states(value)
            self._dispatch_type(value)

    def _make_commit_handler(self, ctrl: DarkTextCtrl, dispatcher_attr: str) -> Callable[[wx.Event], None]:
        # Look up the dispatcher method by name at fire-time so re-binding the
        # row to a different point is automatic — the closure only captures the
        # ctrl reference and the bound-method name.
        def _handler(event: wx.Event) -> None:
            getattr(self, dispatcher_attr)(ctrl.GetValue().strip())
            event.Skip()

        return _handler

    def _make_motor_commit_handler(self, ctrl: DarkTextCtrl, shorthand: str) -> Callable[[wx.Event], None]:
        def _handler(event: wx.Event) -> None:
            self._dispatch_motor(shorthand, ctrl.GetValue().strip())
            event.Skip()

        return _handler

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
        self._is_map = False
        self._motor_shorthands = motor_shorthands
        self._rotation_shorthand = rotation_shorthand
        self._labels = self._build_labels(motor_shorthands, rotation_shorthand)
        self._all_selected = False
        self._collecting = False
        self._on_select_all = on_select_all
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_click)

    def set_collecting(self, collecting: bool) -> None:
        self._collecting = collecting

    def update_col_widths(self, motor_shorthands: list[str], rotation_shorthand: str, col_widths: list[int]) -> None:
        self._col_widths = col_widths
        self._motor_shorthands = motor_shorthands
        self._rotation_shorthand = rotation_shorthand
        self._labels = self._build_labels(motor_shorthands, rotation_shorthand)
        self.Refresh()

    def set_map_mode(self, is_map: bool) -> None:
        self._is_map = is_map
        self._labels = self._build_labels(self._motor_shorthands, self._rotation_shorthand)
        self.Refresh()

    def set_all_selected(self, selected: bool) -> None:
        self._all_selected = selected
        self.Refresh()

    def _build_labels(self, motor_shorthands: list[str], rotation_shorthand: str) -> list[str]:
        rot = rotation_shorthand.capitalize() if rotation_shorthand else "Rot"
        motor_action_labels = ["Get", "Move"] if motor_shorthands else []
        ext_label = "Map Ext." if self._is_map else "Ext."
        return ["", ext_label] + [s.capitalize() for s in motor_shorthands] + motor_action_labels + ["Type", f"{rot} Start", f"{rot} End", "Step", "Time", ""]

    def _checkbox_rect(self) -> wx.Rect:
        cw = self._col_widths[0]
        return wx.Rect((cw - _BOX_S) // 2, (_HEADER_H - _BOX_S) // 2, _BOX_S, _BOX_S)

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

        gc.SetBrush(wx.Brush(_HEADER_BG))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)

        _draw_checkbox(gc, self._checkbox_rect(), self._all_selected)

        font = scaled_font(12, weight=wx.FONTWEIGHT_BOLD)
        gc.SetFont(font, FG_SECONDARY)

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
        if self._collecting:
            return
        if self._checkbox_rect().Contains(event.GetPosition()):
            self._all_selected = not self._all_selected
            self.Refresh()
            self._on_select_all(self._all_selected)
        else:
            event.Skip()


_NO_FIELD_ERRORS: tuple[dict[str, bool], bool, bool] = ({}, False, False)


class CollectionTableView(wx.Panel):
    """Editable collection-points table with a traditional grid look.

    Internally the table is virtualized:

    * ``self._points`` is the authoritative list of :class:`CollectionPoint`
      references (the view's logical row model).
    * ``self._pool`` holds a small number of :class:`_CollectionRow` widgets,
      enough to fill the viewport plus an overscan buffer.
    * Per-row UI state (selection, active highlight, limit errors,
      per-field limit errors) is stored in parallel ``list[...]`` attributes
      keyed by logical row index, so it survives across pool rebinds.

    The number of realized HWNDs / GDI handles is therefore bounded by the
    viewport height, not by the number of points in the table.
    """

    _SIDE_PAD = 20

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self.SetBackgroundColour(BG_CARD)

        self._motor_shorthands: list[str] = []
        self._motor_precisions: dict[str, int] = {}
        self._rotation_precision: int = 4
        self._rotation_shorthand: str = ""
        self._is_map: bool = False

        # Logical row model — the source of truth for what the table shows.
        self._points: list[CollectionPoint] = []
        self._selected_flags: list[bool] = []
        self._limit_error_flags: list[bool] = []
        self._field_errors: list[tuple[dict[str, bool], bool, bool]] = []
        self._active_index: int | None = None
        self._collecting: bool = False

        # Pool of realized row widgets.
        self._pool: list[_CollectionRow] = []
        self._dispatcher = _RowDispatcher()
        self._dispatcher.on_label = self._dispatch_label
        self._dispatcher.on_motor = self._dispatch_motor
        self._dispatcher.on_type = self._dispatch_type
        self._dispatcher.on_rot_start = self._dispatch_rot_start
        self._dispatcher.on_rot_end = self._dispatch_rot_end
        self._dispatcher.on_step = self._dispatch_step
        self._dispatcher.on_time = self._dispatch_time
        self._dispatcher.on_selection = self._dispatch_selection
        self._dispatcher.on_remove = self._dispatch_remove
        self._dispatcher.on_get = self._dispatch_get
        self._dispatcher.on_move = self._dispatch_move

        # External callbacks
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
        self._on_get_cb: Callable[[int], None] | None = None
        self._on_move_cb: Callable[[int], None] | None = None
        self._on_use_ext_changed_cb: Callable[[bool], None] | None = None
        self._on_keep_shutter_open_changed_cb: Callable[[bool], None] | None = None
        self._on_min_width_changed_cb: Callable[[int], None] | None = None

        self._build_layout()
        self.SetMinSize((self._min_content_width(), -1))
        self.Bind(wx.EVT_SIZE, self._on_size)

    # ---------------- Public API: collecting / mode toggles ----------------

    def set_collecting(self, collecting: bool) -> None:
        self._collecting = collecting
        self._delete_selected_btn.Enable(not collecting)
        self._clear_btn.Enable(not collecting)
        self._slew_scan_toggle.SetLocked(collecting)
        self._use_ext_toggle.SetLocked(collecting)
        self._keep_shutter_open_toggle.SetLocked(collecting)
        self._header.set_collecting(collecting)
        if not collecting:
            self._active_index = None
        self._repopulate_visible()

    def set_active_row(self, index: int | None) -> None:
        self._active_index = index
        if index is not None and 0 <= index < len(self._points):
            row_top = index * _ROW_H
            row_bot = row_top + _ROW_H
            self._viewport.ensure_visible(row_top, row_bot)
        self._repopulate_visible()

    def set_trajectory_visible(self, visible: bool) -> None:
        self._slew_scan_toggle.Show(visible)
        self.Layout()

    def set_keep_shutter_open_visible(self, visible: bool) -> None:
        self._keep_shutter_open_toggle.Show(visible)
        self.Layout()

    def set_use_ext_visible(self, visible: bool) -> None:
        self._use_ext_toggle.Show(visible)
        self.Layout()

    def set_map_mode(self, is_map: bool) -> None:
        self._is_map = is_map
        self._header.set_map_mode(is_map)
        self._repopulate_visible()

    def bind_use_ext_changed(self, callback: Callable[[bool], None]) -> None:
        self._on_use_ext_changed_cb = callback

    def bind_keep_shutter_open_changed(self, callback: Callable[[bool], None]) -> None:
        self._on_keep_shutter_open_changed_cb = callback

    def _on_use_ext_toggled(self, value: bool) -> None:
        self._repopulate_visible()
        if self._on_use_ext_changed_cb is not None:
            self._on_use_ext_changed_cb(value)

    def _on_trajectory_toggled(self, value: bool) -> None:
        if not value:
            self._keep_shutter_open_toggle.SetValue(False)
            self._keep_shutter_open_toggle.Hide()
        else:
            self._keep_shutter_open_toggle.Show()
        self.Layout()

    def _on_keep_shutter_open_toggled(self, event: wx.Event) -> None:
        if self._on_keep_shutter_open_changed_cb is not None:
            self._on_keep_shutter_open_changed_cb(self._keep_shutter_open_toggle.GetValue())

    @property
    def keep_shutter_open(self) -> bool:
        return self._keep_shutter_open_toggle.GetValue()

    @property
    def use_ext(self) -> bool:
        return self._use_ext_toggle.GetValue()

    @property
    def trajectory_scan(self) -> bool:
        return self._slew_scan_toggle.GetValue()

    @property
    def slew_scan(self) -> bool:
        return self._slew_scan_toggle.GetValue()

    @property
    def min_content_width(self) -> int:
        return self._min_content_width()

    def _min_content_width(self) -> int:
        n_motor = len(self._motor_shorthands)
        motor_cols = _MOTOR_W * n_motor + (_GET_W + _MOVE_W if n_motor else 0)
        return _CHECK_W + _EXT_W + motor_cols + _TYPE_W + _ROT_W + _ROT_W + _STEP_W + _TIME_W + _REMOVE_W + _SB_W + self._SIDE_PAD

    def _col_widths(self) -> list[int]:
        total = self.GetClientSize().width - _SB_W - self._SIDE_PAD
        n_motor = len(self._motor_shorthands)
        motor_cols = _MOTOR_W * n_motor + (_GET_W + _MOVE_W if n_motor else 0)
        fixed = _CHECK_W + motor_cols + _TYPE_W + _ROT_W + _ROT_W + _STEP_W + _TIME_W + _REMOVE_W
        ext_w = max(_EXT_W, total - fixed)
        motor_action_cols = [_GET_W, _MOVE_W] if n_motor else []
        return [_CHECK_W, ext_w] + [_MOTOR_W] * n_motor + motor_action_cols + [_TYPE_W, _ROT_W, _ROT_W, _STEP_W, _TIME_W, _REMOVE_W]

    def _build_layout(self) -> None:
        self._delete_selected_btn = FlatButton(self, "Delete selected", color_scheme=DANGER_SCHEME)
        self._delete_selected_btn.SetMinSize((100, 22))
        self._delete_selected_btn.set_action(self._on_delete_selected_clicked)

        self._clear_btn = FlatButton(self, "Clear all", color_scheme=DANGER_SCHEME)
        self._clear_btn.SetMinSize((70, 22))
        self._clear_btn.set_action(self._on_clear_clicked)

        self._slew_scan_toggle = DarkToggle(self, "Trajectory scanning")
        self._slew_scan_toggle.SetBackgroundColour(BG_CARD)
        self._slew_scan_toggle.SetValue(True)
        self._slew_scan_toggle.Hide()
        self._slew_scan_toggle.Bind(wx.EVT_CHECKBOX, self._on_trajectory_toggled)

        self._use_ext_toggle = DarkToggle(self, "Use Ext.")
        self._use_ext_toggle.SetBackgroundColour(BG_CARD)
        self._use_ext_toggle.SetValue(True)
        self._use_ext_toggle.Bind(wx.EVT_CHECKBOX, self._on_use_ext_toggled)

        self._keep_shutter_open_toggle = DarkToggle(self, "Keep shutter open")
        self._keep_shutter_open_toggle.SetBackgroundColour(BG_CARD)
        self._keep_shutter_open_toggle.Bind(wx.EVT_CHECKBOX, self._on_keep_shutter_open_toggled)
        self._keep_shutter_open_toggle.Hide()

        title_row = wx.BoxSizer(wx.HORIZONTAL)
        title_row.AddStretchSpacer()
        title_row.Add(self._keep_shutter_open_toggle, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.TOP | wx.BOTTOM, 4)
        title_row.Add(self._slew_scan_toggle, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.TOP | wx.BOTTOM, 4)
        title_row.Add(self._use_ext_toggle, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.TOP | wx.BOTTOM, 4)
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
        self._viewport = _RowsViewport(
            self,
            on_scroll_changed=self._on_scroll_changed,
            on_repopulate=self._repopulate_visible,
        )
        self._scrollbar.SetBackgroundColour(BG_ELEVATED)

        scroll_row = wx.BoxSizer(wx.HORIZONTAL)
        scroll_row.Add(self._viewport, 1, wx.EXPAND)
        scroll_row.Add(self._scrollbar, 0, wx.EXPAND)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(title_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.Add(title_sep, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.Add(self._header, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.Add(header_border, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.Add(scroll_row, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        self.SetSizer(outer)

    # ---------------- Public API: columns and row mutation ----------------

    def set_columns(self, motor_shorthands: list[str], rotation_shorthand: str = "", motor_precisions: dict[str, int] | None = None, rotation_precision: int = 4) -> None:
        self._motor_shorthands = list(motor_shorthands)
        self._motor_precisions = motor_precisions or {}
        self._rotation_precision = rotation_precision
        self._rotation_shorthand = rotation_shorthand
        min_w = self._min_content_width()
        self.SetMinSize((min_w, -1))
        if self._on_min_width_changed_cb is not None:
            self._on_min_width_changed_cb(min_w)
        widths = self._col_widths()
        self._header.update_col_widths(self._motor_shorthands, self._rotation_shorthand, widths)

        # Column set changed: tear down the entire pool (motor shorthands are
        # baked into each pooled row's child controls).
        for row in self._pool:
            row.Destroy()
        self._pool.clear()

        # Drop data too; the caller is expected to repopulate via add_row(s).
        self._points.clear()
        self._selected_flags.clear()
        self._limit_error_flags.clear()
        self._field_errors.clear()
        self._active_index = None

        self._viewport.set_virtual_height(0)
        self.Layout()

    def add_row(self, point: CollectionPoint) -> None:
        self.add_rows([point])

    def add_rows(self, points: list[CollectionPoint]) -> None:
        if not points:
            return
        for point in points:
            self._points.append(point)
            self._selected_flags.append(bool(point.selected))
            self._limit_error_flags.append(False)
            self._field_errors.append(_NO_FIELD_ERRORS)
        self._viewport.set_virtual_height(len(self._points) * _ROW_H)
        # Scroll to the bottom so newly-added rows are visible (matches the
        # previous non-virtualized behavior).
        self._viewport.scroll_to(1.0)
        self._sync_header_checkbox()

    def remove_row(self, index: int) -> None:
        if not (0 <= index < len(self._points)):
            return
        del self._points[index]
        del self._selected_flags[index]
        del self._limit_error_flags[index]
        del self._field_errors[index]
        if self._active_index is not None:
            if self._active_index == index:
                self._active_index = None
            elif self._active_index > index:
                self._active_index -= 1
        self._viewport.set_virtual_height(len(self._points) * _ROW_H)
        self._sync_header_checkbox()

    def refresh_row(self, index: int, point: CollectionPoint) -> None:
        if 0 <= index < len(self._points):
            self._points[index] = point
            self._refresh_pooled_for_index(index)

    def set_row_selected(self, index: int, selected: bool) -> None:
        if 0 <= index < len(self._selected_flags):
            self._selected_flags[index] = selected
            if 0 <= index < len(self._points):
                self._points[index].selected = selected
            self._refresh_pooled_for_index(index)
            self._sync_header_checkbox()

    def set_row_limit_error(self, index: int, error: bool) -> None:
        if 0 <= index < len(self._limit_error_flags):
            self._limit_error_flags[index] = error
            self._refresh_pooled_for_index(index)

    def set_row_field_limit_errors(self, index: int, motor_errors: dict[str, bool], rot_start_error: bool, rot_end_error: bool) -> None:
        if 0 <= index < len(self._field_errors):
            self._field_errors[index] = (dict(motor_errors), rot_start_error, rot_end_error)
            self._refresh_pooled_for_index(index)

    def update_row_motor_values(self, index: int, values: dict[str, str]) -> None:
        if not (0 <= index < len(self._points)):
            return
        point = self._points[index]
        for shorthand, value in values.items():
            point.motor_positions[shorthand] = value
        row = self._pooled_for_index(index)
        if row is not None:
            row.update_motor_values(values)

    # ---------------- Public API: bind callbacks ----------------

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

    def bind_get(self, callback: Callable[[int], None]) -> None:
        self._on_get_cb = callback

    def bind_move(self, callback: Callable[[int], None]) -> None:
        self._on_move_cb = callback

    def bind_min_width_changed(self, callback: Callable[[int], None]) -> None:
        self._on_min_width_changed_cb = callback

    # ---------------- Toolbar handlers ----------------

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
        for i in range(len(self._selected_flags)):
            self._selected_flags[i] = selected
            if i < len(self._points):
                self._points[i].selected = selected
            if self._on_selection_cb is not None:
                self._on_selection_cb(i, selected)
        self._repopulate_visible()

    def _on_sb_scroll(self, fraction: float) -> None:
        self._viewport.scroll_to(fraction)

    def _on_scroll_changed(self, pos: float, size: float) -> None:
        self._scrollbar.update(pos, size)

    def _on_size(self, event: wx.SizeEvent) -> None:
        widths = self._col_widths()
        self._header.update_col_widths(self._motor_shorthands, self._rotation_shorthand, widths)
        for row in self._pool:
            row.update_col_widths(widths)
        # Repopulating happens via the viewport's own EVT_SIZE handler.
        event.Skip()

    # ---------------- Dispatchers: pooled row -> external callbacks ----------------

    def _dispatch_label(self, idx: int, value: str) -> None:
        if 0 <= idx < len(self._points):
            self._points[idx].label = value
        if self._on_label_cb is not None:
            self._on_label_cb(idx, value)

    def _dispatch_motor(self, idx: int, shorthand: str, value: str) -> None:
        if 0 <= idx < len(self._points):
            self._points[idx].motor_positions[shorthand] = value
        if self._on_motor_cb is not None:
            self._on_motor_cb(idx, shorthand, value)

    def _dispatch_type(self, idx: int, value: ScanType) -> None:
        if 0 <= idx < len(self._points):
            self._points[idx].scan_type = value
        if self._on_type_cb is not None:
            self._on_type_cb(idx, value)

    def _dispatch_rot_start(self, idx: int, value: str) -> None:
        if 0 <= idx < len(self._points):
            self._points[idx].rotation_start = value
        if self._on_rotation_start_cb is not None:
            self._on_rotation_start_cb(idx, value)

    def _dispatch_rot_end(self, idx: int, value: str) -> None:
        if 0 <= idx < len(self._points):
            self._points[idx].rotation_end = value
        if self._on_rotation_end_cb is not None:
            self._on_rotation_end_cb(idx, value)

    def _dispatch_step(self, idx: int, value: str) -> None:
        if 0 <= idx < len(self._points):
            self._points[idx].step = value
        if self._on_step_cb is not None:
            self._on_step_cb(idx, value)

    def _dispatch_time(self, idx: int, value: str) -> None:
        if 0 <= idx < len(self._points):
            self._points[idx].time = value
        if self._on_time_cb is not None:
            self._on_time_cb(idx, value)

    def _dispatch_selection(self, idx: int, selected: bool) -> None:
        if 0 <= idx < len(self._selected_flags):
            self._selected_flags[idx] = selected
            if idx < len(self._points):
                self._points[idx].selected = selected
        if self._on_selection_cb is not None:
            self._on_selection_cb(idx, selected)
        self._sync_header_checkbox()

    def _dispatch_remove(self, idx: int) -> None:
        if self._on_remove_cb is not None:
            self._on_remove_cb(idx)

    def _dispatch_get(self, idx: int) -> None:
        if self._on_get_cb is not None:
            self._on_get_cb(idx)

    def _dispatch_move(self, idx: int) -> None:
        if self._on_move_cb is not None:
            self._on_move_cb(idx)

    def _sync_header_checkbox(self) -> None:
        all_checked = bool(self._selected_flags) and all(self._selected_flags)
        self._header.set_all_selected(all_checked)

    # ---------------- Pool management ----------------

    def _pool_capacity_needed(self) -> int:
        vh = self._viewport.viewport_height()
        if vh <= 0:
            return 0
        visible = (vh + _ROW_H - 1) // _ROW_H
        return visible + 2 * _OVERSCAN_ROWS

    def _ensure_pool_capacity(self, needed: int) -> None:
        widths = self._col_widths()
        rows_panel = self._viewport.rows_panel
        while len(self._pool) < needed:
            row = _CollectionRow(
                rows_panel,
                self._motor_shorthands,
                self._motor_precisions,
                self._rotation_precision,
                widths,
                self._dispatcher,
            )
            self._pool.append(row)
        # We deliberately never shrink the pool: when the viewport temporarily
        # gets smaller, surplus rows are simply hidden by the repopulate pass
        # so they stay warm for future growth without churning HWND/GDI.

    def _pooled_for_index(self, data_idx: int) -> _CollectionRow | None:
        for row in self._pool:
            if row.data_idx == data_idx and row.IsShown():
                return row
        return None

    def _refresh_pooled_for_index(self, data_idx: int) -> None:
        row = self._pooled_for_index(data_idx)
        if row is None:
            return
        self._bind_pool_row(row, data_idx)

    def _bind_pool_row(self, row: _CollectionRow, data_idx: int) -> None:
        point = self._points[data_idx]
        bg = BG_CARD if data_idx % 2 == 0 else _ROW_ALT
        selected = self._selected_flags[data_idx]
        active = (self._active_index == data_idx)
        limit_error = self._limit_error_flags[data_idx]
        field_errors = self._field_errors[data_idx]
        label_enabled = (not self._is_map) and self._use_ext_toggle.GetValue()
        row.bind_to(
            data_idx=data_idx,
            point=point,
            bg=bg,
            selected=selected,
            active=active,
            limit_error=limit_error,
            field_errors=field_errors,
            collecting=self._collecting,
            label_enabled=label_enabled,
        )

    def _repopulate_visible(self) -> None:
        n_points = len(self._points)
        needed = self._pool_capacity_needed()
        if n_points == 0 or needed == 0:
            # Nothing to show — hide all pooled rows but keep them allocated
            # so we don't churn HWND/GDI on small data changes.
            for row in self._pool:
                row.clear_binding()
            return

        # Make sure the pool is large enough. We never shrink (only hide).
        self._ensure_pool_capacity(needed)

        vh = self._viewport.viewport_height()
        offset = self._viewport.scroll_offset
        first_visible = max(0, offset // _ROW_H - _OVERSCAN_ROWS)
        last_visible = min(n_points - 1, (offset + vh) // _ROW_H + _OVERSCAN_ROWS)
        want_indices = list(range(first_visible, last_visible + 1))

        # Pool rows already bound to a wanted index stay put; others are reused
        # for indices that aren't covered yet. This minimizes how many widgets
        # we have to repaint per scroll tick.
        bound_now: dict[int, _CollectionRow] = {}
        unused: list[_CollectionRow] = []
        for row in self._pool:
            if row.data_idx in want_indices and row.data_idx not in bound_now:
                bound_now[row.data_idx] = row
            else:
                unused.append(row)

        rows_panel = self._viewport.rows_panel
        rows_panel.Freeze()
        try:
            for data_idx in want_indices:
                row = bound_now.get(data_idx)
                if row is None:
                    if not unused:
                        # Should not happen given _ensure_pool_capacity, but be
                        # defensive in case the viewport changed mid-loop.
                        break
                    row = unused.pop()
                    self._bind_pool_row(row, data_idx)
                else:
                    # Still re-bind so per-row state (selection, active, errors)
                    # stays in sync with the view's authoritative model after
                    # external mutations.
                    self._bind_pool_row(row, data_idx)
                y = data_idx * _ROW_H - offset
                row.SetPosition((0, y))
                row.SetSize(rows_panel.GetClientSize().width, _ROW_H)
                if not row.IsShown():
                    row.Show()
            # Hide whatever we didn't use.
            for row in unused:
                row.clear_binding()
        finally:
            rows_panel.Thaw()
