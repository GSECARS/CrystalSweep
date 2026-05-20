#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/beamline_config_view.py
# ----------------------------------------------------------------------------------
# Purpose:
# Beamline configuration panel and modal dialog: edit beamline name, detectors,
# controllers, rotation stage, and motors with a consistent table-styled UI.
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

__all__ = ["BeamlineConfigDialog", "BeamlineConfigView"]


# ---------------------------------------------------------------------------
# Shared table styling constants (mirror collection_table_view)
# ---------------------------------------------------------------------------
_ROW_H      = 28
_HEADER_H   = 30
_ROW_ALT    = wx.Colour(32, 32, 36)
_HEADER_BG  = wx.Colour(22, 22, 26)
_BORDER     = wx.Colour(50, 50, 56)
_PAD        = 6
_REMOVE_W   = 32

# ---------------------------------------------------------------------------
# Placeholder strings
# ---------------------------------------------------------------------------
_PLACEHOLDER_BEAMLINE            = "e.g. 13-IDD"
_PLACEHOLDER_ROTATION_SHORT      = "e.g. omega"
_PLACEHOLDER_ROTATION_DESCRIPTION = "e.g. rotation"
_PLACEHOLDER_ROTATION_PV         = "e.g. 13IDD:m7.VAL"
_PLACEHOLDER_DETECTOR_NAME       = "e.g. Eiger 9M"
_PLACEHOLDER_DETECTOR_PREFIX     = "e.g. 13EIG2_9M:"
_PLACEHOLDER_CONTROLLER_NAME     = "e.g. xps1"
_PLACEHOLDER_MOTOR_SHORT         = "e.g. vert"
_PLACEHOLDER_MOTOR_DESCRIPTION   = "e.g. vertical"
_PLACEHOLDER_MOTOR_PV            = "e.g. 13IDD:m1.VAL"
_PLACEHOLDER_MOTOR_PRECISION     = "4"

# ---------------------------------------------------------------------------
# Controller type definitions
# ---------------------------------------------------------------------------
_CONTROLLER_TYPE_LABELS: list[tuple[str, str]] = [
    ("newport_xps", "NewportXPS C/D"),
    ("aerotech_a1", "Automation1"),
]
_CONTROLLER_TYPES        = [t for t, _ in _CONTROLLER_TYPE_LABELS]
_CONTROLLER_DISPLAY_NAMES = [label for _, label in _CONTROLLER_TYPE_LABELS]
_LABEL_TO_TYPE = {label: t for t, label in _CONTROLLER_TYPE_LABELS}
_TYPE_TO_LABEL = {t: label for t, label in _CONTROLLER_TYPE_LABELS}

_CONTROLLER_TYPE_PARAMS: dict[str, list[tuple[str, str]]] = {
    "newport_xps": [("host", "e.g. 192.168.0.1"), ("username", "Administrator"), ("password", "")],
    "aerotech_a1": [("ip", "e.g. 192.168.0.2"), ("axis_name", "e.g. Theta"), ("counts_per_unit", "e.g. 1491308.09")],
}

# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
class _ActiveConfigChangedCallback(Protocol):
    def __call__(self, name: str) -> None: ...

class _ConfigSaveCallback(Protocol):
    def __call__(self, config: BeamlineConfig) -> None: ...

