#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/model/test_epics_scan_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for EpicsScanModel parameter validation, wide-slew velocity management,
# and step-loop execution.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from unittest import mock

import pytest

from crystalsweep.model.epics_scan_model import EpicsScanModel
from crystalsweep.model.scan_model import ScanSpec


def _spec(**kwargs) -> ScanSpec:
    defaults = dict(pv="TEST:MOTOR", start=0.0, end=10.0, points=5, exposure=1.0)
    defaults.update(kwargs)
    return ScanSpec(**defaults)


def _still_spec(**kwargs) -> ScanSpec:
    defaults = dict(pv="TEST:MOTOR", start=5.0, end=5.0, points=1, exposure=1.0)
    defaults.update(kwargs)
    return ScanSpec(**defaults)


def _wide_spec(**kwargs) -> ScanSpec:
    defaults = dict(pv="TEST:MOTOR", start=0.0, end=10.0, points=1, exposure=2.0)
    defaults.update(kwargs)
    return ScanSpec(**defaults)


class TestEpicsScanModelPrepare:
    """Verify prepare() raises ValueError for invalid specs and resets wide-slew state."""

    def test_raises_value_error_for_empty_pv(self):
        model = EpicsScanModel()
        with pytest.raises(ValueError, match="PV"):
            model.prepare(_spec(pv=""))

    def test_raises_value_error_for_zero_points(self):
        model = EpicsScanModel()
        with pytest.raises(ValueError, match="points"):
            model.prepare(_spec(points=0))

    def test_raises_value_error_for_zero_exposure(self):
        model = EpicsScanModel()
        with pytest.raises(ValueError, match="exposure"):
            model.prepare(_spec(exposure=0.0))

    def test_raises_value_error_for_negative_exposure(self):
        model = EpicsScanModel()
        with pytest.raises(ValueError, match="exposure"):
            model.prepare(_spec(exposure=-1.0))

    def test_succeeds_for_valid_still_point_spec(self):
        model = EpicsScanModel()
        with mock.patch("crystalsweep.model.epics_scan_model.caget"), mock.patch("crystalsweep.model.epics_scan_model.caput"):
            model.prepare(_still_spec())

    def test_resets_wide_velo_pv_on_each_call(self):
        """Stale wide-slew state from a previous prepare() is cleared before the new one."""
        model = EpicsScanModel()
        model._wide_velo_pv = "TEST:MOTOR.VELO"
        model._wide_saved_velocity = 5.0
        with mock.patch("crystalsweep.model.epics_scan_model.caget"), mock.patch("crystalsweep.model.epics_scan_model.caput"):
            model.prepare(_still_spec())
        assert model._wide_velo_pv is None
        assert model._wide_saved_velocity is None

    def test_resets_wide_state_even_when_no_prior_wide_slew(self):
        model = EpicsScanModel()
        with mock.patch("crystalsweep.model.epics_scan_model.caget"), mock.patch("crystalsweep.model.epics_scan_model.caput"):
            model.prepare(_spec())
        assert model._wide_velo_pv is None
        assert model._wide_saved_velocity is None

    def test_wide_slew_calls_caput_with_velo_pv(self):
        """prepare() writes the computed slew velocity to the motor VELO PV."""
        model = EpicsScanModel()
        with mock.patch("crystalsweep.model.epics_scan_model.caget", return_value=1.0), mock.patch("crystalsweep.model.epics_scan_model.caput") as mock_caput:
            model.prepare(_wide_spec(pv="TEST:MOTOR", start=0.0, end=10.0, exposure=2.0))
            mock_caput.assert_called_once_with("TEST:MOTOR.VELO", pytest.approx(5.0), wait=True)


class TestEpicsScanModelAbort:
    """Verify abort() sets the abort flag and restores any saved wide velocity."""

    def test_sets_abort_flag(self):
        model = EpicsScanModel()
        model.abort()
        assert model._abort is True

    def test_restores_saved_wide_velocity_on_abort(self):
        """When a wide-slew velocity was saved, abort() writes it back to the PV."""
        model = EpicsScanModel()
        model._wide_velo_pv = "TEST:MOTOR.VELO"
        model._wide_saved_velocity = 3.5
        with mock.patch("crystalsweep.model.epics_scan_model.caput") as mock_caput:
            model.abort()
            mock_caput.assert_called_once_with("TEST:MOTOR.VELO", 3.5, wait=True)

    def test_abort_clears_wide_state_after_restore(self):
        model = EpicsScanModel()
        model._wide_velo_pv = "TEST:MOTOR.VELO"
        model._wide_saved_velocity = 2.0
        with mock.patch("crystalsweep.model.epics_scan_model.caput"):
            model.abort()
        assert model._wide_velo_pv is None
        assert model._wide_saved_velocity is None

    def test_abort_without_saved_velocity_does_not_call_caput(self):
        model = EpicsScanModel()
        with mock.patch("crystalsweep.model.epics_scan_model.caput") as mock_caput:
            model.abort()
            mock_caput.assert_not_called()


class TestEpicsScanModelRun:
    """Verify run() calls on_at_start and on_point correctly, and honours abort."""

    def test_calls_on_at_start_once(self):
        model = EpicsScanModel()
        on_at_start = mock.Mock()
        on_point = mock.Mock()
        spec = _spec(points=3)
        with mock.patch("crystalsweep.model.epics_scan_model.caput"), mock.patch("crystalsweep.model.epics_scan_model.time"):
            model.run(spec, on_point, on_at_start)
        on_at_start.assert_called_once()

    def test_calls_on_point_for_each_position(self):
        model = EpicsScanModel()
        on_point = mock.Mock()
        spec = _spec(points=4)
        with mock.patch("crystalsweep.model.epics_scan_model.caput"), mock.patch("crystalsweep.model.epics_scan_model.time"):
            model.run(spec, on_point)
        assert on_point.call_count == 4

    def test_stops_early_when_abort_set_during_run(self):
        """Setting _abort mid-run causes the loop to exit before all points are visited."""
        model = EpicsScanModel()
        on_point = mock.Mock()
        spec = _spec(points=5)
        call_count = []

        def _side_effect(pv, pos, wait=False):
            call_count.append(1)
            if len(call_count) >= 1:
                model._abort = True

        with mock.patch("crystalsweep.model.epics_scan_model.caput", side_effect=_side_effect), mock.patch("crystalsweep.model.epics_scan_model.time"):
            model.run(spec, on_point)

        assert on_point.call_count < 5

    def test_run_without_on_at_start_does_not_raise(self):
        model = EpicsScanModel()
        on_point = mock.Mock()
        spec = _spec(points=2)
        with mock.patch("crystalsweep.model.epics_scan_model.caput"), mock.patch("crystalsweep.model.epics_scan_model.time"):
            model.run(spec, on_point)

    def test_on_point_called_once_when_abort_set_during_first_caput(self):
        """Abort signalled on the very first caput still allows the first on_point callback."""
        model = EpicsScanModel()
        on_point = mock.Mock()
        spec = _spec(points=3)

        def _abort_immediately(pv, pos, wait=False):
            model._abort = True

        with mock.patch("crystalsweep.model.epics_scan_model.caput", side_effect=_abort_immediately), mock.patch("crystalsweep.model.epics_scan_model.time"):
            model.run(spec, on_point)

        assert on_point.call_count == 1
