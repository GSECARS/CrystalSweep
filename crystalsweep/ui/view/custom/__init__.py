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

from epicsapps.pva_adviewer.image_canvas import BinMethod, ImageCanvas
from epicsapps.pva_adviewer.integration_plot import IntegrationPlot
from epicsapps.pva_adviewer.settings_popup import ImageSettingsPopup
from wxmplot.colors import colormap_color, get_colormap_names, lookup_colormap

from crystalsweep.ui.view.custom.colormaps import register_cs_colormaps
from crystalsweep.ui.view.custom.widgets import CrystalMenuBar

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
]
