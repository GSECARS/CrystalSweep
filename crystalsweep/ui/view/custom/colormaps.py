#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/colormaps.py
# ----------------------------------------------------------------------------------
# Purpose:
# Registers CrystalSweep-specific colormaps with the wxmplot colormap registry.
# Call register_cs_colormaps() once at application startup before any widgets
# are constructed.  After registration, use wxmplot.colors.lookup_colormap and
# wxmplot.colors.get_colormap_names directly.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from vispy.color.colormap import Colormap
from wxmplot.colors import colormap_color, get_colormap_names, lookup_colormap, register_colormap

__all__ = ["register_cs_colormaps", "colormap_color", "get_colormap_names", "lookup_colormap"]


def register_cs_colormaps() -> None:
    """Register CrystalSweep custom colormaps with the wxmplot registry."""
    register_colormap("grays_reverse", Colormap(["white", "black"]))
