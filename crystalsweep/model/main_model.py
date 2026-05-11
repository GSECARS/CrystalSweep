#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/main_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# This file is used to implement the main model for the CrystalSweep application.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from dataclasses import dataclass, field

from crystalsweep.model.ad_viewer_model import ADViewerModel
from crystalsweep.model.config_model import ConfigModel
from crystalsweep.model.image_loader_model import ImageLoaderModel
from crystalsweep.model.integration_model import IntegrationModel

__all__ = ["MainModel"]


@dataclass(frozen=True)
class MainModel:
    """Implements the main model for the CrystalSweep application."""

    config: ConfigModel = field(init=False, compare=False, repr=False, default_factory=ConfigModel)
    ad_viewer: ADViewerModel = field(init=False, compare=False, repr=False, default_factory=ADViewerModel)
    image_loader: ImageLoaderModel = field(init=False, compare=False, repr=False, default_factory=ImageLoaderModel)
    integration: IntegrationModel = field(init=False, compare=False, repr=False, default_factory=IntegrationModel)
