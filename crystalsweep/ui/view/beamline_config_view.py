#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/beamline_config_view.py
# ----------------------------------------------------------------------------------
# Purpose:
# Beamline configuration panel and modal dialog: edit beamline name, detectors,
# and motors, and switch between / create / save named TOML configurations.
# Opened from the File menu.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from typing import Callable, Protocol

import wx

from crystalsweep.model.beamline_config_model import BeamlineConfig, DetectorConfig, MotorConfig
from crystalsweep.ui.view.custom.theme import BG_CARD, BG_SURFACE, DANGER, FG_PRIMARY, FG_SECONDARY, POPUP_BG, POPUP_FG, SEP_COLOUR, scaled_font
from crystalsweep.ui.view.custom.widgets import DANGER_SCHEME, DarkCombo, DarkScrollBar, DarkTextCtrl, DarkToggle, FlatButton, RadioDot

__all__ = ["BeamlineConfigDialog", "BeamlineConfigView"]


_ROW_INPUT_HEIGHT = 28

_PLACEHOLDER_BEAMLINE = "e.g. 13-IDD"
_PLACEHOLDER_ROTATION_SHORT = "e.g. omega"
_PLACEHOLDER_ROTATION_DESCRIPTION = "e.g. rotation"
_PLACEHOLDER_ROTATION_PV = "e.g. 13IDD:m7.VAL"
_PLACEHOLDER_DETECTOR_NAME = "e.g. Eiger 9M"
_PLACEHOLDER_DETECTOR_PREFIX = "e.g. 13EIG2_9M:"
_PLACEHOLDER_MOTOR_SHORT = "e.g. vert"
_PLACEHOLDER_MOTOR_DESCRIPTION = "e.g. vertical"
_PLACEHOLDER_MOTOR_PV = "e.g. 13IDD:m1.VAL"
_PLACEHOLDER_MOTOR_PRECISION = "4"


class _ActiveConfigChangedCallback(Protocol):
    def __call__(self, name: str) -> None: ...


class _ConfigSaveCallback(Protocol):
    def __call__(self, config: BeamlineConfig) -> None: ...


class _CreateConfigCallback(Protocol):
    def __call__(self, name: str) -> None: ...


def _label(parent: wx.Window, text: str, bold: bool = False, secondary: bool = False) -> wx.StaticText:
    lbl = wx.StaticText(parent, label=text)
    lbl.SetBackgroundColour(parent.GetBackgroundColour())
    lbl.SetForegroundColour(FG_SECONDARY if secondary else FG_PRIMARY)
    lbl.SetFont(scaled_font(12, weight=wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL))
    return lbl


class _Section(wx.Panel):
    """Card-like grouping with a title bar, separator, and a body panel."""

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


class _DetectorRow(wx.Panel):
    """Editable row for a single detector: active radio, name, PV prefix, remove."""

    def __init__(
        self,
        parent: wx.Window,
        detector: DetectorConfig,
        active: bool,
        on_make_active: Callable[["_DetectorRow"], None],
        on_remove: Callable[["_DetectorRow"], None],
    ) -> None:
        super().__init__(parent)
        self.SetBackgroundColour(BG_CARD)
        self._on_make_active = on_make_active
        self._on_remove = on_remove

        self.active_dot = RadioDot(self, value=active, tooltip="Set as active detector")
        self.active_dot.set_action(self._request_active)

        self.name_ctrl = DarkTextCtrl(self, value=detector.name, placeholder=_PLACEHOLDER_DETECTOR_NAME)
        self.name_ctrl.SetMinSize((120, _ROW_INPUT_HEIGHT))

        self.prefix_ctrl = DarkTextCtrl(self, value=detector.pv_prefix, placeholder=_PLACEHOLDER_DETECTOR_PREFIX)
        self.prefix_ctrl.SetMinSize((140, _ROW_INPUT_HEIGHT))

        self._remove_btn = FlatButton(self, "X", color_scheme=DANGER_SCHEME)
        self._remove_btn.SetMinSize((28, _ROW_INPUT_HEIGHT))
        self._remove_btn.SetToolTip("Remove detector")
        self._remove_btn.set_action(self._request_remove)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.active_dot, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        sizer.Add(self.name_ctrl, 2, wx.EXPAND | wx.RIGHT, 4)
        sizer.Add(self.prefix_ctrl, 3, wx.EXPAND | wx.RIGHT, 6)
        sizer.Add(self._remove_btn, 0, wx.EXPAND)
        self.SetSizer(sizer)

    def to_detector(self) -> DetectorConfig:
        return DetectorConfig(
            name=self.name_ctrl.GetValue().strip(),
            pv_prefix=self.prefix_ctrl.GetValue().strip(),
        )

    def set_active_visual(self, active: bool) -> None:
        self.active_dot.set_value(active)

    def _request_active(self) -> None:
        self._on_make_active(self)

    def _request_remove(self) -> None:
        self._on_remove(self)


