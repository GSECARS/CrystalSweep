#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/__init__.py
# ----------------------------------------------------------------------------------
# Purpose:
# This file is used to initialize the CrystalSweep model.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from epicsapps.pva_adviewer.ad_viewer_model import ADViewerModel
from epicsapps.pva_adviewer.image_loader_model import ImageLoaderModel
from epicsapps.pva_adviewer.integration_model import IntegrationModel

from crystalsweep.model.aerotech_a1_model import AerotechA1Model
from crystalsweep.model.beamline_config_model import BeamlineConfig, BeamlineConfigModel, DetectorConfig, MotorConfig
from crystalsweep.model.collection_model import SCAN_TYPES, CollectionPoint, CollectionTableModel
from crystalsweep.model.collection_settings_model import CollectionSettingsModel
from crystalsweep.model.controller_connection_model import ControllerConnectionModel
from crystalsweep.model.detector_model import ADEigerModel, ADPilatusModel, ADSpinnakerModel, DetectorModel, get_detector_model
from crystalsweep.model.epics_model import EpicsModel
from crystalsweep.model.epics_scan_model import EpicsScanModel
from crystalsweep.model.file_settings_model import FileSettingsModel
from crystalsweep.model.main_model import MainModel
from crystalsweep.model.newport_xps_model import NewportXPSModel
from crystalsweep.model.scan_model import ScanDriver, ScanSpec, get_driver, register_driver
from crystalsweep.model.script_model import ScriptModel
from crystalsweep.utils import MotorPositionValidator

__all__ = [
    "ADEigerModel",
    "ADPilatusModel",
    "ADSpinnakerModel",
    "ADViewerModel",
    "CollectionSettingsModel",
    "ControllerConnectionModel",
    "DetectorModel",
    "EpicsModel",
    "BeamlineConfig",
    "BeamlineConfigModel",
    "CollectionPoint",
    "CollectionTableModel",
    "DetectorConfig",
    "FileSettingsModel",
    "ImageLoaderModel",
    "IntegrationModel",
    "MainModel",
    "MotorConfig",
    "MotorPositionValidator",
    "ScriptModel",
    "AerotechA1Model",
    "EpicsScanModel",
    "NewportXPSModel",
    "ScanDriver",
    "ScanSpec",
    "SCAN_TYPES",
    "get_detector_model",
    "get_driver",
    "register_driver",
]
