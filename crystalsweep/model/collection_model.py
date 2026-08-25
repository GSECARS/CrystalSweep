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
from typing import Literal, NamedTuple

__all__ = ["CollectionPoint", "CollectionTableModel", "ScanType", "StepParams", "WideParams"]

ScanType = Literal["still", "step", "wide"]
SCAN_TYPES: tuple[ScanType, ...] = ("still", "wide", "step")


class StepParams(NamedTuple):
    exposure: float
    step: float
    omega_start: float
    omega_end: float
    n_frames: int


class WideParams(NamedTuple):
    exposure: float
    omega_start: float
    omega_end: float


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
    map_row_shift: float = 0.0

    def parse_exposure(self) -> float | None:
        """Return exposure time in seconds. Returns None if missing or invalid."""
        if not self.time:
            return None
        try:
            return float(self.time)
        except ValueError:
            return None

    def parse_step_params(self) -> StepParams | None:
        """Parse step scan parameters. Returns None if any value is missing or invalid."""
        if not self.step or not self.time or not self.rotation_start or not self.rotation_end:
            return None
        try:
            exposure = float(self.time)
            step = float(self.step)
            omega_start = float(self.rotation_start)
            omega_end = float(self.rotation_end)
        except (ValueError, ZeroDivisionError):
            return None
        if step <= 0 or omega_start == omega_end:
            return None
        n_frames = max(1, round(abs(omega_end - omega_start) / step))
        return StepParams(
            exposure=exposure,
            step=step,
            omega_start=omega_start,
            omega_end=omega_end,
            n_frames=n_frames,
        )

    def parse_wide_params(self) -> WideParams | None:
        """Parse wide scan parameters. Returns None if any value is missing or invalid."""
        if not self.time or not self.rotation_start or not self.rotation_end:
            return None
        try:
            exposure = float(self.time)
            omega_start = float(self.rotation_start)
            omega_end = float(self.rotation_end)
        except ValueError:
            return None
        if omega_start == omega_end:
            return None
        return WideParams(
            exposure=exposure,
            omega_start=omega_start,
            omega_end=omega_end,
        )


class CollectionTableModel:
    """Ordered list of CollectionPoints with add / remove / update operations."""

    def __init__(self) -> None:
        self._points: list[CollectionPoint] = []

    @property
    def points(self) -> list[CollectionPoint]:
        return list(self._points)

    def add_point(self, motor_shorthands: list[str], label: str | None = None) -> CollectionPoint:
        """Append a new point with empty motor positions."""
        if label is None:
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

    def remove_points(self, indices: list[int]) -> None:
        """Remove multiple points by index in a single pass."""
        if not indices:
            return
        drop = {i for i in indices if 0 <= i < len(self._points)}
        if not drop:
            return
        self._points = [p for i, p in enumerate(self._points) if i not in drop]

    def clear_points(self) -> None:
        """Remove all points."""
        self._points.clear()

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