class _MotorRow(wx.Panel):
    """Editable row for a single motor: shorthand, variable name, PV, mapping toggle, remove."""

    def __init__(
        self,
        parent: wx.Window,
        motor: MotorConfig,
        on_remove: Callable[["_MotorRow"], None],
    ) -> None:
        super().__init__(parent)
        self.SetBackgroundColour(BG_CARD)
        self._on_remove = on_remove

        self.shorthand_ctrl = DarkTextCtrl(self, value=motor.shorthand, placeholder=_PLACEHOLDER_MOTOR_SHORT)
        self.shorthand_ctrl.SetMinSize((70, _ROW_INPUT_HEIGHT))
        self.description_ctrl = DarkTextCtrl(self, value=motor.description, placeholder=_PLACEHOLDER_MOTOR_DESCRIPTION)
        self.description_ctrl.SetMinSize((90, _ROW_INPUT_HEIGHT))
        self.pv_ctrl = DarkTextCtrl(self, value=motor.pv, placeholder=_PLACEHOLDER_MOTOR_PV)
        self.pv_ctrl.SetMinSize((140, _ROW_INPUT_HEIGHT))
        self.precision_ctrl = DarkTextCtrl(self, value=str(motor.precision), placeholder=_PLACEHOLDER_MOTOR_PRECISION)
        self.precision_ctrl.SetMinSize((40, _ROW_INPUT_HEIGHT))
        self.mapping_toggle = DarkToggle(self, "Map")
        self.mapping_toggle.SetBackgroundColour(BG_CARD)
        self.mapping_toggle.SetValue(motor.mapping_enabled)

        self._remove_btn = FlatButton(self, "X", color_scheme=DANGER_SCHEME)
        self._remove_btn.SetMinSize((28, _ROW_INPUT_HEIGHT))
        self._remove_btn.SetToolTip("Remove motor")
        self._remove_btn.set_action(self._request_remove)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.shorthand_ctrl, 1, wx.EXPAND | wx.RIGHT, 4)
        sizer.Add(self.description_ctrl, 2, wx.EXPAND | wx.RIGHT, 4)
        sizer.Add(self.pv_ctrl, 3, wx.EXPAND | wx.RIGHT, 4)
        sizer.Add(self.precision_ctrl, 0, wx.EXPAND | wx.RIGHT, 6)
        sizer.Add(self.mapping_toggle, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        sizer.Add(self._remove_btn, 0, wx.EXPAND)
        self.SetSizer(sizer)

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
        )

    def _request_remove(self) -> None:
        self._on_remove(self)


