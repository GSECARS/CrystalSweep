#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/model/test_crysalis_converter.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for CrysAlis output directory creation, calibration file copying, and PAR
# file rewriting.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import logging
import os
from unittest.mock import patch

from crystalsweep.model.crysalis_converter import (
    _copy_set_ccd,
    _create_par_file,
    _make_directory,
    run_conversion,
)


class TestMakeDirectory:
    """Verify _make_directory() creates a clean output directory at the expected path."""

    def test_creates_directory_at_output_dir(self, tmp_path):
        output = str(tmp_path / "out")
        result = _make_directory(str(tmp_path), "sample", output_dir=output)
        assert os.path.isdir(output)
        assert result == os.path.normpath(output)

    def test_creates_filepath_basename_crys_when_no_output_dir(self, tmp_path):
        result = _make_directory(str(tmp_path), "sample")
        expected = os.path.normpath(os.path.join(str(tmp_path), "sample_crys"))
        assert result == expected
        assert os.path.isdir(expected)

    def test_removes_and_recreates_existing_directory(self, tmp_path):
        """An existing directory is wiped and recreated, removing stale contents."""
        target = tmp_path / "sample_crys"
        target.mkdir()
        (target / "leftover.txt").write_text("old")
        _make_directory(str(tmp_path), "sample")
        assert os.path.isdir(str(target))
        assert not (target / "leftover.txt").exists()

    def test_returns_string(self, tmp_path):
        result = _make_directory(str(tmp_path), "sample")
        assert isinstance(result, str)

    def test_accepts_path_args(self, tmp_path):
        result = _make_directory(tmp_path, "sample")
        assert os.path.isdir(result)


class TestCopySetCcd:
    """Verify _copy_set_ccd() copies companion files and warns when they are missing."""

    def _write(self, path, content="data"):
        path.write_text(content)
        return path

    def test_copies_set_from_par_file_when_set_file_empty(self, tmp_path):
        par = self._write(tmp_path / "calib.par")
        self._write(tmp_path / "calib.set", "set-content")
        self._write(tmp_path / "calib.ccd", "ccd-content")
        dest = tmp_path / "dest"
        dest.mkdir()
        _copy_set_ccd(str(dest), "out", str(par))
        assert (dest / "out.set").read_text() == "set-content"

    def test_copies_ccd_from_par_file_when_ccd_file_empty(self, tmp_path):
        par = self._write(tmp_path / "calib.par")
        self._write(tmp_path / "calib.set", "set-content")
        self._write(tmp_path / "calib.ccd", "ccd-content")
        dest = tmp_path / "dest"
        dest.mkdir()
        _copy_set_ccd(str(dest), "out", str(par))
        assert (dest / "out.ccd").read_text() == "ccd-content"

    def test_uses_explicit_set_file_when_provided(self, tmp_path):
        par = self._write(tmp_path / "calib.par")
        explicit_set = self._write(tmp_path / "explicit.set", "explicit-set")
        self._write(tmp_path / "calib.ccd", "ccd-content")
        dest = tmp_path / "dest"
        dest.mkdir()
        _copy_set_ccd(str(dest), "out", str(par), set_file=str(explicit_set))
        assert (dest / "out.set").read_text() == "explicit-set"

    def test_uses_explicit_ccd_file_when_provided(self, tmp_path):
        par = self._write(tmp_path / "calib.par")
        self._write(tmp_path / "calib.set", "set-content")
        explicit_ccd = self._write(tmp_path / "explicit.ccd", "explicit-ccd")
        dest = tmp_path / "dest"
        dest.mkdir()
        _copy_set_ccd(str(dest), "out", str(par), ccd_file=str(explicit_ccd))
        assert (dest / "out.ccd").read_text() == "explicit-ccd"

    def test_logs_warning_when_derived_set_missing(self, tmp_path, caplog):
        par = self._write(tmp_path / "calib.par")
        self._write(tmp_path / "calib.ccd", "ccd-content")
        dest = tmp_path / "dest"
        dest.mkdir()
        with caplog.at_level(logging.WARNING):
            _copy_set_ccd(str(dest), "out", str(par))
        assert any(".set" in r.message for r in caplog.records)

    def test_does_not_raise_when_companion_files_missing(self, tmp_path):
        par = self._write(tmp_path / "calib.par")
        dest = tmp_path / "dest"
        dest.mkdir()
        _copy_set_ccd(str(dest), "out", str(par))

    def test_copies_to_basename_set_and_ccd(self, tmp_path):
        par = self._write(tmp_path / "calib.par")
        self._write(tmp_path / "calib.set", "s")
        self._write(tmp_path / "calib.ccd", "c")
        dest = tmp_path / "dest"
        dest.mkdir()
        _copy_set_ccd(str(dest), "mybase", str(par))
        assert (dest / "mybase.set").exists()
        assert (dest / "mybase.ccd").exists()


