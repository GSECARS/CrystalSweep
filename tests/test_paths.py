#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/test_paths.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for platform-specific user app directory and config directory path resolution.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------
import os
import sys
from pathlib import Path
from unittest import mock

from crystalsweep.paths import APP_NAME, user_app_dir, user_config_dir


class TestAppName:
    """Verify the application name constant."""

    def test_app_name_is_crystalsweep(self):
        assert APP_NAME == "CrystalSweep"


class TestUserAppDir:
    """Verify user_app_dir() returns platform-correct paths."""

    def test_returns_path_instance(self):
        assert isinstance(user_app_dir(), Path)

    def test_ends_with_app_name(self):
        assert user_app_dir().name == APP_NAME

    def test_darwin_uses_library_application_support(self):
        with mock.patch.object(sys, "platform", "darwin"):
            result = user_app_dir()
        assert "Library" in result.parts
        assert "Application Support" in result.parts
        assert result.name == APP_NAME

    def test_windows_uses_appdata(self):
        fake_appdata = "/fake/AppData/Roaming"
        with mock.patch.object(sys, "platform", "win32"), mock.patch.dict(os.environ, {"APPDATA": fake_appdata}):
            result = user_app_dir()
        assert result == Path(fake_appdata) / APP_NAME

    def test_windows_falls_back_to_home_when_appdata_missing(self):
        env = {k: v for k, v in os.environ.items() if k != "APPDATA"}
        with mock.patch.object(sys, "platform", "win32"), mock.patch.dict(os.environ, env, clear=True):
            result = user_app_dir()
        assert result.name == APP_NAME

    def test_linux_uses_xdg_data_home(self):
        fake_xdg = "/fake/xdg"
        env = dict(os.environ)
        env["XDG_DATA_HOME"] = fake_xdg
        with mock.patch.object(sys, "platform", "linux"), mock.patch.dict(os.environ, env, clear=True):
            result = user_app_dir()
        assert result == Path(fake_xdg) / APP_NAME

    def test_linux_falls_back_to_local_share(self):
        env = {k: v for k, v in os.environ.items() if k != "XDG_DATA_HOME"}
        with mock.patch.object(sys, "platform", "linux"), mock.patch.dict(os.environ, env, clear=True):
            result = user_app_dir()
        assert result == Path.home() / ".local" / "share" / APP_NAME


class TestUserConfigDir:
    """Verify user_config_dir() creates and returns the configs subdirectory."""

    def test_returns_path_instance(self, tmp_path):
        with mock.patch("crystalsweep.paths.user_app_dir", return_value=tmp_path / APP_NAME):
            result = user_config_dir()
        assert isinstance(result, Path)

    def test_ends_with_configs(self, tmp_path):
        with mock.patch("crystalsweep.paths.user_app_dir", return_value=tmp_path / APP_NAME):
            result = user_config_dir()
        assert result.name == "configs"

    def test_creates_directory(self, tmp_path):
        target = tmp_path / "app" / "configs"
        assert not target.exists()
        with mock.patch("crystalsweep.paths.user_app_dir", return_value=tmp_path / "app"):
            user_config_dir()
        assert target.is_dir()

    def test_idempotent_when_directory_already_exists(self, tmp_path):
        target = tmp_path / APP_NAME / "configs"
        target.mkdir(parents=True)
        with mock.patch("crystalsweep.paths.user_app_dir", return_value=tmp_path / APP_NAME):
            result = user_config_dir()
        assert result == target
