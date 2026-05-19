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
from pathlib import Path

from crystalsweep.model import MainModel
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
        fs.bind_directory_changed(self._on_directory_changed)
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
        fs.set_apex(m.use_apex)

    def _on_filename_changed(self, value: str) -> None:
        self._model.file_settings.filename = value
        _log.debug("file_settings.filename = %r", value)

    def _on_directory_changed(self, path: Path) -> None:
        self._model.file_settings.directory = path
        _log.debug("file_settings.directory = %s", path)

    def _on_frame_reset(self) -> None:
        self._model.file_settings.reset_frame_number()
        self._view.file_settings.set_frame_number(0)
        _log.debug("file_settings.frame_number reset to 0")

    def _on_frame_update(self, value: int) -> None:
        self._model.file_settings.frame_number = value
        _log.debug("file_settings.frame_number = %d", value)

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
