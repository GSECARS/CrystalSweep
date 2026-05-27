#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/beamline_config_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# This files is used to define the load/save TOML configuration files describing the
# beamline name, a list of detectors (one of which is active), and a list of motors.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import tomllib
from contextlib import suppress
from dataclasses import dataclass, field, replace
from pathlib import Path

import tomli_w

__all__ = ["BeamlineConfig", "BeamlineConfigModel", "ControllerConfig", "DetectorConfig", "MotorConfig"]

_ACTIVE_FILE_NAME = ".active"


@dataclass(frozen=True, slots=True)
class ControllerConfig:
    """A motion controller (Newport XPS, Aerotech Automation1, etc.) used by one or more motors."""

    name: str
    type: str
    params: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MotorConfig:
    """Single motor entry: shorthand, description, EPICS PV, decimal precision, mapping flag, and controller."""

    shorthand: str
    description: str
    pv: str
    precision: int = 4
    mapping_enabled: bool = False
    controller: str = "epics"
    xps_group: str = ""
    xps_positioner: str = ""
    beam_angle: float = 0.0


@dataclass(frozen=True, slots=True)
class DetectorConfig:
    """Detector identity and EPICS prefix; the PVA image PV is derived from the prefix."""

    name: str = ""
    pv_prefix: str = ""
    type: str = "eiger"
    file_format: str = "hdf5"
    file_template: str = ""
    path_prefix_local: str = ""
    path_prefix_remote: str = ""

    @property
    def file_number_width(self) -> int:
        """Extract the zero-padding width from the file template (e.g. %4.4d → 4). Defaults to 4."""
        import re
        m = re.search(r"%(\d+)\.(\d+)d", self.file_template)
        if m:
            return int(m.group(2))
        return 4

    def translate_path(self, local_path: str) -> str:
        """Return *local_path* with the local prefix replaced by the remote prefix.

        If either prefix is empty the path is returned unchanged.
        """
        loc = self.path_prefix_local.strip()
        rem = self.path_prefix_remote.strip()
        if not loc or not rem:
            return local_path
        norm = local_path.replace("\\", "/")
        loc_norm = loc.replace("\\", "/").rstrip("/")
        rem_norm = rem.rstrip("/")
        if norm.lower().startswith(loc_norm.lower()):
            remainder = norm[len(loc_norm):]
            return rem_norm + remainder
        return local_path

    def translate_path_reverse(self, remote_path: str) -> str:
        """Return *remote_path* with the remote prefix replaced by the local prefix.

        Restores the Windows path from what the IOC reports back.
        If either prefix is empty the path is returned unchanged.
        """
        loc = self.path_prefix_local.strip()
        rem = self.path_prefix_remote.strip()
        if not loc or not rem:
            return remote_path
        norm = remote_path.replace("\\", "/")
        rem_norm = rem.rstrip("/")
        loc_norm = loc.replace("\\", "/").rstrip("/")
        if norm.lower().startswith(rem_norm.lower()):
            remainder = norm[len(rem_norm):]
            return loc_norm + remainder
        return remote_path

    @property
    def image_pv(self) -> str:
        """Derive the PVA NTNDArray image PV from the detector prefix."""
        prefix = self.pv_prefix.strip()
        if not prefix:
            return ""
        if not prefix.endswith(":"):
            prefix = f"{prefix}:"
        return f"{prefix}Pva1:Image"


@dataclass(frozen=True, slots=True)
class BeamlineConfig:
    """In-memory representation of a beamline TOML configuration."""

    name: str = ""
    beamline: str = ""
    rotation_motor: MotorConfig | None = None
    detectors: tuple[DetectorConfig, ...] = field(default_factory=tuple)
    active_detector: int = -1
    motors: tuple[MotorConfig, ...] = field(default_factory=tuple)
    controllers: tuple[ControllerConfig, ...] = field(default_factory=tuple)
    abort_pvs: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    restore_pvs: tuple[str, ...] = field(default_factory=tuple)
    crysalis_par_path: str = ""
    crysalis_load_on_startup: bool = False
    shutter_pv: str = ""
    shutter_open_value: str = ""
    shutter_close_value: str = ""
    shutter_delay: float = 0.0

    @property
    def is_empty(self) -> bool:
        return not self.name and not self.beamline and self.rotation_motor is None and not self.detectors and not self.motors

    @property
    def active_detector_config(self) -> DetectorConfig | None:
        """Return the active DetectorConfig, or None if there is no valid selection."""
        if 0 <= self.active_detector < len(self.detectors):
            return self.detectors[self.active_detector]
        return None

    def with_motors(self, motors: list[MotorConfig] | tuple[MotorConfig, ...]) -> "BeamlineConfig":
        return replace(self, motors=tuple(motors))


