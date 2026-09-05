#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/model/test_format_converter.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for image format conversion helpers, source file discovery, and subprocess
# entry point.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from pathlib import Path
from unittest import mock

from crystalsweep.model.format_converter import (
    _find_source_files,
    _suffixes_for,
    convert_point,
    run_conversion,
)


class TestSuffixesFor:
    """Verify _suffixes_for() returns the correct file extension tuples per format."""

    def test_hdf5_returns_h5_and_hdf5(self):
        assert _suffixes_for("hdf5") == (".h5", ".hdf5")

    def test_cbf_returns_cbf(self):
        assert _suffixes_for("cbf") == (".cbf",)

    def test_tif_returns_tif_and_tiff(self):
        assert _suffixes_for("tif") == (".tif", ".tiff")

    def test_unknown_returns_empty_tuple(self):
        assert _suffixes_for("xyz") == ()

    def test_empty_string_returns_empty_tuple(self):
        assert _suffixes_for("") == ()


class TestFindSourceFiles:
    """Verify _find_source_files() discovers, deduplicates, and sorts matching files."""

    def test_empty_directory_returns_empty_list(self, tmp_path):
        result = _find_source_files(tmp_path, "sample_0001", "hdf5")
        assert result == []

    def test_finds_exact_basename_h5(self, tmp_path):
        f = tmp_path / "sample_0001.h5"
        f.touch()
        result = _find_source_files(tmp_path, "sample_0001", "hdf5")
        assert result == [f]

    def test_finds_basename_with_underscore_suffix_h5(self, tmp_path):
        f = tmp_path / "sample_0001_000001.h5"
        f.touch()
        result = _find_source_files(tmp_path, "sample_0001", "hdf5")
        assert result == [f]

    def test_finds_basename_with_underscore_suffix_cbf(self, tmp_path):
        f = tmp_path / "data_001_000001.cbf"
        f.touch()
        result = _find_source_files(tmp_path, "data_001", "cbf")
        assert result == [f]

    def test_ignores_wrong_suffix(self, tmp_path):
        (tmp_path / "sample_0001.cbf").touch()
        result = _find_source_files(tmp_path, "sample_0001", "hdf5")
        assert result == []

    def test_ignores_directories(self, tmp_path):
        d = tmp_path / "sample_0001.h5"
        d.mkdir()
        result = _find_source_files(tmp_path, "sample_0001", "hdf5")
        assert result == []

    def test_returns_sorted_list(self, tmp_path):
        files = [
            tmp_path / "run_0001_003.h5",
            tmp_path / "run_0001_001.h5",
            tmp_path / "run_0001_002.h5",
        ]
        for f in files:
            f.touch()
        result = _find_source_files(tmp_path, "run_0001", "hdf5")
        assert result == sorted(files)

    def test_deduplicates_results(self, tmp_path):
        f = tmp_path / "scan.h5"
        f.touch()
        result = _find_source_files(tmp_path, "scan", "hdf5")
        assert len(result) == 1

    def test_unknown_format_returns_empty_list(self, tmp_path):
        (tmp_path / "sample.xyz").touch()
        result = _find_source_files(tmp_path, "sample", "xyz")
        assert result == []

    def test_tif_finds_tiff_extension(self, tmp_path):
        f = tmp_path / "frame.tiff"
        f.touch()
        result = _find_source_files(tmp_path, "frame", "tif")
        assert result == [f]

    def test_tif_finds_tif_extension(self, tmp_path):
        f = tmp_path / "frame.tif"
        f.touch()
        result = _find_source_files(tmp_path, "frame", "tif")
        assert result == [f]


class TestRunConversion:
    """Verify run_conversion() early-exits on missing args and delegates correctly."""

    def test_returns_without_error_when_directory_missing(self):
        run_conversion({"basename": "sample", "source_format": "hdf5", "target_formats": ["cbf"]})

    def test_returns_without_error_when_basename_missing(self):
        run_conversion({"directory": "/some/path", "source_format": "hdf5", "target_formats": ["cbf"]})

    def test_returns_without_error_when_directory_not_on_disk(self):
        run_conversion(
            {
                "directory": "/does/not/exist/ever",
                "basename": "sample",
                "source_format": "hdf5",
                "target_formats": ["cbf"],
            }
        )

    def test_calls_convert_point_with_correct_args(self, tmp_path):
        with mock.patch("crystalsweep.model.format_converter.convert_point") as mock_cp:
            run_conversion(
                {
                    "directory": str(tmp_path),
                    "basename": "scan_0001",
                    "source_format": "hdf5",
                    "target_formats": ["cbf", "tif"],
                    "file_number_width": 6,
                    "output_dirs": {"cbf": str(tmp_path / "cbf_out")},
                }
            )
            mock_cp.assert_called_once()
            call_args = mock_cp.call_args
            positional = call_args[0]
            keyword = call_args[1]
            assert positional[0] == tmp_path
            assert positional[1] == "scan_0001"
            assert positional[2] == "hdf5"
            assert positional[3] == ["cbf", "tif"]
            assert positional[4] == 6 or keyword.get("file_number_width") == 6
            output_dirs = positional[5] if len(positional) > 5 else keyword.get("output_dirs", {})
            assert "cbf" in output_dirs


class TestConvertPoint:
    """Verify convert_point() handles missing sources and respects output_dirs overrides."""

    def test_returns_without_error_when_target_formats_only_contains_source(self, tmp_path):
        convert_point(tmp_path, "sample", "hdf5", ["hdf5"])

    def test_returns_without_error_when_directory_does_not_exist(self):
        convert_point(Path("/no/such/path"), "sample", "hdf5", ["cbf"])

    def test_returns_without_error_when_no_source_files_found(self, tmp_path):
        convert_point(tmp_path, "missing_sample", "hdf5", ["cbf"])

    def test_fallback_output_dir_is_basename_fmt(self, tmp_path):
        src = tmp_path / "scan.h5"
        src.touch()
        with mock.patch("crystalsweep.model.format_converter._convert_to") as mock_ct:
            mock_ct.return_value = 0
            convert_point(tmp_path, "scan", "hdf5", ["cbf"])
            mock_ct.assert_called_once()
            target_dir_arg = mock_ct.call_args[0][1]
            assert target_dir_arg == tmp_path / "scan_cbf"

    def test_explicit_output_dirs_override_fallback(self, tmp_path):
        src = tmp_path / "scan.h5"
        src.touch()
        custom_out = tmp_path / "custom_out"
        with mock.patch("crystalsweep.model.format_converter._convert_to") as mock_ct:
            mock_ct.return_value = 0
            convert_point(tmp_path, "scan", "hdf5", ["cbf"], output_dirs={"cbf": custom_out})
            target_dir_arg = mock_ct.call_args[0][1]
            assert target_dir_arg == custom_out

    def test_skips_extra_equal_to_source_format(self, tmp_path):
        src = tmp_path / "scan.h5"
        src.touch()
        with mock.patch("crystalsweep.model.format_converter._convert_to") as mock_ct:
            convert_point(tmp_path, "scan", "hdf5", ["hdf5", "cbf"])
            assert mock_ct.call_count == 1
            assert mock_ct.call_args[0][3] == "cbf"