class BeamlineConfigView(wx.Panel):
    """Beamline configuration editor panel."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.SetBackgroundColour(POPUP_BG)
        self.SetForegroundColour(POPUP_FG)

        self._detector_rows: list[_DetectorRow] = []
        self._motor_rows: list[_MotorRow] = []
        self._on_active_changed_cb: _ActiveConfigChangedCallback | None = None
        self._on_save_cb: _ConfigSaveCallback | None = None
        self._on_create_cb: _CreateConfigCallback | None = None
        self._available_names: list[str] = []
        self._current_name: str = ""

        self._build_layout()

    def _build_layout(self) -> None:
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

        self._beamline_section = _Section(self, "Beamline")
        b_body = self._beamline_section.body
        self._beamline_ctrl = DarkTextCtrl(b_body, placeholder=_PLACEHOLDER_BEAMLINE)
        self._beamline_ctrl.SetMinSize((-1, _ROW_INPUT_HEIGHT))

        b_sizer = wx.BoxSizer(wx.VERTICAL)
        b_sizer.Add(_label(b_body, "Name", secondary=True), 0, wx.BOTTOM, 4)
        b_sizer.Add(self._beamline_ctrl, 0, wx.EXPAND)
        b_body.SetSizer(b_sizer)

        self._rotation_section = _Section(self, "Rotation Stage")
        r_body = self._rotation_section.body

        rot_header = wx.Panel(r_body)
        rot_header.SetBackgroundColour(BG_CARD)
        rot_header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        rot_header_sizer.Add(_label(rot_header, "Short", secondary=True), 1, wx.RIGHT, 4)
        rot_header_sizer.Add(_label(rot_header, "Description", secondary=True), 2, wx.RIGHT, 4)
        rot_header_sizer.Add(_label(rot_header, "PV  \u2731", secondary=True), 3, wx.RIGHT, 4)
        rot_header_sizer.Add(_label(rot_header, "Prec", secondary=True), 0)
        rot_header.SetSizer(rot_header_sizer)

        self._rotation_short_ctrl = DarkTextCtrl(r_body, placeholder=_PLACEHOLDER_ROTATION_SHORT)
        self._rotation_short_ctrl.SetMinSize((70, _ROW_INPUT_HEIGHT))
        self._rotation_description_ctrl = DarkTextCtrl(r_body, placeholder=_PLACEHOLDER_ROTATION_DESCRIPTION)
        self._rotation_description_ctrl.SetMinSize((90, _ROW_INPUT_HEIGHT))
        self._rotation_pv_ctrl = DarkTextCtrl(r_body, placeholder=_PLACEHOLDER_ROTATION_PV)
        self._rotation_pv_ctrl.SetMinSize((140, _ROW_INPUT_HEIGHT))
        self._rotation_precision_ctrl = DarkTextCtrl(r_body, value="4", placeholder=_PLACEHOLDER_MOTOR_PRECISION)
        self._rotation_precision_ctrl.SetMinSize((40, _ROW_INPUT_HEIGHT))

        rot_row = wx.BoxSizer(wx.HORIZONTAL)
        rot_row.Add(self._rotation_short_ctrl, 1, wx.EXPAND | wx.RIGHT, 4)
        rot_row.Add(self._rotation_description_ctrl, 2, wx.EXPAND | wx.RIGHT, 4)
        rot_row.Add(self._rotation_pv_ctrl, 3, wx.EXPAND | wx.RIGHT, 4)
        rot_row.Add(self._rotation_precision_ctrl, 0, wx.EXPAND)

        r_sizer = wx.BoxSizer(wx.VERTICAL)
        r_sizer.Add(rot_header, 0, wx.EXPAND | wx.BOTTOM, 4)
        r_sizer.Add(rot_row, 0, wx.EXPAND)
        r_body.SetSizer(r_sizer)

        self._detectors_section = _Section(self, "Detectors")
        d_body = self._detectors_section.body

        det_header = wx.Panel(d_body)
        det_header.SetBackgroundColour(BG_CARD)
        det_header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        det_header_sizer.AddSpacer(28)
        det_header_sizer.Add(_label(det_header, "Name", secondary=True), 2, wx.RIGHT, 4)
        det_header_sizer.Add(_label(det_header, "PV prefix", secondary=True), 3, wx.RIGHT, 6)
        det_header_sizer.AddSpacer(28)
        det_header.SetSizer(det_header_sizer)

        self._detector_rows_panel = wx.ScrolledWindow(d_body, style=wx.VSCROLL)
        self._detector_rows_panel.SetBackgroundColour(BG_CARD)
        self._detector_rows_panel.SetScrollRate(0, 12)
        self._detector_rows_sizer = wx.BoxSizer(wx.VERTICAL)
        self._detector_rows_panel.SetSizer(self._detector_rows_sizer)
        self._detector_rows_panel.SetMinSize((-1, 90))

        self._add_detector_btn = FlatButton(d_body, "+ Add detector")
        self._add_detector_btn.SetMinSize((-1, 28))
        self._add_detector_btn.set_action(self._on_add_detector_clicked)

        d_sizer = wx.BoxSizer(wx.VERTICAL)
        d_sizer.Add(det_header, 0, wx.EXPAND | wx.BOTTOM, 4)
        d_sizer.Add(self._detector_rows_panel, 1, wx.EXPAND | wx.BOTTOM, 8)
        d_sizer.Add(self._add_detector_btn, 0, wx.EXPAND)
        d_body.SetSizer(d_sizer)

        self._motors_section = _Section(self, "Motors")
        m_body = self._motors_section.body

        mot_header = wx.Panel(m_body)
        mot_header.SetBackgroundColour(BG_CARD)
        mot_header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        mot_header_sizer.Add(_label(mot_header, "Short", secondary=True), 1, wx.RIGHT, 4)
        mot_header_sizer.Add(_label(mot_header, "Description", secondary=True), 2, wx.RIGHT, 4)
        mot_header_sizer.Add(_label(mot_header, "PV", secondary=True), 3, wx.RIGHT, 4)
        mot_header_sizer.Add(_label(mot_header, "Prec", secondary=True), 0, wx.RIGHT, 6)
        mot_header_sizer.Add(_label(mot_header, "Map", secondary=True), 0, wx.RIGHT, 6)
        mot_header_sizer.AddSpacer(28)
        mot_header.SetSizer(mot_header_sizer)

        self._motor_rows_panel = wx.ScrolledWindow(m_body, style=wx.VSCROLL)
        self._motor_rows_panel.SetBackgroundColour(BG_CARD)
        self._motor_rows_panel.SetScrollRate(0, 12)
        self._motor_rows_sizer = wx.BoxSizer(wx.VERTICAL)
        self._motor_rows_panel.SetSizer(self._motor_rows_sizer)
        self._motor_rows_panel.SetMinSize((-1, 90))

        self._add_motor_btn = FlatButton(m_body, "+ Add motor")
        self._add_motor_btn.SetMinSize((-1, 28))
        self._add_motor_btn.set_action(self._on_add_motor_clicked)

        m_sizer = wx.BoxSizer(wx.VERTICAL)
        m_sizer.Add(mot_header, 0, wx.EXPAND | wx.BOTTOM, 4)
        m_sizer.Add(self._motor_rows_panel, 1, wx.EXPAND | wx.BOTTOM, 8)
        m_sizer.Add(self._add_motor_btn, 0, wx.EXPAND)
        m_body.SetSizer(m_sizer)

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
        outer.Add(self._rotation_section, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        outer.Add(self._detectors_section, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        outer.Add(self._motors_section, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        outer.Add(self._save_btn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.Add(self._status_label, 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(outer)

        self.SetMinSize((460, -1))

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
        """Populate all fields from the given configuration."""
        self._current_name = config.name
        self._beamline_ctrl.SetValue(config.beamline)
        rm = config.rotation_motor
        self._rotation_short_ctrl.SetValue(rm.shorthand if rm else "")
        self._rotation_description_ctrl.SetValue(rm.description if rm else "")
        self._rotation_pv_ctrl.SetValue(rm.pv if rm else "")
        self._rotation_precision_ctrl.SetValue(str(rm.precision) if rm else "4")

        self._clear_detector_rows()
        for idx, detector in enumerate(config.detectors):
            self._append_detector_row(detector, active=idx == config.active_detector)

        self._clear_motor_rows()
        for motor in config.motors:
            self._append_motor_row(motor)

        if config.name and config.name in self._available_names:
            self._config_combo.SetSelection(self._available_names.index(config.name))

        self._detector_rows_panel.FitInside()
        self._motor_rows_panel.FitInside()
        self.Layout()
        self.set_status("")

    def collect_config(self) -> BeamlineConfig:
        """Build a BeamlineConfig from the current field values."""
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

        rot_pv = self._rotation_pv_ctrl.GetValue().strip()
        try:
            rot_precision = max(0, int(self._rotation_precision_ctrl.GetValue().strip()))
        except ValueError:
            rot_precision = 4
        rotation_motor = (
            MotorConfig(
                shorthand=self._rotation_short_ctrl.GetValue().strip(),
                description=self._rotation_description_ctrl.GetValue().strip(),
                pv=rot_pv,
                precision=rot_precision,
            )
            if rot_pv
            else None
        )

        motors = tuple(row.to_motor() for row in self._motor_rows if row.to_motor().shorthand)
        return BeamlineConfig(
            name=self._current_name,
            beamline=self._beamline_ctrl.GetValue().strip(),
            rotation_motor=rotation_motor,
            detectors=tuple(detectors),
            active_detector=active_index,
            motors=motors,
        )

    def set_status(self, text: str, error: bool = False) -> None:
        self._status_label.SetForegroundColour(DANGER if error else FG_SECONDARY)
        self._status_label.SetLabel(text)
        self.Layout()

    def _clear_detector_rows(self) -> None:
        for row in self._detector_rows:
            self._detector_rows_sizer.Detach(row)
            row.Destroy()
        self._detector_rows.clear()
        self._detector_rows_panel.Layout()

    def _append_detector_row(self, detector: DetectorConfig, active: bool) -> None:
        row = _DetectorRow(
            self._detector_rows_panel,
            detector,
            active=active,
            on_make_active=self._on_make_detector_active,
            on_remove=self._on_remove_detector,
        )
        self._detector_rows_sizer.Add(row, 0, wx.EXPAND | wx.BOTTOM, 4)
        self._detector_rows.append(row)
        self._detector_rows_panel.FitInside()
        self._detector_rows_panel.Layout()

    def _on_add_detector_clicked(self) -> None:
        first = not self._detector_rows
        self._append_detector_row(DetectorConfig(), active=first)

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
        self._detector_rows_panel.FitInside()
        self._detector_rows_panel.Layout()

    def _clear_motor_rows(self) -> None:
        for row in self._motor_rows:
            self._motor_rows_sizer.Detach(row)
            row.Destroy()
        self._motor_rows.clear()
        self._motor_rows_panel.Layout()

    def _append_motor_row(self, motor: MotorConfig) -> None:
        row = _MotorRow(self._motor_rows_panel, motor, on_remove=self._on_remove_motor)
        self._motor_rows_sizer.Add(row, 0, wx.EXPAND | wx.BOTTOM, 4)
        self._motor_rows.append(row)
        self._motor_rows_panel.FitInside()
        self._motor_rows_panel.Layout()

    def _on_add_motor_clicked(self) -> None:
        self._append_motor_row(MotorConfig(shorthand="", name="", pv=""))

    def _on_remove_motor(self, row: _MotorRow) -> None:
        if row not in self._motor_rows:
            return
        self._motor_rows.remove(row)
        self._motor_rows_sizer.Detach(row)
        row.Destroy()
        self._motor_rows_panel.FitInside()
        self._motor_rows_panel.Layout()

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


class BeamlineConfigDialog(wx.Dialog):
    """Top-level dialog that wraps the BeamlineConfigView panel with a dark scrollbar."""

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

        self.SetSize(628, 680)
        self.SetMinSize((488, 540))
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
