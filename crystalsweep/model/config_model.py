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

from dataclasses import dataclass

import dotenv

__all__ = ["ConfigModel"]


@dataclass(frozen=True)
class ConfigModel:
    """Implements the Config model."""

    # Reads the .env file and sets the config variables
    def __post_init__(self) -> None:
        dotenv.load_dotenv()