class TestCreateParFile:
    """Verify _create_par_file() rewrites FILE CHIP lines and passes all others through."""

    def test_creates_par_file_in_new_directory(self, tmp_path):
        src = tmp_path / "orig.par"
        src.write_text("SOME LINE\n")
        dest = tmp_path / "dest"
        dest.mkdir()
        _create_par_file(str(dest), "out", str(src))
        assert (dest / "out.par").exists()

    def test_passes_through_non_file_chip_lines(self, tmp_path):
        src = tmp_path / "orig.par"
        src.write_text("FIRST LINE\nSECOND LINE\n")
        dest = tmp_path / "dest"
        dest.mkdir()
        _create_par_file(str(dest), "out", str(src))
        content = (dest / "out.par").read_text()
        assert "FIRST LINE" in content
        assert "SECOND LINE" in content

    def test_replaces_file_chip_line(self, tmp_path):
        """FILE CHIP lines are rewritten to reference the new basename."""
        src = tmp_path / "orig.par"
        src.write_text("FILE CHIP old.ccd \n")
        dest = tmp_path / "dest"
        dest.mkdir()
        _create_par_file(str(dest), "mybase", str(src))
        content = (dest / "mybase.par").read_text()
        assert "FILE CHIP mybase.ccd \n" in content
        assert "old.ccd" not in content

    def test_handles_multiple_non_matching_lines(self, tmp_path):
        src = tmp_path / "orig.par"
        src.write_text("LINE A\nLINE B\nLINE C\n")
        dest = tmp_path / "dest"
        dest.mkdir()
        _create_par_file(str(dest), "out", str(src))
        content = (dest / "out.par").read_text()
        assert content == "LINE A\nLINE B\nLINE C\n"

    def test_mixed_lines_with_file_chip(self, tmp_path):
        src = tmp_path / "orig.par"
        src.write_text("HEADER\nFILE CHIP original.ccd \nFOOTER\n")
        dest = tmp_path / "dest"
        dest.mkdir()
        _create_par_file(str(dest), "newbase", str(src))
        content = (dest / "newbase.par").read_text()
        assert content == "HEADER\nFILE CHIP newbase.ccd \nFOOTER\n"


class TestRunConversion:
    """Verify run_conversion() routes to the correct format-specific converter."""

    def _base_args(self, tmp_path):
        return {
            "filepath": str(tmp_path),
            "basename": "sample",
            "filenumber": 1,
            "par_file": str(tmp_path / "nonexistent.par"),
            "set_file": "",
            "ccd_file": "",
            "scan_info": {},
            "file_format": "hdf5",
        }

    def test_missing_par_file_does_not_raise(self, tmp_path):
        args = self._base_args(tmp_path)
        with patch("crystalsweep.model.crysalis_converter._create_crysalis_run"), patch("crystalsweep.model.crysalis_converter._convert_hdf5"):
            run_conversion(args)

    def test_hdf5_format_calls_convert_hdf5(self, tmp_path):
        args = self._base_args(tmp_path)
        args["file_format"] = "hdf5"
        with patch("crystalsweep.model.crysalis_converter._create_crysalis_run"), patch("crystalsweep.model.crysalis_converter._convert_hdf5") as mock_hdf5:
            run_conversion(args)
            mock_hdf5.assert_called_once()

    def test_cbf_format_calls_convert_cbf(self, tmp_path):
        args = self._base_args(tmp_path)
        args["file_format"] = "cbf"
        with patch("crystalsweep.model.crysalis_converter._create_crysalis_run"), patch("crystalsweep.model.crysalis_converter._convert_cbf") as mock_cbf:
            run_conversion(args)
            mock_cbf.assert_called_once()

    def test_hdf5_format_does_not_call_convert_cbf(self, tmp_path):
        args = self._base_args(tmp_path)
        args["file_format"] = "hdf5"
        with (
            patch("crystalsweep.model.crysalis_converter._create_crysalis_run"),
            patch("crystalsweep.model.crysalis_converter._convert_hdf5"),
            patch("crystalsweep.model.crysalis_converter._convert_cbf") as mock_cbf,
        ):
            run_conversion(args)
            mock_cbf.assert_not_called()
