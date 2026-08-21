#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/model/test_beamline_config_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for BeamlineConfig dataclasses and BeamlineConfigModel TOML file operations.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import pytest

from crystalsweep.model.beamline_config_model import (
    BeamlineConfig,
    BeamlineConfigModel,
    ControllerConfig,
    DetectorConfig,
    MotorConfig,
)


class TestDetectorConfigImagePv:
    """Verify image_pv is constructed correctly from pv_prefix."""

    def test_empty_prefix_returns_empty(self):
        d = DetectorConfig(pv_prefix="")
        assert d.image_pv == ""

    def test_prefix_without_colon_appends_pva_image(self):
        d = DetectorConfig(pv_prefix="DET1")
        assert d.image_pv == "DET1:Pva1:Image"

    def test_prefix_with_colon_appends_pva_image(self):
        d = DetectorConfig(pv_prefix="DET1:")
        assert d.image_pv == "DET1:Pva1:Image"

    def test_prefix_with_whitespace_stripped(self):
        d = DetectorConfig(pv_prefix="  DET2  ")
        assert d.image_pv == "DET2:Pva1:Image"


class TestDetectorConfigFileNumberWidth:
    """Verify file_number_width is parsed from the file_template format string."""

    def test_standard_four_wide_template(self):
        d = DetectorConfig(file_template="%4.4d")
        assert d.file_number_width == 4

    def test_six_wide_template(self):
        d = DetectorConfig(file_template="%6.6d")
        assert d.file_number_width == 6

    def test_empty_template_defaults_to_four(self):
        d = DetectorConfig(file_template="")
        assert d.file_number_width == 4

    def test_template_without_format_defaults_to_four(self):
        d = DetectorConfig(file_template="some_string")
        assert d.file_number_width == 4

    def test_two_wide_template(self):
        d = DetectorConfig(file_template="%2.2d")
        assert d.file_number_width == 2


class TestDetectorConfigTranslatePath:
    """Verify translate_path() maps local paths to their remote equivalents."""

    def test_empty_remote_prefix_returns_unchanged(self):
        d = DetectorConfig(path_prefix_local="/local", path_prefix_remote="")
        assert d.translate_path("/local/data") == "/local/data"

    def test_matching_local_prefix_swapped_for_remote(self):
        d = DetectorConfig(path_prefix_local="/local", path_prefix_remote="/remote")
        assert d.translate_path("/local/data/sample") == "/remote/data/sample"

    def test_no_local_prefix_anchors_tail_under_remote(self):
        d = DetectorConfig(path_prefix_local="", path_prefix_remote="/remote")
        assert d.translate_path("/some/path/folder") == "/remote/folder"

    def test_non_matching_local_prefix_anchors_tail(self):
        d = DetectorConfig(path_prefix_local="/other", path_prefix_remote="/remote")
        assert d.translate_path("/different/path/folder") == "/remote/folder"

    def test_backslashes_normalised(self):
        d = DetectorConfig(path_prefix_local="C:\\local", path_prefix_remote="/remote")
        result = d.translate_path("C:\\local\\data")
        assert result.startswith("/remote")

    def test_case_insensitive_local_match(self):
        d = DetectorConfig(path_prefix_local="/LOCAL", path_prefix_remote="/remote")
        result = d.translate_path("/local/data")
        assert result == "/remote/data"

    def test_path_with_no_slash_is_anchored_directly(self):
        d = DetectorConfig(path_prefix_local="", path_prefix_remote="/remote")
        result = d.translate_path("folder")
        assert result == "/remote/folder"

    def test_trailing_slash_on_remote_prefix_trimmed(self):
        d = DetectorConfig(path_prefix_local="/local", path_prefix_remote="/remote/")
        result = d.translate_path("/local/sub")
        assert not result.startswith("/remote//")


