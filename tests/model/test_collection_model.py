#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/model/test_collection_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for CollectionPoint scan parameter parsing and CollectionTableModel CRUD
# operations.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import pytest

from crystalsweep.model.collection_model import (
    CollectionPoint,
    CollectionTableModel,
    StepParams,
    WideParams,
)


class TestCollectionPointParseExposure:
    """Verify parse_exposure() returns a float or None for valid/invalid input."""

    def test_valid_float_returns_float(self):
        p = CollectionPoint(label="p", motor_positions={}, time="2.5")
        assert p.parse_exposure() == pytest.approx(2.5)

    def test_integer_string_returns_float(self):
        p = CollectionPoint(label="p", motor_positions={}, time="1")
        assert p.parse_exposure() == pytest.approx(1.0)

    def test_empty_string_returns_none(self):
        p = CollectionPoint(label="p", motor_positions={}, time="")
        assert p.parse_exposure() is None

    def test_non_numeric_returns_none(self):
        p = CollectionPoint(label="p", motor_positions={}, time="fast")
        assert p.parse_exposure() is None

    def test_default_time_parses(self):
        p = CollectionPoint(label="p", motor_positions={})
        assert p.parse_exposure() == pytest.approx(1.0)

    def test_small_value(self):
        p = CollectionPoint(label="p", motor_positions={}, time="0.01")
        assert p.parse_exposure() == pytest.approx(0.01)


class TestCollectionPointParseStepParams:
    """Verify parse_step_params() validates step scan field combinations."""

    def _pt(self, start="0", end="10", step="1", time="0.5"):
        return CollectionPoint(label="p", motor_positions={}, scan_type="step", rotation_start=start, rotation_end=end, step=step, time=time)

    def test_valid_params_returns_step_params(self):
        result = self._pt().parse_step_params()
        assert isinstance(result, StepParams)

    def test_n_frames_calculated_correctly(self):
        result = self._pt(start="0", end="10", step="1").parse_step_params()
        assert result.n_frames == 10

    def test_n_frames_rounds(self):
        result = self._pt(start="0", end="1", step="0.3").parse_step_params()
        assert result.n_frames == round(1.0 / 0.3)

    def test_n_frames_minimum_one(self):
        result = self._pt(start="0", end="0.0001", step="10").parse_step_params()
        assert result.n_frames >= 1

    def test_negative_range_allowed(self):
        result = self._pt(start="10", end="0", step="1").parse_step_params()
        assert result is not None
        assert result.n_frames == 10

    def test_missing_step_returns_none(self):
        p = CollectionPoint(label="p", motor_positions={}, scan_type="step", rotation_start="0", rotation_end="10", step="", time="0.5")
        assert p.parse_step_params() is None

    def test_missing_rotation_start_returns_none(self):
        p = CollectionPoint(label="p", motor_positions={}, scan_type="step", rotation_start="", rotation_end="10", step="1", time="0.5")
        assert p.parse_step_params() is None

    def test_missing_rotation_end_returns_none(self):
        p = CollectionPoint(label="p", motor_positions={}, scan_type="step", rotation_start="0", rotation_end="", step="1", time="0.5")
        assert p.parse_step_params() is None

    def test_missing_time_returns_none(self):
        p = CollectionPoint(label="p", motor_positions={}, scan_type="step", rotation_start="0", rotation_end="10", step="1", time="")
        assert p.parse_step_params() is None

    def test_start_equals_end_returns_none(self):
        result = self._pt(start="5", end="5").parse_step_params()
        assert result is None

    def test_step_zero_returns_none(self):
        result = self._pt(step="0").parse_step_params()
        assert result is None

    def test_step_negative_returns_none(self):
        result = self._pt(step="-1").parse_step_params()
        assert result is None

    def test_non_numeric_step_returns_none(self):
        result = self._pt(step="fast").parse_step_params()
        assert result is None

    def test_exposure_preserved(self):
        result = self._pt(time="0.25").parse_step_params()
        assert result.exposure == pytest.approx(0.25)

    def test_omega_values_preserved(self):
        result = self._pt(start="-5.0", end="5.0", step="0.5").parse_step_params()
        assert result.omega_start == pytest.approx(-5.0)
        assert result.omega_end == pytest.approx(5.0)
        assert result.step == pytest.approx(0.5)


