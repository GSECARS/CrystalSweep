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
    map_start: float = field(default=0.0)
    map_end: float = field(default=1.0)
    map_step: float = field(default=0.1)
    map_points: int = field(default=11)
    map2_enabled: bool = field(default=False)
    map2_motor: str = field(default="")
    map2_start: float = field(default=0.0)
    map2_end: float = field(default=1.0)
    map2_step: float = field(default=0.1)
    map2_points: int = field(default=11)
    rotation_start: float = field(default=0.0)
    rotation_end: float = field(default=180.0)
    rotation_range: float = field(default=180.0)
    step_size: float = field(default=1.0)
    rotation_shorthand: str = field(default="")
