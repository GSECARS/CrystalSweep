#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/model/test_detector_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for area detector model prefix normalisation, protocol compliance, frame
# counting, and plugin arming.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from unittest.mock import patch

from crystalsweep.model.detector_model import (
    ADEigerModel,
    ADPilatusModel,
    ADSpinnakerModel,
    DetectorModel,
    _file_plugin,
    get_detector_model,
)


class TestFilePlugin:
    """Verify _file_plugin() maps format strings to EPICS plugin names."""

    def test_hdf5_returns_hdf1(self):
        assert _file_plugin("hdf5") == "HDF1"

    def test_cbf_returns_tiff1(self):
        assert _file_plugin("cbf") == "TIFF1"

    def test_tif_returns_tiff1(self):
        assert _file_plugin("tif") == "TIFF1"

    def test_unknown_format_falls_back_to_hdf1(self):
        assert _file_plugin("png") == "HDF1"

    def test_empty_string_falls_back_to_hdf1(self):
        assert _file_plugin("") == "HDF1"


class TestPrefixNormalizationEiger:
    """Verify ADEigerModel normalises the PV prefix."""

    def test_prefix_without_colon_gets_colon_appended(self):
        with patch("crystalsweep.model.detector_model.caget"):
            model = ADEigerModel("DET1")
        assert model._prefix == "DET1:"

    def test_prefix_with_colon_not_doubled(self):
        with patch("crystalsweep.model.detector_model.caget"):
            model = ADEigerModel("DET1:")
        assert model._prefix == "DET1:"

    def test_prefix_with_leading_trailing_whitespace_stripped(self):
        with patch("crystalsweep.model.detector_model.caget"):
            model = ADEigerModel("  DET1  ")
        assert model._prefix == "DET1:"


class TestPrefixNormalizationPilatus:
    """Verify ADPilatusModel normalises the PV prefix."""

    def test_prefix_without_colon_gets_colon_appended(self):
        with patch("crystalsweep.model.detector_model.caget"):
            model = ADPilatusModel("PIL1")
        assert model._prefix == "PIL1:"

    def test_prefix_with_colon_not_doubled(self):
        with patch("crystalsweep.model.detector_model.caget"):
            model = ADPilatusModel("PIL1:")
        assert model._prefix == "PIL1:"

    def test_prefix_with_leading_trailing_whitespace_stripped(self):
        with patch("crystalsweep.model.detector_model.caget"):
            model = ADPilatusModel("  PIL1  ")
        assert model._prefix == "PIL1:"


class TestPrefixNormalizationSpinnaker:
    """Verify ADSpinnakerModel normalises the PV prefix."""

    def test_prefix_without_colon_gets_colon_appended(self):
        with patch("crystalsweep.model.detector_model.caget"):
            model = ADSpinnakerModel("CAM1")
        assert model._prefix == "CAM1:"

    def test_prefix_with_colon_not_doubled(self):
        with patch("crystalsweep.model.detector_model.caget"):
            model = ADSpinnakerModel("CAM1:")
        assert model._prefix == "CAM1:"

    def test_prefix_with_leading_trailing_whitespace_stripped(self):
        with patch("crystalsweep.model.detector_model.caget"):
            model = ADSpinnakerModel("  CAM1  ")
        assert model._prefix == "CAM1:"


class TestGetDetectorModel:
    """Verify get_detector_model() returns the correct class for known types and falls back for unknown ones."""

    def test_eiger_returns_adeigermodel(self):
        model = get_detector_model("eiger", "DET1:")
        assert isinstance(model, ADEigerModel)

    def test_pilatus_returns_adpilatusmodel(self):
        model = get_detector_model("pilatus", "DET1:")
        assert isinstance(model, ADPilatusModel)

    def test_spinnaker_returns_adspinnakermodel(self):
        model = get_detector_model("spinnaker", "DET1:")
        assert isinstance(model, ADSpinnakerModel)

    def test_unknown_type_falls_back_to_adeigermodel(self):
        model = get_detector_model("unknown_detector", "DET1:")
        assert isinstance(model, ADEigerModel)


class TestProtocolCompliance:
    """Verify all concrete detector models satisfy the DetectorModel protocol."""

    def test_eiger_satisfies_detector_model_protocol(self):
        model = ADEigerModel("DET1:")
        assert isinstance(model, DetectorModel)

    def test_pilatus_satisfies_detector_model_protocol(self):
        model = ADPilatusModel("DET1:")
        assert isinstance(model, DetectorModel)

    def test_spinnaker_satisfies_detector_model_protocol(self):
        model = ADSpinnakerModel("DET1:")
        assert isinstance(model, DetectorModel)


class TestADEigerFramesCaptured:
    """Verify frames_captured() reads NumImagesCounter_RBV and handles None."""

    def test_returns_int_value_from_pv(self):
        with patch("crystalsweep.model.detector_model.caget", return_value=42) as mock_caget:
            model = ADEigerModel("DET1:")
            result = model.frames_captured()
        assert result == 42
        mock_caget.assert_called_with("DET1:cam1:NumImagesCounter_RBV")

    def test_returns_zero_when_caget_returns_none(self):
        with patch("crystalsweep.model.detector_model.caget", return_value=None):
            model = ADEigerModel("DET1:")
            result = model.frames_captured()
        assert result == 0


class TestADPilatusFramesCaptured:
    """Verify frames_captured() subtracts the snapshot baseline and handles exceptions."""

    def test_subtracts_baseline_from_snapshot(self):
        model = ADPilatusModel("PIL1:")
        call_count = 0

        def side_effect(pv):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 10
            return 15

        with patch("crystalsweep.model.detector_model.caget", side_effect=side_effect):
            model._snapshot_array_counter()
            result = model.frames_captured()

        assert result == 5

    def test_returns_zero_when_caget_raises(self):
        model = ADPilatusModel("PIL1:")
        with patch("crystalsweep.model.detector_model.caget", side_effect=Exception("CA error")):
            result = model.frames_captured()
        assert result == 0


class TestADEigerArmPlugin:
    """Verify arm_plugin() targets the correct plugin PVs based on file format."""

    def test_hdf5_format_arms_hdf1_plugin(self):
        model = ADEigerModel("DET1:", file_format="hdf5")
        with patch("crystalsweep.model.detector_model.caput") as mock_caput:
            model.arm_plugin(10)
        mock_caput.assert_any_call("DET1:HDF1:NumCapture", 10)
        mock_caput.assert_any_call("DET1:HDF1:Capture", 1)

    def test_hdf5_format_does_not_call_tiff1(self):
        model = ADEigerModel("DET1:", file_format="hdf5")
        with patch("crystalsweep.model.detector_model.caput") as mock_caput:
            model.arm_plugin(10)
        called_pvs = [c.args[0] for c in mock_caput.call_args_list]
        assert not any("TIFF1" in pv for pv in called_pvs)

    def test_cbf_format_arms_tiff1_plugin(self):
        model = ADEigerModel("DET1:", file_format="cbf")
        with patch("crystalsweep.model.detector_model.caput") as mock_caput:
            model.arm_plugin(5)
        mock_caput.assert_any_call("DET1:TIFF1:NumCapture", 5)
        mock_caput.assert_any_call("DET1:TIFF1:Capture", 1)

    def test_cbf_format_does_not_call_hdf1(self):
        model = ADEigerModel("DET1:", file_format="cbf")
        with patch("crystalsweep.model.detector_model.caput") as mock_caput:
            model.arm_plugin(5)
        called_pvs = [c.args[0] for c in mock_caput.call_args_list]
        assert not any("HDF1" in pv for pv in called_pvs)
