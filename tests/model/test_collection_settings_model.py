#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/model/test_collection_settings_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for CollectionSettingsModel field defaults and mutability.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import pytest

from crystalsweep.model.collection_settings_model import CollectionSettingsModel


class TestCollectionSettingsModelDefaults:
    """Verify all CollectionSettingsModel fields start at their documented defaults."""

    def test_scan_type_is_still(self):
        assert CollectionSettingsModel().scan_type == "still"

    def test_exposure_is_one(self):
        assert CollectionSettingsModel().exposure == pytest.approx(1.0)

    def test_map_is_false(self):
        assert CollectionSettingsModel().map is False

    def test_map_motor_is_empty(self):
        assert CollectionSettingsModel().map_motor == ""

    def test_map_start(self):
        assert CollectionSettingsModel().map_start == pytest.approx(-0.0025)

    def test_map_end(self):
        assert CollectionSettingsModel().map_end == pytest.approx(0.0025)

    def test_map_step(self):
        assert CollectionSettingsModel().map_step == pytest.approx(0.001)

    def test_map_points_is_six(self):
        assert CollectionSettingsModel().map_points == 6

    def test_map2_enabled_is_false(self):
        assert CollectionSettingsModel().map2_enabled is False

    def test_map2_motor_is_empty(self):
        assert CollectionSettingsModel().map2_motor == ""

    def test_map2_start(self):
        assert CollectionSettingsModel().map2_start == pytest.approx(-0.0025)

    def test_map2_end(self):
        assert CollectionSettingsModel().map2_end == pytest.approx(0.0025)

    def test_map2_step(self):
        assert CollectionSettingsModel().map2_step == pytest.approx(0.001)

    def test_map2_points_is_six(self):
        assert CollectionSettingsModel().map2_points == 6

    def test_rotation_start(self):
        assert CollectionSettingsModel().rotation_start == pytest.approx(-10.0)

    def test_rotation_end(self):
        assert CollectionSettingsModel().rotation_end == pytest.approx(10.0)

    def test_rotation_range(self):
        assert CollectionSettingsModel().rotation_range == pytest.approx(20.0)

    def test_step_size_is_one(self):
        assert CollectionSettingsModel().step_size == pytest.approx(1.0)

    def test_rotation_shorthand_is_empty(self):
        assert CollectionSettingsModel().rotation_shorthand == ""

    def test_beam_angle_is_zero(self):
        assert CollectionSettingsModel().beam_angle == pytest.approx(0.0)

    def test_wide_flip_is_true(self):
        assert CollectionSettingsModel().wide_flip is True


class TestCollectionSettingsModelMutability:
    """Verify each field can be reassigned after construction."""

    def test_scan_type_can_be_changed(self):
        m = CollectionSettingsModel()
        m.scan_type = "step"
        assert m.scan_type == "step"

    def test_exposure_can_be_changed(self):
        m = CollectionSettingsModel()
        m.exposure = 2.5
        assert m.exposure == pytest.approx(2.5)

    def test_map_can_be_enabled(self):
        m = CollectionSettingsModel()
        m.map = True
        assert m.map is True

    def test_map_motor_can_be_set(self):
        m = CollectionSettingsModel()
        m.map_motor = "vert"
        assert m.map_motor == "vert"

    def test_rotation_shorthand_can_be_set(self):
        m = CollectionSettingsModel()
        m.rotation_shorthand = "omega"
        assert m.rotation_shorthand == "omega"

    def test_wide_flip_can_be_disabled(self):
        m = CollectionSettingsModel()
        m.wide_flip = False
        assert m.wide_flip is False

    def test_step_size_can_be_changed(self):
        m = CollectionSettingsModel()
        m.step_size = 0.5
        assert m.step_size == pytest.approx(0.5)

    def test_map2_enabled_can_be_set(self):
        m = CollectionSettingsModel()
        m.map2_enabled = True
        assert m.map2_enabled is True


class TestCollectionSettingsModelInstances:
    """Verify separate instances are fully independent (no shared state)."""

    def test_instances_are_independent(self):
        a = CollectionSettingsModel()
        b = CollectionSettingsModel()
        a.exposure = 5.0
        assert b.exposure == pytest.approx(1.0)

    def test_scan_type_mutation_does_not_affect_other_instance(self):
        a = CollectionSettingsModel()
        b = CollectionSettingsModel()
        a.scan_type = "wide"
        assert b.scan_type == "still"
