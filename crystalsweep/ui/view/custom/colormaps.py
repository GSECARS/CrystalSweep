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

from epicsapps.pva_adviewer.colormaps import register_colormaps as register_cs_colormaps
from wxmplot.colors import colormap_color, get_colormap_names, lookup_colormap

__all__ = ["register_cs_colormaps", "colormap_color", "get_colormap_names", "lookup_colormap"]
