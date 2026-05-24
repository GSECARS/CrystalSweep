#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/collection_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Data model for the collection-points table.  Each CollectionPoint represents one
# row: a user-editable label, a float position per motor shorthand, and a scan type.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from dataclasses import dataclass
from typing import Literal

__all__ = ["CollectionPoint", "CollectionTableModel", "ScanType"]

ScanType = Literal["still", "step", "wide"]
SCAN_TYPES: tuple[ScanType, ...] = ("still", "step", "wide")


@dataclass
class CollectionPoint:
    """A single row in the collection table."""

    label: str
    motor_positions: dict[str, str]
    scan_type: ScanType = "still"
    rotation_start: str = ""
    rotation_end: str = ""
    step: str = ""
    time: str = "1.0000"
    selected: bool = False
    map_group: str = ""
    map_row: int = -1
    map_col: int = -1
    map_motor1: str = ""
    map_motor2: str = ""


class CollectionTableModel:
    """Ordered list of CollectionPoints with add / remove / update operations."""

    def __init__(self) -> None:
        self._points: list[CollectionPoint] = []

    @property
    def points(self) -> list[CollectionPoint]:
        return list(self._points)

    def add_point(self, motor_shorthands: list[str]) -> CollectionPoint:
        """Append a new point with a unique default label and empty motor positions."""
        label = self._unique_label()
        point = CollectionPoint(
            label=label,
            motor_positions={s: "" for s in motor_shorthands},
        )
        self._points.append(point)
        return point

    def remove_point(self, index: int) -> None:
        if 0 <= index < len(self._points):
            del self._points[index]

    def update_label(self, index: int, label: str) -> None:
        if 0 <= index < len(self._points):
            self._points[index].label = label

    def update_motor_position(self, index: int, shorthand: str, value: str) -> None:
        if 0 <= index < len(self._points):
            self._points[index].motor_positions[shorthand] = value

    def update_scan_type(self, index: int, scan_type: ScanType) -> None:
        if 0 <= index < len(self._points):
            self._points[index].scan_type = scan_type

    def update_rotation_start(self, index: int, value: str) -> None:
        if 0 <= index < len(self._points):
            self._points[index].rotation_start = value

    def update_rotation_end(self, index: int, value: str) -> None:
        if 0 <= index < len(self._points):
            self._points[index].rotation_end = value

    def update_step(self, index: int, value: str) -> None:
        if 0 <= index < len(self._points):
            self._points[index].step = value

    def update_time(self, index: int, value: str) -> None:
        if 0 <= index < len(self._points):
            self._points[index].time = value

    def set_selected(self, index: int, selected: bool) -> None:
        if 0 <= index < len(self._points):
            self._points[index].selected = selected

    def set_all_selected(self, selected: bool) -> None:
        for pt in self._points:
            pt.selected = selected

    @property
    def selected_indices(self) -> list[int]:
        return [i for i, pt in enumerate(self._points) if pt.selected]

    def rebuild_motor_columns(self, motor_shorthands: list[str]) -> None:
        """Re-key all rows when the active config changes (preserves matching keys)."""
        for pt in self._points:
            updated: dict[str, str] = {}
            for s in motor_shorthands:
                updated[s] = pt.motor_positions.get(s, "")
            pt.motor_positions = updated

    def _unique_label(self) -> str:
        existing = {p.label for p in self._points}
        n = 1
        while f"pos{n}" in existing:
            n += 1
        return f"pos{n}"
