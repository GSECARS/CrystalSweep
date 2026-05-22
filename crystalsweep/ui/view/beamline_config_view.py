#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/beamline_config_view.py
# ----------------------------------------------------------------------------------
# Purpose:
# Beamline configuration panels and modal dialogs: General, Detectors, Controllers,
# and Positioners (rotation stage + motors) with a consistent table-styled UI.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from typing import Callable, Protocol

import wx

from crystalsweep.model.beamline_config_model import BeamlineConfig, ControllerConfig, DetectorConfig, MotorConfig
from crystalsweep.ui.view.custom.theme import ACCENT, BG_CARD, BG_SURFACE, DANGER, FG_PRIMARY, FG_SECONDARY, POPUP_BG, POPUP_FG, SEP_COLOUR, scaled_font
from crystalsweep.ui.view.custom.widgets import DANGER_SCHEME, DarkCombo, DarkScrollBar, DarkTextCtrl, DarkToggle, FlatButton, RadioDot

__all__ = [
    "GeneralConfigView",
    "GeneralConfigDialog",
    "DetectorsConfigView",
    "DetectorsConfigDialog",
    "ControllersConfigView",
    "ControllersConfigDialog",
    "PositionersConfigView",
    "PositionersConfigDialog",
]

_ROW_H = 28
_HEADER_H = 30
_ROW_ALT = wx.Colour(32, 32, 36)
_HEADER_BG = wx.Colour(22, 22, 26)
_BORDER = wx.Colour(50, 50, 56)
_PAD = 6

_PLACEHOLDER_BEAMLINE = "e.g. 13-IDD"
_PLACEHOLDER_ROTATION_SHORT = "e.g. omega"
_PLACEHOLDER_ROTATION_DESCRIPTION = "e.g. rotation"
_PLACEHOLDER_ROTATION_PV = "e.g. 13IDD:m7.VAL"
_PLACEHOLDER_DETECTOR_NAME = "e.g. Eiger 9M"
_PLACEHOLDER_DETECTOR_PREFIX = "e.g. 13EIG2_9M:"
_PLACEHOLDER_CONTROLLER_NAME = "e.g. xps1"
_PLACEHOLDER_MOTOR_SHORT = "e.g. vert"
_PLACEHOLDER_MOTOR_DESCRIPTION = "e.g. vertical"
_PLACEHOLDER_MOTOR_PV = "e.g. 13IDD:m1.VAL"
_PLACEHOLDER_MOTOR_PRECISION = "4"
_PLACEHOLDER_XPS_GROUP = "e.g. G6"
_PLACEHOLDER_XPS_POSITIONER = "e.g. ST-Hor"

_DETECTOR_TYPE_LABELS: list[tuple[str, str]] = [
    ("eiger", "Eiger"),
    ("pilatus", "Pilatus"),
    ("spinnaker", "Spinnaker"),
]
_DETECTOR_TYPES = [t for t, _ in _DETECTOR_TYPE_LABELS]
_DETECTOR_DISPLAY_NAMES = [label for _, label in _DETECTOR_TYPE_LABELS]
_DET_LABEL_TO_TYPE = {label: t for t, label in _DETECTOR_TYPE_LABELS}
_DET_TYPE_TO_LABEL = {t: label for t, label in _DETECTOR_TYPE_LABELS}

_CONTROLLER_TYPE_LABELS: list[tuple[str, str]] = [
    ("newport_xps", "NewportXPS C/D"),
    ("aerotech_a1", "Automation1"),
]
_CONTROLLER_TYPES = [t for t, _ in _CONTROLLER_TYPE_LABELS]
_CONTROLLER_DISPLAY_NAMES = [label for _, label in _CONTROLLER_TYPE_LABELS]
_LABEL_TO_TYPE = {label: t for t, label in _CONTROLLER_TYPE_LABELS}
_TYPE_TO_LABEL = {t: label for t, label in _CONTROLLER_TYPE_LABELS}

_CONTROLLER_TYPE_PARAMS: dict[str, list[tuple[str, str]]] = {
    "newport_xps": [("host", "e.g. 192.168.0.1"), ("username", "Administrator"), ("password", "")],
    "aerotech_a1": [("ip", "e.g. 192.168.0.2"), ("axis_name", "e.g. Theta"), ("counts_per_unit", "e.g. 1491308.09")],
}


class _ConfigSaveCallback(Protocol):
    def __call__(self) -> None: ...


def _label(parent: wx.Window, text: str, bold: bool = False, secondary: bool = False) -> wx.StaticText:
    lbl = wx.StaticText(parent, label=text)
    lbl.SetBackgroundColour(parent.GetBackgroundColour())
    lbl.SetForegroundColour(FG_SECONDARY if secondary else FG_PRIMARY)
    lbl.SetFont(scaled_font(12, weight=wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL))
    return lbl


