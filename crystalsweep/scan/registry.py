#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/scan/registry.py
# ----------------------------------------------------------------------------------
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crystalsweep.scan.driver import ScanDriver

__all__ = ["get_driver", "register_driver"]

_log = logging.getLogger(__name__)
_REGISTRY: dict[str, type] = {}


def _ensure_defaults() -> None:
    if _REGISTRY:
        return
    from crystalsweep.scan.step_driver import StepDriver
    from crystalsweep.scan.newport_xps import NewportXPSDriver
    from crystalsweep.scan.aerotech_a1 import AerotechA1Driver

    _REGISTRY["step"] = StepDriver
    _REGISTRY["epics"] = StepDriver
    _REGISTRY["newport_xps"] = NewportXPSDriver
    _REGISTRY["aerotech_a1"] = AerotechA1Driver


def register_driver(name: str, cls: type) -> None:
    _REGISTRY[name] = cls
    _log.debug("Registered scan driver %r -> %s", name, cls.__name__)


def get_driver(controller: str) -> "ScanDriver":
    _ensure_defaults()
    cls = _REGISTRY.get(controller)
    if cls is None:
        _log.warning("Unknown scan controller %r, falling back to StepDriver.", controller)
        from crystalsweep.scan.step_driver import StepDriver
        cls = StepDriver
    return cls()
