#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/controller/collection_settings_controller.py
# ----------------------------------------------------------------------------------
# Purpose:
# Controller that bridges CollectionSettingsModel, CollectionSettingsView, and the
# CollectionTableModel / CollectionTableView, driving the "add point" action.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging

from crystalsweep.model import MainModel
from crystalsweep.model.collection_model import ScanType
from crystalsweep.ui.view import MainView

__all__ = ["CollectionSettingsController"]

_log = logging.getLogger(__name__)


class CollectionSettingsController:
    """Bridges the collection settings panel to the model and collection table."""

    def __init__(self, model: MainModel, view: MainView) -> None:
        self._model = model
        self._view = view

        cs = self._view.collection_settings
        cs.bind_scan_type_changed(self._on_scan_type_changed)
        cs.bind_exposure_changed(self._on_exposure_changed)
        cs.bind_rotation_start_changed(self._on_rotation_start_changed)
        cs.bind_rotation_end_changed(self._on_rotation_end_changed)
        cs.bind_rotation_range_changed(self._on_rotation_range_changed)
        cs.bind_step_size_changed(self._on_step_size_changed)
        cs.bind_add_point(self._on_add_point)
        cs.bind_update_selected(self._on_update_selected)

        self._sync_rotation_shorthand()

    def on_config_applied(self) -> None:
        """Called when a new beamline config is applied — refresh rotation shorthand."""
        self._sync_rotation_shorthand()

    def _sync_rotation_shorthand(self) -> None:
        rm = self._model.beamline.active.rotation_motor
        shorthand = rm.shorthand if rm else ""
        self._model.collection_settings.rotation_shorthand = shorthand
        self._view.collection_settings.set_rotation_shorthand(shorthand)

    def _on_scan_type_changed(self, scan_type: ScanType) -> None:
        self._model.collection_settings.scan_type = scan_type
        _log.debug("collection_settings.scan_type = %s", scan_type)

    def _on_exposure_changed(self, value: float) -> None:
        self._model.collection_settings.exposure = value
        _log.debug("collection_settings.exposure = %s", value)

    def _on_rotation_start_changed(self, value: float) -> None:
        self._model.collection_settings.rotation_start = value
        _log.debug("collection_settings.rotation_start = %s", value)

    def _on_rotation_end_changed(self, value: float) -> None:
        self._model.collection_settings.rotation_end = value
        _log.debug("collection_settings.rotation_end = %s", value)

    def _on_rotation_range_changed(self, value: float) -> None:
        self._model.collection_settings.rotation_range = value
        _log.debug("collection_settings.rotation_range = %s", value)

    def _on_step_size_changed(self, value: float) -> None:
        self._model.collection_settings.step_size = value
        _log.debug("collection_settings.step_size = %s", value)

    def _on_add_point(self) -> None:
        cs = self._model.collection_settings
        shorthands = [m.shorthand for m in self._model.beamline.active.motors if m.shorthand]
        point = self._model.collection.add_point(shorthands)
        point.scan_type = cs.scan_type
        point.time = str(cs.exposure)
        if cs.scan_type in ("wide", "step"):
            point.rotation_start = str(cs.rotation_start)
            point.rotation_end = str(cs.rotation_end)
        if cs.scan_type == "step":
            point.step = str(cs.step_size)
        self._view.collection_table.add_row(point)
        _log.debug("Added collection point: %s (%s)", point.label, point.scan_type)

    def _on_update_selected(self) -> None:
        cs = self._model.collection_settings
        indices = self._model.collection.selected_indices
        for index in indices:
            self._model.collection.update_scan_type(index, cs.scan_type)
            self._model.collection.update_time(index, str(cs.exposure))
            if cs.scan_type in ("wide", "step"):
                self._model.collection.update_rotation_start(index, str(cs.rotation_start))
                self._model.collection.update_rotation_end(index, str(cs.rotation_end))
            else:
                self._model.collection.update_rotation_start(index, "")
                self._model.collection.update_rotation_end(index, "")
            if cs.scan_type == "step":
                self._model.collection.update_step(index, str(cs.step_size))
            else:
                self._model.collection.update_step(index, "")
            self._view.collection_table.refresh_row(index, self._model.collection.points[index])
        _log.debug("Updated %d selected collection points", len(indices))
