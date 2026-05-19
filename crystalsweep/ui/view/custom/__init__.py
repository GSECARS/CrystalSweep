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

from crystalsweep.ui.view.custom.colormaps import COLORMAP_NAMES, CUSTOM_COLORMAPS, colormap_color
from crystalsweep.ui.view.custom.image_canvas import ImageCanvas
from crystalsweep.ui.view.custom.integration_plot import IntegrationPlot
from crystalsweep.ui.view.custom.intensity_histogram import IntensityHistogramWidget
from crystalsweep.ui.view.custom.settings_popup import ImageSettingsPopup
from crystalsweep.ui.view.custom.widgets import DarkCombo, DarkScrollBar, DarkTextCtrl, DarkToggle, FlatButton, FrameLabel, IconButton, LiveToggle, ThemedSplitter

__all__ = [
    "COLORMAP_NAMES",
    "CUSTOM_COLORMAPS",
    "colormap_color",
    "DarkCombo",
    "DarkScrollBar",
    "DarkTextCtrl",
    "DarkToggle",
    "FlatButton",
    "FrameLabel",
    "IconButton",
    "ImageCanvas",
    "ImageSettingsPopup",
    "IntegrationPlot",
    "IntensityHistogramWidget",
    "LiveToggle",
    "ThemedSplitter",
]
