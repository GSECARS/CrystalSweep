#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/model/test_epics_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for EpicsModel Channel Access delegation and PV connectivity checks.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from unittest.mock import patch

import pytest

from crystalsweep.model.epics_model import EpicsModel


class TestEpicsModelDefaults:
    """Verify EpicsModel default and custom connect_timeout values."""

    def test_connect_timeout_defaults_to_2(self):
        model = EpicsModel()
        assert model.connect_timeout == pytest.approx(2.0)

    def test_custom_connect_timeout_stored(self):
        model = EpicsModel(connect_timeout=5.0)
        assert model.connect_timeout == pytest.approx(5.0)


class TestEpicsModelCaget:
    """Verify caget() delegates to epics.caget with the configured timeout."""

    def test_delegates_to_epics_caget_with_timeout(self):
        model = EpicsModel(connect_timeout=3.0)
        with patch("crystalsweep.model.epics_model.caget", return_value=42.0) as mock_caget:
            model.caget("TEST:PV")
            mock_caget.assert_called_once_with("TEST:PV", timeout=3.0)

    def test_returns_value_from_epics_caget(self):
        model = EpicsModel()
        with patch("crystalsweep.model.epics_model.caget", return_value=7.5):
            result = model.caget("TEST:PV")
        assert result == pytest.approx(7.5)

    def test_returns_none_when_epics_caget_returns_none(self):
        model = EpicsModel()
        with patch("crystalsweep.model.epics_model.caget", return_value=None):
            result = model.caget("TEST:PV")
        assert result is None


class TestEpicsModelIsOnline:
    """Verify is_online() returns True for any non-None value and False for None."""

    def test_returns_true_for_float_value(self):
        model = EpicsModel()
        with patch("crystalsweep.model.epics_model.caget", return_value=1.0):
            assert model.is_online("TEST:PV") is True

    def test_returns_true_for_zero(self):
        """Zero is a valid PV value and should still indicate the PV is online."""
        model = EpicsModel()
        with patch("crystalsweep.model.epics_model.caget", return_value=0):
            assert model.is_online("TEST:PV") is True

    def test_returns_true_for_string_value(self):
        model = EpicsModel()
        with patch("crystalsweep.model.epics_model.caget", return_value="value"):
            assert model.is_online("TEST:PV") is True

    def test_returns_false_when_caget_returns_none(self):
        model = EpicsModel()
        with patch("crystalsweep.model.epics_model.caget", return_value=None):
            assert model.is_online("TEST:PV") is False