class _CreateConfigCallback(Protocol):
    def __call__(self, name: str) -> None: ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Generic painted table header
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Generic painted table row base
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Detector table
# ---------------------------------------------------------------------------
class _DetectorRow(_TableRow):
    # proportions: [active(radio), name, prefix, remove]
    _PROPS = [2, 10, 14, 2]

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
        # active radio — centre in first col
        rw, rh = self.active_dot.GetBestSize()
        self.active_dot.SetSize(x + (widths[0] - rw) // 2, (_ROW_H - rh) // 2, rw, rh)
        x += widths[0]
        self._place(self.name_ctrl, x, widths[1]);   x += widths[1]
        self._place(self.prefix_ctrl, x, widths[2]); x += widths[2]
        self._place(self._remove_btn, x, widths[3])

    def to_detector(self) -> DetectorConfig:
        return DetectorConfig(
            name=self.name_ctrl.GetValue().strip(),
            pv_prefix=self.prefix_ctrl.GetValue().strip(),
        )

    def set_active_visual(self, active: bool) -> None:
        self.active_dot.set_value(active)


# ---------------------------------------------------------------------------
# Controller table
# ---------------------------------------------------------------------------
class _ControllerRow(_TableRow):
    # proportions: [name, type, params..., remove]
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
        self._place(self.name_ctrl, x, widths[0]);   x += widths[0]
        self._place(self.type_combo, x, widths[1]);   x += widths[1]
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
        self.GetParent().FitInside()
        self.GetParent().Layout()

    def to_controller(self) -> ControllerConfig:
        params = {k: ctrl.GetValue().strip() for k, ctrl in self._param_ctrls.items() if ctrl.GetValue().strip()}
        return ControllerConfig(name=self.name_ctrl.GetValue().strip(), type=self._current_type(), params=params)

    def controller_name(self) -> str:
        return self.name_ctrl.GetValue().strip()


# ---------------------------------------------------------------------------
# Rotation stage row (single painted row — no scrolling needed)
# ---------------------------------------------------------------------------
class _RotationRow(_TableRow):
    # proportions: [short, description, pv, prec, controller]
    _PROPS = [3, 6, 10, 2, 7]

    def __init__(self, parent: wx.Window, motor: MotorConfig | None) -> None:
        super().__init__(parent, BG_CARD, self._PROPS)
        rm = motor

        self.short_ctrl = DarkTextCtrl(self, value=rm.shorthand if rm else "", placeholder=_PLACEHOLDER_ROTATION_SHORT)
        self.description_ctrl = DarkTextCtrl(self, value=rm.description if rm else "", placeholder=_PLACEHOLDER_ROTATION_DESCRIPTION)
        self.pv_ctrl = DarkTextCtrl(self, value=rm.pv if rm else "", placeholder=_PLACEHOLDER_ROTATION_PV)
        self.precision_ctrl = DarkTextCtrl(self, value=str(rm.precision) if rm else "4", placeholder=_PLACEHOLDER_MOTOR_PRECISION)
        self.controller_combo = DarkCombo(self, choices=["epics"], selection=0)
        self._reposition()

    def _reposition(self) -> None:
        w, _ = self.GetClientSize()
        if w <= 0:
            return
        widths = self._col_widths(w)
        x = 0
        for ctrl, cw in zip(
            (self.short_ctrl, self.description_ctrl, self.pv_ctrl, self.precision_ctrl, self.controller_combo),
            widths,
        ):
            self._place(ctrl, x, cw)
            x += cw

    def update_controller_choices(self, choices: list[str], selected: str = "epics") -> None:
        self.controller_combo.SetChoices(choices)
        if selected in choices:
            self.controller_combo.SetSelection(choices.index(selected))


# ---------------------------------------------------------------------------
# Motor table
# ---------------------------------------------------------------------------
class _MotorRow(_TableRow):
    # proportions: [short, description, pv, prec, map, controller, remove]
    _PROPS = [3, 6, 10, 2, 2, 6, 2]

    def __init__(
        self,
        parent: wx.Window,
        motor: MotorConfig,
        controller_names: list[str],
        index: int,
        on_remove: Callable[["_MotorRow"], None],
    ) -> None:
        bg = BG_CARD if index % 2 == 0 else _ROW_ALT
        super().__init__(parent, bg, self._PROPS)

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

        self._remove_btn = FlatButton(self, "×", color_scheme=DANGER_SCHEME)
        self._remove_btn.set_action(lambda: on_remove(self))
        self._reposition()

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
        # mapping toggle — centre vertically
        tw, th = self.mapping_toggle.GetBestSize()
        self.mapping_toggle.SetSize(x + (widths[4] - tw) // 2, (_ROW_H - th) // 2, tw, th)
        x += widths[4]
        self._place(self.controller_combo, x, widths[5]); x += widths[5]
        self._place(self._remove_btn, x, widths[6])

    def update_controller_choices(self, controller_names: list[str]) -> None:
        current = self.controller_combo.GetStringSelection()
        choices = ["epics"] + controller_names
        self.controller_combo.SetChoices(choices)
        if current in choices:
            self.controller_combo.SetSelection(choices.index(current))

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
        )


# ---------------------------------------------------------------------------
# Main config panel
# ---------------------------------------------------------------------------
class BeamlineConfigView(wx.Panel):
    """Beamline configuration editor panel."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.SetBackgroundColour(POPUP_BG)
        self.SetForegroundColour(POPUP_FG)

        self._detector_rows: list[_DetectorRow] = []
        self._controller_rows: list[_ControllerRow] = []
        self._motor_rows: list[_MotorRow] = []
        self._on_active_changed_cb: _ActiveConfigChangedCallback | None = None
        self._on_save_cb: _ConfigSaveCallback | None = None
        self._on_create_cb: _CreateConfigCallback | None = None
        self._available_names: list[str] = []
        self._current_name: str = ""

        self._build_layout()

    def _build_layout(self) -> None:
        # --- config selector ---
        selector_panel = wx.Panel(self)
        selector_panel.SetBackgroundColour(POPUP_BG)
        self._config_combo = DarkCombo(selector_panel, choices=[])
        self._config_combo.Bind(wx.EVT_CHOICE, self._on_combo_choice)
        self._create_btn = FlatButton(selector_panel, "New")
        self._create_btn.SetMinSize((70, 28))
        self._create_btn.set_action(self._on_create_clicked)
        sel_row = wx.BoxSizer(wx.HORIZONTAL)
        sel_row.Add(_label(selector_panel, "Configuration", bold=True), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        sel_row.Add(self._config_combo, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        sel_row.Add(self._create_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        selector_panel.SetSizer(sel_row)

        # --- beamline name ---
        self._beamline_section = _Section(self, "Beamline")
        b_body = self._beamline_section.body
        self._beamline_ctrl = DarkTextCtrl(b_body, placeholder=_PLACEHOLDER_BEAMLINE)
        self._beamline_ctrl.SetMinSize((-1, 28))
        b_sizer = wx.BoxSizer(wx.VERTICAL)
        b_sizer.Add(_label(b_body, "Name", secondary=True), 0, wx.BOTTOM, 4)
        b_sizer.Add(self._beamline_ctrl, 0, wx.EXPAND)
        b_body.SetSizer(b_sizer)

        # --- detectors ---
        self._detectors_section = _Section(self, "Detectors")
        d_body = self._detectors_section.body
        self._det_header = _TableHeader(d_body, ["", "Name", "PV prefix", ""], [2, 10, 14, 2])
        self._detector_rows_panel = wx.ScrolledWindow(d_body, style=wx.VSCROLL)
        self._detector_rows_panel.SetBackgroundColour(BG_CARD)
        self._detector_rows_panel.SetScrollRate(0, _ROW_H)
        self._detector_rows_sizer = wx.BoxSizer(wx.VERTICAL)
        self._detector_rows_panel.SetSizer(self._detector_rows_sizer)
        self._detector_rows_panel.SetMinSize((-1, _ROW_H * 3))
        self._add_detector_btn = FlatButton(d_body, "+ Add detector")
        self._add_detector_btn.SetMinSize((-1, 26))
        self._add_detector_btn.set_action(self._on_add_detector_clicked)
        d_sizer = wx.BoxSizer(wx.VERTICAL)
        d_sizer.Add(self._det_header, 0, wx.EXPAND)
        d_sizer.Add(self._detector_rows_panel, 1, wx.EXPAND | wx.BOTTOM, 6)
        d_sizer.Add(self._add_detector_btn, 0, wx.EXPAND)
        d_body.SetSizer(d_sizer)

        # --- controllers ---
        self._controllers_section = _Section(self, "Controllers")
        ctrl_body = self._controllers_section.body
        self._ctrl_header = _TableHeader(ctrl_body, ["Name", "Type", "Connection params", ""], [5, 5, 18, 2])
        self._controller_rows_panel = wx.ScrolledWindow(ctrl_body, style=wx.VSCROLL)
        self._controller_rows_panel.SetBackgroundColour(BG_CARD)
        self._controller_rows_panel.SetScrollRate(0, _ROW_H)
        self._controller_rows_sizer = wx.BoxSizer(wx.VERTICAL)
        self._controller_rows_panel.SetSizer(self._controller_rows_sizer)
        self._controller_rows_panel.SetMinSize((-1, _ROW_H * 3))
        self._add_controller_btn = FlatButton(ctrl_body, "+ Add controller")
        self._add_controller_btn.SetMinSize((-1, 26))
        self._add_controller_btn.set_action(self._on_add_controller_clicked)
        ctrl_sizer = wx.BoxSizer(wx.VERTICAL)
        ctrl_sizer.Add(self._ctrl_header, 0, wx.EXPAND)
        ctrl_sizer.Add(self._controller_rows_panel, 1, wx.EXPAND | wx.BOTTOM, 6)
        ctrl_sizer.Add(self._add_controller_btn, 0, wx.EXPAND)
        ctrl_body.SetSizer(ctrl_sizer)

        # --- rotation stage ---
        self._rotation_section = _Section(self, "Rotation Stage")
        r_body = self._rotation_section.body
        self._rot_header = _TableHeader(r_body, ["Short", "Description", "PV \u2731", "Prec", "Controller"], [3, 6, 10, 2, 7])
        self._rotation_row = _RotationRow(r_body, None)
        r_sizer = wx.BoxSizer(wx.VERTICAL)
        r_sizer.Add(self._rot_header, 0, wx.EXPAND)
        r_sizer.Add(self._rotation_row, 0, wx.EXPAND)
        r_body.SetSizer(r_sizer)

        # --- motors ---
        self._motors_section = _Section(self, "Motors")
        m_body = self._motors_section.body
        self._mot_header = _TableHeader(m_body, ["Short", "Description", "PV", "Prec", "Map", "Controller", ""], [3, 6, 10, 2, 2, 6, 2])
        self._motor_rows_panel = wx.ScrolledWindow(m_body, style=wx.VSCROLL)
        self._motor_rows_panel.SetBackgroundColour(BG_CARD)
        self._motor_rows_panel.SetScrollRate(0, _ROW_H)
        self._motor_rows_sizer = wx.BoxSizer(wx.VERTICAL)
        self._motor_rows_panel.SetSizer(self._motor_rows_sizer)
        self._motor_rows_panel.SetMinSize((-1, _ROW_H * 3))
        self._add_motor_btn = FlatButton(m_body, "+ Add motor")
        self._add_motor_btn.SetMinSize((-1, 26))
        self._add_motor_btn.set_action(self._on_add_motor_clicked)
        m_sizer = wx.BoxSizer(wx.VERTICAL)
        m_sizer.Add(self._mot_header, 0, wx.EXPAND)
        m_sizer.Add(self._motor_rows_panel, 1, wx.EXPAND | wx.BOTTOM, 6)
        m_sizer.Add(self._add_motor_btn, 0, wx.EXPAND)
        m_body.SetSizer(m_sizer)

        # --- save / status ---
        self._save_btn = FlatButton(self, "Save configuration")
        self._save_btn.SetMinSize((-1, 32))
        self._save_btn.set_action(self._on_save_clicked)
        self._status_label = wx.StaticText(self, label="")
        self._status_label.SetBackgroundColour(POPUP_BG)
        self._status_label.SetForegroundColour(FG_SECONDARY)
        self._status_label.SetFont(scaled_font(11))

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(selector_panel, 0, wx.EXPAND | wx.ALL, 10)
        outer.Add(self._beamline_section, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        outer.Add(self._detectors_section, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        outer.Add(self._controllers_section, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        outer.Add(self._rotation_section, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        outer.Add(self._motors_section, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        outer.Add(self._save_btn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.Add(self._status_label, 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(outer)
        self.SetMinSize((500, -1))

    # --- public API ---
    def bind_active_config_changed(self, callback: _ActiveConfigChangedCallback) -> None:
        self._on_active_changed_cb = callback

    def bind_save(self, callback: _ConfigSaveCallback) -> None:
        self._on_save_cb = callback

    def bind_create(self, callback: _CreateConfigCallback) -> None:
        self._on_create_cb = callback

    def set_available_configs(self, names: list[str], active: str | None = None) -> None:
        self._available_names = list(names)
        sel = 0
        if active and active in self._available_names:
            sel = self._available_names.index(active)
            self._current_name = active
        elif self._available_names:
            self._current_name = self._available_names[0]
        else:
            self._current_name = ""
        self._config_combo.SetChoices(self._available_names, selection=sel)

    def load_config(self, config: BeamlineConfig) -> None:
        self._current_name = config.name
        self._beamline_ctrl.SetValue(config.beamline)

        self._clear_detector_rows()
        for idx, detector in enumerate(config.detectors):
            self._append_detector_row(detector, active=idx == config.active_detector)

        self._clear_controller_rows()
        for controller in config.controllers:
            self._append_controller_row(controller)

        rm = config.rotation_motor
        self._rotation_row.short_ctrl.SetValue(rm.shorthand if rm else "")
        self._rotation_row.description_ctrl.SetValue(rm.description if rm else "")
        self._rotation_row.pv_ctrl.SetValue(rm.pv if rm else "")
        self._rotation_row.precision_ctrl.SetValue(str(rm.precision) if rm else "4")
        self._refresh_rotation_controller_choices(selected=rm.controller if rm else "epics")

        self._clear_motor_rows()
        for motor in config.motors:
            self._append_motor_row(motor)

        if config.name and config.name in self._available_names:
            self._config_combo.SetSelection(self._available_names.index(config.name))

        self._detector_rows_panel.FitInside()
        self._controller_rows_panel.FitInside()
        self._motor_rows_panel.FitInside()
        self.Layout()
        self.set_status("")

    def collect_config(self) -> BeamlineConfig:
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

        rot_pv = self._rotation_row.pv_ctrl.GetValue().strip()
        try:
            rot_precision = max(0, int(self._rotation_row.precision_ctrl.GetValue().strip()))
        except ValueError:
            rot_precision = 4
        rotation_motor = (
            MotorConfig(
                shorthand=self._rotation_row.short_ctrl.GetValue().strip(),
                description=self._rotation_row.description_ctrl.GetValue().strip(),
                pv=rot_pv,
                precision=rot_precision,
                controller=self._rotation_row.controller_combo.GetStringSelection() or "epics",
            )
            if rot_pv
            else None
        )

        controllers = tuple(row.to_controller() for row in self._controller_rows if row.to_controller().name)
        motors = tuple(row.to_motor() for row in self._motor_rows if row.to_motor().shorthand)
        return BeamlineConfig(
            name=self._current_name,
            beamline=self._beamline_ctrl.GetValue().strip(),
            rotation_motor=rotation_motor,
            detectors=tuple(detectors),
            active_detector=active_index,
            controllers=controllers,
            motors=motors,
        )

    def set_status(self, text: str, error: bool = False) -> None:
        self._status_label.SetForegroundColour(DANGER if error else FG_SECONDARY)
        self._status_label.SetLabel(text)
        self.Layout()

    # --- detector management ---
    def _clear_detector_rows(self) -> None:
        for row in self._detector_rows:
            self._detector_rows_sizer.Detach(row)
            row.Destroy()
        self._detector_rows.clear()
        self._detector_rows_panel.Layout()

    def _append_detector_row(self, detector: DetectorConfig, active: bool) -> None:
        index = len(self._detector_rows)
        row = _DetectorRow(
            self._detector_rows_panel, detector, active, index,
            on_make_active=self._on_make_detector_active,
            on_remove=self._on_remove_detector,
        )
        self._detector_rows_sizer.Add(row, 0, wx.EXPAND)
        self._detector_rows.append(row)
        self._detector_rows_panel.FitInside()
        self._detector_rows_panel.Layout()

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
        self._detector_rows_sizer.Detach(row)
        row.Destroy()
        if was_active and self._detector_rows:
            self._detector_rows[0].set_active_visual(True)
        self._restripe(self._detector_rows, self._detector_rows_sizer)
        self._detector_rows_panel.FitInside()
        self._detector_rows_panel.Layout()

    # --- controller management ---
    def _clear_controller_rows(self) -> None:
        for row in self._controller_rows:
            self._controller_rows_sizer.Detach(row)
            row.Destroy()
        self._controller_rows.clear()
        self._controller_rows_panel.Layout()

    def _append_controller_row(self, controller: ControllerConfig) -> None:
        index = len(self._controller_rows)
        row = _ControllerRow(
            self._controller_rows_panel, controller, index,
            on_remove=self._on_remove_controller,
            on_name_changed=self._refresh_motor_controller_choices,
        )
        self._controller_rows_sizer.Add(row, 0, wx.EXPAND)
        self._controller_rows.append(row)
        self._controller_rows_panel.FitInside()
        self._controller_rows_panel.Layout()
        self._refresh_motor_controller_choices()

    def _on_add_controller_clicked(self) -> None:
        self._append_controller_row(ControllerConfig(name="", type=_CONTROLLER_TYPES[0]))

    def _on_remove_controller(self, row: _ControllerRow) -> None:
        if row not in self._controller_rows:
            return
        self._controller_rows.remove(row)
        self._controller_rows_sizer.Detach(row)
        row.Destroy()
        self._restripe(self._controller_rows, self._controller_rows_sizer)
        self._controller_rows_panel.FitInside()
        self._controller_rows_panel.Layout()
        self._refresh_motor_controller_choices()

    def _refresh_motor_controller_choices(self) -> None:
        names = [r.controller_name() for r in self._controller_rows if r.controller_name()]
        for row in self._motor_rows:
            row.update_controller_choices(names)
        self._refresh_rotation_controller_choices()

    def _refresh_rotation_controller_choices(self, selected: str | None = None) -> None:
        names = [r.controller_name() for r in self._controller_rows if r.controller_name()]
        choices = ["epics"] + names
        current = selected or self._rotation_row.controller_combo.GetStringSelection() or "epics"
        self._rotation_row.update_controller_choices(choices, selected=current)

    # --- motor management ---
    def _clear_motor_rows(self) -> None:
        for row in self._motor_rows:
            self._motor_rows_sizer.Detach(row)
            row.Destroy()
        self._motor_rows.clear()
        self._motor_rows_panel.Layout()

    def _append_motor_row(self, motor: MotorConfig) -> None:
        index = len(self._motor_rows)
        names = [r.controller_name() for r in self._controller_rows if r.controller_name()]
        row = _MotorRow(self._motor_rows_panel, motor, names, index, on_remove=self._on_remove_motor)
        self._motor_rows_sizer.Add(row, 0, wx.EXPAND)
        self._motor_rows.append(row)
        self._motor_rows_panel.FitInside()
        self._motor_rows_panel.Layout()

    def _on_add_motor_clicked(self) -> None:
        self._append_motor_row(MotorConfig(shorthand="", description="", pv=""))

    def _on_remove_motor(self, row: _MotorRow) -> None:
        if row not in self._motor_rows:
            return
        self._motor_rows.remove(row)
        self._motor_rows_sizer.Detach(row)
        row.Destroy()
        self._restripe(self._motor_rows, self._motor_rows_sizer)
        self._motor_rows_panel.FitInside()
        self._motor_rows_panel.Layout()

    # --- helpers ---
    @staticmethod
    def _restripe(rows: list, sizer: wx.BoxSizer) -> None:
        """Reapply alternating row colours after a removal."""
        for i, row in enumerate(rows):
            row.SetBackgroundColour(BG_CARD if i % 2 == 0 else _ROW_ALT)
            row.Refresh()

    # --- events ---
    def _on_combo_choice(self, name: str) -> None:
        if not name or name == self._current_name:
            return
        self._current_name = name
        if self._on_active_changed_cb is not None:
            self._on_active_changed_cb(name)

    def _on_create_clicked(self) -> None:
        with wx.TextEntryDialog(self, "Configuration name (e.g. 2026-2)", "New configuration") as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            name = dlg.GetValue().strip()
        if not name:
            return
        if self._on_create_cb is not None:
            self._on_create_cb(name)

    def _on_save_clicked(self) -> None:
        if self._on_save_cb is not None:
            self._on_save_cb(self.collect_config())


# ---------------------------------------------------------------------------
# Dialog wrapper
# ---------------------------------------------------------------------------
class BeamlineConfigDialog(wx.Dialog):
    """Top-level dialog that wraps BeamlineConfigView with a dark scrollbar."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(
            parent,
            title="Beamline configuration",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.SetBackgroundColour(BG_SURFACE)
        self._viewport = wx.Panel(self, style=wx.BORDER_NONE)
        self._viewport.SetBackgroundColour(BG_SURFACE)
        self._scroll_offset: int = 0
        self.config_panel = BeamlineConfigView(self._viewport)
        self._scrollbar = DarkScrollBar(self, on_scroll=self._on_sb_scroll)
        self._viewport.Bind(wx.EVT_SIZE, self._on_viewport_size)
        self._viewport.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel)
        self.config_panel.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel)
        outer = wx.BoxSizer(wx.HORIZONTAL)
        outer.Add(self._viewport, 1, wx.EXPAND)
        outer.Add(self._scrollbar, 0, wx.EXPAND)
        self.SetSizer(outer)
        self.SetSize(680, 720)
        self.SetMinSize((520, 560))
        self.CentreOnParent()

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
