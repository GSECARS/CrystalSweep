#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/detector_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Protocol and concrete implementations for area detector models.
# Each model knows how to perform detector-specific acquisition sequences
# using EPICS PVs derived from a common prefix.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from __future__ import annotations

import logging
import time
from typing import Protocol, runtime_checkable

from epics import caput

__all__ = ["DetectorModel", "ADEigerModel", "ADPilatusModel", "ADSpinnakerModel", "get_detector_model"]

_log = logging.getLogger(__name__)


@runtime_checkable
class DetectorModel(Protocol):
    """Protocol for area detector models."""

    def collect_still(self, exposure: float) -> None:
        """Arm the detector, trigger one frame, and block until complete."""
        ...


class ADEigerModel:
    """Detector model for Dectris Eiger detectors via EPICS areaDetector."""

    def __init__(self, pv_prefix: str) -> None:
        prefix = pv_prefix.strip()
        if not prefix.endswith(":"):
            prefix += ":"
        self._prefix = prefix

    def collect_still(self, exposure: float) -> None:
        p = self._prefix
        acq_time = max(0.001, exposure * 0.99 - 0.001)

        caput(f"{p}cam1:TriggerMode", 0, wait=True)
        caput(f"{p}cam1:AcquirePeriod", acq_time, wait=True)
        caput(f"{p}cam1:AcquireTime", acq_time, wait=True)
        caput(f"{p}cam1:NumImages", 1, wait=True)
        caput(f"{p}HDF1:NumCapture", 1)
        caput(f"{p}HDF1:Capture", 1)
        time.sleep(0.2)
        caput(f"{p}cam1:Acquire", 1, wait=True, timeout=300)

        print(f"[detector] Eiger {p}: still done (exposure={exposure:.4f}s)")
        _log.debug("ADEigerModel still: %s exposure=%.4f done", p, exposure)


class ADPilatusModel:
    """Detector model for Dectris Pilatus detectors via EPICS areaDetector."""

    def __init__(self, pv_prefix: str) -> None:
        prefix = pv_prefix.strip()
        if not prefix.endswith(":"):
            prefix += ":"
        self._prefix = prefix

    def collect_still(self, exposure: float) -> None:
        p = self._prefix
        acq_time = max(0.001, exposure)

        caput(f"{p}cam1:TriggerMode", 0, wait=True)
        caput(f"{p}cam1:AcquireTime", acq_time, wait=True)
        caput(f"{p}cam1:NumImages", 1, wait=True)
        caput(f"{p}HDF1:NumCapture", 1)
        caput(f"{p}HDF1:Capture", 1)
        caput(f"{p}cam1:Acquire", 1, wait=True, timeout=300)

        print(f"[detector] Pilatus {p}: still done (exposure={exposure:.4f}s)")
        _log.debug("ADPilatusModel still: %s exposure=%.4f done", p, exposure)


class ADSpinnakerModel:
    """Detector model for FLIR/Point Grey cameras via EPICS ADSpinnaker (ADGenICam).

    ADSpinnaker uses GenICam string enums for trigger control:
      TriggerMode = "Off"  (internal / free-run)
    No AcquirePeriod is used; AcquireTime controls exposure directly.
    """

    def __init__(self, pv_prefix: str) -> None:
        prefix = pv_prefix.strip()
        if not prefix.endswith(":"):
            prefix += ":"
        self._prefix = prefix

    def collect_still(self, exposure: float) -> None:
        p = self._prefix
        acq_time = max(0.001, exposure)

        caput(f"{p}cam1:TriggerMode", "Off", wait=True)
        caput(f"{p}cam1:AcquireTime", acq_time, wait=True)
        caput(f"{p}cam1:NumImages", 1, wait=True)
        caput(f"{p}HDF1:NumCapture", 1)
        caput(f"{p}HDF1:Capture", 1)
        caput(f"{p}cam1:Acquire", 1, wait=True, timeout=300)

        print(f"[detector] Spinnaker {p}: still done (exposure={exposure:.4f}s)")
        _log.debug("ADSpinnakerModel still: %s exposure=%.4f done", p, exposure)


_REGISTRY: dict[str, type] = {
    "eiger": ADEigerModel,
    "pilatus": ADPilatusModel,
    "spinnaker": ADSpinnakerModel,
}


def get_detector_model(detector_type: str, pv_prefix: str) -> DetectorModel:
    """Return the appropriate DetectorModel for *detector_type*."""
    cls = _REGISTRY.get(detector_type)
    if cls is None:
        _log.warning("Unknown detector type %r, falling back to ADEigerModel.", detector_type)
        cls = ADEigerModel
    return cls(pv_prefix)
