#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/utils/test_limits.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for EPICS soft limit checking and PV monitor subscription management.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------
from unittest import mock


from crystalsweep.utils.limits import check_soft_limits, clear_limit_monitors, subscribe_limit_monitors


class TestCheckSoftLimits:
    """Verify check_soft_limits() returns None within limits and an error string outside them."""

    def _mock_caget(self, llm, hlm):
        def _caget(pv):
            if pv.endswith(".LLM"):
                return llm
            if pv.endswith(".HLM"):
                return hlm
            return None

        return _caget

    def test_position_within_limits_returns_none(self):
        with mock.patch("crystalsweep.utils.limits.caget", side_effect=self._mock_caget(-10.0, 10.0)):
            assert check_soft_limits("MOTOR:POS.VAL", 0.0) is None

    def test_position_at_lower_limit_returns_none(self):
        with mock.patch("crystalsweep.utils.limits.caget", side_effect=self._mock_caget(-5.0, 5.0)):
            assert check_soft_limits("MOTOR:POS", -5.0) is None

    def test_position_at_upper_limit_returns_none(self):
        with mock.patch("crystalsweep.utils.limits.caget", side_effect=self._mock_caget(-5.0, 5.0)):
            assert check_soft_limits("MOTOR:POS", 5.0) is None

    def test_position_below_lower_limit_returns_error(self):
        with mock.patch("crystalsweep.utils.limits.caget", side_effect=self._mock_caget(-5.0, 5.0)):
            result = check_soft_limits("MOTOR:POS", -10.0)
        assert result is not None
        assert "-10" in result or "-10.0" in result
        assert "lower limit" in result

    def test_position_above_upper_limit_returns_error(self):
        with mock.patch("crystalsweep.utils.limits.caget", side_effect=self._mock_caget(-5.0, 5.0)):
            result = check_soft_limits("MOTOR:POS", 99.0)
        assert result is not None
        assert "upper limit" in result

    def test_both_limits_zero_returns_none(self):
        with mock.patch("crystalsweep.utils.limits.caget", side_effect=self._mock_caget(0.0, 0.0)):
            assert check_soft_limits("MOTOR:POS", 1000.0) is None

    def test_caget_returns_none_for_llm_returns_none(self):
        with mock.patch("crystalsweep.utils.limits.caget", side_effect=self._mock_caget(None, 10.0)):
            assert check_soft_limits("MOTOR:POS", 0.0) is None

    def test_caget_returns_none_for_hlm_returns_none(self):
        with mock.patch("crystalsweep.utils.limits.caget", side_effect=self._mock_caget(-10.0, None)):
            assert check_soft_limits("MOTOR:POS", 0.0) is None

    def test_caget_raises_returns_none(self):
        with mock.patch("crystalsweep.utils.limits.caget", side_effect=Exception("timeout")):
            assert check_soft_limits("MOTOR:POS", 0.0) is None

    def test_val_suffix_removed_from_pv(self):
        calls = []

        def _caget(pv):
            calls.append(pv)
            return -10.0 if pv.endswith(".LLM") else 10.0

        with mock.patch("crystalsweep.utils.limits.caget", side_effect=_caget):
            check_soft_limits("MOTOR:POS.VAL", 0.0)

        assert all(".VAL" not in p for p in calls)
        assert any("MOTOR:POS.LLM" == p for p in calls)
        assert any("MOTOR:POS.HLM" == p for p in calls)

    def test_pv_without_val_suffix_works(self):
        with mock.patch("crystalsweep.utils.limits.caget", side_effect=self._mock_caget(-5.0, 5.0)):
            assert check_soft_limits("MOTOR:POS", 0.0) is None

    def test_error_string_contains_pv_name(self):
        with mock.patch("crystalsweep.utils.limits.caget", side_effect=self._mock_caget(-1.0, 1.0)):
            result = check_soft_limits("MOTOR:FOO", -999.0)
        assert "MOTOR:FOO" in result

    def test_non_numeric_limit_returns_none(self):
        with mock.patch("crystalsweep.utils.limits.caget", side_effect=self._mock_caget("bad", 5.0)):
            assert check_soft_limits("MOTOR:POS", 0.0) is None


class TestSubscribeLimitMonitors:
    """Verify subscribe_limit_monitors() registers LLM and HLM PVs for each motor."""

    def test_subscribes_llm_and_hlm_for_each_pv(self):
        calls = []

        def _camonitor(pv, callback=None):
            calls.append(pv)

        with mock.patch("crystalsweep.utils.limits.camonitor", side_effect=_camonitor):
            result = subscribe_limit_monitors(["MOTOR1:POS", "MOTOR2:POS"], callback=lambda **_: None)

        assert "MOTOR1:POS.LLM" in calls
        assert "MOTOR1:POS.HLM" in calls
        assert "MOTOR2:POS.LLM" in calls
        assert "MOTOR2:POS.HLM" in calls
        assert len(result) == 4

    def test_val_suffix_removed_before_subscribing(self):
        calls = []

        def _camonitor(pv, callback=None):
            calls.append(pv)

        with mock.patch("crystalsweep.utils.limits.camonitor", side_effect=_camonitor):
            subscribe_limit_monitors(["MOTOR:POS.VAL"], callback=lambda **_: None)

        assert "MOTOR:POS.LLM" in calls
        assert "MOTOR:POS.HLM" in calls
        assert not any(".VAL" in p for p in calls)

    def test_returns_empty_list_for_empty_input(self):
        with mock.patch("crystalsweep.utils.limits.camonitor"):
            result = subscribe_limit_monitors([], callback=lambda **_: None)
        assert result == []

    def test_failed_subscribe_silently_skipped(self):
        def _camonitor(pv, callback=None):
            raise RuntimeError("connection failed")

        with mock.patch("crystalsweep.utils.limits.camonitor", side_effect=_camonitor):
            result = subscribe_limit_monitors(["MOTOR:POS"], callback=lambda **_: None)
        assert result == []

    def test_returned_list_contains_monitored_pvs(self):
        with mock.patch("crystalsweep.utils.limits.camonitor"):
            result = subscribe_limit_monitors(["X:M"], callback=lambda **_: None)
        assert "X:M.LLM" in result
        assert "X:M.HLM" in result


class TestClearLimitMonitors:
    """Verify clear_limit_monitors() unsubscribes each monitored PV."""

    def test_clears_each_monitored_pv(self):
        calls = []

        def _clear(pv):
            calls.append(pv)

        pvs = ["MOTOR:POS.LLM", "MOTOR:POS.HLM"]
        with mock.patch("crystalsweep.utils.limits.camonitor_clear", side_effect=_clear):
            clear_limit_monitors(pvs)

        assert calls == pvs

    def test_empty_list_does_nothing(self):
        with mock.patch("crystalsweep.utils.limits.camonitor_clear") as m:
            clear_limit_monitors([])
        m.assert_not_called()

    def test_failed_clear_silently_suppressed(self):
        def _clear(pv):
            raise RuntimeError("cannot clear")

        with mock.patch("crystalsweep.utils.limits.camonitor_clear", side_effect=_clear):
            clear_limit_monitors(["MOTOR:POS.LLM"])