class _Section(wx.Panel):
    """Card-like grouping with a bold title, separator, and a body panel."""

    def __init__(self, parent: wx.Window, title: str) -> None:
        super().__init__(parent)
        self.SetBackgroundColour(BG_CARD)
        title_lbl = _label(self, title, bold=True)
        title_lbl.SetForegroundColour(FG_PRIMARY)
        sep = wx.Panel(self, size=wx.Size(-1, 1))
        sep.SetBackgroundColour(SEP_COLOUR)
        self.body = wx.Panel(self)
        self.body.SetBackgroundColour(BG_CARD)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(title_lbl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        sizer.AddSpacer(6)
        sizer.Add(sep, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        sizer.AddSpacer(8)
        sizer.Add(self.body, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.SetSizer(sizer)


class _TableHeader(wx.Panel):
    """Painted column-header bar matching the collection table style."""

    def __init__(self, parent: wx.Window, labels: list[str], proportions: list[int]) -> None:
        super().__init__(parent, size=(-1, _HEADER_H), style=wx.BORDER_NONE)
        self.SetBackgroundColour(_HEADER_BG)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self._labels = labels
        self._proportions = proportions
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, lambda _e: self.Refresh())

    def _col_widths(self, total: int) -> list[int]:
        total_parts = sum(self._proportions)
        if total_parts == 0:
            return [0] * len(self._proportions)
        widths = [total * p // total_parts for p in self._proportions]
        widths[-1] += total - sum(widths)
        return widths

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(_HEADER_BG))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        widths = self._col_widths(w)
        font = scaled_font(12, weight=wx.FONTWEIGHT_BOLD)
        gc.SetFont(font, ACCENT)
        gc.SetPen(wx.Pen(_BORDER, 1))
        x = 0
        for i, (label, cw) in enumerate(zip(self._labels, widths)):
            if label:
                tw, th = gc.GetTextExtent(label)
                gc.DrawText(label, x + (cw - tw) / 2, (h - th) / 2)
            if i < len(widths) - 1:
                gc.StrokeLine(x + cw, 0, x + cw, h)
            x += cw
        gc.SetPen(wx.Pen(_BORDER, 1))
        gc.StrokeLine(0, h - 1, w, h - 1)


class _TableRow(wx.Panel):
    """Base for a painted data row with absolute-positioned controls."""

    def __init__(self, parent: wx.Window, bg: wx.Colour, proportions: list[int]) -> None:
        super().__init__(parent, size=(-1, _ROW_H), style=wx.BORDER_NONE)
        self.SetBackgroundColour(bg)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self._proportions = proportions
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, self._on_size)

    def _col_widths(self, total: int) -> list[int]:
        total_parts = sum(self._proportions)
        if total_parts == 0:
            return [0] * len(self._proportions)
        widths = [total * p // total_parts for p in self._proportions]
        widths[-1] += total - sum(widths)
        return widths

    def _reposition(self) -> None:
        """Subclasses place controls using _col_widths(self.GetClientSize().width)."""

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetBrush(wx.Brush(self.GetBackgroundColour()))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)
        gc.SetPen(wx.Pen(_BORDER, 1))
        gc.StrokeLine(0, h - 1, w, h - 1)
        widths = self._col_widths(w)
        x = 0
        for i, cw in enumerate(widths[:-1]):
            x += cw
            gc.StrokeLine(x, 0, x, h)

    def _on_size(self, event: wx.SizeEvent) -> None:
        self._reposition()
        self.Refresh()
        event.Skip()

    def _place(self, ctrl: wx.Window, x: int, cw: int) -> None:
        ctrl.SetSize(x + _PAD, 4, cw - _PAD * 2, _ROW_H - 8)


class _DetectorRow(_TableRow):
    _PROPS = [2, 8, 4, 12, 2]

    def __init__(
        self,
        parent: wx.Window,
        detector: DetectorConfig,
        active: bool,
        index: int,
        on_make_active: Callable[["_DetectorRow"], None],
        on_remove: Callable[["_DetectorRow"], None],
    ) -> None:
        bg = BG_CARD if index % 2 == 0 else _ROW_ALT
        super().__init__(parent, bg, self._PROPS)
        self._on_make_active = on_make_active
        self._on_remove = on_remove

        self.active_dot = RadioDot(self, value=active, tooltip="Set as active detector")
        self.active_dot.set_action(lambda: on_make_active(self))
        self.name_ctrl = DarkTextCtrl(self, value=detector.name, placeholder=_PLACEHOLDER_DETECTOR_NAME)
        display = _DET_TYPE_TO_LABEL.get(detector.type, _DETECTOR_DISPLAY_NAMES[0])
        sel = _DETECTOR_DISPLAY_NAMES.index(display) if display in _DETECTOR_DISPLAY_NAMES else 0
        self.type_combo = DarkCombo(self, choices=_DETECTOR_DISPLAY_NAMES, selection=sel)
        self.prefix_ctrl = DarkTextCtrl(self, value=detector.pv_prefix, placeholder=_PLACEHOLDER_DETECTOR_PREFIX)
        self._remove_btn = FlatButton(self, "×", color_scheme=DANGER_SCHEME)
        self._remove_btn.set_action(lambda: on_remove(self))
        self._reposition()

    def _reposition(self) -> None:
        w, _ = self.GetClientSize()
        if w <= 0:
            return
        widths = self._col_widths(w)
        x = 0
        rw, rh = self.active_dot.GetBestSize()
        self.active_dot.SetSize(x + (widths[0] - rw) // 2, (_ROW_H - rh) // 2, rw, rh)
        x += widths[0]
        self._place(self.name_ctrl, x, widths[1])
        x += widths[1]
        self._place(self.type_combo, x, widths[2])
        x += widths[2]
        self._place(self.prefix_ctrl, x, widths[3])
        x += widths[3]
        self._place(self._remove_btn, x, widths[4])

    def to_detector(self) -> DetectorConfig:
        det_type = _DET_LABEL_TO_TYPE.get(self.type_combo.GetStringSelection(), _DETECTOR_TYPES[0])
        return DetectorConfig(
            name=self.name_ctrl.GetValue().strip(),
            pv_prefix=self.prefix_ctrl.GetValue().strip(),
            type=det_type,
        )

    def set_active_visual(self, active: bool) -> None:
        self.active_dot.set_value(active)


class _ControllerRow(_TableRow):
    _PROPS = [5, 5, 18, 2]

    def __init__(
        self,
        parent: wx.Window,
        controller: ControllerConfig,
        index: int,
        on_remove: Callable[["_ControllerRow"], None],
        on_name_changed: Callable[[], None] | None = None,
    ) -> None:
        bg = BG_CARD if index % 2 == 0 else _ROW_ALT
        super().__init__(parent, bg, self._PROPS)
        self._on_remove = on_remove
        self._on_name_changed = on_name_changed

        self.name_ctrl = DarkTextCtrl(self, value=controller.name, placeholder=_PLACEHOLDER_CONTROLLER_NAME)
        self.name_ctrl.Bind(wx.EVT_TEXT, self._on_name_text)
        self.name_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_name_text)

        display = _TYPE_TO_LABEL.get(controller.type, _CONTROLLER_DISPLAY_NAMES[0])
        sel = _CONTROLLER_DISPLAY_NAMES.index(display) if display in _CONTROLLER_DISPLAY_NAMES else 0
        self.type_combo = DarkCombo(self, choices=_CONTROLLER_DISPLAY_NAMES, selection=sel)
        self.type_combo.Bind(wx.EVT_CHOICE, self._on_type_changed)

        self._params_panel = wx.Panel(self)
        self._params_panel.SetBackgroundColour(self.GetBackgroundColour())
        self._params_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._params_panel.SetSizer(self._params_sizer)
        self._param_ctrls: dict[str, DarkTextCtrl] = {}
        self._build_params(controller.type, controller.params)

        self._remove_btn = FlatButton(self, "×", color_scheme=DANGER_SCHEME)
        self._remove_btn.set_action(lambda: on_remove(self))
        self._reposition()

    def _reposition(self) -> None:
        w, _ = self.GetClientSize()
        if w <= 0:
            return
        widths = self._col_widths(w)
        x = 0
        self._place(self.name_ctrl, x, widths[0])
        x += widths[0]
        self._place(self.type_combo, x, widths[1])
        x += widths[1]
        self._params_panel.SetSize(x + _PAD, 4, widths[2] - _PAD * 2, _ROW_H - 8)
        x += widths[2]
        self._place(self._remove_btn, x, widths[3])

    def _build_params(self, controller_type: str, existing: dict) -> None:
        self._params_sizer.Clear(delete_windows=True)
        self._param_ctrls.clear()
        bg = self.GetBackgroundColour()
        for key, placeholder in _CONTROLLER_TYPE_PARAMS.get(controller_type, []):
            lbl = wx.StaticText(self._params_panel, label=f"{key}:")
            lbl.SetForegroundColour(FG_SECONDARY)
            lbl.SetBackgroundColour(bg)
            lbl.SetFont(scaled_font(11))
            ctrl = DarkTextCtrl(self._params_panel, value=str(existing.get(key, "")), placeholder=placeholder)
            self._params_sizer.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 2)
            self._params_sizer.Add(ctrl, 1, wx.EXPAND | wx.RIGHT, 6)
            self._param_ctrls[key] = ctrl
        self._params_panel.Layout()

    def _current_type(self) -> str:
        return _LABEL_TO_TYPE.get(self.type_combo.GetStringSelection(), _CONTROLLER_TYPES[0])

    def _on_name_text(self, event: wx.Event) -> None:
        if self._on_name_changed is not None:
            self._on_name_changed()
        event.Skip()

    def _on_type_changed(self, value: str) -> None:
        self._build_params(_LABEL_TO_TYPE.get(value, _CONTROLLER_TYPES[0]), {})
        self._reposition()
        p = self.GetParent()
        if hasattr(p, "_sync"):
            p._sync()
        else:
            p.Layout()

    def to_controller(self) -> ControllerConfig:
        params = {k: ctrl.GetValue().strip() for k, ctrl in self._param_ctrls.items() if ctrl.GetValue().strip()}
        return ControllerConfig(name=self.name_ctrl.GetValue().strip(), type=self._current_type(), params=params)

    def controller_name(self) -> str:
        return self.name_ctrl.GetValue().strip()


