#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: CrystalSweep
# File: crystalsweep/ui/view/custom/intensity_histogram.py
# ----------------------------------------------------------------------------------
# Purpose:
# IntensityHistogramWidget: Histogram configured for image intensity display,
# with log-scale axis and colormap gradient strip.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from wxmplot.histogram import Histogram


class IntensityHistogramWidget(Histogram):
    """Histogram pre-configured for image intensity: log scale + colorbar strip."""

    def __init__(self, parent, colormap="gray", on_levels_changed=None):
        """Initialise with log_scale and show_colorbar enabled."""
        super().__init__(
            parent,
            colormap=colormap,
            log_scale=True,
            show_colorbar=True,
            on_levels_changed=on_levels_changed,
        )


__all__ = ["IntensityHistogramWidget"]
