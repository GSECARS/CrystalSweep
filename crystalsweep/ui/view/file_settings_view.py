#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/file_settings_view.py
# ----------------------------------------------------------------------------------
# Purpose:
# File settings panel displayed at the top of the left side panel.  Exposes
# filename, directory path (with folder-browser button), frame number (with
# reset and update buttons), map extension, image-format checkboxes, and
# external software toggles with load-calibration buttons.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import sys
from pathlib import Path
from typing import Callable

import wx

from crystalsweep.ui.view.custom.icons import draw_folder_open, draw_refresh, draw_update
from crystalsweep.ui.view.custom.theme import (
    ACCENT,
    BG_CARD,
    BG_ELEVATED,
    BG_SURFACE,
    FG_PRIMARY,
    FG_SECONDARY,
    PONI_LOADED,
    SEP_COLOUR,
    scaled_font,
)
from crystalsweep.ui.view.custom.widgets import DarkTextCtrl, DarkToggle, FlatButton, IconButton

__all__ = ["FileSettingsView"]

_DEFAULT_MAP_EXT = "map"
_PATH_OK = wx.Colour(72, 199, 116)
_PATH_EXISTS = wx.Colour(220, 80, 80)
_PATH_NO_DIR = wx.Colour(210, 140, 40)


class FileSettingsView(wx.Panel):
    """File settings panel: filename, path, frame #, map ext, format flags, software flags."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)

        self._on_filename_changed_cb: Callable[[str], None] | None = None
        self._on_directory_changed_cb: Callable[[Path], None] | None = None
        self._on_frame_reset_cb: Callable[[], None] | None = None
        self._on_frame_update_cb: Callable[[int], None] | None = None
        self._on_map_ext_changed_cb: Callable[[str], None] | None = None
        self._on_hdf5_changed_cb: Callable[[bool], None] | None = None
        self._on_cbf_changed_cb: Callable[[bool], None] | None = None
        self._on_tif_changed_cb: Callable[[bool], None] | None = None
        self._on_crysalis_changed_cb: Callable[[bool], None] | None = None
        self._on_crysalis_calibration_cb: Callable[[Path], None] | None = None
        self._on_apex_changed_cb: Callable[[bool], None] | None = None
        self._on_apex_calibration_cb: Callable[[Path], None] | None = None

        self.SetBackgroundColour(BG_CARD)
        self._build_layout()

    def _build_layout(self) -> None:
        label_font = scaled_font(12)
        section_font = scaled_font(13, weight=wx.FONTWEIGHT_BOLD)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.AddSpacer(6)

        outer.Add(self._make_section_label("File Settings", section_font), 0, wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(6)

        outer.Add(self._make_sep(), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        outer.AddSpacer(6)

        outer.Add(self._make_row_filename_and_frame(label_font), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(4)

        outer.Add(self._make_row_path(label_font), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(2)

        outer.Add(self._make_row_path_status(label_font), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(4)

        outer.Add(self._make_row_format_and_map_ext(label_font), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(8)

        outer.Add(self._make_sep(), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        outer.AddSpacer(6)

        outer.Add(self._make_row_software(label_font), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(8)

        self.SetSizer(outer)

    def _make_section_label(self, text: str, font: wx.Font) -> wx.StaticText:
        lbl = wx.StaticText(self, label=text)
        lbl.SetFont(font)
        lbl.SetForegroundColour(FG_PRIMARY)
        lbl.SetBackgroundColour(BG_CARD)
        return lbl

    def _make_sep(self) -> wx.Panel:
        sep = wx.Panel(self, size=(-1, 1))
        sep.SetBackgroundColour(SEP_COLOUR)
        return sep

    def _field_label(self, text: str, font: wx.Font) -> wx.StaticText:
        lbl = wx.StaticText(self, label=text)
        lbl.SetFont(font)
        lbl.SetForegroundColour(FG_SECONDARY)
        lbl.SetBackgroundColour(BG_CARD)
        return lbl

    def _make_row_filename_and_frame(self, label_font: wx.Font) -> wx.Sizer:
        row = wx.BoxSizer(wx.HORIZONTAL)
        lbl = self._field_label("Filename", label_font)
        lbl.SetMinSize((70, -1))
        self._filename_ctrl = DarkTextCtrl(self, placeholder="filename", parent_bg=BG_CARD)
        self._filename_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_filename_enter)
        self._filename_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_filename_enter)
        row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(6)
        row.Add(self._filename_ctrl, 1, wx.EXPAND)
        return row

    def _make_row_path(self, label_font: wx.Font) -> wx.Sizer:
        row = wx.BoxSizer(wx.HORIZONTAL)
        lbl = self._field_label("Path", label_font)
        lbl.SetMinSize((70, -1))
        self._path_ctrl = DarkTextCtrl(self, placeholder="directory path", parent_bg=BG_CARD)
        self._path_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_path_enter)
        self._path_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_path_enter)
        self._path_browse_btn = IconButton(self, draw_folder_open, size=16, tooltip="Browse for directory", bg=BG_CARD)
        self._path_browse_btn.Bind(wx.EVT_BUTTON, lambda _: self._browse_directory())
        row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(6)
        row.Add(self._path_ctrl, 1, wx.EXPAND)
        row.AddSpacer(4)
        row.Add(self._path_browse_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        return row

    def _make_row_path_status(self, label_font: wx.Font) -> wx.Sizer:
        row = wx.BoxSizer(wx.HORIZONTAL)
        self._path_status_label = wx.StaticText(self, label="", style=wx.ST_ELLIPSIZE_START | wx.ST_NO_AUTORESIZE)
        self._path_status_label.SetFont(scaled_font(12))
        self._path_status_label.SetBackgroundColour(BG_CARD)
        self._path_status_label.SetForegroundColour(FG_SECONDARY)
        row.Add(self._path_status_label, 1, wx.EXPAND)
        return row

    def _make_row_format_and_map_ext(self, label_font: wx.Font) -> wx.Sizer:
        row = wx.BoxSizer(wx.HORIZONTAL)
        frame_lbl = self._field_label("Frame #", label_font)
        self._frame_ctrl = DarkTextCtrl(self, value="0", placeholder="0", parent_bg=BG_CARD)
        self._frame_ctrl.SetSize(wx.Size(62, 28))
        self._frame_reset_btn = IconButton(self, draw_refresh, size=16, tooltip="Reset frame number", bg=BG_CARD)
        self._frame_reset_btn.Bind(wx.EVT_BUTTON, lambda _: self._on_frame_reset())
        self._frame_update_btn = IconButton(self, draw_update, size=16, tooltip="Apply frame number", bg=BG_CARD)
        self._frame_update_btn.Bind(wx.EVT_BUTTON, lambda _: self._on_frame_update())
        self._hdf5_toggle = DarkToggle(self, "HDF5")
        self._hdf5_toggle.SetBackgroundColour(BG_CARD)
        self._hdf5_toggle.Bind(wx.EVT_CHECKBOX, lambda v: self._fire(self._on_hdf5_changed_cb, v))
        self._cbf_toggle = DarkToggle(self, "CBF")
        self._cbf_toggle.SetBackgroundColour(BG_CARD)
        self._cbf_toggle.Bind(wx.EVT_CHECKBOX, lambda v: self._fire(self._on_cbf_changed_cb, v))
        self._tif_toggle = DarkToggle(self, "TIF")
        self._tif_toggle.SetBackgroundColour(BG_CARD)
        self._tif_toggle.Bind(wx.EVT_CHECKBOX, lambda v: self._fire(self._on_tif_changed_cb, v))
        map_lbl = self._field_label("Map ext.", label_font)
        self._map_ext_ctrl = DarkTextCtrl(self, value=_DEFAULT_MAP_EXT, placeholder="map", parent_bg=BG_CARD)
        self._map_ext_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_map_ext_enter)
        self._map_ext_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_map_ext_enter)
        row.Add(frame_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(4)
        row.Add(self._frame_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.FIXED_MINSIZE)
        row.AddSpacer(2)
        row.Add(self._frame_reset_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(2)
        row.Add(self._frame_update_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(10)
        row.Add(self._hdf5_toggle, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(6)
        row.Add(self._cbf_toggle, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(6)
        row.Add(self._tif_toggle, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(8)
        row.Add(map_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(4)
        row.Add(self._map_ext_ctrl, 1, wx.EXPAND)
        return row

    def _make_row_software(self, label_font: wx.Font) -> wx.Sizer:
        row = wx.BoxSizer(wx.HORIZONTAL)
        cal_font = scaled_font(12)

        left = wx.BoxSizer(wx.VERTICAL)
        top_left = wx.BoxSizer(wx.HORIZONTAL)
        self._crysalis_toggle = DarkToggle(self, "Use CrysAlis")
        self._crysalis_toggle.SetBackgroundColour(BG_CARD)
        self._crysalis_toggle.Bind(wx.EVT_CHECKBOX, lambda v: self._fire(self._on_crysalis_changed_cb, v))
        self._crysalis_cal_label = wx.StaticText(self, label="Not loaded", style=wx.ST_ELLIPSIZE_START | wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)
        self._crysalis_cal_label.SetFont(cal_font)
        self._crysalis_cal_label.SetForegroundColour(FG_SECONDARY)
        self._crysalis_cal_label.SetBackgroundColour(BG_CARD)
        top_left.Add(self._crysalis_toggle, 0, wx.ALIGN_CENTER_VERTICAL)
        top_left.AddSpacer(4)
        top_left.Add(self._crysalis_cal_label, 1, wx.EXPAND)
        self._crysalis_cal_btn = FlatButton(self, "Load Calibration")
        self._crysalis_cal_btn.SetMinSize((-1, 24))
        self._crysalis_cal_btn.set_action(self._browse_crysalis_calibration)
        left.Add(top_left, 0, wx.EXPAND)
        left.AddSpacer(4)
        left.Add(self._crysalis_cal_btn, 0, wx.EXPAND | wx.LEFT, 4)

        vsep = wx.Panel(self, size=(1, -1))
        vsep.SetBackgroundColour(SEP_COLOUR)

        right = wx.BoxSizer(wx.VERTICAL)
        top_right = wx.BoxSizer(wx.HORIZONTAL)
        self._apex_toggle = DarkToggle(self, "Use APEX")
        self._apex_toggle.SetBackgroundColour(BG_CARD)
        self._apex_toggle.Bind(wx.EVT_CHECKBOX, lambda v: self._fire(self._on_apex_changed_cb, v))
        self._apex_cal_label = wx.StaticText(self, label="Not loaded", style=wx.ST_ELLIPSIZE_START | wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)
        self._apex_cal_label.SetFont(cal_font)
        self._apex_cal_label.SetForegroundColour(FG_SECONDARY)
        self._apex_cal_label.SetBackgroundColour(BG_CARD)
        top_right.Add(self._apex_toggle, 0, wx.ALIGN_CENTER_VERTICAL)
        top_right.AddSpacer(4)
        top_right.Add(self._apex_cal_label, 1, wx.EXPAND)
        self._apex_cal_btn = FlatButton(self, "Load Calibration")
        self._apex_cal_btn.SetMinSize((-1, 24))
        self._apex_cal_btn.set_action(self._browse_apex_calibration)
        right.Add(top_right, 0, wx.EXPAND)
        right.AddSpacer(4)
        right.Add(self._apex_cal_btn, 0, wx.EXPAND | wx.LEFT, 4)

        row.Add(left, 1, wx.EXPAND)
        row.AddSpacer(8)
        row.Add(vsep, 0, wx.EXPAND)
        row.AddSpacer(8)
        row.Add(right, 1, wx.EXPAND)
        return row

    def bind_filename_changed(self, callback: Callable[[str], None]) -> None:
        self._on_filename_changed_cb = callback

    def bind_directory_changed(self, callback: Callable[[Path], None]) -> None:
        self._on_directory_changed_cb = callback

    def bind_frame_reset(self, callback: Callable[[], None]) -> None:
        self._on_frame_reset_cb = callback

    def bind_frame_update(self, callback: Callable[[int], None]) -> None:
        self._on_frame_update_cb = callback

    def bind_map_ext_changed(self, callback: Callable[[str], None]) -> None:
        self._on_map_ext_changed_cb = callback

    def bind_hdf5_changed(self, callback: Callable[[bool], None]) -> None:
        self._on_hdf5_changed_cb = callback

    def bind_cbf_changed(self, callback: Callable[[bool], None]) -> None:
        self._on_cbf_changed_cb = callback

    def bind_tif_changed(self, callback: Callable[[bool], None]) -> None:
        self._on_tif_changed_cb = callback

    def bind_crysalis_changed(self, callback: Callable[[bool], None]) -> None:
        self._on_crysalis_changed_cb = callback

    def bind_crysalis_calibration(self, callback: Callable[[Path], None]) -> None:
        self._on_crysalis_calibration_cb = callback

    def bind_apex_changed(self, callback: Callable[[bool], None]) -> None:
        self._on_apex_changed_cb = callback

    def bind_apex_calibration(self, callback: Callable[[Path], None]) -> None:
        self._on_apex_calibration_cb = callback

    def set_filename(self, value: str) -> None:
        self._filename_ctrl.SetValue(value)

    def set_directory(self, path: Path) -> None:
        self._path_ctrl.SetValue(str(path) if path != Path() else "")

    def set_frame_number(self, value: int) -> None:
        self._frame_ctrl.SetValue(str(value))

    def set_map_ext(self, value: str) -> None:
        self._map_ext_ctrl.SetValue(value)

    def set_hdf5(self, value: bool) -> None:
        self._hdf5_toggle.SetValue(value)

    def set_cbf(self, value: bool) -> None:
        self._cbf_toggle.SetValue(value)

    def set_tif(self, value: bool) -> None:
        self._tif_toggle.SetValue(value)

    def set_crysalis(self, value: bool) -> None:
        self._crysalis_toggle.SetValue(value)

    def set_crysalis_calibration_label(self, path: Path | None) -> None:
        if path is not None:
            self._crysalis_cal_label.SetLabel(path.name)
            self._crysalis_cal_label.SetForegroundColour(PONI_LOADED)
        else:
            self._crysalis_cal_label.SetLabel("Not loaded")
            self._crysalis_cal_label.SetForegroundColour(FG_SECONDARY)
        self._crysalis_cal_label.Refresh()

    def set_apex(self, value: bool) -> None:
        self._apex_toggle.SetValue(value)

    def set_apex_calibration_label(self, path: Path | None) -> None:
        if path is not None:
            self._apex_cal_label.SetLabel(path.name)
            self._apex_cal_label.SetForegroundColour(PONI_LOADED)
        else:
            self._apex_cal_label.SetLabel("Not loaded")
            self._apex_cal_label.SetForegroundColour(FG_SECONDARY)
        self._apex_cal_label.Refresh()

    def _fire(self, cb, value) -> None:
        if cb is not None:
            cb(value)

    def _validate_path(self) -> None:
        filename = self._filename_ctrl.GetValue().strip()
        raw_path = self._path_ctrl.GetValue().strip()
        if not filename or not raw_path:
            self._path_status_label.SetLabel("")
            return
        directory = Path(raw_path)
        full_path = directory / filename
        if not directory.exists():
            self._path_status_label.SetLabel(str(full_path))
            self._path_status_label.SetForegroundColour(_PATH_NO_DIR)
        elif full_path.exists():
            self._path_status_label.SetLabel(str(full_path))
            self._path_status_label.SetForegroundColour(_PATH_EXISTS)
        else:
            self._path_status_label.SetLabel(str(full_path))
            self._path_status_label.SetForegroundColour(_PATH_OK)
        self._path_status_label.Refresh()

    def _on_filename_enter(self, event: wx.Event) -> None:
        value = self._filename_ctrl.GetValue()
        if self._on_filename_changed_cb is not None:
            self._on_filename_changed_cb(value)
        self._validate_path()
        event.Skip()

    def _on_path_enter(self, event: wx.Event) -> None:
        raw = self._path_ctrl.GetValue().strip()
        if self._on_directory_changed_cb is not None and raw:
            self._on_directory_changed_cb(Path(raw))
        self._validate_path()
        event.Skip()

    def _on_frame_reset(self) -> None:
        self._frame_ctrl.SetValue("0")
        if self._on_frame_reset_cb is not None:
            self._on_frame_reset_cb()

    def _on_frame_update(self) -> None:
        try:
            value = int(self._frame_ctrl.GetValue())
        except ValueError:
            return
        if self._on_frame_update_cb is not None:
            self._on_frame_update_cb(value)

    def _on_map_ext_enter(self, event: wx.Event) -> None:
        value = self._map_ext_ctrl.GetValue().strip()
        if value and self._on_map_ext_changed_cb is not None:
            self._on_map_ext_changed_cb(value)
        event.Skip()

    def _browse_directory(self) -> None:
        with wx.DirDialog(
            self,
            "Select directory",
            defaultPath=self._path_ctrl.GetValue() or str(Path.home()),
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            chosen = Path(dlg.GetPath())
        self._path_ctrl.SetValue(str(chosen))
        if self._on_directory_changed_cb is not None:
            self._on_directory_changed_cb(chosen)
        self._validate_path()

    def _browse_crysalis_calibration(self) -> None:
        with wx.FileDialog(
            self,
            "Load CrysAlis calibration file",
            wildcard="All files (*.*)|*.*" if sys.platform == "win32" else "*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            chosen = Path(dlg.GetPath())
        if self._on_crysalis_calibration_cb is not None:
            self._on_crysalis_calibration_cb(chosen)

    def _browse_apex_calibration(self) -> None:
        with wx.FileDialog(
            self,
            "Load APEX calibration file",
            wildcard="All files (*.*)|*.*" if sys.platform == "win32" else "*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            chosen = Path(dlg.GetPath())
        if self._on_apex_calibration_cb is not None:
            self._on_apex_calibration_cb(chosen)