class _RotationRow(_TableRow):
    _PROPS = [3, 6, 10, 2, 7]

    def __init__(self, parent: wx.Window, motor: MotorConfig | None) -> None:
        super().__init__(parent, BG_CARD, self._PROPS)
        rm = motor
        self._controller_types: dict[str, str] = {}

        self.short_ctrl = DarkTextCtrl(self, value=rm.shorthand if rm else "", placeholder=_PLACEHOLDER_ROTATION_SHORT)
        self.description_ctrl = DarkTextCtrl(self, value=rm.description if rm else "", placeholder=_PLACEHOLDER_ROTATION_DESCRIPTION)
        self.pv_ctrl = DarkTextCtrl(self, value=rm.pv if rm else "", placeholder=_PLACEHOLDER_ROTATION_PV)
        self.precision_ctrl = DarkTextCtrl(self, value=str(rm.precision) if rm else "4", placeholder=_PLACEHOLDER_MOTOR_PRECISION)
        self.controller_combo = DarkCombo(self, choices=["epics"], selection=0)
        self.controller_combo.Bind(wx.EVT_CHOICE, lambda _e: self._on_controller_changed())

        self.xps_group_ctrl = DarkTextCtrl(self, value=rm.xps_group if rm else "", placeholder=_PLACEHOLDER_XPS_GROUP)
        self.xps_positioner_ctrl = DarkTextCtrl(self, value=rm.xps_positioner if rm else "", placeholder=_PLACEHOLDER_XPS_POSITIONER)
        self._reposition()

    def _is_xps(self) -> bool:
        name = self.controller_combo.GetStringSelection()
        return self._controller_types.get(name) == "newport_xps"

    def _on_controller_changed(self) -> None:
        self._reposition()
        self.Refresh()

    def _reposition(self) -> None:
        w, _ = self.GetClientSize()
        if w <= 0:
            return
        widths = self._col_widths(w)
        x = 0
        for ctrl, cw in zip(
            (self.short_ctrl, self.description_ctrl, self.pv_ctrl, self.precision_ctrl),
            widths[:4],
        ):
            self._place(ctrl, x, cw)
            x += cw
        xps = self._is_xps()
        ctrl_w = widths[4]
        if xps:
            third = ctrl_w // 3
            self._place(self.controller_combo, x, third)
            self._place(self.xps_group_ctrl, x + third, third)
            self._place(self.xps_positioner_ctrl, x + third * 2, ctrl_w - third * 2)
            self.xps_group_ctrl.Show()
            self.xps_positioner_ctrl.Show()
        else:
            self._place(self.controller_combo, x, ctrl_w)
            self.xps_group_ctrl.Hide()
            self.xps_positioner_ctrl.Hide()

    def update_controller_choices(self, choices: list[str], selected: str = "epics", controller_types: dict[str, str] | None = None) -> None:
        if controller_types is not None:
            self._controller_types = controller_types
        self.controller_combo.SetChoices(choices)
        if selected in choices:
            self.controller_combo.SetSelection(choices.index(selected))
        self._reposition()
        self.Refresh()