class TestDetectorConfigTranslatePathReverse:
    """Verify translate_path_reverse() maps remote paths back to local equivalents."""

    def test_remote_prefix_swapped_for_local(self):
        d = DetectorConfig(path_prefix_local="/local", path_prefix_remote="/remote")
        assert d.translate_path_reverse("/remote/data") == "/local/data"

    def test_empty_local_returns_unchanged(self):
        d = DetectorConfig(path_prefix_local="", path_prefix_remote="/remote")
        assert d.translate_path_reverse("/remote/data") == "/remote/data"

    def test_empty_remote_returns_unchanged(self):
        d = DetectorConfig(path_prefix_local="/local", path_prefix_remote="")
        assert d.translate_path_reverse("/something/data") == "/something/data"

    def test_non_matching_path_returned_unchanged(self):
        d = DetectorConfig(path_prefix_local="/local", path_prefix_remote="/remote")
        assert d.translate_path_reverse("/other/data") == "/other/data"

    def test_case_insensitive_remote_match(self):
        d = DetectorConfig(path_prefix_local="/local", path_prefix_remote="/REMOTE")
        result = d.translate_path_reverse("/remote/file")
        assert result == "/local/file"


class TestBeamlineConfigIsEmpty:
    """Verify is_empty reflects whether any field has been populated."""

    def test_default_is_empty(self):
        assert BeamlineConfig().is_empty

    def test_name_only_is_not_empty(self):
        assert not BeamlineConfig(name="test").is_empty

    def test_beamline_only_is_not_empty(self):
        assert not BeamlineConfig(beamline="13-ID-C").is_empty

    def test_with_motors_is_not_empty(self):
        cfg = BeamlineConfig(motors=(MotorConfig(shorthand="x", description="X", pv="X:POS"),))
        assert not cfg.is_empty


class TestBeamlineConfigActiveDetector:
    """Verify active_detector_config returns the correct detector or None."""

    def test_no_detectors_returns_none(self):
        assert BeamlineConfig().active_detector_config is None

    def test_index_minus_one_returns_none(self):
        d = DetectorConfig(name="Eiger")
        cfg = BeamlineConfig(detectors=(d,), active_detector=-1)
        assert cfg.active_detector_config is None

    def test_valid_index_returns_correct_detector(self):
        d0 = DetectorConfig(name="Eiger")
        d1 = DetectorConfig(name="Pilatus")
        cfg = BeamlineConfig(detectors=(d0, d1), active_detector=1)
        assert cfg.active_detector_config is d1

    def test_index_out_of_range_returns_none(self):
        d = DetectorConfig(name="Eiger")
        cfg = BeamlineConfig(detectors=(d,), active_detector=5)
        assert cfg.active_detector_config is None


class TestBeamlineConfigWithMotors:
    """Verify with_motors() returns a new frozen instance with updated motors."""

    def test_returns_new_instance(self):
        cfg = BeamlineConfig(name="test")
        m = MotorConfig(shorthand="x", description="X", pv="X:POS")
        new_cfg = cfg.with_motors([m])
        assert new_cfg is not cfg

    def test_motors_updated(self):
        cfg = BeamlineConfig(name="test")
        m = MotorConfig(shorthand="y", description="Y", pv="Y:POS")
        new_cfg = cfg.with_motors([m])
        assert len(new_cfg.motors) == 1
        assert new_cfg.motors[0].shorthand == "y"

    def test_name_preserved(self):
        cfg = BeamlineConfig(name="original")
        new_cfg = cfg.with_motors([])
        assert new_cfg.name == "original"


class TestBeamlineConfigFrozen:
    """Verify BeamlineConfig is immutable - attribute assignment raises."""

    def test_cannot_mutate_name(self):
        cfg = BeamlineConfig(name="test")
        with pytest.raises((AttributeError, TypeError)):
            cfg.name = "other"  # type: ignore[misc]


