#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/model/test_scan_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for ScanSpec position generation, step-size calculation, and the driver
# registry.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import pytest

import crystalsweep.model.scan_model as _scan_model_module
from crystalsweep.model.scan_model import ScanDriver, ScanSpec, get_driver, register_driver


def _clear_registry():
    """Remove all entries from the driver registry for isolation."""
    _scan_model_module._REGISTRY.clear()


class TestScanSpecStepSize:
    """Verify step_size property for various point counts and ranges."""

    def test_two_points_correct_step(self):
        spec = ScanSpec(pv="X", start=0.0, end=10.0, points=2, exposure=1.0)
        assert spec.step_size == pytest.approx(10.0)

    def test_five_points(self):
        spec = ScanSpec(pv="X", start=0.0, end=4.0, points=5, exposure=1.0)
        assert spec.step_size == pytest.approx(1.0)

    def test_single_point_returns_zero(self):
        spec = ScanSpec(pv="X", start=5.0, end=10.0, points=1, exposure=1.0)
        assert spec.step_size == pytest.approx(0.0)

    def test_zero_points_returns_zero(self):
        spec = ScanSpec(pv="X", start=0.0, end=10.0, points=0, exposure=1.0)
        assert spec.step_size == pytest.approx(0.0)

    def test_negative_range(self):
        spec = ScanSpec(pv="X", start=10.0, end=0.0, points=3, exposure=1.0)
        assert spec.step_size == pytest.approx(-5.0)

    def test_fractional_step(self):
        spec = ScanSpec(pv="X", start=-0.5, end=0.5, points=3, exposure=1.0)
        assert spec.step_size == pytest.approx(0.5)

    def test_same_start_end(self):
        spec = ScanSpec(pv="X", start=5.0, end=5.0, points=5, exposure=1.0)
        assert spec.step_size == pytest.approx(0.0)


class TestScanSpecPositions:
    """Verify positions() returns evenly-spaced values matching start and end."""

    def test_single_point_returns_start(self):
        spec = ScanSpec(pv="X", start=3.0, end=10.0, points=1, exposure=1.0)
        assert spec.positions() == [pytest.approx(3.0)]

    def test_two_points(self):
        spec = ScanSpec(pv="X", start=0.0, end=10.0, points=2, exposure=1.0)
        assert spec.positions() == [pytest.approx(0.0), pytest.approx(10.0)]

    def test_five_points_uniform(self):
        spec = ScanSpec(pv="X", start=0.0, end=4.0, points=5, exposure=1.0)
        expected = [0.0, 1.0, 2.0, 3.0, 4.0]
        pos = spec.positions()
        assert len(pos) == 5
        for actual, exp in zip(pos, expected):
            assert actual == pytest.approx(exp)

    def test_negative_range(self):
        spec = ScanSpec(pv="X", start=10.0, end=0.0, points=3, exposure=1.0)
        pos = spec.positions()
        assert pos[0] == pytest.approx(10.0)
        assert pos[-1] == pytest.approx(0.0)
        assert len(pos) == 3

    def test_zero_points_returns_start(self):
        spec = ScanSpec(pv="X", start=5.0, end=10.0, points=0, exposure=1.0)
        assert spec.positions() == [pytest.approx(5.0)]

    def test_count_matches_points(self):
        for n in [1, 3, 7, 10]:
            spec = ScanSpec(pv="X", start=0.0, end=1.0, points=n, exposure=1.0)
            assert len(spec.positions()) == n

    def test_first_position_is_start(self):
        spec = ScanSpec(pv="X", start=2.5, end=7.5, points=4, exposure=1.0)
        assert spec.positions()[0] == pytest.approx(2.5)

    def test_last_position_is_end(self):
        spec = ScanSpec(pv="X", start=2.5, end=7.5, points=4, exposure=1.0)
        pos = spec.positions()
        assert pos[-1] == pytest.approx(7.5)


class TestScanSpecDefaults:
    """Verify ScanSpec default field values."""

    def test_controller_params_default_empty(self):
        spec = ScanSpec(pv="X", start=0.0, end=1.0, points=2, exposure=0.5)
        assert spec.controller_params == {}


class TestRegisterAndGetDriver:
    """Verify register_driver/get_driver round-trip and unknown-name fallback."""

    def setup_method(self):
        _clear_registry()

    def teardown_method(self):
        _clear_registry()

    def test_registered_driver_is_returned(self):
        class FakeDriver:
            def prepare(self, spec):
                pass

            def run(self, spec, on_point, on_at_start=None):
                pass

            def abort(self):
                pass

        register_driver("fake", FakeDriver)
        driver = get_driver("fake")
        assert isinstance(driver, FakeDriver)

    def test_get_driver_returns_instance_not_class(self):
        class FakeDriver:
            def prepare(self, spec):
                pass

            def run(self, spec, on_point, on_at_start=None):
                pass

            def abort(self):
                pass

        register_driver("my_driver", FakeDriver)
        driver = get_driver("my_driver")
        assert not isinstance(driver, type)

    def test_register_overwrites_existing_name(self):
        class DriverA:
            def prepare(self, spec):
                pass

            def run(self, spec, on_point, on_at_start=None):
                pass

            def abort(self):
                pass

        class DriverB:
            def prepare(self, spec):
                pass

            def run(self, spec, on_point, on_at_start=None):
                pass

            def abort(self):
                pass

        register_driver("ctrl", DriverA)
        register_driver("ctrl", DriverB)
        driver = get_driver("ctrl")
        assert isinstance(driver, DriverB)

    def test_unknown_controller_falls_back_to_epics(self):
        from crystalsweep.model.epics_scan_model import EpicsScanModel

        register_driver("step", EpicsScanModel)
        register_driver("epics", EpicsScanModel)
        driver = get_driver("does_not_exist")
        assert isinstance(driver, EpicsScanModel)

    def test_driver_satisfies_scan_driver_protocol(self):
        class MinimalDriver:
            def prepare(self, spec):
                pass

            def run(self, spec, on_point, on_at_start=None):
                pass

            def abort(self):
                pass

        register_driver("minimal", MinimalDriver)
        driver = get_driver("minimal")
        assert isinstance(driver, ScanDriver)


class TestScanDriverProtocol:
    """Verify ScanDriver protocol checks at runtime."""

    def test_class_with_all_methods_is_scan_driver(self):
        class Good:
            def prepare(self, spec):
                pass

            def run(self, spec, on_point, on_at_start=None):
                pass

            def abort(self):
                pass

        assert isinstance(Good(), ScanDriver)

    def test_class_missing_abort_is_not_scan_driver(self):
        class Bad:
            def prepare(self, spec):
                pass

            def run(self, spec, on_point, on_at_start=None):
                pass

        assert not isinstance(Bad(), ScanDriver)

    def test_class_missing_prepare_is_not_scan_driver(self):
        class Bad:
            def run(self, spec, on_point, on_at_start=None):
                pass

            def abort(self):
                pass

        assert not isinstance(Bad(), ScanDriver)
