# SPDX-License-Identifier: MIT

from epicsapps.pva_adviewer.colormaps import register_colormaps as register_cs_colormaps
from wxmplot.colors import colormap_color, get_colormap_names, lookup_colormap

__all__ = ["register_cs_colormaps", "colormap_color", "get_colormap_names", "lookup_colormap"]