class _MotorRow(_TableRow):
    _PROPS = [3, 6, 10, 2, 2, 6, 2]

    def __init__(
        self,
        parent: wx.Window,
        motor: MotorConfig,
        controller_names: list[str],
        controller_types: dict[str, str],
        index: int,
        on_remove: Callable[["_MotorRow"], None],
    ) -> None:
        bg = BG_CARD if index % 2 == 0 else _ROW_ALT
        super().__init__(parent, bg, self._PROPS)
        self._controller_types = controller_types

        self.shorthand_ctrl = DarkTextCtrl(self, value=motor.shorthand, placeholder=_PLACEHOLDER_MOTOR_SHORT)
        self.description_ctrl = DarkTextCtrl(self, value=motor.description, placeholder=_PLACEHOLDER_MOTOR_DESCRIPTION)
        self.pv_ctrl = DarkTextCtrl(self, value=motor.pv, placeholder=_PLACEHOLDER_MOTOR_PV)
        self.precision_ctrl = DarkTextCtrl(self, value=str(motor.precision), placeholder=_PLACEHOLDER_MOTOR_PRECISION)

        self.mapping_toggle = DarkToggle(self, "")
        self.mapping_toggle.SetBackgroundColour(bg)
        self.mapping_toggle.SetValue(motor.mapping_enabled)

        controller_choices = ["epics"] + controller_names
        sel = controller_choices.index(motor.controller) if motor.controller in controller_choices else 0
        self.controller_combo = DarkCombo(self, choices=controller_choices, selection=sel)
        self.controller_combo.Bind(wx.EVT_CHOICE, lambda _e: self._on_controller_changed())

        self.xps_group_ctrl = DarkTextCtrl(self, value=motor.xps_group, placeholder=_PLACEHOLDER_XPS_GROUP)
        self.xps_positioner_ctrl = DarkTextCtrl(self, value=motor.xps_positioner, placeholder=_PLACEHOLDER_XPS_POSITIONER)

        self._remove_btn = FlatButton(self, "×", color_scheme=DANGER_SCHEME)
        self._remove_btn.set_action(lambda: on_remove(self))
        self._reposition()

    def _is_xps(self) -> bool:
        name = self.controller_combo.GetStringSelection()
        return self._controller_types.get(name) == "newport_xps"

    def _on_controller_changed(self) -> None:
        self._reposition()
        self.Refresh()

    def _reposition(self) -> None:
        w, _ = self.GetClientSize()
        if w <= 0:
            return
        widths = self._col_widths(w)
        x = 0
        for ctrl, cw in zip(
            (self.shorthand_ctrl, self.description_ctrl, self.pv_ctrl, self.precision_ctrl),
            widths[:4],
        ):
            self._place(ctrl, x, cw)
            x += cw
        tw, th = self.mapping_toggle.GetBestSize()
        self.mapping_toggle.SetSize(x + (widths[4] - tw) // 2, (_ROW_H - th) // 2, tw, th)
        x += widths[4]
        xps = self._is_xps()
        ctrl_w = widths[5]
        if xps:
            third = ctrl_w // 3
            self._place(self.controller_combo, x, third)
            self._place(self.xps_group_ctrl, x + third, third)
            self._place(self.xps_positioner_ctrl, x + third * 2, ctrl_w - third * 2)
            self.xps_group_ctrl.Show()
            self.xps_positioner_ctrl.Show()
        else:
            self._place(self.controller_combo, x, ctrl_w)
            self.xps_group_ctrl.Hide()
            self.xps_positioner_ctrl.Hide()
        x += ctrl_w
        self._place(self._remove_btn, x, widths[6])

    def update_controller_choices(self, controller_names: list[str], controller_types: dict[str, str] | None = None) -> None:
        if controller_types is not None:
            self._controller_types = controller_types
        current = self.controller_combo.GetStringSelection()
        choices = ["epics"] + controller_names
        self.controller_combo.SetChoices(choices)
        if current in choices:
            self.controller_combo.SetSelection(choices.index(current))
        self._reposition()
        self.Refresh()

    def to_motor(self) -> MotorConfig:
        try:
            precision = max(0, int(self.precision_ctrl.GetValue().strip()))
        except ValueError:
            precision = 4
        return MotorConfig(
            shorthand=self.shorthand_ctrl.GetValue().strip(),
            description=self.description_ctrl.GetValue().strip(),
            pv=self.pv_ctrl.GetValue().strip(),
            precision=precision,
            mapping_enabled=self.mapping_toggle.GetValue(),
            controller=self.controller_combo.GetStringSelection() or "epics",
            xps_group=self.xps_group_ctrl.GetValue().strip() if self._is_xps() else "",
            xps_positioner=self.xps_positioner_ctrl.GetValue().strip() if self._is_xps() else "",
        )


def _restripe(rows: list, sizer: wx.BoxSizer) -> None:
    for i, row in enumerate(rows):
        row.SetBackgroundColour(BG_CARD if i % 2 == 0 else _ROW_ALT)
        row.Refresh()


def _status_label(parent: wx.Panel) -> wx.StaticText:
    lbl = wx.StaticText(parent, label="")
    lbl.SetBackgroundColour(POPUP_BG)
    lbl.SetForegroundColour(FG_SECONDARY)
    lbl.SetFont(scaled_font(11))
    return lbl


class _DarkScrolledPanel(wx.Panel):
    """A viewport + DarkScrollBar container that replaces wx.ScrolledWindow for
    dark-themed table rows. Children are stacked in a vertical sizer inside a
    plain panel; the DarkScrollBar keeps them in sync."""

    def __init__(self, parent: wx.Window, row_height: int = _ROW_H) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self.SetBackgroundColour(BG_CARD)
        self._row_h = row_height
        self._offset: int = 0

        self._viewport = wx.Panel(self, style=wx.BORDER_NONE)
        self._viewport.SetBackgroundColour(BG_CARD)

        self.rows_sizer = wx.BoxSizer(wx.VERTICAL)
        self._content = wx.Panel(self._viewport, style=wx.BORDER_NONE)
        self._content.SetBackgroundColour(BG_CARD)
        self._content.SetSizer(self.rows_sizer)

        self._scrollbar = DarkScrollBar(self, on_scroll=self._on_sb_scroll)

        outer = wx.BoxSizer(wx.HORIZONTAL)
        outer.Add(self._viewport, 1, wx.EXPAND)
        outer.Add(self._scrollbar, 0, wx.EXPAND)
        self.SetSizer(outer)

        self._viewport.Bind(wx.EVT_SIZE, self._on_viewport_size)
        self._viewport.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel)
        self._content.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel)

    def add_row(self, row: wx.Window) -> None:
        self.rows_sizer.Add(row, 0, wx.EXPAND)
        self._content.Layout()
        self._sync()

    def remove_row(self, row: wx.Window) -> None:
        self.rows_sizer.Detach(row)
        self._content.Layout()
        self._sync()

    def clear_rows(self) -> None:
        self.rows_sizer.Clear(delete_windows=False)
        self._content.Layout()
        self._sync()

    def bind_mousewheel(self, window: wx.Window) -> None:
        window.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel)

    def _content_height(self) -> int:
        return self._content.GetBestSize().height

    def _viewport_height(self) -> int:
        return self._viewport.GetClientSize().height

    def _max_offset(self) -> int:
        return max(0, self._content_height() - self._viewport_height())

    def _apply_offset(self) -> None:
        self._offset = max(0, min(self._offset, self._max_offset()))
        w = self._viewport.GetClientSize().width
        h = max(self._content_height(), self._viewport_height())
        self._content.SetSize(0, -self._offset, w, h)
        self._sync_scrollbar()

    def _sync_scrollbar(self) -> None:
        total = self._content_height()
        visible = self._viewport_height()
        if total <= visible:
            self._scrollbar.update(0.0, 1.0)
        else:
            self._scrollbar.update(self._offset / (total - visible), visible / total)

    def _sync(self) -> None:
        self._apply_offset()

    def _on_sb_scroll(self, fraction: float) -> None:
        self._offset = int(fraction * self._max_offset())
        self._apply_offset()

    def _on_viewport_size(self, event: wx.SizeEvent) -> None:
        event.Skip()
        self._apply_offset()

    def _on_wheel(self, event: wx.MouseEvent) -> None:
        delta = event.GetWheelRotation() // event.GetWheelDelta()
        self._offset = max(0, min(self._offset - delta * self._row_h, self._max_offset()))
        self._apply_offset()
        event.Skip()


