#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/collection_settings_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Data model for the collection settings panel: scan type and the per-type
# parameters (exposure, rotation start/end/range, step size).
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from dataclasses import dataclass, field

from crystalsweep.model.collection_model import ScanType

__all__ = ["CollectionSettingsModel"]


@dataclass()
class CollectionSettingsModel:
    """Holds the current collection settings used to populate new collection points."""

    scan_type: ScanType = field(default="still")
    exposure: float = field(default=1.0)
    map: bool = field(default=False)
    map_motor: str = field(default="")
    map_start: float = field(default=-0.0025)
    map_end: float = field(default=0.0025)
    map_step: float = field(default=0.001)
    map_points: int = field(default=6)
    map2_enabled: bool = field(default=False)
    map2_motor: str = field(default="")
    map2_start: float = field(default=-0.0025)
    map2_end: float = field(default=0.0025)
    map2_step: float = field(default=0.001)
    map2_points: int = field(default=6)
    rotation_start: float = field(default=-10.0)
    rotation_end: float = field(default=10.0)
    rotation_range: float = field(default=20.0)
    step_size: float = field(default=1.0)
    rotation_shorthand: str = field(default="")
    beam_angle: float = field(default=0.0)
    wide_flip: bool = field(default=True)
