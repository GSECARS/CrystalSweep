#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/config_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# This file is used to implement the Config model.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import os
from dataclasses import dataclass

import dotenv

__all__ = ["ConfigModel"]


@dataclass(frozen=True)
class ConfigModel:
    """Implements the Config model."""

    # Reads the .env file and sets the config variables
    def __post_init__(self) -> None:
        dotenv.load_dotenv()

    @property
    def ad_viewer_pv_name(self) -> str:
        """Returns the PV name for the Area Detector viewer."""
        return os.getenv("AD_VIEWER_PV", "13SIM1:Pva1:Image")
