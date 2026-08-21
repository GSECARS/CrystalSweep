#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/model/test_file_settings_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for FileSettingsModel field defaults, mutability, and frame number reset.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from pathlib import Path

from crystalsweep.model.file_settings_model import FileSettingsModel


class TestFileSettingsModelDefaults:
    """Verify all FileSettingsModel fields start at their documented defaults."""

    def test_filename_is_empty_string(self):
        assert FileSettingsModel().filename == ""

    def test_directory_is_empty_path(self):
        assert FileSettingsModel().directory == Path()

    def test_frame_number_is_zero(self):
        assert FileSettingsModel().frame_number == 0

    def test_map_ext_is_empty(self):
        assert FileSettingsModel().map_ext == ""

    def test_use_ext_is_true(self):
        assert FileSettingsModel().use_ext is True

    def test_use_hdf5_is_false(self):
        assert FileSettingsModel().use_hdf5 is False

    def test_use_cbf_is_false(self):
        assert FileSettingsModel().use_cbf is False

    def test_use_tif_is_false(self):
        assert FileSettingsModel().use_tif is False

    def test_use_snake_combine_is_false(self):
        assert FileSettingsModel().use_snake_combine is False

    def test_use_crysalis_is_false(self):
        assert FileSettingsModel().use_crysalis is False

    def test_crysalis_calibration_is_none(self):
        assert FileSettingsModel().crysalis_calibration is None

    def test_crysalis_set_file_is_none(self):
        assert FileSettingsModel().crysalis_set_file is None

    def test_crysalis_ccd_file_is_none(self):
        assert FileSettingsModel().crysalis_ccd_file is None

    def test_use_apex_is_false(self):
        assert FileSettingsModel().use_apex is False

    def test_apex_calibration_is_none(self):
        assert FileSettingsModel().apex_calibration is None


class TestFileSettingsModelMutability:
    """Verify fields can be reassigned after construction."""

    def test_filename_can_be_set(self):
        m = FileSettingsModel()
        m.filename = "sample001"
        assert m.filename == "sample001"

    def test_directory_can_be_set(self):
        m = FileSettingsModel()
        m.directory = Path("/data/beamline")
        assert m.directory == Path("/data/beamline")

    def test_frame_number_can_be_set(self):
        m = FileSettingsModel()
        m.frame_number = 42
        assert m.frame_number == 42

    def test_use_hdf5_can_be_enabled(self):
        m = FileSettingsModel()
        m.use_hdf5 = True
        assert m.use_hdf5 is True

    def test_crysalis_calibration_can_be_set(self):
        m = FileSettingsModel()
        m.crysalis_calibration = Path("/cal/test.set")
        assert m.crysalis_calibration == Path("/cal/test.set")

    def test_map_ext_can_be_set(self):
        m = FileSettingsModel()
        m.map_ext = "map"
        assert m.map_ext == "map"


class TestFileSettingsModelResetFrameNumber:
    """Verify reset_frame_number() sets frame_number to 1."""

    def test_resets_to_one(self):
        m = FileSettingsModel()
        m.frame_number = 99
        m.reset_frame_number()
        assert m.frame_number == 1

    def test_resets_from_zero(self):
        m = FileSettingsModel()
        assert m.frame_number == 0
        m.reset_frame_number()
        assert m.frame_number == 1

    def test_multiple_resets_stay_at_one(self):
        m = FileSettingsModel()
        m.frame_number = 100
        m.reset_frame_number()
        m.reset_frame_number()
        assert m.frame_number == 1

    def test_does_not_affect_other_fields(self):
        m = FileSettingsModel()
        m.filename = "my_sample"
        m.frame_number = 5
        m.reset_frame_number()
        assert m.filename == "my_sample"


class TestFileSettingsModelInstances:
    """Verify separate instances are fully independent."""

    def test_independent_instances(self):
        a = FileSettingsModel()
        b = FileSettingsModel()
        a.filename = "foo"
        assert b.filename == ""

    def test_directory_field_is_not_shared(self):
        a = FileSettingsModel()
        b = FileSettingsModel()
        a.directory = Path("/x")
        assert b.directory == Path()
