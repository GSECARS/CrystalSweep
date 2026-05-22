#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/controller_connection_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Manages a single persistent connection per named motion controller for the
# lifetime of the application. Connections are opened (or replaced) when the
# beamline configuration is saved and remain open until the application exits
# or the configuration changes.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crystalsweep.model.beamline_config_model import ControllerConfig

__all__ = ["ControllerConnectionModel"]

_log = logging.getLogger(__name__)

_MISSING_NEWPORT = "newportxps is not installed. Run: pip install newportxps"
_MISSING_AEROTECH = "pyautomation is not installed. Run: pip install pyautomation"

try:
    from newportxps import NewportXPS
except ImportError:
    NewportXPS = None  # type: ignore[assignment,misc]

try:
    from pyautomation import PyAutomation, PsoDistanceInput, PsoOutputPin, PsoWindowInput
    from pyautomation.controller import AutomationAxis
except ImportError:
    PyAutomation = None  # type: ignore[assignment,misc]
    AutomationAxis = None  # type: ignore[assignment,misc]
    PsoDistanceInput = None  # type: ignore[assignment,misc]
    PsoWindowInput = None  # type: ignore[assignment,misc]
    PsoOutputPin = None  # type: ignore[assignment,misc]


class ControllerConnectionModel:
    """Holds one persistent connection object per named controller.

    Call :meth:`apply_config` with the list of :class:`ControllerConfig`
    objects from the active beamline config. Any controller whose name or
    params have changed (or that is new) will be reconnected; controllers
    that have been removed are disconnected.

    All network I/O is performed on a daemon thread so the UI is never
    blocked.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connections: dict[str, object] = {}
        self._params_cache: dict[str, dict] = {}

    def get(self, name: str) -> object | None:
        """Return the live connection object for *name*, or None if not connected."""
        with self._lock:
            return self._connections.get(name)

    def apply_config(self, controllers: tuple[ControllerConfig, ...]) -> None:
        """Reconcile live connections with *controllers* on a background thread."""
        threading.Thread(
            target=self._reconcile,
            args=(controllers,),
            daemon=True,
            name="controller-connect",
        ).start()

    def _reconcile(self, controllers: tuple[ControllerConfig, ...]) -> None:
        wanted_names = {c.name for c in controllers if c.name}

        with self._lock:
            stale = [n for n in list(self._connections) if n not in wanted_names]

        for name in stale:
            self._disconnect(name)

        for cfg in controllers:
            if not cfg.name:
                continue
            cached = self._params_cache.get(cfg.name)
            if cached == cfg.params and cfg.name in self._connections:
                print(f"[controllers] {cfg.name!r}: already connected, skipping.")
                continue
            self._connect(cfg)

    def _connect(self, cfg: ControllerConfig) -> None:
        print(f"[controllers] {cfg.name!r} ({cfg.type}): connecting …")
        try:
            conn = self._build_connection(cfg)
        except Exception as exc:
            print(f"[controllers] {cfg.name!r}: connection FAILED – {exc}")
            _log.exception("Failed to connect controller %r (%s)", cfg.name, cfg.type)
            return

        with self._lock:
            self._connections[cfg.name] = conn
            self._params_cache[cfg.name] = dict(cfg.params)

        print(f"[controllers] {cfg.name!r} ({cfg.type}): connected OK")
        _log.info("Controller %r (%s) connected.", cfg.name, cfg.type)

    def _disconnect(self, name: str) -> None:
        with self._lock:
            conn = self._connections.pop(name, None)
            self._params_cache.pop(name, None)

        if conn is None:
            return

        print(f"[controllers] {name!r}: disconnecting …")
        try:
            if hasattr(conn, "disconnect"):
                conn.disconnect()
            elif hasattr(conn, "close"):
                conn.close()
        except Exception:
            pass
        print(f"[controllers] {name!r}: disconnected")
        _log.info("Controller %r disconnected.", name)

    def _build_connection(self, cfg: ControllerConfig) -> object:
        if cfg.type == "newport_xps":
            return self._connect_newport(cfg)
        if cfg.type == "aerotech_a1":
            return self._connect_aerotech(cfg)
        raise ValueError(f"Unknown controller type {cfg.type!r}")

    def _connect_newport(self, cfg: ControllerConfig) -> object:
        if NewportXPS is None:
            raise RuntimeError(_MISSING_NEWPORT)
        p = cfg.params
        if not p.get("host"):
            raise ValueError("Newport XPS requires 'host' in params.")
        return NewportXPS(
            p["host"],
            username=p.get("username", "Administrator"),
            password=p.get("password", ""),
        )

    def _connect_aerotech(self, cfg: ControllerConfig) -> object:
        if PyAutomation is None:
            raise RuntimeError(_MISSING_AEROTECH)
        p = cfg.params
        for key in ("ip", "axis_name", "counts_per_unit"):
            if not p.get(key):
                raise ValueError(f"Aerotech Automation1 requires '{key}' in params.")
        axis = AutomationAxis(
            name=p["axis_name"],
            counts_per_unit=float(p["counts_per_unit"]),
        )
        automation = PyAutomation(
            ip=p["ip"],
            axis=[axis],
            verbose=bool(p.get("verbose", False)),
            pso_distance_input=getattr(PsoDistanceInput, p.get("pso_distance_input", "iXC4ePrimaryFeedback")),
            pso_window_input=getattr(PsoWindowInput, p.get("pso_window_input", "iXC4ePrimaryFeedback")),
            pso_output_pin=getattr(PsoOutputPin, p.get("pso_output_pin", "iXC4eAuxiliaryMarkerDifferential")),
        )
        automation.enable_controller()
        return automation
