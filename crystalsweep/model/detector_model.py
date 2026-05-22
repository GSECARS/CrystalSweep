#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/detector_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Protocol and concrete implementations for area detector models.
# Each model knows how to perform detector-specific acquisition sequences
# using EPICS PVs derived from a common prefix, and arms the correct file
# writer plugin based on the configured file format.
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

_PLUGIN_MAP: dict[str, str] = {
    "hdf5": "HDF1",
    "cbf": "CBF1",
    "tif": "TIFF1",
}


def _file_plugin(file_format: str) -> str:
    return _PLUGIN_MAP.get(file_format, "HDF1")


@runtime_checkable
class DetectorModel(Protocol):
    """Protocol for area detector models."""

    def save_hdf5(self) -> None:
        """Arm the HDF5 file writer plugin to capture one frame."""
        ...

    def save_tiff(self) -> None:
        """Arm the TIFF file writer plugin to capture one frame."""
        ...

    def save_cbf(self) -> None:
        """Arm the CBF file writer plugin to capture one frame."""
        ...

    def collect_still(self, exposure: float) -> None:
        """Arm the detector, trigger one frame, and block until complete."""
        ...


class ADEigerModel:
    """Detector model for Dectris Eiger detectors via EPICS areaDetector.

    Supported file formats: hdf5 (default), tif.
    """

    def __init__(self, pv_prefix: str, file_format: str = "hdf5") -> None:
        prefix = pv_prefix.strip()
        if not prefix.endswith(":"):
            prefix += ":"
        self._prefix = prefix
        self._plugin = _file_plugin(file_format)

    def save_hdf5(self) -> None:
        p = self._prefix
        caput(f"{p}HDF1:NumCapture", 1)
        caput(f"{p}HDF1:Capture", 1)

    def save_tiff(self) -> None:
        p = self._prefix
        caput(f"{p}TIFF1:NumCapture", 1)
        caput(f"{p}TIFF1:Capture", 1)

    def save_cbf(self) -> None:
        p = self._prefix
        caput(f"{p}CBF1:NumCapture", 1)
        caput(f"{p}CBF1:Capture", 1)

    def collect_still(self, exposure: float) -> None:
        p = self._prefix
        plugin = self._plugin
        acq_time = max(0.001, exposure * 0.99 - 0.001)

        caput(f"{p}cam1:TriggerMode", 0, wait=True)
        caput(f"{p}cam1:AcquirePeriod", acq_time, wait=True)
        caput(f"{p}cam1:AcquireTime", acq_time, wait=True)
        caput(f"{p}cam1:NumImages", 1, wait=True)

        if plugin == "HDF1":
            self.save_hdf5()
        elif plugin == "TIFF1":
            self.save_tiff()
        else:
            self.save_cbf()

        time.sleep(0.2)
        caput(f"{p}cam1:Acquire", 1, wait=True, timeout=300)

        print(f"[detector] Eiger {p} ({plugin}): still done (exposure={exposure:.4f}s)")
        _log.debug("ADEigerModel still: %s plugin=%s exposure=%.4f done", p, plugin, exposure)


class ADPilatusModel:
    """Detector model for Dectris Pilatus detectors via EPICS areaDetector.

    Supported file formats: cbf (default), tif, hdf5.
    """

    def __init__(self, pv_prefix: str, file_format: str = "cbf") -> None:
        prefix = pv_prefix.strip()
        if not prefix.endswith(":"):
            prefix += ":"
        self._prefix = prefix
        self._plugin = _file_plugin(file_format)

    def save_hdf5(self) -> None:
        p = self._prefix
        caput(f"{p}HDF1:NumCapture", 1)
        caput(f"{p}HDF1:Capture", 1)

    def save_tiff(self) -> None:
        p = self._prefix
        caput(f"{p}TIFF1:NumCapture", 1)
        caput(f"{p}TIFF1:Capture", 1)

    def save_cbf(self) -> None:
        p = self._prefix
        caput(f"{p}CBF1:NumCapture", 1)
        caput(f"{p}CBF1:Capture", 1)

    def collect_still(self, exposure: float) -> None:
        p = self._prefix
        plugin = self._plugin
        acq_time = max(0.001, exposure)

        caput(f"{p}cam1:TriggerMode", 0, wait=True)
        caput(f"{p}cam1:AcquireTime", acq_time, wait=True)
        caput(f"{p}cam1:NumImages", 1, wait=True)

        if plugin == "HDF1":
            self.save_hdf5()
        elif plugin == "TIFF1":
            self.save_tiff()
        else:
            self.save_cbf()

        caput(f"{p}cam1:Acquire", 1, wait=True, timeout=300)

        print(f"[detector] Pilatus {p} ({plugin}): still done (exposure={exposure:.4f}s)")
        _log.debug("ADPilatusModel still: %s plugin=%s exposure=%.4f done", p, plugin, exposure)


class ADSpinnakerModel:
    """Detector model for FLIR/Point Grey cameras via EPICS ADSpinnaker (ADGenICam).

    ADSpinnaker uses GenICam string enums for trigger control:
      TriggerMode = "Off"  (internal / free-run)
    No AcquirePeriod is used; AcquireTime controls exposure directly.

    Supported file formats: hdf5 (default), tif.
    """

    def __init__(self, pv_prefix: str, file_format: str = "hdf5") -> None:
        prefix = pv_prefix.strip()
        if not prefix.endswith(":"):
            prefix += ":"
        self._prefix = prefix
        self._plugin = _file_plugin(file_format)

    def save_hdf5(self) -> None:
        p = self._prefix
        caput(f"{p}HDF1:NumCapture", 1)
        caput(f"{p}HDF1:Capture", 1)

    def save_tiff(self) -> None:
        p = self._prefix
        caput(f"{p}TIFF1:NumCapture", 1)
        caput(f"{p}TIFF1:Capture", 1)

    def save_cbf(self) -> None:
        p = self._prefix
        caput(f"{p}CBF1:NumCapture", 1)
        caput(f"{p}CBF1:Capture", 1)

    def collect_still(self, exposure: float) -> None:
        p = self._prefix
        plugin = self._plugin
        acq_time = max(0.001, exposure)

        caput(f"{p}cam1:TriggerMode", "Off", wait=True)
        caput(f"{p}cam1:AcquireTime", acq_time, wait=True)
        caput(f"{p}cam1:NumImages", 1, wait=True)

        if plugin == "HDF1":
            self.save_hdf5()
        elif plugin == "TIFF1":
            self.save_tiff()
        else:
            self.save_cbf()

        caput(f"{p}cam1:Acquire", 1, wait=True, timeout=300)

        print(f"[detector] Spinnaker {p} ({plugin}): still done (exposure={exposure:.4f}s)")
        _log.debug("ADSpinnakerModel still: %s plugin=%s exposure=%.4f done", p, plugin, exposure)


_REGISTRY: dict[str, type] = {
    "eiger": ADEigerModel,
    "pilatus": ADPilatusModel,
    "spinnaker": ADSpinnakerModel,
}


def get_detector_model(detector_type: str, pv_prefix: str, file_format: str = "hdf5") -> DetectorModel:
    """Return the appropriate DetectorModel for *detector_type* and *file_format*."""
    cls = _REGISTRY.get(detector_type)
    if cls is None:
        _log.warning("Unknown detector type %r, falling back to ADEigerModel.", detector_type)
        cls = ADEigerModel
    return cls(pv_prefix, file_format)