class TestCollectionPointParseWideParams:
    """Verify parse_wide_params() validates wide scan field combinations."""

    def _pt(self, start="0", end="180", time="1.0"):
        return CollectionPoint(label="p", motor_positions={}, scan_type="wide", rotation_start=start, rotation_end=end, time=time)

    def test_valid_params_returns_wide_params(self):
        result = self._pt().parse_wide_params()
        assert isinstance(result, WideParams)

    def test_exposure_preserved(self):
        result = self._pt(time="0.5").parse_wide_params()
        assert result.exposure == pytest.approx(0.5)

    def test_omega_range_preserved(self):
        result = self._pt(start="-90", end="90").parse_wide_params()
        assert result.omega_start == pytest.approx(-90.0)
        assert result.omega_end == pytest.approx(90.0)

    def test_start_equals_end_returns_none(self):
        result = self._pt(start="10", end="10").parse_wide_params()
        assert result is None

    def test_missing_time_returns_none(self):
        p = CollectionPoint(label="p", motor_positions={}, scan_type="wide", rotation_start="0", rotation_end="10", time="")
        assert p.parse_wide_params() is None

    def test_missing_start_returns_none(self):
        p = CollectionPoint(label="p", motor_positions={}, scan_type="wide", rotation_start="", rotation_end="10", time="1")
        assert p.parse_wide_params() is None

    def test_missing_end_returns_none(self):
        p = CollectionPoint(label="p", motor_positions={}, scan_type="wide", rotation_start="0", rotation_end="", time="1")
        assert p.parse_wide_params() is None

    def test_non_numeric_start_returns_none(self):
        p = CollectionPoint(label="p", motor_positions={}, scan_type="wide", rotation_start="abc", rotation_end="10", time="1")
        assert p.parse_wide_params() is None

    def test_negative_range(self):
        result = self._pt(start="180", end="0").parse_wide_params()
        assert result is not None
        assert result.omega_start == pytest.approx(180.0)
        assert result.omega_end == pytest.approx(0.0)


class TestCollectionTableModelAddPoint:
    """Verify add_point() appends a CollectionPoint with correct defaults and auto-label."""

    def test_adds_point_to_empty_table(self):
        model = CollectionTableModel()
        model.add_point([])
        assert len(model.points) == 1

    def test_returns_new_point(self):
        model = CollectionTableModel()
        point = model.add_point([])
        assert isinstance(point, CollectionPoint)

    def test_point_has_motor_positions_keys(self):
        model = CollectionTableModel()
        point = model.add_point(["x", "y", "z"])
        assert set(point.motor_positions.keys()) == {"x", "y", "z"}

    def test_motor_positions_initially_empty_strings(self):
        model = CollectionTableModel()
        point = model.add_point(["x", "y"])
        assert all(v == "" for v in point.motor_positions.values())

    def test_explicit_label_used(self):
        model = CollectionTableModel()
        point = model.add_point([], label="my_point")
        assert point.label == "my_point"

    def test_auto_label_starts_at_pos1(self):
        model = CollectionTableModel()
        point = model.add_point([])
        assert point.label == "pos1"

    def test_auto_label_increments(self):
        model = CollectionTableModel()
        model.add_point([])
        model.add_point([])
        assert model.points[0].label == "pos1"
        assert model.points[1].label == "pos2"

    def test_auto_label_skips_existing_labels(self):
        model = CollectionTableModel()
        model.add_point([], label="pos1")
        point = model.add_point([])
        assert point.label == "pos2"

    def test_auto_label_handles_gaps(self):
        model = CollectionTableModel()
        model.add_point([], label="pos1")
        model.add_point([], label="pos2")
        model.remove_point(0)
        point = model.add_point([])
        assert point.label == "pos1"


class TestCollectionTableModelRemovePoint:
    """Verify remove_point() deletes by index and ignores out-of-range values."""

    def test_removes_single_point(self):
        model = CollectionTableModel()
        model.add_point([])
        model.add_point([])
        model.remove_point(0)
        assert len(model.points) == 1

    def test_removes_correct_point(self):
        model = CollectionTableModel()
        model.add_point([], label="first")
        model.add_point([], label="second")
        model.remove_point(0)
        assert model.points[0].label == "second"

    def test_out_of_range_index_does_nothing(self):
        model = CollectionTableModel()
        model.add_point([])
        model.remove_point(5)
        assert len(model.points) == 1

    def test_negative_index_does_nothing(self):
        model = CollectionTableModel()
        model.add_point([])
        model.remove_point(-1)
        assert len(model.points) == 1


class TestCollectionTableModelRemovePoints:
    """Verify remove_points() deletes multiple indices in one pass."""

    def test_removes_multiple_at_once(self):
        model = CollectionTableModel()
        for _ in range(5):
            model.add_point([])
        model.remove_points([0, 2, 4])
        assert len(model.points) == 2

    def test_preserves_order_after_removal(self):
        model = CollectionTableModel()
        for i in range(4):
            model.add_point([], label=f"p{i}")
        model.remove_points([1, 3])
        assert model.points[0].label == "p0"
        assert model.points[1].label == "p2"

    def test_empty_list_does_nothing(self):
        model = CollectionTableModel()
        model.add_point([])
        model.remove_points([])
        assert len(model.points) == 1

    def test_out_of_range_indices_ignored(self):
        model = CollectionTableModel()
        model.add_point([])
        model.remove_points([99, -1])
        assert len(model.points) == 1

    def test_duplicate_indices_only_removes_once(self):
        model = CollectionTableModel()
        for _ in range(3):
            model.add_point([])
        model.remove_points([1, 1, 1])
        assert len(model.points) == 2


