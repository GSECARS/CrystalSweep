#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/controller/file_settings_controller.py
# ----------------------------------------------------------------------------------
# Purpose:
# Controller that bridges FileSettingsModel and FileSettingsView: binds all view
# callbacks, updates the model on every user action, and syncs the view from the
# model on startup.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
import threading
from pathlib import Path

import wx

from crystalsweep.model import MainModel
from crystalsweep.model.detector_model import get_detector_model
from crystalsweep.ui.view import MainView

__all__ = ["FileSettingsController"]

_log = logging.getLogger(__name__)


class FileSettingsController:
    """Bridges the file settings model and view."""

    def __init__(self, model: MainModel, view: MainView) -> None:
        self._model = model
        self._view = view

        fs = self._view.file_settings
        fs.bind_filename_changed(self._on_filename_changed)
        fs.bind_filename_update(self._on_filename_update)
        fs.bind_directory_changed(self._on_directory_changed)
        fs.bind_path_update(self._on_path_update)
        fs.bind_frame_changed(self._on_frame_changed)
        fs.bind_frame_reset(self._on_frame_reset)
        fs.bind_frame_update(self._on_frame_update)
        fs.bind_map_ext_changed(self._on_map_ext_changed)
        fs.bind_hdf5_changed(self._on_hdf5_changed)
        fs.bind_cbf_changed(self._on_cbf_changed)
        fs.bind_tif_changed(self._on_tif_changed)
        fs.bind_crysalis_changed(self._on_crysalis_changed)
        fs.bind_crysalis_calibration(self._on_crysalis_calibration)
        fs.bind_apex_changed(self._on_apex_changed)
        fs.bind_apex_calibration(self._on_apex_calibration)

        self._sync_view_from_model()
        self.sync_from_detector()

    def sync_from_detector(self) -> None:
        """Fetch FilePath, FileName and FileNumber from the active detector — updates all three fields."""
        self._push_file_number_width()
        self._sync_format_from_detector()
        self._fetch_from_detector(update_directory=True, update_filename=True, update_frame=True)

    def apply_crysalis_from_config(self) -> None:
        """If the active beamline config has crysalis_load_on_startup set, load the PAR file and enable CrysAlis."""
        cfg = self._model.beamline.active
        if not cfg.crysalis_load_on_startup or not cfg.crysalis_par_path:
            return
        path = Path(cfg.crysalis_par_path)
        if not path.is_file():
            _log.warning("apply_crysalis_from_config: PAR file not found: %s", path)
            return
        self._model.file_settings.crysalis_calibration = path
        self._model.file_settings.use_crysalis = True
        self._view.file_settings.set_crysalis_calibration_label(path)
        self._view.file_settings.set_crysalis(True)
        _log.debug("apply_crysalis_from_config: loaded %s", path)

    def _sync_format_from_detector(self) -> None:
        cfg = self._model.beamline.active
        det = cfg.active_detector_config if cfg else None
        fmt = det.file_format if det else None
        self._view.file_settings.set_detector_format(fmt)

    def push_to_detector(self) -> None:
        """Push current file settings (path, filename, frame number, template) to the active detector plugin."""
        cfg = self._model.beamline.active
        det = cfg.active_detector_config if cfg else None
        if det is None or not det.pv_prefix.strip():
            return

        m = self._model.file_settings
        detector = get_detector_model(det.type, det.pv_prefix, det.file_format)
        directory = det.translate_path(str(m.directory))
        filename = m.filename
        frame_number = m.frame_number
        file_template = det.file_template

        def _push() -> None:
            try:
                detector.set_file_info(directory, filename, frame_number, False, file_template)
            except Exception as exc:
                _log.warning("push_to_detector: failed: %s", exc)

        threading.Thread(target=_push, daemon=True, name="detector-file-push").start()

    def _push_file_number_width(self) -> None:
        cfg = self._model.beamline.active
        det = cfg.active_detector_config if cfg else None
        width = det.file_number_width if det else 4
        self._view.file_settings.set_file_number_width(width)

    def _on_filename_update(self) -> None:
        self._fetch_from_detector(update_filename=True)

    def _on_path_update(self) -> None:
        self._fetch_from_detector(update_directory=True)

    def _on_frame_update(self) -> None:
        self._fetch_from_detector(update_frame=True)

    def _fetch_from_detector(
        self,
        update_directory: bool = False,
        update_filename: bool = False,
        update_frame: bool = False,
    ) -> None:
        cfg = self._model.beamline.active
        det = cfg.active_detector_config if cfg else None
        if det is None or not det.pv_prefix.strip():
            return

        detector = get_detector_model(det.type, det.pv_prefix, det.file_format)

        def _fetch() -> None:
            try:
                directory, filename, file_number = detector.fetch_file_info()
            except Exception as exc:
                _log.warning("sync_from_detector: failed to fetch file info: %s", exc)
                return
            wx.CallAfter(self._apply_detector_file_info, directory, filename, file_number,
                         update_directory, update_filename, update_frame)

        threading.Thread(target=_fetch, daemon=True, name="detector-file-sync").start()

    def _apply_detector_file_info(
        self,
        directory: str,
        filename: str,
        file_number: int,
        update_directory: bool,
        update_filename: bool,
        update_frame: bool,
    ) -> None:
        m = self._model.file_settings
        fs = self._view.file_settings
        cfg = self._model.beamline.active
        det = cfg.active_detector_config if cfg else None
        if update_directory and directory:
            local_dir = det.translate_path_reverse(directory) if det else directory
            path = Path(local_dir)
            m.directory = path
            fs.set_directory(path)
            _log.debug("sync_from_detector: remote_dir=%r local_dir=%r", directory, local_dir)
        if update_filename and filename:
            m.filename = filename
            fs.set_filename(filename)
            _log.debug("sync_from_detector: filename=%r", filename)
        if update_frame:
            m.frame_number = file_number
            fs.set_frame_number(file_number)
            _log.debug("sync_from_detector: frame_number=%d", file_number)

    def _sync_view_from_model(self) -> None:
        m = self._model.file_settings
        fs = self._view.file_settings
        fs.set_filename(m.filename)
        fs.set_directory(m.directory)
        fs.set_frame_number(m.frame_number)
        fs.set_map_ext(m.map_ext)
        fs.set_hdf5(m.use_hdf5)
        fs.set_cbf(m.use_cbf)
        fs.set_tif(m.use_tif)
        fs.set_crysalis(m.use_crysalis)
        fs.set_crysalis_calibration_label(m.crysalis_calibration)
        fs.set_apex(m.use_apex)
        self._sync_format_from_detector()

    def _on_filename_changed(self, value: str) -> None:
        self._model.file_settings.filename = value
        _log.debug("file_settings.filename = %r", value)

    def _on_directory_changed(self, path: Path) -> None:
        self._model.file_settings.directory = path
        _log.debug("file_settings.directory = %s", path)

    def _on_frame_changed(self, value: int) -> None:
        self._model.file_settings.frame_number = value
        _log.debug("file_settings.frame_number = %d", value)

    def _on_frame_reset(self) -> None:
        self._model.file_settings.reset_frame_number()
        self._view.file_settings.set_frame_number(1)
        _log.debug("file_settings.frame_number reset to 1")

    def _on_map_ext_changed(self, value: str) -> None:
        self._model.file_settings.map_ext = value
        _log.debug("file_settings.map_ext = %r", value)

    def _on_hdf5_changed(self, value: bool) -> None:
        self._model.file_settings.use_hdf5 = value
        _log.debug("file_settings.use_hdf5 = %s", value)

    def _on_cbf_changed(self, value: bool) -> None:
        self._model.file_settings.use_cbf = value
        _log.debug("file_settings.use_cbf = %s", value)

    def _on_tif_changed(self, value: bool) -> None:
        self._model.file_settings.use_tif = value
        _log.debug("file_settings.use_tif = %s", value)

    def _on_crysalis_changed(self, value: bool) -> None:
        if value and self._model.file_settings.crysalis_calibration is None:
            self._view.file_settings.set_crysalis(False)
            return
        self._model.file_settings.use_crysalis = value
        _log.debug("file_settings.use_crysalis = %s", value)

    def _on_crysalis_calibration(self, path: Path) -> None:
        self._model.file_settings.crysalis_calibration = path
        self._view.file_settings.set_crysalis_calibration_label(path)
        _log.debug("file_settings.crysalis_calibration = %s", path)

    def _on_apex_changed(self, value: bool) -> None:
        self._model.file_settings.use_apex = value
        _log.debug("file_settings.use_apex = %s", value)

    def _on_apex_calibration(self, path: Path) -> None:
        self._model.file_settings.apex_calibration = path
        self._view.file_settings.set_apex_calibration_label(path)
        _log.debug("file_settings.apex_calibration = %s", path)
