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
import uuid

import wx

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
        self._desc_to_shorthand: dict[str, str] = {}
        self._shorthand_to_desc: dict[str, str] = {}
        self._on_points_changed: list = []

        cs = self._view.collection_settings
        cs.bind_scan_type_changed(self._on_scan_type_changed)
        cs.bind_exposure_changed(self._on_exposure_changed)
        cs.bind_map_changed(self._on_map_changed)
        cs.bind_map_motor_changed(self._on_map_motor_changed)
        cs.bind_map_start_changed(self._on_map_start_changed)
        cs.bind_map_end_changed(self._on_map_end_changed)
        cs.bind_map_step_changed(self._on_map_step_changed)
        cs.bind_map_points_changed(self._on_map_points_changed)
        cs.bind_map2_enabled_changed(self._on_map2_enabled_changed)
        cs.bind_map2_motor_changed(self._on_map2_motor_changed)
        cs.bind_map2_start_changed(self._on_map2_start_changed)
        cs.bind_map2_end_changed(self._on_map2_end_changed)
        cs.bind_map2_step_changed(self._on_map2_step_changed)
        cs.bind_map2_points_changed(self._on_map2_points_changed)
        cs.bind_rotation_start_changed(self._on_rotation_start_changed)
        cs.bind_rotation_end_changed(self._on_rotation_end_changed)
        cs.bind_rotation_range_changed(self._on_rotation_range_changed)
        cs.bind_step_size_changed(self._on_step_size_changed)
        cs.bind_wide_flip_changed(self._on_wide_flip_changed)
        cs.bind_add_point(self._on_add_point)
        cs.bind_update_selected(self._on_update_selected)

        self._sync_rotation_shorthand()
        self._sync_map_motors()
        self._sync_view_from_model()

    def _sync_view_from_model(self) -> None:
        cs = self._model.collection_settings
        v = self._view.collection_settings
        v.set_scan_type(cs.scan_type)
        v.set_exposure(cs.exposure)
        v.set_rotation_start(cs.rotation_start)
        v.set_rotation_end(cs.rotation_end)
        v.set_rotation_range(cs.rotation_range)
        v.set_step_size(cs.step_size)
        v.set_wide_flip(cs.wide_flip)

    def add_points_changed_listener(self, callback) -> None:
        self._on_points_changed.append(callback)

    def _notify_points_changed(self) -> None:
        for cb in self._on_points_changed:
            cb()

    def on_config_applied(self) -> None:
        """Called when a new beamline config is applied — refresh rotation shorthand and map motors."""
        self._sync_rotation_shorthand()
        self._sync_map_motors()

    def _sync_rotation_shorthand(self) -> None:
        rm = self._model.beamline.active.rotation_motor
        shorthand = rm.shorthand if rm else ""
        self._model.collection_settings.rotation_shorthand = shorthand
        self._view.collection_settings.set_rotation_shorthand(shorthand)
        beam_angle = rm.beam_angle if rm else 0.0
        self._model.collection_settings.beam_angle = beam_angle

    def _sync_map_motors(self) -> None:
        cfg = self._model.beamline.active
        rm_shorthand = cfg.rotation_motor.shorthand if cfg.rotation_motor else ""
        mapping_motors = [m for m in cfg.motors if m.shorthand != rm_shorthand and m.mapping_enabled]
        self._desc_to_shorthand = {m.description: m.shorthand for m in mapping_motors}
        self._shorthand_to_desc = {m.shorthand: m.description for m in mapping_motors}
        descriptions = [m.description for m in mapping_motors]
        self._view.collection_settings.set_map_motors(descriptions)
        cs = self._model.collection_settings
        if descriptions:
            if cs.map_motor not in self._shorthand_to_desc:
                cs.map_motor = mapping_motors[0].shorthand
            self._view.collection_settings.set_map_motor(self._shorthand_to_desc.get(cs.map_motor, ""))
            map2_descs = [d for d in descriptions if d != self._shorthand_to_desc.get(cs.map_motor, "")]
            map2_shorthands = [self._desc_to_shorthand[d] for d in map2_descs]
            if cs.map2_motor not in map2_shorthands and map2_shorthands:
                cs.map2_motor = map2_shorthands[0]
            self._view.collection_settings.set_map2_motor(self._shorthand_to_desc.get(cs.map2_motor, ""))

    def _on_scan_type_changed(self, scan_type: ScanType) -> None:
        self._model.collection_settings.scan_type = scan_type
        self._apply_type_defaults(scan_type)
        self._sync_trajectory_toggle()
        _log.debug("collection_settings.scan_type = %s", scan_type)

    def _sync_trajectory_toggle(self) -> None:
        cs = self._model.collection_settings
        self._view.collection_table.set_trajectory_visible(cs.scan_type == "still" and cs.map)

    def _apply_type_defaults(self, scan_type: ScanType) -> None:
        cs = self._model.collection_settings
        if scan_type == "still":
            cs.exposure = 1.0
            self._view.collection_settings.set_exposure(1.0)
        elif scan_type == "wide":
            cs.exposure = 20.0
            cs.rotation_range = 20.0
            cs.rotation_start = -10.0
            cs.rotation_end = 10.0
            self._view.collection_settings.set_exposure(20.0)
            self._view.collection_settings.set_rotation_range(20.0)
            self._view.collection_settings.set_rotation_start(-10.0)
            self._view.collection_settings.set_rotation_end(10.0)
        elif scan_type == "step":
            cs.exposure = 1.0
            cs.rotation_range = 70.0
            cs.rotation_start = -35.0
            cs.rotation_end = 35.0
            cs.step_size = 0.5
            self._view.collection_settings.set_exposure(1.0)
            self._view.collection_settings.set_rotation_range(70.0)
            self._view.collection_settings.set_rotation_start(-35.0)
            self._view.collection_settings.set_rotation_end(35.0)
            self._view.collection_settings.set_step_size(0.5)

    def _on_exposure_changed(self, value: float) -> None:
        self._model.collection_settings.exposure = value
        _log.debug("collection_settings.exposure = %s", value)

    def _on_map_changed(self, value: bool) -> None:
        self._model.collection_settings.map = value
        self._sync_trajectory_toggle()
        _log.debug("collection_settings.map = %s", value)

    def _on_map_motor_changed(self, value: str) -> None:
        self._model.collection_settings.map_motor = self._desc_to_shorthand.get(value, value)
        _log.debug("collection_settings.map_motor = %r", self._model.collection_settings.map_motor)

    def _on_map_start_changed(self, value: float) -> None:
        self._model.collection_settings.map_start = value
        _log.debug("collection_settings.map_start = %s", value)

    def _on_map_end_changed(self, value: float) -> None:
        self._model.collection_settings.map_end = value
        _log.debug("collection_settings.map_end = %s", value)

    def _on_map_step_changed(self, value: float) -> None:
        self._model.collection_settings.map_step = value
        _log.debug("collection_settings.map_step = %s", value)

    def _on_map_points_changed(self, value: int) -> None:
        self._model.collection_settings.map_points = value
        _log.debug("collection_settings.map_points = %d", value)

    def _on_map2_enabled_changed(self, value: bool) -> None:
        self._model.collection_settings.map2_enabled = value
        _log.debug("collection_settings.map2_enabled = %s", value)

    def _on_map2_motor_changed(self, value: str) -> None:
        self._model.collection_settings.map2_motor = self._desc_to_shorthand.get(value, value)
        _log.debug("collection_settings.map2_motor = %r", self._model.collection_settings.map2_motor)

    def _on_map2_start_changed(self, value: float) -> None:
        self._model.collection_settings.map2_start = value
        _log.debug("collection_settings.map2_start = %s", value)

    def _on_map2_end_changed(self, value: float) -> None:
        self._model.collection_settings.map2_end = value
        _log.debug("collection_settings.map2_end = %s", value)

    def _on_map2_step_changed(self, value: float) -> None:
        self._model.collection_settings.map2_step = value
        _log.debug("collection_settings.map2_step = %s", value)

    def _on_map2_points_changed(self, value: int) -> None:
        self._model.collection_settings.map2_points = value
        _log.debug("collection_settings.map2_points = %d", value)

    def _on_wide_flip_changed(self, value: bool) -> None:
        self._model.collection_settings.wide_flip = value
        _log.debug("collection_settings.wide_flip = %s", value)

    def _on_rotation_start_changed(self, value: float) -> None:
        cs = self._model.collection_settings
        cs.rotation_start = value
        new_range = abs(cs.rotation_end - value)
        cs.rotation_range = new_range
        self._view.collection_settings.set_rotation_range(new_range)
        _log.debug("collection_settings.rotation_start = %s  range = %s", value, new_range)

    def _on_rotation_end_changed(self, value: float) -> None:
        cs = self._model.collection_settings
        cs.rotation_end = value
        new_range = abs(value - cs.rotation_start)
        cs.rotation_range = new_range
        self._view.collection_settings.set_rotation_range(new_range)
        _log.debug("collection_settings.rotation_end = %s  range = %s", value, new_range)

    def _on_rotation_range_changed(self, value: float) -> None:
        cs = self._model.collection_settings
        cs.rotation_range = value
        half = value / 2.0
        cs.rotation_start = -half
        cs.rotation_end = half
        self._view.collection_settings.set_rotation_start(-half)
        self._view.collection_settings.set_rotation_end(half)
        _log.debug("collection_settings.rotation_range = %s  start = %s  end = %s", value, -half, half)

    def _on_step_size_changed(self, value: float) -> None:
        self._model.collection_settings.step_size = value
        _log.debug("collection_settings.step_size = %s", value)

    def _on_add_point(self) -> None:
        cs = self._model.collection_settings
        if cs.map:
            self._on_add_map_points()
            return
        motors = [m for m in self._model.beamline.active.motors if m.shorthand]
        shorthands = [m.shorthand for m in motors]
        point = self._model.collection.add_point(shorthands)
        point.selected = True
        point.scan_type = cs.scan_type
        point.time = str(cs.exposure)
        if cs.scan_type in ("wide", "step"):
            point.rotation_start = str(cs.rotation_start + cs.beam_angle)
            point.rotation_end = str(cs.rotation_end + cs.beam_angle)
        if cs.scan_type == "step":
            point.step = str(cs.step_size)
        for motor in motors:
            raw = self._model.epics.caget(motor.pv)
            if raw is not None:
                try:
                    point.motor_positions[motor.shorthand] = f"{float(raw):.{motor.precision}f}"
                except (ValueError, TypeError):
                    pass
        self._view.collection_table.add_row(point)
        self._notify_points_changed()
        _log.debug("Added collection point: %s (%s)", point.label, point.scan_type)

    def _on_add_map_points(self) -> None:
        cs = self._model.collection_settings
        motors = [m for m in self._model.beamline.active.motors if m.shorthand]
        shorthands = [m.shorthand for m in motors]

        def axis_positions(start: float, end: float, n: int) -> list[float]:
            if n <= 1:
                return [start]
            return [start + (end - start) * i / (n - 1) for i in range(n)]

        def current_pos(motor_cfg) -> float:
            if motor_cfg is None:
                return 0.0
            raw = self._model.epics.caget(motor_cfg.pv)
            try:
                return float(raw) if raw is not None else 0.0
            except (ValueError, TypeError):
                return 0.0

        motor1_cfg = next((m for m in motors if m.shorthand == cs.map_motor), None)
        motor2_cfg = next((m for m in motors if m.shorthand == cs.map2_motor), None) if cs.map2_enabled else None

        origin1 = current_pos(motor1_cfg)
        origin2 = current_pos(motor2_cfg) if cs.map2_enabled else 0.0

        prec1 = motor1_cfg.precision if motor1_cfg else 4
        prec2 = motor2_cfg.precision if motor2_cfg else 4

        axis1 = [origin1 + p for p in axis_positions(cs.map_start, cs.map_end, cs.map_points)]
        axis2 = [origin2 + p for p in axis_positions(cs.map2_start, cs.map2_end, cs.map2_points)] if cs.map2_enabled else [None]

        group_id = str(uuid.uuid4())
        point_index = 0
        for row_idx, pos2 in enumerate(axis2):
            for col_idx, pos1 in enumerate(axis1):
                point = self._model.collection.add_point(shorthands)
                point.selected = True
                point.scan_type = cs.scan_type
                point.time = str(cs.exposure)
                if cs.scan_type in ("wide", "step"):
                    rot_start = cs.rotation_start + cs.beam_angle
                    rot_end = cs.rotation_end + cs.beam_angle
                    if cs.scan_type == "wide" and cs.wide_flip and point_index % 2 == 1:
                        rot_start, rot_end = rot_end, rot_start
                    point.rotation_start = str(rot_start)
                    point.rotation_end = str(rot_end)
                if cs.scan_type == "step":
                    point.step = str(cs.step_size)
                for motor in motors:
                    raw = self._model.epics.caget(motor.pv)
                    if raw is not None:
                        try:
                            point.motor_positions[motor.shorthand] = f"{float(raw):.{motor.precision}f}"
                        except (ValueError, TypeError):
                            pass
                if cs.map_motor in point.motor_positions:
                    point.motor_positions[cs.map_motor] = f"{pos1:.{prec1}f}"
                if pos2 is not None and motor2_cfg and cs.map2_motor in point.motor_positions:
                    point.motor_positions[cs.map2_motor] = f"{pos2:.{prec2}f}"
                point.map_group = group_id
                point.map_row = row_idx
                point.map_col = col_idx
                point.map_motor1 = cs.map_motor
                point.map_motor2 = cs.map2_motor if cs.map2_enabled else ""
                self._view.collection_table.add_row(point)
                point_index += 1

        n_total = cs.map_points * (cs.map2_points if cs.map2_enabled else 1)
        wx.CallAfter(self._notify_points_changed)
        _log.debug("Added %d map collection points (origin1=%.4f, origin2=%.4f)", n_total, origin1, origin2)

    def _on_update_selected(self) -> None:
        cs = self._model.collection_settings
        indices = self._model.collection.selected_indices
        for index in indices:
            self._model.collection.update_scan_type(index, cs.scan_type)
            self._model.collection.update_time(index, str(cs.exposure))
            if cs.scan_type in ("wide", "step"):
                self._model.collection.update_rotation_start(index, str(cs.rotation_start + cs.beam_angle))
                self._model.collection.update_rotation_end(index, str(cs.rotation_end + cs.beam_angle))
            else:
                self._model.collection.update_rotation_start(index, "")
                self._model.collection.update_rotation_end(index, "")
            if cs.scan_type == "step":
                self._model.collection.update_step(index, str(cs.step_size))
            else:
                self._model.collection.update_step(index, "")
            self._view.collection_table.refresh_row(index, self._model.collection.points[index])
        self._notify_points_changed()
        _log.debug("Updated %d selected collection points", len(indices))
