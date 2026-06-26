#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/ui/view/custom/__init__.py
# ----------------------------------------------------------------------------------
# Purpose:
# Custom view widgets: reusable controls, plot canvases, and shared theme/icons.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from crystalsweep.ui.view.custom.colormaps import register_cs_colormaps
from crystalsweep.ui.view.custom.image_canvas import ImageCanvas
from crystalsweep.ui.view.custom.integration_plot import IntegrationPlot
from crystalsweep.ui.view.custom.intensity_histogram import IntensityHistogramWidget
from crystalsweep.ui.view.custom.settings_popup import ImageSettingsPopup
from crystalsweep.ui.view.custom.widgets import (
    CrystalMenuBar,
    LiveToggle,
)
from wxmplot.colors import colormap_color, get_colormap_names, lookup_colormap

# Register CS-specific colormaps as soon as this package is imported.
register_cs_colormaps()

__all__ = [
    "colormap_color",
    "get_colormap_names",
    "lookup_colormap",
    "register_cs_colormaps",
    "CrystalMenuBar",
    "ImageCanvas",
    "ImageSettingsPopup",
    "IntegrationPlot",
    "IntensityHistogramWidget",
    "LiveToggle",
]