class GeneralConfigView(wx.Panel):
    """General configuration: beamline name."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.SetBackgroundColour(POPUP_BG)
        self.SetForegroundColour(POPUP_FG)
        self._on_save_cb: Callable[[], None] | None = None
        self._build_layout()

    def _build_layout(self) -> None:
        self._beamline_section = _Section(self, "Beamline")
        b_body = self._beamline_section.body
        self._beamline_ctrl = DarkTextCtrl(b_body, placeholder=_PLACEHOLDER_BEAMLINE)
        self._beamline_ctrl.SetMinSize((-1, 28))
        b_sizer = wx.BoxSizer(wx.VERTICAL)
        b_sizer.Add(_label(b_body, "Name", secondary=True), 0, wx.BOTTOM, 4)
        b_sizer.Add(self._beamline_ctrl, 0, wx.EXPAND)
        b_body.SetSizer(b_sizer)

        self._status_label = _status_label(self)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(self._beamline_section, 0, wx.EXPAND | wx.ALL, 10)
        outer.Add(self._status_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.SetSizer(outer)
        self.SetMinSize((400, -1))

    def bind_save(self, callback: Callable[[], None]) -> None:
        self._on_save_cb = callback

    def load_config(self, config: BeamlineConfig) -> None:
        self._beamline_ctrl.SetValue(config.beamline)
        self.set_status("")

    def beamline_name(self) -> str:
        return self._beamline_ctrl.GetValue().strip()

    def set_status(self, text: str, error: bool = False) -> None:
        self._status_label.SetForegroundColour(DANGER if error else FG_SECONDARY)
        self._status_label.SetLabel(text)
        self.Layout()

    def trigger_save(self) -> None:
        if self._on_save_cb is not None:
            self._on_save_cb()


class DetectorsConfigView(wx.Panel):
    """Detectors configuration: manage detector list."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.SetBackgroundColour(POPUP_BG)
        self.SetForegroundColour(POPUP_FG)
        self._detector_rows: list[_DetectorRow] = []
        self._on_save_cb: Callable[[], None] | None = None
        self._build_layout()

    def _build_layout(self) -> None:
        self._detectors_section = _Section(self, "Detectors")
        d_body = self._detectors_section.body
        self._det_header = _TableHeader(d_body, ["", "Name", "Type", "PV prefix", ""], [2, 8, 4, 12, 2])
        self._detector_rows_panel = _DarkScrolledPanel(d_body)
        self._detector_rows_panel.SetMinSize((-1, _ROW_H * 3))
        self._add_detector_btn = FlatButton(d_body, "+ Add detector")
        self._add_detector_btn.SetMinSize((-1, 26))
        self._add_detector_btn.set_action(self._on_add_detector_clicked)
        d_sizer = wx.BoxSizer(wx.VERTICAL)
        d_sizer.Add(self._det_header, 0, wx.EXPAND)
        d_sizer.Add(self._detector_rows_panel, 1, wx.EXPAND | wx.BOTTOM, 6)
        d_sizer.Add(self._add_detector_btn, 0, wx.EXPAND)
        d_body.SetSizer(d_sizer)

        self._status_label = _status_label(self)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(self._detectors_section, 1, wx.EXPAND | wx.ALL, 10)
        outer.Add(self._status_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.SetSizer(outer)
        self.SetMinSize((500, -1))

    def bind_save(self, callback: Callable[[], None]) -> None:
        self._on_save_cb = callback

    def load_config(self, config: BeamlineConfig) -> None:
        self._clear_detector_rows()
        for idx, detector in enumerate(config.detectors):
            self._append_detector_row(detector, active=idx == config.active_detector)
        self.Layout()
        self.set_status("")

    def collect_detectors(self) -> tuple[tuple[DetectorConfig, ...], int]:
        detectors: list[DetectorConfig] = []
        active_index = -1
        for row in self._detector_rows:
            det = row.to_detector()
            if not det.name and not det.pv_prefix:
                continue
            if row.active_dot.get_value() and active_index == -1:
                active_index = len(detectors)
            detectors.append(det)
        if detectors and active_index == -1:
            active_index = 0
        return tuple(detectors), active_index

    def set_status(self, text: str, error: bool = False) -> None:
        self._status_label.SetForegroundColour(DANGER if error else FG_SECONDARY)
        self._status_label.SetLabel(text)
        self.Layout()

    def trigger_save(self) -> None:
        if self._on_save_cb is not None:
            self._on_save_cb()

    def _clear_detector_rows(self) -> None:
        for row in self._detector_rows:
            self._detector_rows_panel.remove_row(row)
            row.Destroy()
        self._detector_rows.clear()

    def _append_detector_row(self, detector: DetectorConfig, active: bool) -> None:
        index = len(self._detector_rows)
        row = _DetectorRow(
            self._detector_rows_panel._content,
            detector,
            active,
            index,
            on_make_active=self._on_make_detector_active,
            on_remove=self._on_remove_detector,
        )
        self._detector_rows_panel.bind_mousewheel(row)
        self._detector_rows.append(row)
        self._detector_rows_panel.add_row(row)

    def _on_add_detector_clicked(self) -> None:
        self._append_detector_row(DetectorConfig(), active=not self._detector_rows)

    def _on_make_detector_active(self, row: _DetectorRow) -> None:
        for r in self._detector_rows:
            r.set_active_visual(r is row)

    def _on_remove_detector(self, row: _DetectorRow) -> None:
        if row not in self._detector_rows:
            return
        was_active = row.active_dot.get_value()
        self._detector_rows.remove(row)
        self._detector_rows_panel.remove_row(row)
        row.Destroy()
        if was_active and self._detector_rows:
            self._detector_rows[0].set_active_visual(True)
        _restripe(self._detector_rows, self._detector_rows_panel.rows_sizer)


class ControllersConfigView(wx.Panel):
    """Controllers configuration: manage motion controller list."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.SetBackgroundColour(POPUP_BG)
        self.SetForegroundColour(POPUP_FG)
        self._controller_rows: list[_ControllerRow] = []
        self._on_save_cb: Callable[[], None] | None = None
        self._build_layout()

    def _build_layout(self) -> None:
        self._controllers_section = _Section(self, "Controllers")
        ctrl_body = self._controllers_section.body
        self._ctrl_header = _TableHeader(ctrl_body, ["Name", "Type", "Connection params", ""], [5, 5, 18, 2])
        self._controller_rows_panel = _DarkScrolledPanel(ctrl_body)
        self._controller_rows_panel.SetMinSize((-1, _ROW_H * 3))
        self._add_controller_btn = FlatButton(ctrl_body, "+ Add controller")
        self._add_controller_btn.SetMinSize((-1, 26))
        self._add_controller_btn.set_action(self._on_add_controller_clicked)
        ctrl_sizer = wx.BoxSizer(wx.VERTICAL)
        ctrl_sizer.Add(self._ctrl_header, 0, wx.EXPAND)
        ctrl_sizer.Add(self._controller_rows_panel, 1, wx.EXPAND | wx.BOTTOM, 6)
        ctrl_sizer.Add(self._add_controller_btn, 0, wx.EXPAND)
        ctrl_body.SetSizer(ctrl_sizer)

        self._status_label = _status_label(self)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(self._controllers_section, 1, wx.EXPAND | wx.ALL, 10)
        outer.Add(self._status_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.SetSizer(outer)
        self.SetMinSize((560, -1))

    def bind_save(self, callback: Callable[[], None]) -> None:
        self._on_save_cb = callback

    def load_config(self, config: BeamlineConfig) -> None:
        self._clear_controller_rows()
        for controller in config.controllers:
            self._append_controller_row(controller)
        self.Layout()
        self.set_status("")

    def collect_controllers(self) -> tuple[ControllerConfig, ...]:
        return tuple(row.to_controller() for row in self._controller_rows if row.to_controller().name)

    def controller_names(self) -> list[str]:
        return [r.controller_name() for r in self._controller_rows if r.controller_name()]

    def set_status(self, text: str, error: bool = False) -> None:
        self._status_label.SetForegroundColour(DANGER if error else FG_SECONDARY)
        self._status_label.SetLabel(text)
        self.Layout()

    def trigger_save(self) -> None:
        if self._on_save_cb is not None:
            self._on_save_cb()

    def _clear_controller_rows(self) -> None:
        for row in self._controller_rows:
            self._controller_rows_panel.remove_row(row)
            row.Destroy()
        self._controller_rows.clear()

    def _append_controller_row(self, controller: ControllerConfig) -> None:
        index = len(self._controller_rows)
        row = _ControllerRow(
            self._controller_rows_panel._content,
            controller,
            index,
            on_remove=self._on_remove_controller,
        )
        self._controller_rows_panel.bind_mousewheel(row)
        self._controller_rows.append(row)
        self._controller_rows_panel.add_row(row)

    def _on_add_controller_clicked(self) -> None:
        self._append_controller_row(ControllerConfig(name="", type=_CONTROLLER_TYPES[0]))

    def _on_remove_controller(self, row: _ControllerRow) -> None:
        if row not in self._controller_rows:
            return
        self._controller_rows.remove(row)
        self._controller_rows_panel.remove_row(row)
        row.Destroy()
        _restripe(self._controller_rows, self._controller_rows_panel.rows_sizer)


class PositionersConfigView(wx.Panel):
    """Positioners configuration: rotation stage and motors."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.SetBackgroundColour(POPUP_BG)
        self.SetForegroundColour(POPUP_FG)
        self._motor_rows: list[_MotorRow] = []
        self._controller_names: list[str] = []
        self._controller_types: dict[str, str] = {}
        self._on_save_cb: Callable[[], None] | None = None
        self._build_layout()

    def _build_layout(self) -> None:
        self._rotation_section = _Section(self, "Rotation Stage")
        r_body = self._rotation_section.body
        self._rot_header = _TableHeader(r_body, ["Short", "Description", "PV", "Prec", "Controller"], [3, 6, 10, 2, 7])
        self._rotation_row = _RotationRow(r_body, None)
        r_sizer = wx.BoxSizer(wx.VERTICAL)
        r_sizer.Add(self._rot_header, 0, wx.EXPAND)
        r_sizer.Add(self._rotation_row, 0, wx.EXPAND)
        r_body.SetSizer(r_sizer)

        self._motors_section = _Section(self, "Motors")
        m_body = self._motors_section.body
        self._mot_header = _TableHeader(m_body, ["Short", "Description", "PV", "Prec", "Map", "Controller", ""], [3, 6, 10, 2, 2, 6, 2])
        self._motor_rows_panel = _DarkScrolledPanel(m_body)
        self._motor_rows_panel.SetMinSize((-1, _ROW_H * 3))
        self._add_motor_btn = FlatButton(m_body, "+ Add motor")
        self._add_motor_btn.SetMinSize((-1, 26))
        self._add_motor_btn.set_action(self._on_add_motor_clicked)
        m_sizer = wx.BoxSizer(wx.VERTICAL)
        m_sizer.Add(self._mot_header, 0, wx.EXPAND)
        m_sizer.Add(self._motor_rows_panel, 1, wx.EXPAND | wx.BOTTOM, 6)
        m_sizer.Add(self._add_motor_btn, 0, wx.EXPAND)
        m_body.SetSizer(m_sizer)

        self._status_label = _status_label(self)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(self._rotation_section, 0, wx.EXPAND | wx.ALL, 10)
        outer.Add(self._motors_section, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        outer.Add(self._status_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.SetSizer(outer)
        self.SetMinSize((560, -1))

    def bind_save(self, callback: Callable[[], None]) -> None:
        self._on_save_cb = callback

    def set_controller_names(self, names: list[str], controller_types: dict[str, str] | None = None) -> None:
        self._controller_names = names
        if controller_types is not None:
            self._controller_types = controller_types
        for row in self._motor_rows:
            row.update_controller_choices(names, self._controller_types)
        self._refresh_rotation_controller_choices()

    def load_config(self, config: BeamlineConfig) -> None:
        rm = config.rotation_motor
        self._rotation_row.short_ctrl.SetValue(rm.shorthand if rm else "")
        self._rotation_row.description_ctrl.SetValue(rm.description if rm else "")
        self._rotation_row.pv_ctrl.SetValue(rm.pv if rm else "")
        self._rotation_row.precision_ctrl.SetValue(str(rm.precision) if rm else "4")
        self._refresh_rotation_controller_choices(selected=rm.controller if rm else "epics")

        self._clear_motor_rows()
        for motor in config.motors:
            self._append_motor_row(motor)

        self.Layout()
        self.set_status("")

    def collect_rotation_motor(self) -> MotorConfig | None:
        rot_pv = self._rotation_row.pv_ctrl.GetValue().strip()
        try:
            rot_precision = max(0, int(self._rotation_row.precision_ctrl.GetValue().strip()))
        except ValueError:
            rot_precision = 4
        if not rot_pv:
            return None
        is_xps = self._rotation_row._is_xps()
        return MotorConfig(
            shorthand=self._rotation_row.short_ctrl.GetValue().strip(),
            description=self._rotation_row.description_ctrl.GetValue().strip(),
            pv=rot_pv,
            precision=rot_precision,
            controller=self._rotation_row.controller_combo.GetStringSelection() or "epics",
            xps_group=self._rotation_row.xps_group_ctrl.GetValue().strip() if is_xps else "",
            xps_positioner=self._rotation_row.xps_positioner_ctrl.GetValue().strip() if is_xps else "",
        )

    def collect_motors(self) -> tuple[MotorConfig, ...]:
        return tuple(row.to_motor() for row in self._motor_rows if row.to_motor().shorthand)

    def set_status(self, text: str, error: bool = False) -> None:
        self._status_label.SetForegroundColour(DANGER if error else FG_SECONDARY)
        self._status_label.SetLabel(text)
        self.Layout()

    def trigger_save(self) -> None:
        if self._on_save_cb is not None:
            self._on_save_cb()

    def _clear_motor_rows(self) -> None:
        for row in self._motor_rows:
            self._motor_rows_panel.remove_row(row)
            row.Destroy()
        self._motor_rows.clear()

    def _append_motor_row(self, motor: MotorConfig) -> None:
        index = len(self._motor_rows)
        row = _MotorRow(self._motor_rows_panel._content, motor, self._controller_names, self._controller_types, index, on_remove=self._on_remove_motor)
        self._motor_rows_panel.bind_mousewheel(row)
        self._motor_rows.append(row)
        self._motor_rows_panel.add_row(row)

    def _on_add_motor_clicked(self) -> None:
        self._append_motor_row(MotorConfig(shorthand="", description="", pv=""))

    def _on_remove_motor(self, row: _MotorRow) -> None:
        if row not in self._motor_rows:
            return
        self._motor_rows.remove(row)
        self._motor_rows_panel.remove_row(row)
        row.Destroy()
        _restripe(self._motor_rows, self._motor_rows_panel.rows_sizer)

    def _refresh_rotation_controller_choices(self, selected: str | None = None) -> None:
        choices = ["epics"] + self._controller_names
        current = selected or self._rotation_row.controller_combo.GetStringSelection() or "epics"
        self._rotation_row.update_controller_choices(choices, selected=current, controller_types=self._controller_types)


class _ConfigDialog(wx.Dialog):
    """Generic scrollable dialog wrapper; pressing Enter triggers save."""

    def __init__(self, parent: wx.Window, title: str, size: tuple[int, int] = (680, 500)) -> None:
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.SetBackgroundColour(BG_SURFACE)
        self._viewport = wx.Panel(self, style=wx.BORDER_NONE)
        self._viewport.SetBackgroundColour(BG_SURFACE)
        self._scroll_offset: int = 0
        self.config_panel = self._make_panel(self._viewport)
        self._scrollbar = DarkScrollBar(self, on_scroll=self._on_sb_scroll)
        self._viewport.Bind(wx.EVT_SIZE, self._on_viewport_size)
        self._viewport.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel)
        self.config_panel.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        outer = wx.BoxSizer(wx.HORIZONTAL)
        outer.Add(self._viewport, 1, wx.EXPAND)
        outer.Add(self._scrollbar, 0, wx.EXPAND)
        self.SetSizer(outer)
        self.SetSize(*size)
        self.SetMinSize((420, 320))
        self.CentreOnParent()

    def _make_panel(self, viewport: wx.Panel) -> wx.Panel:
        raise NotImplementedError

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() == wx.WXK_RETURN and not event.ShiftDown():
            self.config_panel.trigger_save()
        else:
            event.Skip()

    def _content_height(self) -> int:
        return self.config_panel.GetBestSize().height

    def _viewport_height(self) -> int:
        return self._viewport.GetClientSize().height

    def _max_offset(self) -> int:
        return max(0, self._content_height() - self._viewport_height())

    def _apply_offset(self) -> None:
        w = self._viewport.GetClientSize().width
        h = self._content_height()
        self._scroll_offset = max(0, min(self._scroll_offset, self._max_offset()))
        self.config_panel.SetSize(0, -self._scroll_offset, w, max(h, self._viewport_height()))
        self._sync_scrollbar()

    def _sync_scrollbar(self) -> None:
        total = self._content_height()
        visible = self._viewport_height()
        if total <= visible:
            self._scrollbar.update(0.0, 1.0)
        else:
            self._scrollbar.update(self._scroll_offset / (total - visible), visible / total)

    def _on_sb_scroll(self, fraction: float) -> None:
        self._scroll_offset = int(fraction * self._max_offset())
        self._apply_offset()

    def _on_viewport_size(self, event: wx.SizeEvent) -> None:
        event.Skip()
        self._apply_offset()

    def _on_wheel(self, event: wx.MouseEvent) -> None:
        delta = event.GetWheelRotation() // event.GetWheelDelta()
        self._scroll_offset = max(0, min(self._scroll_offset - delta * 20, self._max_offset()))
        self._apply_offset()
        event.Skip()


class GeneralConfigDialog(_ConfigDialog):
    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, "General configuration", size=(520, 200))

    def _make_panel(self, viewport: wx.Panel) -> GeneralConfigView:
        return GeneralConfigView(viewport)


class DetectorsConfigDialog(_ConfigDialog):
    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, "Detectors configuration", size=(620, 380))

    def _make_panel(self, viewport: wx.Panel) -> DetectorsConfigView:
        return DetectorsConfigView(viewport)


class ControllersConfigDialog(_ConfigDialog):
    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, "Controllers configuration", size=(700, 380))

    def _make_panel(self, viewport: wx.Panel) -> ControllersConfigView:
        return ControllersConfigView(viewport)


class PositionersConfigDialog(_ConfigDialog):
    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, "Positioners configuration", size=(680, 500))

    def _make_panel(self, viewport: wx.Panel) -> PositionersConfigView:
        return PositionersConfigView(viewport)
