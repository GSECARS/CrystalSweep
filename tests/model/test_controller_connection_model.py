#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/model/test_controller_connection_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for ControllerConnectionModel connection lifecycle and driver instantiation
# guards.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from unittest.mock import MagicMock

import pytest

import crystalsweep.model.controller_connection_model as ccm_module
from crystalsweep.model.beamline_config_model import ControllerConfig
from crystalsweep.model.controller_connection_model import ControllerConnectionModel


class TestInit:
    """Verify a fresh model has no stored connections."""

    def test_get_returns_none_for_unknown_name(self):
        model = ControllerConnectionModel()
        assert model.get("anything") is None


class TestDisconnect:
    """Verify _disconnect() calls the connection teardown method and removes the entry."""

    def test_no_connection_stored_no_exception(self):
        model = ControllerConnectionModel()
        model._disconnect("nonexistent")

    def test_connection_with_disconnect_method_calls_it(self):
        model = ControllerConnectionModel()
        conn = MagicMock(spec=["disconnect"])
        model._connections["ctrl"] = conn
        model._disconnect("ctrl")
        conn.disconnect.assert_called_once()

    def test_connection_with_close_but_no_disconnect_calls_close(self):
        """Falls back to close() when disconnect() is not available."""
        model = ControllerConnectionModel()
        conn = MagicMock(spec=["close"])
        model._connections["ctrl"] = conn
        model._disconnect("ctrl")
        conn.close.assert_called_once()

    def test_connection_with_neither_disconnect_nor_close_no_exception(self):
        model = ControllerConnectionModel()
        conn = MagicMock(spec=[])
        model._connections["ctrl"] = conn
        model._disconnect("ctrl")

    def test_connection_removed_from_dict_after_disconnect(self):
        model = ControllerConnectionModel()
        conn = MagicMock(spec=["disconnect"])
        model._connections["ctrl"] = conn
        model._disconnect("ctrl")
        assert "ctrl" not in model._connections
        assert model.get("ctrl") is None


class TestGet:
    """Verify get() returns None for unknown names and the stored object for known ones."""

    def test_returns_none_when_not_connected(self):
        model = ControllerConnectionModel()
        assert model.get("missing") is None

    def test_returns_stored_connection(self):
        model = ControllerConnectionModel()
        fake_conn = object()
        model._connections["myctrl"] = fake_conn
        assert model.get("myctrl") is fake_conn


class TestBuildConnection:
    """Verify _build_connection() raises for unknown types and missing SDK/params."""

    def test_unknown_type_raises_value_error(self):
        model = ControllerConnectionModel()
        cfg = ControllerConfig(name="x", type="unknown_type", params={})
        with pytest.raises(ValueError, match="Unknown controller type"):
            model._build_connection(cfg)

    def test_newport_xps_raises_runtime_error_when_not_installed(self):
        """RuntimeError is raised when the newportxps package is absent."""
        model = ControllerConnectionModel()
        cfg = ControllerConfig(name="xps", type="newport_xps", params={"host": "192.168.1.1"})
        original = ccm_module.NewportXPS
        try:
            ccm_module.NewportXPS = None
            with pytest.raises(RuntimeError, match="newportxps is not installed"):
                model._build_connection(cfg)
        finally:
            ccm_module.NewportXPS = original

    def test_aerotech_a1_raises_runtime_error_when_not_installed(self):
        """RuntimeError is raised when the pyautomation package is absent."""
        model = ControllerConnectionModel()
        cfg = ControllerConfig(
            name="aero",
            type="aerotech_a1",
            params={"ip": "10.0.0.1", "axis_name": "X", "counts_per_unit": "1000"},
        )
        original = ccm_module.PyAutomation
        try:
            ccm_module.PyAutomation = None
            with pytest.raises(RuntimeError, match="pyautomation is not installed"):
                model._build_connection(cfg)
        finally:
            ccm_module.PyAutomation = original

    def test_newport_xps_raises_value_error_when_host_missing(self):
        """ValueError is raised when the required host param is absent from the config."""
        model = ControllerConnectionModel()
        cfg = ControllerConfig(name="xps", type="newport_xps", params={})
        original = ccm_module.NewportXPS
        try:
            ccm_module.NewportXPS = MagicMock()
            with pytest.raises(ValueError, match="host"):
                model._build_connection(cfg)
        finally:
            ccm_module.NewportXPS = original
