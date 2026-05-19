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
from crystalsweep.model.beamline_config_model import BeamlineConfigModel
from crystalsweep.model.collection_model import CollectionTableModel
from crystalsweep.model.epics_model import EpicsModel
from crystalsweep.model.image_loader_model import ImageLoaderModel
from crystalsweep.model.integration_model import IntegrationModel

__all__ = ["MainModel"]


@dataclass(frozen=True)
class MainModel:
    """Implements the main model for the CrystalSweep application."""

    beamline: BeamlineConfigModel = field(init=False, compare=False, repr=False, default_factory=BeamlineConfigModel)
    ad_viewer: ADViewerModel = field(init=False, compare=False, repr=False, default_factory=ADViewerModel)
    epics: EpicsModel = field(init=False, compare=False, repr=False, default_factory=EpicsModel)
    image_loader: ImageLoaderModel = field(init=False, compare=False, repr=False, default_factory=ImageLoaderModel)
    integration: IntegrationModel = field(init=False, compare=False, repr=False, default_factory=IntegrationModel)
    collection: CollectionTableModel = field(init=False, compare=False, repr=False, default_factory=CollectionTableModel)

    def __post_init__(self) -> None:
        """Load the previously remembered active beamline configuration, if available."""
        active_name = self.beamline.get_remembered_active_name()
        if active_name and self.beamline.exists(active_name):
            self.beamline.load(active_name)