class TestBeamlineConfigModelDirectory:
    """Verify BeamlineConfigModel uses and creates its config directory."""

    def test_uses_provided_directory(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        assert model.directory == tmp_path

    def test_creates_directory_if_missing(self, tmp_path):
        target = tmp_path / "new_configs"
        assert not target.exists()
        BeamlineConfigModel(directory=target)
        assert target.is_dir()


class TestBeamlineConfigModelListConfigNames:
    """Verify list_config_names() returns sorted TOML file stems, ignoring other files."""

    def test_empty_directory_returns_empty_list(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        assert model.list_config_names() == []

    def test_returns_toml_file_stems(self, tmp_path):
        (tmp_path / "alpha.toml").write_text("[]\n")
        (tmp_path / "beta.toml").write_text("[]\n")
        (tmp_path / "other.txt").write_text("")
        model = BeamlineConfigModel(directory=tmp_path)
        names = model.list_config_names()
        assert names == ["alpha", "beta"]

    def test_names_sorted_alphabetically(self, tmp_path):
        for name in ["zoo", "alpha", "middle"]:
            (tmp_path / f"{name}.toml").write_text("[]\n")
        model = BeamlineConfigModel(directory=tmp_path)
        assert model.list_config_names() == ["alpha", "middle", "zoo"]


class TestBeamlineConfigModelHasActive:
    """Verify has_active reflects whether a config has been loaded into the model."""

    def test_false_by_default(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        assert not model.has_active

    def test_true_after_loading_config_with_name(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        cfg = BeamlineConfig(name="test", beamline="13-ID", motors=(MotorConfig(shorthand="x", description="X", pv="X"),))
        model.save(cfg)
        model.load("test")
        assert model.has_active


class TestBeamlineConfigModelLoad:
    """Verify load() reads TOML configs and sets the active config."""

    def test_missing_file_returns_config_with_name(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        cfg = model.load("nonexistent")
        assert cfg.name == "nonexistent"

    def test_missing_file_returns_empty_config(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        cfg = model.load("nonexistent")
        assert cfg.is_empty or cfg.name == "nonexistent"

    def test_sets_active(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        model.save(BeamlineConfig(name="x"))
        model.load("x")
        assert model.active.name == "x"


class TestBeamlineConfigModelSave:
    """Verify save() writes a valid TOML file and enforces a non-empty name."""

    def test_save_creates_toml_file(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        cfg = BeamlineConfig(name="myconfig")
        path = model.save(cfg)
        assert path.exists()
        assert path.suffix == ".toml"

    def test_save_empty_name_raises(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        with pytest.raises(ValueError):
            model.save(BeamlineConfig(name=""))

    def test_save_whitespace_only_name_raises(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        with pytest.raises(ValueError):
            model.save(BeamlineConfig(name="   "))

    def test_save_sets_active(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        cfg = BeamlineConfig(name="saved")
        model.save(cfg)
        assert model.active.name == "saved"

    def test_returns_path_inside_directory(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        cfg = BeamlineConfig(name="cfg")
        path = model.save(cfg)
        assert path.parent == tmp_path


class TestBeamlineConfigRoundTrip:
    """Verify all config fields survive a save/load round-trip to TOML."""

    def test_basic_fields_preserved(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        cfg = BeamlineConfig(
            name="test",
            beamline="13-ID-C",
            shutter_pv="SHUTTER:PV",
            shutter_open_value="1",
            shutter_close_value="0",
            shutter_delay=0.05,
        )
        model.save(cfg)
        loaded = model.load("test")
        assert loaded.beamline == "13-ID-C"
        assert loaded.shutter_pv == "SHUTTER:PV"
        assert loaded.shutter_open_value == "1"
        assert loaded.shutter_delay == pytest.approx(0.05)

    def test_motors_preserved(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        m = MotorConfig(shorthand="x", description="X motor", pv="X:POS", precision=3)
        cfg = BeamlineConfig(name="m", motors=(m,))
        model.save(cfg)
        loaded = model.load("m")
        assert len(loaded.motors) == 1
        assert loaded.motors[0].shorthand == "x"
        assert loaded.motors[0].description == "X motor"
        assert loaded.motors[0].precision == 3

    def test_detectors_preserved(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        d = DetectorConfig(name="Eiger", pv_prefix="13EIG:", type="eiger", file_format="hdf5")
        cfg = BeamlineConfig(name="d", detectors=(d,), active_detector=0)
        model.save(cfg)
        loaded = model.load("d")
        assert len(loaded.detectors) == 1
        assert loaded.detectors[0].name == "Eiger"
        assert loaded.detectors[0].pv_prefix == "13EIG:"
        assert loaded.active_detector == 0

    def test_active_detector_flag_preserved(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        d0 = DetectorConfig(name="A", pv_prefix="A:")
        d1 = DetectorConfig(name="B", pv_prefix="B:")
        cfg = BeamlineConfig(name="two", detectors=(d0, d1), active_detector=1)
        model.save(cfg)
        loaded = model.load("two")
        assert loaded.active_detector == 1
        assert loaded.active_detector_config.name == "B"

    def test_rotation_motor_preserved(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        rm = MotorConfig(shorthand="omega", description="Omega", pv="OM:POS", beam_angle=12.5)
        cfg = BeamlineConfig(name="r", rotation_motor=rm)
        model.save(cfg)
        loaded = model.load("r")
        assert loaded.rotation_motor is not None
        assert loaded.rotation_motor.shorthand == "omega"
        assert loaded.rotation_motor.beam_angle == pytest.approx(12.5)

    def test_crysalis_fields_preserved(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        cfg = BeamlineConfig(
            name="cry",
            crysalis_wavelength=0.3100,
            crysalis_distance=150.0,
            crysalis_center_x=1024.0,
            crysalis_center_y=512.0,
        )
        model.save(cfg)
        loaded = model.load("cry")
        assert loaded.crysalis_wavelength == pytest.approx(0.3100)
        assert loaded.crysalis_distance == pytest.approx(150.0)
        assert loaded.crysalis_center_x == pytest.approx(1024.0)

    def test_abort_pvs_preserved(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        cfg = BeamlineConfig(name="a", abort_pvs=(("SHUTTER:ABORT", "1"), ("BEAM:OFF", "0")))
        model.save(cfg)
        loaded = model.load("a")
        assert len(loaded.abort_pvs) == 2
        assert ("SHUTTER:ABORT", "1") in loaded.abort_pvs

    def test_restore_pvs_preserved(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        cfg = BeamlineConfig(name="r", restore_pvs=("MOTOR:PV1", "MOTOR:PV2"))
        model.save(cfg)
        loaded = model.load("r")
        assert "MOTOR:PV1" in loaded.restore_pvs
        assert "MOTOR:PV2" in loaded.restore_pvs

    def test_raw_directory_preserved(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        cfg = BeamlineConfig(name="raw", raw_directory="/scratch/raw")
        model.save(cfg)
        loaded = model.load("raw")
        assert loaded.raw_directory == "/scratch/raw"

    def test_controllers_preserved(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        c = ControllerConfig(name="xps1", type="newport_xps", params={"host": "192.168.1.1"})
        cfg = BeamlineConfig(name="ctrl", controllers=(c,))
        model.save(cfg)
        loaded = model.load("ctrl")
        assert len(loaded.controllers) == 1
        assert loaded.controllers[0].name == "xps1"
        assert loaded.controllers[0].params.get("host") == "192.168.1.1"


class TestBeamlineConfigModelRememberActive:
    """Verify remember_active() persists the active config name across model instances."""

    def test_remember_and_get(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        model.remember_active("my_config")
        assert model.get_remembered_active_name() == "my_config"

    def test_get_returns_empty_when_no_marker(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        assert model.get_remembered_active_name() == ""

    def test_remember_empty_removes_marker(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        model.remember_active("something")
        model.remember_active("")
        assert model.get_remembered_active_name() == ""

    def test_clear_active_resets_state(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        cfg = BeamlineConfig(name="c", beamline="13-ID")
        model.save(cfg)
        model.load("c")
        model.clear_active()
        assert not model.has_active
        assert model.get_remembered_active_name() == ""


class TestBeamlineConfigModelExists:
    """Verify exists() checks whether a named TOML config file is present."""

    def test_true_for_existing_file(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        model.save(BeamlineConfig(name="exists"))
        assert model.exists("exists")

    def test_false_for_missing_file(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        assert not model.exists("missing")


class TestBeamlineConfigModelCreateBlank:
    """Verify create_blank() writes an empty TOML file with the given name."""

    def test_creates_file(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        model.create_blank("blank_cfg")
        assert (tmp_path / "blank_cfg.toml").is_file()

    def test_returned_config_has_correct_name(self, tmp_path):
        model = BeamlineConfigModel(directory=tmp_path)
        cfg = model.create_blank("named")
        assert cfg.name == "named"
