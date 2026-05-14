#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/controller/collection_table_controller.py
# ----------------------------------------------------------------------------------
# Purpose:
# Controller that bridges CollectionTableModel and CollectionTableView.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging

from crystalsweep.model import BeamlineConfig, MainModel
from crystalsweep.model.collection_model import ScanType
from crystalsweep.ui.view.collection_table_view import CollectionTableView

__all__ = ["CollectionTableController"]

_log = logging.getLogger(__name__)


class CollectionTableController:
    """Wires the collection-points table model and view."""

    def __init__(self, model: MainModel, view: CollectionTableView) -> None:
        self._model = model
        self._view = view

        self._view.bind_add(self._on_add)
        self._view.bind_clear(self._on_clear)
        self._view.bind_delete_selected(self._on_delete_selected)
        self._view.bind_label_changed(self._on_label_changed)
        self._view.bind_motor_changed(self._on_motor_changed)
        self._view.bind_type_changed(self._on_type_changed)
        self._view.bind_rotation_start_changed(self._on_rotation_start_changed)
        self._view.bind_rotation_end_changed(self._on_rotation_end_changed)
        self._view.bind_step_changed(self._on_step_changed)
        self._view.bind_time_changed(self._on_time_changed)
        self._view.bind_selection_changed(self._on_selection_changed)
        self._view.bind_remove(self._on_remove)

        self.refresh_columns()

    def refresh_columns(self) -> None:
        """Rebuild the table columns from the currently active beamline config."""
        shorthands = self._current_shorthands()
        rot_shorthand = self._current_rotation_shorthand()
        precisions = self._current_precisions()
        rot_precision = self._current_rotation_precision()
        self._model.collection.rebuild_motor_columns(shorthands)
        self._view.set_columns(shorthands, rotation_shorthand=rot_shorthand, motor_precisions=precisions, rotation_precision=rot_precision)
        for point in self._model.collection.points:
            self._view.add_row(point)

    def on_config_applied(self, config: BeamlineConfig) -> None:
        """Called by MainController when a new beamline config is applied."""
        shorthands = [m.shorthand for m in config.motors if m.shorthand]
        rot_shorthand = config.rotation_motor.shorthand if config.rotation_motor else ""
        precisions = {m.shorthand: m.precision for m in config.motors if m.shorthand}
        rot_precision = config.rotation_motor.precision if config.rotation_motor else 4
        self._model.collection.rebuild_motor_columns(shorthands)
        self._view.set_columns(shorthands, rotation_shorthand=rot_shorthand, motor_precisions=precisions, rotation_precision=rot_precision)
        for point in self._model.collection.points:
            self._view.add_row(point)

    def _current_shorthands(self) -> list[str]:
        return [m.shorthand for m in self._model.beamline.active.motors if m.shorthand]

    def _current_rotation_shorthand(self) -> str:
        rm = self._model.beamline.active.rotation_motor
        return rm.shorthand if rm else ""

    def _current_precisions(self) -> dict[str, int]:
        return {m.shorthand: m.precision for m in self._model.beamline.active.motors if m.shorthand}

    def _current_rotation_precision(self) -> int:
        rm = self._model.beamline.active.rotation_motor
        return rm.precision if rm else 4

    def _on_add(self) -> None:
        point = self._model.collection.add_point(self._current_shorthands())
        self._view.add_row(point)
        _log.debug("Added collection point: %s", point.label)

    def _on_label_changed(self, index: int, label: str) -> None:
        self._model.collection.update_label(index, label)

    def _on_motor_changed(self, index: int, shorthand: str, value: str) -> None:
        self._model.collection.update_motor_position(index, shorthand, value)

    def _on_type_changed(self, index: int, scan_type: ScanType) -> None:
        self._model.collection.update_scan_type(index, scan_type)

    def _on_rotation_start_changed(self, index: int, value: str) -> None:
        self._model.collection.update_rotation_start(index, value)

    def _on_rotation_end_changed(self, index: int, value: str) -> None:
        self._model.collection.update_rotation_end(index, value)

    def _on_step_changed(self, index: int, value: str) -> None:
        self._model.collection.update_step(index, value)

    def _on_time_changed(self, index: int, value: str) -> None:
        self._model.collection.update_time(index, value)

    def _on_selection_changed(self, index: int, selected: bool) -> None:
        self._model.collection.set_selected(index, selected)

    def _on_remove(self, index: int) -> None:
        self._model.collection.remove_point(index)
        self._view.remove_row(index)
        _log.debug("Removed collection point at index %d", index)

    def _on_clear(self) -> None:
        count = len(self._model.collection.points)
        for _ in range(count):
            self._model.collection.remove_point(0)
            self._view.remove_row(0)
        _log.debug("Cleared all %d collection points", count)

    def _on_delete_selected(self) -> None:
        indices = [i for i, p in enumerate(self._model.collection.points) if p.selected]
        for index in reversed(indices):
            self._model.collection.remove_point(index)
            self._view.remove_row(index)
        _log.debug("Deleted %d selected collection points", len(indices))
