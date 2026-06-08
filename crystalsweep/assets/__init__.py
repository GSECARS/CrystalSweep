#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/assets/__init__.py
# ----------------------------------------------------------------------------------
# Purpose:
# Helper utilities for locating bundled asset files (icons, logos, etc.).
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from pathlib import Path

__all__ = ["asset_path", "LOGO_PNG", "LOGO_SVG"]

_ASSETS_DIR = Path(__file__).resolve().parent


def asset_path(name: str) -> Path:
    """Return the absolute path to a bundled asset file."""
    return _ASSETS_DIR / name


LOGO_PNG = asset_path("crystalsweep_logo.png")
LOGO_SVG = asset_path("crystalsweep_logo.svg")
