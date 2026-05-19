#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/file_settings_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Data model for the file settings panel: filename, path, frame number,
# map extension, image format flags, and external software flags.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["FileSettingsModel"]

_DEFAULT_MAP_EXT: str = "map"


@dataclass()
class FileSettingsModel:
    """Holds state for the file settings section of the GUI."""

    filename: str = field(default="")
    directory: Path = field(default_factory=Path)
    frame_number: int = field(default=0)
    map_ext: str = field(default=_DEFAULT_MAP_EXT)

    use_hdf5: bool = field(default=False)
    use_cbf: bool = field(default=False)
    use_tif: bool = field(default=False)

    use_crysalis: bool = field(default=False)
    crysalis_calibration: Path | None = field(default=None)

    use_apex: bool = field(default=False)
    apex_calibration: Path | None = field(default=None)

    def reset_frame_number(self) -> None:
        """Reset the frame number to zero."""
        self.frame_number = 0
