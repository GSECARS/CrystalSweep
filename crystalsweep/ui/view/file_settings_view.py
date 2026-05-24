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

from crystalsweep.ui.view.custom.icons import draw_folder, draw_folder_open, draw_refresh, draw_update
from crystalsweep.ui.view.custom.theme import (
    ACCENT,
    BG_CARD,
    BG_ELEVATED,
    BG_SURFACE,
    DISABLED_FG,
    FG_PRIMARY,
    FG_SECONDARY,
    PONI_LOADED,
    SEP_COLOUR,
    scaled_font,
)
from crystalsweep.ui.view.custom.widgets import DarkTextCtrl, DarkToggle, IconButton

__all__ = ["FileSettingsView"]

_PATH_NO_DIR = wx.Colour(220, 160, 40)
_PATH_EXISTS = wx.Colour(220, 160, 40)
_PATH_OK = wx.Colour(46, 139, 78)


class FileSettingsView(wx.Panel):
    """File settings panel: filename, path, frame #, map ext, format flags, software flags."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)

        self._file_number_width: int = 4
        self._on_filename_changed_cb: Callable[[str], None] | None = None
        self._on_filename_update_cb: Callable[[], None] | None = None
        self._on_directory_changed_cb: Callable[[Path], None] | None = None
        self._on_path_update_cb: Callable[[], None] | None = None
        self._on_frame_changed_cb: Callable[[int], None] | None = None
        self._on_frame_reset_cb: Callable[[], None] | None = None
        self._on_frame_update_cb: Callable[[], None] | None = None
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

        outer = wx.BoxSizer(wx.VERTICAL)

        outer.Add(self._make_row_path_status(), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(4)

        outer.Add(self._make_row_filename_and_frame(label_font), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(4)

        outer.Add(self._make_row_path(label_font), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(4)

        outer.Add(self._make_row_format_and_map_ext(label_font), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        outer.AddSpacer(8)

        self.SetSizer(outer)
        self._validate_path()

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
        self._filename_lbl = self._field_label("Filename", label_font)
        lbl = self._filename_lbl
        lbl.SetMinSize((70, -1))
        self._filename_ctrl = DarkTextCtrl(self, parent_bg=BG_CARD)
        self._filename_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_filename_enter)
        self._filename_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_filename_enter)
        self._filename_update_btn = IconButton(self, draw_update, size=16, tooltip="Update filename", bg=BG_CARD)
        self._filename_update_btn.Bind(wx.EVT_BUTTON, lambda _: self._fire(self._on_filename_update_cb))
        self._frame_lbl = self._field_label("Frame #", label_font)
        frame_lbl = self._frame_lbl
        self._frame_ctrl = DarkTextCtrl(self, value="0", placeholder="0", parent_bg=BG_CARD)
        self._frame_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_frame_enter)
        self._frame_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_frame_enter)
        self._frame_reset_btn = IconButton(self, draw_refresh, size=16, tooltip="Reset frame number", bg=BG_CARD)
        self._frame_reset_btn.Bind(wx.EVT_BUTTON, lambda _: self._on_frame_reset())
        self._frame_update_btn = IconButton(self, draw_update, size=16, tooltip="Update frame number", bg=BG_CARD)
        self._frame_update_btn.Bind(wx.EVT_BUTTON, lambda _: self._on_frame_update())
        vsep = wx.Panel(self, size=(1, -1))
        vsep.SetBackgroundColour(SEP_COLOUR)
        frame_section = wx.BoxSizer(wx.HORIZONTAL)
        frame_section.Add(frame_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        frame_section.AddSpacer(4)
        frame_section.Add(self._frame_ctrl, 1, wx.EXPAND)
        frame_section.AddSpacer(4)
        frame_section.Add(self._frame_reset_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        frame_section.AddSpacer(2)
        frame_section.Add(self._frame_update_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(6)
        row.Add(self._filename_ctrl, 1, wx.EXPAND)
        row.AddSpacer(4)
        row.Add(self._filename_update_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(8)
        row.Add(vsep, 0, wx.EXPAND)
        row.AddSpacer(8)
        row.Add(frame_section, 0, wx.ALIGN_CENTER_VERTICAL)
        return row

    def _make_row_path(self, label_font: wx.Font) -> wx.Sizer:
        row = wx.BoxSizer(wx.HORIZONTAL)
        self._path_lbl = self._field_label("Path", label_font)
        lbl = self._path_lbl
        lbl.SetMinSize((70, -1))
        self._path_ctrl = DarkTextCtrl(self, parent_bg=BG_CARD)
        self._path_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_path_enter)
        self._path_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_path_enter)
        self._path_browse_btn = IconButton(self, draw_folder_open, size=16, tooltip="Browse for directory", bg=BG_CARD)
        self._path_browse_btn.Bind(wx.EVT_BUTTON, lambda _: self._browse_directory())
        self._path_update_btn = IconButton(self, draw_update, size=16, tooltip="Update path", bg=BG_CARD)
        self._path_update_btn.Bind(wx.EVT_BUTTON, lambda _: self._fire(self._on_path_update_cb))
        row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(6)
        row.Add(self._path_ctrl, 1, wx.EXPAND)
        row.AddSpacer(4)
        row.Add(self._path_browse_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(2)
        row.Add(self._path_update_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        return row

    def _make_row_path_status(self) -> wx.Sizer:
        row = wx.BoxSizer(wx.HORIZONTAL)
        self._path_status_label = wx.StaticText(self, label="", style=wx.ST_ELLIPSIZE_START | wx.ST_NO_AUTORESIZE)
        self._path_status_label.SetFont(scaled_font(12, style=wx.FONTSTYLE_ITALIC))
        self._path_status_label.SetBackgroundColour(BG_CARD)
        self._path_status_label.SetForegroundColour(FG_SECONDARY)
        self._hdf5_toggle = DarkToggle(self, "HDF5")
        self._hdf5_toggle.SetBackgroundColour(BG_CARD)
        self._hdf5_toggle.Bind(wx.EVT_CHECKBOX, lambda v: self._fire(self._on_hdf5_changed_cb, v))
        self._cbf_toggle = DarkToggle(self, "CBF")
        self._cbf_toggle.SetBackgroundColour(BG_CARD)
        self._cbf_toggle.Bind(wx.EVT_CHECKBOX, lambda v: self._fire(self._on_cbf_changed_cb, v))
        self._tif_toggle = DarkToggle(self, "TIF")
        self._tif_toggle.SetBackgroundColour(BG_CARD)
        self._tif_toggle.Bind(wx.EVT_CHECKBOX, lambda v: self._fire(self._on_tif_changed_cb, v))
        row.SetMinSize((-1, 22))
        row.Add(self._path_status_label, 1, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(8)
        row.Add(self._hdf5_toggle, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(6)
        row.Add(self._cbf_toggle, 0, wx.ALIGN_CENTER_VERTICAL)
        row.AddSpacer(6)
        row.Add(self._tif_toggle, 0, wx.ALIGN_CENTER_VERTICAL)
        return row

    def _make_row_format_and_map_ext(self, label_font: wx.Font) -> wx.Sizer:
        row = wx.BoxSizer(wx.HORIZONTAL)
        cal_font = scaled_font(12)

        self._map_ext_lbl = self._field_label("Map ext.", label_font)
        map_lbl = self._map_ext_lbl
        map_lbl.SetMinSize((70, -1))
        self._map_ext_ctrl = DarkTextCtrl(self, parent_bg=BG_CARD)
        self._map_ext_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_map_ext_enter)
        self._map_ext_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_map_ext_enter)

        vsep1 = wx.Panel(self, size=(1, -1))
        vsep1.SetBackgroundColour(SEP_COLOUR)

        self._crysalis_toggle = DarkToggle(self, "Use CrysAlis")
        self._crysalis_toggle.SetBackgroundColour(BG_CARD)
        self._crysalis_toggle.Bind(wx.EVT_CHECKBOX, lambda v: self._fire(self._on_crysalis_changed_cb, v))
        self._crysalis_cal_label = wx.StaticText(self, label="Not loaded", style=wx.ST_ELLIPSIZE_START | wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)
        self._crysalis_cal_label.SetFont(cal_font)
        self._crysalis_cal_label.SetForegroundColour(FG_SECONDARY)
        self._crysalis_cal_label.SetBackgroundColour(BG_CARD)
        self._crysalis_cal_btn = IconButton(self, draw_folder, size=16, tooltip="Load CrysAlis calibration", bg=BG_CARD)
        self._crysalis_cal_btn.Bind(wx.EVT_BUTTON, lambda _: self._browse_crysalis_calibration())

        vsep2 = wx.Panel(self, size=(1, -1))
        vsep2.SetBackgroundColour(SEP_COLOUR)

        self._apex_toggle = DarkToggle(self, "Use APEX")
        self._apex_toggle.SetBackgroundColour(BG_CARD)
        self._apex_toggle.Bind(wx.EVT_CHECKBOX, lambda v: self._fire(self._on_apex_changed_cb, v))
        self._apex_cal_label = wx.StaticText(self, label="Not loaded", style=wx.ST_ELLIPSIZE_START | wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)
        self._apex_cal_label.SetFont(cal_font)
        self._apex_cal_label.SetForegroundColour(FG_SECONDARY)
        self._apex_cal_label.SetBackgroundColour(BG_CARD)
        self._apex_cal_btn = IconButton(self, draw_folder, size=16, tooltip="Load APEX calibration", bg=BG_CARD)
        self._apex_cal_btn.Bind(wx.EVT_BUTTON, lambda _: self._browse_apex_calibration())

        crysalis_inner = wx.BoxSizer(wx.HORIZONTAL)
        crysalis_inner.Add(self._crysalis_toggle, 0, wx.ALIGN_CENTER_VERTICAL)
        crysalis_inner.AddSpacer(4)
        crysalis_inner.Add(self._crysalis_cal_label, 1, wx.ALIGN_CENTER_VERTICAL)
        crysalis_inner.AddSpacer(4)
        crysalis_inner.Add(self._crysalis_cal_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        crysalis_col = wx.BoxSizer(wx.VERTICAL)
        crysalis_col.AddStretchSpacer()
        crysalis_col.Add(crysalis_inner, 0, wx.EXPAND)
        crysalis_col.AddStretchSpacer()

        apex_inner = wx.BoxSizer(wx.HORIZONTAL)
        apex_inner.Add(self._apex_toggle, 0, wx.ALIGN_CENTER_VERTICAL)
        apex_inner.AddSpacer(4)
        apex_inner.Add(self._apex_cal_label, 1, wx.ALIGN_CENTER_VERTICAL)
        apex_inner.AddSpacer(4)
        apex_inner.Add(self._apex_cal_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        apex_col = wx.BoxSizer(wx.VERTICAL)
        apex_col.AddStretchSpacer()
        apex_col.Add(apex_inner, 0, wx.EXPAND)
        apex_col.AddStretchSpacer()

        map_col = wx.BoxSizer(wx.HORIZONTAL)
        map_col.Add(map_lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        map_col.AddSpacer(6)
        map_col.Add(self._map_ext_ctrl, 1, wx.EXPAND)

        row.Add(map_col, 1, wx.EXPAND)
        row.AddSpacer(8)
        row.Add(vsep1, 0, wx.EXPAND)
        row.AddSpacer(8)
        row.Add(crysalis_col, 1, wx.EXPAND)
        row.AddSpacer(8)
        row.Add(vsep2, 0, wx.EXPAND)
        row.AddSpacer(8)
        row.Add(apex_col, 1, wx.EXPAND)
        return row

    def bind_filename_changed(self, callback: Callable[[str], None]) -> None:
        self._on_filename_changed_cb = callback

    def bind_filename_update(self, callback: Callable[[], None]) -> None:
        self._on_filename_update_cb = callback

    def bind_directory_changed(self, callback: Callable[[Path], None]) -> None:
        self._on_directory_changed_cb = callback

    def bind_path_update(self, callback: Callable[[], None]) -> None:
        self._on_path_update_cb = callback

    def bind_frame_changed(self, callback: Callable[[int], None]) -> None:
        self._on_frame_changed_cb = callback

    def bind_frame_reset(self, callback: Callable[[], None]) -> None:
        self._on_frame_reset_cb = callback

    def bind_frame_update(self, callback: Callable[[], None]) -> None:
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

    def set_enabled(self, enabled: bool) -> None:
        for ctrl in (
            self._filename_ctrl, self._filename_update_btn,
            self._frame_ctrl, self._frame_reset_btn, self._frame_update_btn,
            self._path_ctrl, self._path_browse_btn, self._path_update_btn,
            self._map_ext_ctrl, self._crysalis_cal_btn, self._apex_cal_btn,
        ):
            ctrl.Enable(enabled)
        for toggle in (
            self._hdf5_toggle, self._cbf_toggle, self._tif_toggle,
            self._crysalis_toggle, self._apex_toggle,
        ):
            toggle.SetLocked(not enabled)
        self._path_status_label.Enable(True)
        lbl_colour = FG_SECONDARY if enabled else DISABLED_FG
        for lbl in (self._filename_lbl, self._frame_lbl, self._path_lbl, self._map_ext_lbl):
            lbl.SetForegroundColour(lbl_colour)
            lbl.Refresh()

    def set_file_number_width(self, width: int) -> None:
        self._file_number_width = max(1, width)
        self._validate_path()

    def set_filename(self, value: str) -> None:
        self._filename_ctrl.SetValue(value)
        self._validate_path()

    def set_directory(self, path: Path) -> None:
        self._path_ctrl.SetValue(str(path) if path != Path() else "")
        self._validate_path()

    def set_frame_number(self, value: int) -> None:
        self._frame_ctrl.SetValue(str(value))
        self._validate_path()

    def set_map_ext(self, value: str) -> None:
        self._map_ext_ctrl.SetValue(value)

    def set_hdf5(self, value: bool) -> None:
        self._hdf5_toggle.SetValue(value)

    def set_cbf(self, value: bool) -> None:
        self._cbf_toggle.SetValue(value)

    def set_tif(self, value: bool) -> None:
        self._tif_toggle.SetValue(value)

    def set_detector_format(self, format_key: str | None) -> None:
        if format_key == "hdf5":
            self._hdf5_toggle.SetValue(True)
            self._hdf5_toggle.SetLocked(True)
        else:
            self._hdf5_toggle.SetLocked(False)
        if format_key == "cbf":
            self._cbf_toggle.SetValue(True)
            self._cbf_toggle.SetLocked(True)
        else:
            self._cbf_toggle.SetLocked(False)
        if format_key == "tif":
            self._tif_toggle.SetValue(True)
            self._tif_toggle.SetLocked(True)
        else:
            self._tif_toggle.SetLocked(False)

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

    def _fire(self, cb, value=None) -> None:
        if cb is None:
            return
        if value is None:
            cb()
        else:
            cb(value)

    def _validate_path(self) -> None:
        filename = self._filename_ctrl.GetValue().strip()
        raw_path = self._path_ctrl.GetValue().strip()
        if not filename or not raw_path:
            self._path_status_label.SetLabel("No file path set")
            self._path_status_label.SetForegroundColour(FG_SECONDARY)
            self._path_status_label.Refresh()
            return
        try:
            frame = int(self._frame_ctrl.GetValue().strip())
        except ValueError:
            frame = 0
        framed_name = f"{filename}_{frame:0{self._file_number_width}d}"
        directory = Path(raw_path)
        display_path = str(directory / framed_name)
        if not directory.exists():
            self._path_status_label.SetLabel(display_path)
            self._path_status_label.SetForegroundColour(_PATH_NO_DIR)
        elif any(directory.glob(f"{framed_name}*")):
            self._path_status_label.SetLabel(display_path)
            self._path_status_label.SetForegroundColour(_PATH_EXISTS)
        else:
            self._path_status_label.SetLabel(display_path)
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

    def _on_frame_enter(self, event: wx.Event) -> None:
        try:
            value = int(self._frame_ctrl.GetValue().strip())
        except ValueError:
            event.Skip()
            return
        if self._on_frame_changed_cb is not None:
            self._on_frame_changed_cb(value)
        self._validate_path()
        event.Skip()

    def _on_frame_reset(self) -> None:
        self._frame_ctrl.SetValue("0")
        if self._on_frame_reset_cb is not None:
            self._on_frame_reset_cb()

    def _on_frame_update(self) -> None:
        if self._on_frame_update_cb is not None:
            self._on_frame_update_cb()

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
