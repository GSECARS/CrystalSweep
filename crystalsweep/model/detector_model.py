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

from epics import caget, caput

__all__ = ["DetectorModel", "ADEigerModel", "ADPilatusModel", "ADSpinnakerModel", "get_detector_model", "set_file_info"]

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

    def frames_captured(self) -> int:
        """Return the current value of NumImagesCounter_RBV — frames acquired so far."""
        ...

    def save_hdf5(self) -> None:
        """Arm the HDF5 file writer plugin to capture one frame."""
        ...

    def save_tiff(self) -> None:
        """Arm the TIFF file writer plugin to capture one frame."""
        ...

    def save_cbf(self) -> None:
        """Arm the CBF file writer plugin to capture one frame."""
        ...

    def arm_plugin(self, n_frames: int) -> None:
        """Set the file writer plugin to capture n_frames into a single file and start capturing.

        Call once before an EPICS step loop so all frames land in one file.
        """
        ...

    def collect_frame(self, exposure: float) -> None:
        """Trigger one frame in internal mode and block until complete, without re-arming the plugin.

        Use inside an EPICS step loop after arm_plugin() has been called.
        """
        ...

    def collect_step(self, exposure: float, n_frames: int) -> None:
        """Arm the detector for n_frames externally-triggered frames and fire Acquire non-blocking.

        Used for slew-step scans where the controller sends one hardware pulse per frame.
        """
        ...

    def collect_wide(self, exposure: float) -> None:
        """Arm the detector in internal-trigger mode for a slew scan and fire Acquire non-blocking.

        The caller is responsible for moving the motor to omega_start before calling this,
        and for executing the motor slew to omega_end immediately after.
        """
        ...

    def collect_still(self, exposure: float) -> None:
        """Arm the detector, trigger one frame, and block until complete."""
        ...

    def fetch_file_info(self) -> tuple[str, str, int]:
        """Read FilePath, FileName, and FileNumber from the active file writer plugin.

        Returns (directory, filename, file_number).
        """
        ...

    def set_file_info(self, directory: str, filename: str, frame_number: int = 1, disable_auto_increment: bool = False, file_template: str = "") -> int:
        """Write FilePath, FileName, FileNumber, FileTemplate, and optionally disable AutoIncrement on the active plugin."""
        ...

    def restore_auto_increment(self, saved_value: int) -> None:
        """Restore the plugin's AutoIncrement PV to *saved_value*."""
        ...

    def abort(self) -> None:
        """Stop acquisition immediately and reset the detector to a safe idle state."""
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

    def frames_captured(self) -> int:
        return int(caget(f"{self._prefix}cam1:NumImagesCounter_RBV") or 0)

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

    def fetch_file_info(self) -> tuple[str, str, int]:
        p = self._prefix
        plugin = self._plugin
        directory = caget(f"{p}{plugin}:FilePath_RBV", as_string=True) or ""
        filename = caget(f"{p}{plugin}:FileName_RBV", as_string=True) or ""
        file_number = int(caget(f"{p}{plugin}:FileNumber") or 0)
        _log.debug("ADEigerModel fetch_file_info: %s plugin=%s dir=%r name=%r num=%d", p, plugin, directory, filename, file_number)
        return directory, filename, file_number

    def set_file_info(self, directory: str, filename: str, frame_number: int = 1, disable_auto_increment: bool = False, file_template: str = "") -> int:
        p = self._prefix
        plugin = self._plugin
        caput(f"{p}{plugin}:FilePath", directory, wait=True)
        caput(f"{p}{plugin}:FileName", filename, wait=True)
        caput(f"{p}{plugin}:FileNumber", frame_number, wait=True)
        if file_template:
            caput(f"{p}{plugin}:FileTemplate", file_template, wait=True)
        saved = 1
        if disable_auto_increment:
            saved = int(caget(f"{p}{plugin}:AutoIncrement") or 1)
            caput(f"{p}{plugin}:AutoIncrement", 0, wait=True)
        _log.debug("ADEigerModel set_file_info: %s plugin=%s dir=%r name=%r num=%d template=%r auto_inc_disabled=%s", p, plugin, directory, filename, frame_number, file_template, disable_auto_increment)
        return saved

    def restore_auto_increment(self, saved_value: int) -> None:
        p = self._prefix
        plugin = self._plugin
        caput(f"{p}{plugin}:AutoIncrement", saved_value, wait=True)
        _log.debug("ADEigerModel restore_auto_increment: %s plugin=%s value=%d", p, plugin, saved_value)

    def arm_plugin(self, n_frames: int) -> None:
        p = self._prefix
        plugin = self._plugin
        if plugin == "HDF1":
            caput(f"{p}HDF1:NumCapture", n_frames)
            caput(f"{p}HDF1:Capture", 1)
        elif plugin == "TIFF1":
            caput(f"{p}TIFF1:NumCapture", n_frames)
            caput(f"{p}TIFF1:Capture", 1)
        else:
            caput(f"{p}CBF1:NumCapture", n_frames)
            caput(f"{p}CBF1:Capture", 1)
        _log.debug("ADEigerModel arm_plugin: %s plugin=%s n_frames=%d", p, plugin, n_frames)

    def collect_frame(self, exposure: float) -> None:
        p = self._prefix
        acq_time = max(0.001, exposure * 0.99 - 0.001)
        caput(f"{p}cam1:TriggerMode", 0, wait=True)
        caput(f"{p}cam1:AcquirePeriod", acq_time, wait=True)
        caput(f"{p}cam1:AcquireTime", acq_time, wait=True)
        caput(f"{p}cam1:NumImages", 1, wait=True)
        caput(f"{p}cam1:Acquire", 1, wait=True, timeout=300)
        _log.debug("ADEigerModel collect_frame: %s exposure=%.4f done", p, exposure)

    def collect_step(self, exposure: float, n_frames: int) -> None:
        p = self._prefix
        plugin = self._plugin
        acq_time = max(0.001, exposure * 0.99 - 0.001)

        caput(f"{p}cam1:TriggerMode", 2, wait=True)
        caput(f"{p}cam1:AcquirePeriod", acq_time, wait=True)
        caput(f"{p}cam1:AcquireTime", acq_time, wait=True)
        caput(f"{p}cam1:NumImages", n_frames, wait=True)

        self.arm_plugin(n_frames)

        caput(f"{p}cam1:Acquire", 1)
        _log.debug("ADEigerModel step: %s plugin=%s exposure=%.4f n_frames=%d armed", p, plugin, exposure, n_frames)

    def collect_wide(self, exposure: float) -> None:
        p = self._prefix
        plugin = self._plugin
        acq_time = max(0.001, exposure * 0.999 - 0.001)

        caput(f"{p}cam1:TriggerMode", 0, wait=True)
        caput(f"{p}cam1:AcquireTime", acq_time, wait=True)
        caput(f"{p}cam1:NumImages", 1, wait=True)

        if plugin == "HDF1":
            self.save_hdf5()
        elif plugin == "TIFF1":
            self.save_tiff()
        else:
            self.save_cbf()

        caput(f"{p}cam1:Acquire", 1)
        _log.debug("ADEigerModel wide: %s plugin=%s exposure=%.4f armed", p, plugin, exposure)

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

    def abort(self) -> None:
        p = self._prefix
        try:
            caput(f"{p}cam1:Acquire", 0)
        except Exception as exc:
            _log.warning("ADEigerModel abort: failed to stop acquire: %s", exc)
        try:
            caput(f"{p}cam1:NumImages", 1)
        except Exception as exc:
            _log.warning("ADEigerModel abort: failed to reset NumImages: %s", exc)
        try:
            caput(f"{p}Proc1:NumFilter", 1)
        except Exception as exc:
            _log.warning("ADEigerModel abort: failed to reset Proc1:NumFilter: %s", exc)
        try:
            caput(f"{p}HDF1:Capture", 0)
        except Exception as exc:
            _log.warning("ADEigerModel abort: failed to stop HDF1:Capture: %s", exc)
        _log.info("ADEigerModel abort: %s", p)


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

    def frames_captured(self) -> int:
        return int(caget(f"{self._prefix}cam1:NumImagesCounter_RBV") or 0)

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

    def fetch_file_info(self) -> tuple[str, str, int]:
        p = self._prefix
        plugin = self._plugin
        directory = caget(f"{p}{plugin}:FilePath_RBV", as_string=True) or ""
        filename = caget(f"{p}{plugin}:FileName_RBV", as_string=True) or ""
        file_number = int(caget(f"{p}{plugin}:FileNumber") or 0)
        _log.debug("ADPilatusModel fetch_file_info: %s plugin=%s dir=%r name=%r num=%d", p, plugin, directory, filename, file_number)
        return directory, filename, file_number

    def set_file_info(self, directory: str, filename: str, frame_number: int = 1, disable_auto_increment: bool = False, file_template: str = "") -> int:
        p = self._prefix
        plugin = self._plugin
        caput(f"{p}{plugin}:FilePath", directory, wait=True)
        caput(f"{p}{plugin}:FileName", filename, wait=True)
        caput(f"{p}{plugin}:FileNumber", frame_number, wait=True)
        if file_template:
            caput(f"{p}{plugin}:FileTemplate", file_template, wait=True)
        saved = 1
        if disable_auto_increment:
            saved = int(caget(f"{p}{plugin}:AutoIncrement") or 1)
            caput(f"{p}{plugin}:AutoIncrement", 0, wait=True)
        _log.debug("ADPilatusModel set_file_info: %s plugin=%s dir=%r name=%r num=%d template=%r auto_inc_disabled=%s", p, plugin, directory, filename, frame_number, file_template, disable_auto_increment)
        return saved

    def restore_auto_increment(self, saved_value: int) -> None:
        p = self._prefix
        plugin = self._plugin
        caput(f"{p}{plugin}:AutoIncrement", saved_value, wait=True)
        _log.debug("ADPilatusModel restore_auto_increment: %s plugin=%s value=%d", p, plugin, saved_value)

    def arm_plugin(self, n_frames: int) -> None:
        p = self._prefix
        plugin = self._plugin
        if plugin == "HDF1":
            caput(f"{p}HDF1:NumCapture", n_frames)
            caput(f"{p}HDF1:Capture", 1)
        elif plugin == "TIFF1":
            caput(f"{p}TIFF1:NumCapture", n_frames)
            caput(f"{p}TIFF1:Capture", 1)
        else:
            caput(f"{p}CBF1:NumCapture", n_frames)
            caput(f"{p}CBF1:Capture", 1)
        _log.debug("ADPilatusModel arm_plugin: %s plugin=%s n_frames=%d", p, plugin, n_frames)

    def collect_frame(self, exposure: float) -> None:
        p = self._prefix
        acq_time = max(0.001, exposure)
        caput(f"{p}cam1:TriggerMode", 0, wait=True)
        caput(f"{p}cam1:AcquireTime", acq_time, wait=True)
        caput(f"{p}cam1:NumImages", 1, wait=True)
        caput(f"{p}cam1:Acquire", 1, wait=True, timeout=300)
        _log.debug("ADPilatusModel collect_frame: %s exposure=%.4f done", p, exposure)

    def collect_step(self, exposure: float, n_frames: int) -> None:
        p = self._prefix
        plugin = self._plugin
        acq_time = max(0.001, exposure - 0.001)

        caput(f"{p}cam1:TriggerMode", 3, wait=True)
        caput(f"{p}cam1:AcquireTime", acq_time, wait=True)
        caput(f"{p}cam1:NumImages", n_frames, wait=True)

        self.arm_plugin(n_frames)

        caput(f"{p}cam1:Acquire", 1)
        _log.debug("ADPilatusModel step: %s plugin=%s exposure=%.4f n_frames=%d armed", p, plugin, exposure, n_frames)

    def collect_wide(self, exposure: float) -> None:
        p = self._prefix
        plugin = self._plugin
        acq_time = max(0.001, exposure - 0.001)

        caput(f"{p}cam1:TriggerMode", 0, wait=True)
        caput(f"{p}cam1:AcquireTime", acq_time, wait=True)
        caput(f"{p}cam1:NumImages", 1, wait=True)

        if plugin == "HDF1":
            self.save_hdf5()
        elif plugin == "TIFF1":
            self.save_tiff()
        else:
            self.save_cbf()

        caput(f"{p}cam1:Acquire", 1)
        _log.debug("ADPilatusModel wide: %s plugin=%s exposure=%.4f armed", p, plugin, exposure)

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

    def abort(self) -> None:
        p = self._prefix
        try:
            caput(f"{p}cam1:Acquire", 0)
        except Exception as exc:
            _log.warning("ADPilatusModel abort: failed to stop acquire: %s", exc)
        try:
            caput(f"{p}cam1:ThresholdApply", 1)
        except Exception as exc:
            _log.warning("ADPilatusModel abort: failed to apply threshold: %s", exc)
        try:
            caput(f"{p}cam1:NumImages", 1)
        except Exception as exc:
            _log.warning("ADPilatusModel abort: failed to reset NumImages: %s", exc)
        try:
            caput(f"{p}Proc1:NumFilter", 1)
        except Exception as exc:
            _log.warning("ADPilatusModel abort: failed to reset Proc1:NumFilter: %s", exc)
        _log.info("ADPilatusModel abort: %s", p)


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

    def frames_captured(self) -> int:
        return int(caget(f"{self._prefix}cam1:NumImagesCounter_RBV") or 0)

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

    def fetch_file_info(self) -> tuple[str, str, int]:
        p = self._prefix
        plugin = self._plugin
        directory = caget(f"{p}{plugin}:FilePath_RBV", as_string=True) or ""
        filename = caget(f"{p}{plugin}:FileName_RBV", as_string=True) or ""
        file_number = int(caget(f"{p}{plugin}:FileNumber") or 0)
        _log.debug("ADSpinnakerModel fetch_file_info: %s plugin=%s dir=%r name=%r num=%d", p, plugin, directory, filename, file_number)
        return directory, filename, file_number

    def set_file_info(self, directory: str, filename: str, frame_number: int = 1, disable_auto_increment: bool = False, file_template: str = "") -> int:
        p = self._prefix
        plugin = self._plugin
        caput(f"{p}{plugin}:FilePath", directory, wait=True)
        caput(f"{p}{plugin}:FileName", filename, wait=True)
        caput(f"{p}{plugin}:FileNumber", frame_number, wait=True)
        if file_template:
            caput(f"{p}{plugin}:FileTemplate", file_template, wait=True)
        saved = 1
        if disable_auto_increment:
            saved = int(caget(f"{p}{plugin}:AutoIncrement") or 1)
            caput(f"{p}{plugin}:AutoIncrement", 0, wait=True)
        _log.debug("ADSpinnakerModel set_file_info: %s plugin=%s dir=%r name=%r num=%d template=%r auto_inc_disabled=%s", p, plugin, directory, filename, frame_number, file_template, disable_auto_increment)
        return saved

    def restore_auto_increment(self, saved_value: int) -> None:
        p = self._prefix
        plugin = self._plugin
        caput(f"{p}{plugin}:AutoIncrement", saved_value, wait=True)
        _log.debug("ADSpinnakerModel restore_auto_increment: %s plugin=%s value=%d", p, plugin, saved_value)

    def arm_plugin(self, n_frames: int) -> None:
        p = self._prefix
        plugin = self._plugin
        if plugin == "HDF1":
            caput(f"{p}HDF1:NumCapture", n_frames)
            caput(f"{p}HDF1:Capture", 1)
        elif plugin == "TIFF1":
            caput(f"{p}TIFF1:NumCapture", n_frames)
            caput(f"{p}TIFF1:Capture", 1)
        else:
            caput(f"{p}CBF1:NumCapture", n_frames)
            caput(f"{p}CBF1:Capture", 1)
        _log.debug("ADSpinnakerModel arm_plugin: %s plugin=%s n_frames=%d", p, plugin, n_frames)

    def collect_frame(self, exposure: float) -> None:
        p = self._prefix
        acq_time = max(0.001, exposure)
        caput(f"{p}cam1:TriggerMode", "Off", wait=True)
        caput(f"{p}cam1:AcquireTime", acq_time, wait=True)
        caput(f"{p}cam1:NumImages", 1, wait=True)
        caput(f"{p}cam1:Acquire", 1, wait=True, timeout=300)
        _log.debug("ADSpinnakerModel collect_frame: %s exposure=%.4f done", p, exposure)

    def collect_step(self, exposure: float, n_frames: int) -> None:
        p = self._prefix
        plugin = self._plugin
        acq_time = max(0.001, exposure)

        caput(f"{p}cam1:TriggerMode", "On", wait=True)
        caput(f"{p}cam1:AcquireTime", acq_time, wait=True)
        caput(f"{p}cam1:NumImages", n_frames, wait=True)

        self.arm_plugin(n_frames)

        caput(f"{p}cam1:Acquire", 1)
        _log.debug("ADSpinnakerModel step: %s plugin=%s exposure=%.4f n_frames=%d armed", p, plugin, exposure, n_frames)

    def collect_wide(self, exposure: float) -> None:
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

        caput(f"{p}cam1:Acquire", 1)
        _log.debug("ADSpinnakerModel wide: %s plugin=%s exposure=%.4f armed", p, plugin, exposure)

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

    def abort(self) -> None:
        p = self._prefix
        try:
            caput(f"{p}cam1:Acquire", 0)
        except Exception as exc:
            _log.warning("ADSpinnakerModel abort: failed to stop acquire: %s", exc)
        try:
            caput(f"{p}cam1:NumImages", 1)
        except Exception as exc:
            _log.warning("ADSpinnakerModel abort: failed to reset NumImages: %s", exc)
        _log.info("ADSpinnakerModel abort: %s", p)


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
