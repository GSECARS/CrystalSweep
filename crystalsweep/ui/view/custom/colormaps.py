#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/colormaps.py
# ----------------------------------------------------------------------------------
# Purpose:
# Colormap definitions shared across view widgets.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import wx
from vispy.color import get_colormap
from vispy.color.colormap import Colormap, get_colormaps

__all__ = ["COLORMAP_NAMES", "CUSTOM_COLORMAPS", "colormap_color"]

CUSTOM_COLORMAPS = {
    "grays_r": Colormap(["white", "black"]),
}

COLORMAP_NAMES = sorted(list(get_colormaps()) + list(CUSTOM_COLORMAPS))


def colormap_color(colormap: str, t: float) -> wx.Colour:
    """Returns the wx.Colour for a given colormap at normalized position t in [0, 1]."""
    t = max(0.0, min(1.0, t))
    cmap = CUSTOM_COLORMAPS.get(colormap) or get_colormap(colormap)
    rgba = cmap[t].rgba[0]
    return wx.Colour(int(rgba[0] * 255), int(rgba[1] * 255), int(rgba[2] * 255))
