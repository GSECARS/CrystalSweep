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

from dataclasses import dataclass


@dataclass(frozen=True)
class MainModel:
    """Implements the main model for the CrystalSweep application."""

    def __post_init__(self) -> None:
        """Runs after the main model is initialized."""
        pass
