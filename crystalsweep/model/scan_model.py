#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/scan_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# ScanSpec dataclass, ScanDriver protocol, and the driver registry used to
# resolve a controller type string to its concrete driver implementation.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Protocol, runtime_checkable

if TYPE_CHECKING:
    pass

__all__ = ["ScanDriver", "ScanSpec", "get_driver", "register_driver"]

_log = logging.getLogger(__name__)


@dataclass
class ScanSpec:
    """Everything needed to execute one scan axis."""

    pv: str
    start: float
    end: float
    points: int
    exposure: float
    controller_params: dict = field(default_factory=dict)

    @property
    def step_size(self) -> float:
        if self.points <= 1:
            return 0.0
        return (self.end - self.start) / (self.points - 1)

    def positions(self) -> list[float]:
        if self.points <= 1:
            return [self.start]
        return [self.start + self.step_size * i for i in range(self.points)]


@runtime_checkable
class ScanDriver(Protocol):
    """Common interface every motion controller scan driver must implement."""

    def prepare(self, spec: ScanSpec) -> None: ...
    def run(self, spec: ScanSpec, on_point: Callable[[int, float], None]) -> None: ...
    def abort(self) -> None: ...


_REGISTRY: dict[str, type] = {}


def _ensure_defaults() -> None:
    if _REGISTRY:
        return
    from crystalsweep.model.epics_scan_model import EpicsScanModel
    from crystalsweep.model.newport_xps_model import NewportXPSModel
    from crystalsweep.model.aerotech_a1_model import AerotechA1Model

    _REGISTRY["step"] = EpicsScanModel
    _REGISTRY["epics"] = EpicsScanModel
    _REGISTRY["newport_xps"] = NewportXPSModel
    _REGISTRY["aerotech_a1"] = AerotechA1Model


def register_driver(name: str, cls: type) -> None:
    _REGISTRY[name] = cls
    _log.debug("Registered scan driver %r -> %s", name, cls.__name__)


def get_driver(controller: str) -> ScanDriver:
    _ensure_defaults()
    cls = _REGISTRY.get(controller)
    if cls is None:
        _log.warning("Unknown scan controller %r, falling back to EpicsScanModel.", controller)
        from crystalsweep.model.epics_scan_model import EpicsScanModel
        cls = EpicsScanModel
    return cls()