class TestCollectionTableModelClearPoints:
    """Verify clear_points() empties the table."""

    def test_removes_all_points(self):
        model = CollectionTableModel()
        for _ in range(5):
            model.add_point([])
        model.clear_points()
        assert len(model.points) == 0

    def test_clear_on_empty_does_nothing(self):
        model = CollectionTableModel()
        model.clear_points()
        assert len(model.points) == 0


class TestCollectionTableModelUpdateMethods:
    """Verify individual field updaters mutate the correct point."""

    def test_update_label(self):
        model = CollectionTableModel()
        model.add_point([])
        model.update_label(0, "renamed")
        assert model.points[0].label == "renamed"

    def test_update_label_out_of_range_does_nothing(self):
        model = CollectionTableModel()
        model.update_label(0, "x")

    def test_update_motor_position(self):
        model = CollectionTableModel()
        model.add_point(["x"])
        model.update_motor_position(0, "x", "3.14")
        assert model.points[0].motor_positions["x"] == "3.14"

    def test_update_scan_type(self):
        model = CollectionTableModel()
        model.add_point([])
        model.update_scan_type(0, "step")
        assert model.points[0].scan_type == "step"

    def test_update_rotation_start(self):
        model = CollectionTableModel()
        model.add_point([])
        model.update_rotation_start(0, "-10")
        assert model.points[0].rotation_start == "-10"

    def test_update_rotation_end(self):
        model = CollectionTableModel()
        model.add_point([])
        model.update_rotation_end(0, "10")
        assert model.points[0].rotation_end == "10"

    def test_update_step(self):
        model = CollectionTableModel()
        model.add_point([])
        model.update_step(0, "0.5")
        assert model.points[0].step == "0.5"

    def test_update_time(self):
        model = CollectionTableModel()
        model.add_point([])
        model.update_time(0, "2.0")
        assert model.points[0].time == "2.0"

    def test_set_selected_true(self):
        model = CollectionTableModel()
        model.add_point([])
        model.set_selected(0, True)
        assert model.points[0].selected

    def test_set_selected_false(self):
        model = CollectionTableModel()
        model.add_point([])
        model.set_selected(0, True)
        model.set_selected(0, False)
        assert not model.points[0].selected

    def test_set_all_selected_true(self):
        model = CollectionTableModel()
        for _ in range(3):
            model.add_point([])
        model.set_all_selected(True)
        assert all(p.selected for p in model.points)

    def test_set_all_selected_false(self):
        model = CollectionTableModel()
        for _ in range(3):
            model.add_point([])
        model.set_all_selected(True)
        model.set_all_selected(False)
        assert all(not p.selected for p in model.points)


class TestCollectionTableModelSelectedIndices:
    """Verify selected_indices returns indices of selected points only."""

    def test_empty_table_returns_empty(self):
        assert CollectionTableModel().selected_indices == []

    def test_returns_only_selected_indices(self):
        model = CollectionTableModel()
        for _ in range(4):
            model.add_point([])
        model.set_selected(0, True)
        model.set_selected(2, True)
        assert model.selected_indices == [0, 2]

    def test_all_deselected_returns_empty(self):
        model = CollectionTableModel()
        for _ in range(3):
            model.add_point([])
        assert model.selected_indices == []


class TestCollectionTableModelRebuildMotorColumns:
    """Verify rebuild_motor_columns() re-keys all rows preserving matching values."""

    def test_preserves_existing_values(self):
        model = CollectionTableModel()
        model.add_point(["x", "y"])
        model.update_motor_position(0, "x", "1.5")
        model.rebuild_motor_columns(["x", "z"])
        assert model.points[0].motor_positions.get("x") == "1.5"

    def test_drops_removed_keys(self):
        model = CollectionTableModel()
        model.add_point(["x", "y"])
        model.update_motor_position(0, "y", "2.5")
        model.rebuild_motor_columns(["x"])
        assert "y" not in model.points[0].motor_positions

    def test_adds_new_keys_as_empty(self):
        model = CollectionTableModel()
        model.add_point(["x"])
        model.rebuild_motor_columns(["x", "z"])
        assert model.points[0].motor_positions.get("z") == ""

    def test_applies_to_all_points(self):
        model = CollectionTableModel()
        for _ in range(3):
            model.add_point(["x", "y"])
        model.rebuild_motor_columns(["x", "newmotor"])
        for p in model.points:
            assert "y" not in p.motor_positions
            assert "newmotor" in p.motor_positions


class TestCollectionTableModelPointsProperty:
    """Verify the points property returns a defensive copy."""

    def test_returns_a_copy(self):
        model = CollectionTableModel()
        model.add_point([])
        pts = model.points
        pts.clear()
        assert len(model.points) == 1