class BeamlineConfigModel:
    """Loads, lists, and saves beamline configuration files (TOML) under a directory."""

    def __init__(self, directory: Path | str = "configs") -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self._active: BeamlineConfig = BeamlineConfig()

    @property
    def directory(self) -> Path:
        return self._directory

    @property
    def active(self) -> BeamlineConfig:
        return self._active

    @property
    def has_active(self) -> bool:
        return bool(self._active.name) and not self._active.is_empty

    def list_config_names(self) -> list[str]:
        """Return all available config names (TOML file stems) sorted alphabetically."""
        return sorted(p.stem for p in self._directory.glob("*.toml"))

    def path_for(self, name: str) -> Path:
        return self._directory / f"{name}.toml"

    def exists(self, name: str) -> bool:
        return self.path_for(name).is_file()

    def get_remembered_active_name(self) -> str:
        """Return the previously remembered active config name (or empty if none)."""
        marker = self._directory / _ACTIVE_FILE_NAME
        if not marker.is_file():
            return ""

        with suppress(OSError):
            return marker.read_text(encoding="utf-8").strip()

    def remember_active(self, name: str) -> None:
        """Persist the active configuration name to a marker file."""
        marker = self._directory / _ACTIVE_FILE_NAME
        with suppress(OSError):
            if name:
                marker.write_text(name, encoding="utf-8")
            elif marker.is_file():
                marker.unlink()

    def clear_active(self) -> None:
        """Drop the in-memory active config and remove the marker file."""
        self._active = BeamlineConfig()
        self.remember_active("")

    def load(self, name: str) -> BeamlineConfig:
        """Load a config by name. Returns a fresh empty config (with the given name) if missing."""
        path = self.path_for(name)
        if not path.is_file():
            cfg = BeamlineConfig(name=name)
            self._active = cfg
            return cfg

        with path.open("rb") as fh:
            data = tomllib.load(fh)

        detectors_data = data.get("detectors", []) or []
        detectors: list[DetectorConfig] = []
        active_detector = -1
        for entry in detectors_data:
            detector = DetectorConfig(
                name=str(entry.get("name", "")),
                pv_prefix=str(entry.get("pv_prefix", "")),
                type=str(entry.get("type", "eiger")),
                file_format=str(entry.get("file_format", "hdf5")),
                file_template=str(entry.get("file_template", "")),
                path_prefix_local=str(entry.get("path_prefix_local", "")),
                path_prefix_remote=str(entry.get("path_prefix_remote", "")),
            )
            if entry.get("active") and active_detector == -1:
                active_detector = len(detectors)
            detectors.append(detector)

        if not detectors and isinstance(data.get("detector"), dict):
            legacy = data["detector"]
            detectors.append(
                DetectorConfig(
                    name=str(legacy.get("name", "")),
                    pv_prefix=str(legacy.get("pv_prefix", "")),
                    type=str(legacy.get("type", "eiger")),
                    file_format=str(legacy.get("file_format", "hdf5")),
                )
            )
            active_detector = 0

        if detectors and active_detector == -1:
            active_detector = 0

        controllers_data = data.get("controllers", []) or []
        controllers = tuple(
            ControllerConfig(
                name=str(c.get("name", "")),
                type=str(c.get("type", "")),
                params=dict(c.get("params", {})),
            )
            for c in controllers_data
        )

        motors_data = data.get("motors", []) or []
        motors = tuple(
            MotorConfig(
                shorthand=str(m.get("shorthand", "")),
                description=str(m.get("description", m.get("name", ""))),
                pv=str(m.get("pv", "")),
                precision=max(0, int(m.get("precision", 4))),
                mapping_enabled=bool(m.get("mapping_enabled", False)),
                controller=str(m.get("controller", "epics")),
                xps_group=str(m.get("xps_group", "")),
                xps_positioner=str(m.get("xps_positioner", "")),
            )
            for m in motors_data
        )

        rotation_motor: MotorConfig | None = None
        rm_data = data.get("rotation_motor")
        if isinstance(rm_data, dict):
            rotation_motor = MotorConfig(
                shorthand=str(rm_data.get("shorthand", "")),
                description=str(rm_data.get("description", rm_data.get("name", ""))),
                pv=str(rm_data.get("pv", "")),
                precision=max(0, int(rm_data.get("precision", 4))),
                controller=str(rm_data.get("controller", "epics")),
                xps_group=str(rm_data.get("xps_group", "")),
                xps_positioner=str(rm_data.get("xps_positioner", "")),
                beam_angle=float(rm_data.get("beam_angle", 0.0)),
            )

        abort_pvs = tuple(
            (str(entry.get("pv", "")), str(entry.get("value", "")))
            for entry in (data.get("abort_pvs", []) or [])
        )

        restore_pvs = tuple(
            str(entry.get("pv", "")) if isinstance(entry, dict) else str(entry)
            for entry in (data.get("restore_pvs", []) or [])
            if (entry.get("pv", "") if isinstance(entry, dict) else entry)
        )

        cfg = BeamlineConfig(
            name=name,
            beamline=str(data.get("beamline", "")),
            rotation_motor=rotation_motor,
            detectors=tuple(detectors),
            active_detector=active_detector,
            motors=motors,
            controllers=controllers,
            abort_pvs=abort_pvs,
            restore_pvs=restore_pvs,
            crysalis_par_path=str(data.get("crysalis_par_path", "")),
            crysalis_load_on_startup=bool(data.get("crysalis_load_on_startup", False)),
            shutter_pv=str(data.get("shutter_pv", "")),
            shutter_open_value=str(data.get("shutter_open_value", "")),
            shutter_close_value=str(data.get("shutter_close_value", "")),
            shutter_delay=float(data.get("shutter_delay", 0.0)),
        )
        self._active = cfg
        return cfg

    def save(self, config: BeamlineConfig) -> Path:
        """Persist a config to directory/name.toml; returns the file path."""
        if not config.name.strip():
            raise ValueError("Configuration name is required to save.")

        payload: dict = {
            "beamline": config.beamline,
            "rotation_motor": (
                {"shorthand": config.rotation_motor.shorthand, "description": config.rotation_motor.description, "pv": config.rotation_motor.pv, "precision": config.rotation_motor.precision, "controller": config.rotation_motor.controller, "xps_group": config.rotation_motor.xps_group, "xps_positioner": config.rotation_motor.xps_positioner, "beam_angle": config.rotation_motor.beam_angle}
                if config.rotation_motor is not None
                else {}
            ),
            "detectors": [
                {"name": d.name, "pv_prefix": d.pv_prefix, "type": d.type, "file_format": d.file_format, "file_template": d.file_template, "path_prefix_local": d.path_prefix_local, "path_prefix_remote": d.path_prefix_remote, "active": idx == config.active_detector}
                for idx, d in enumerate(config.detectors)
            ],
            "controllers": [
                {"name": c.name, "type": c.type, "params": c.params}
                for c in config.controllers
            ],
            "motors": [
                {"shorthand": m.shorthand, "description": m.description, "pv": m.pv, "precision": m.precision, "mapping_enabled": m.mapping_enabled, "controller": m.controller, "xps_group": m.xps_group, "xps_positioner": m.xps_positioner}
                for m in config.motors
            ],
            "abort_pvs": [
                {"pv": pv, "value": value}
                for pv, value in config.abort_pvs
            ],
            "restore_pvs": [
                {"pv": pv}
                for pv in config.restore_pvs
                if pv
            ],
            "crysalis_par_path": config.crysalis_par_path,
            "crysalis_load_on_startup": config.crysalis_load_on_startup,
            "shutter_pv": config.shutter_pv,
            "shutter_open_value": config.shutter_open_value,
            "shutter_close_value": config.shutter_close_value,
            "shutter_delay": config.shutter_delay,
        }

        path = self.path_for(config.name)
        with path.open("wb") as fh:
            tomli_w.dump(payload, fh)
        self._active = config
        return path

    def create_blank(self, name: str) -> BeamlineConfig:
        """Create and persist a blank named config (no detectors or motors)."""
        cfg = BeamlineConfig(name=name)
        self.save(cfg)
        return cfg
