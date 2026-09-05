#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/utils/test_output_paths.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for OutputPaths path derivation covering all scan types and conversion layouts.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------
from pathlib import Path

import pytest

from crystalsweep.model.collection_model import CollectionPoint
from crystalsweep.utils.output_paths import OutputPaths


def _make_output(
    directory="/data/out",
    raw_directory=None,
    filename="sample",
    map_ext="map",
    use_ext=True,
    file_ext="h5",
    file_number_width=4,
    source_format="hdf5",
    extras=(),
    use_crysalis=False,
) -> OutputPaths:
    return OutputPaths(
        directory=Path(directory),
        raw_directory=Path(raw_directory) if raw_directory else None,
        filename=filename,
        map_ext=map_ext,
        use_ext=use_ext,
        file_ext=file_ext,
        file_number_width=file_number_width,
        source_format=source_format,
        extras=extras,
        use_crysalis=use_crysalis,
    )


def _still_point(label="posA") -> CollectionPoint:
    return CollectionPoint(label=label, motor_positions={}, scan_type="still")


def _step_point(label="posB") -> CollectionPoint:
    return CollectionPoint(label=label, motor_positions={}, scan_type="step")


def _wide_point(label="posC") -> CollectionPoint:
    return CollectionPoint(label=label, motor_positions={}, scan_type="wide")


def _map_point(label="sample_map_002", group="g1", row=0, col=1) -> CollectionPoint:
    return CollectionPoint(
        label=label,
        motor_positions={},
        scan_type="still",
        map_group=group,
        map_row=row,
        map_col=col,
    )


class TestExtForFormat:
    """Verify ext_for_format() maps source format strings to file extensions."""

    def test_hdf5_maps_to_h5(self):
        assert OutputPaths.ext_for_format("hdf5") == "h5"

    def test_cbf_maps_to_cbf(self):
        assert OutputPaths.ext_for_format("cbf") == "cbf"

    def test_tif_maps_to_tif(self):
        assert OutputPaths.ext_for_format("tif") == "tif"

    def test_unknown_format_returns_itself(self):
        assert OutputPaths.ext_for_format("xyz") == "xyz"

    def test_empty_string_returns_empty(self):
        assert OutputPaths.ext_for_format("") == ""


class TestStem:
    """Verify stem() output for each scan type."""

    def test_non_map_with_label_when_use_ext_true(self):
        output = _make_output(filename="sample", use_ext=True)
        point = _still_point(label="pos1")
        assert output.stem(point) == "sample_pos1"

    def test_non_map_without_label_when_use_ext_false(self):
        output = _make_output(filename="sample", use_ext=False)
        point = _still_point(label="pos1")
        assert output.stem(point) == "sample"

    def test_non_map_empty_label_trimmed(self):
        output = _make_output(filename="run", use_ext=True)
        point = _still_point(label="   ")
        assert output.stem(point) == "run"

    def test_non_map_empty_filename_only_label(self):
        output = _make_output(filename="", use_ext=True)
        point = _still_point(label="frame")
        assert output.stem(point) == "frame"

    def test_non_map_empty_filename_empty_label_returns_empty(self):
        output = _make_output(filename="", use_ext=True)
        point = _still_point(label="")
        assert output.stem(point) == ""

    def test_map_point_uses_map_folder_name(self):
        output = _make_output(filename="sample", map_ext="map")
        point = _map_point()
        assert output.stem(point) == "sample_map"

    def test_map_point_ignores_point_label(self):
        output = _make_output(filename="x", map_ext="scan")
        point = _map_point(label="something_completely_different")
        assert output.stem(point) == "x_scan"


class TestBasename:
    """Verify basename() pads frame numbers and handles map label parsing."""

    def test_non_map_pads_frame_number(self):
        output = _make_output(filename="s", use_ext=True, file_number_width=4)
        point = _still_point(label="p")
        assert output.basename(point, 7) == "s_p_0007"

    def test_non_map_uses_given_frame_number(self):
        output = _make_output(filename="s", use_ext=False, file_number_width=4)
        point = _still_point(label="label")
        assert output.basename(point, 42) == "s_0042"

    def test_non_map_width_one(self):
        output = _make_output(filename="x", use_ext=False, file_number_width=1)
        point = _still_point()
        assert output.basename(point, 5) == "x_5"

    def test_map_parses_number_from_label(self):
        output = _make_output(filename="sample", map_ext="map", file_number_width=4)
        point = _map_point(label="map_0005_0007")
        assert output.basename(point, 999) == "sample_map_0005_0007"

    def test_map_falls_back_to_frame_number_when_label_unparseable(self):
        output = _make_output(filename="sample", map_ext="map", file_number_width=4)
        point = _map_point(label="no_numeric_suffix_here_abc")
        assert output.basename(point, 3) == "sample_map_0003"

    def test_map_single_segment_label_falls_back(self):
        output = _make_output(filename="s", map_ext="map", file_number_width=4)
        point = _map_point(label="justlabel")
        assert output.basename(point, 1) == "s_map_0001"

    def test_width_clamped_to_at_least_one(self):
        output = _make_output(filename="s", use_ext=False, file_number_width=0)
        point = _still_point()
        assert output.basename(point, 5) == "s_5"


class TestSourceDir:
    """Verify source_dir() resolves raw vs output directory for each scan type."""

    def test_non_map_without_raw_uses_directory(self):
        output = _make_output(directory="/data/out", raw_directory=None)
        assert output.source_dir(_still_point()) == Path("/data/out")

    def test_non_map_with_raw_uses_raw(self):
        output = _make_output(directory="/data/out", raw_directory="/raw")
        assert output.source_dir(_still_point()) == Path("/raw")

    def test_map_without_raw_appends_folder_name(self):
        output = _make_output(directory="/data/out", raw_directory=None, filename="s", map_ext="map")
        assert output.source_dir(_map_point()) == Path("/data/out/s_map")

    def test_map_with_raw_appends_folder_name_to_raw(self):
        output = _make_output(directory="/data/out", raw_directory="/raw", filename="s", map_ext="map")
        assert output.source_dir(_map_point()) == Path("/raw/s_map")


class TestOutputDir:
    """Verify output_dir() returns the correct destination folder for each scan type and conversion layout."""

    def test_still_point_no_extras_is_flat(self):
        output = _make_output(directory="/out", extras=(), use_crysalis=False)
        assert output.output_dir(_still_point(), 1) == Path("/out")

    def test_wide_point_no_extras_is_flat(self):
        output = _make_output(directory="/out", extras=(), use_crysalis=False)
        assert output.output_dir(_wide_point(), 1) == Path("/out")

    def test_step_point_no_extras_no_crysalis_is_flat(self):
        output = _make_output(directory="/out", extras=(), use_crysalis=False)
        assert output.output_dir(_step_point(label="pt"), 1) == Path("/out")

    def test_step_point_with_extras_creates_subfolder(self):
        output = _make_output(directory="/out", filename="s", extras=("cbf",), use_ext=False, file_number_width=4)
        point = _step_point(label="label")
        assert output.output_dir(point, 1) == Path("/out/s_0001")

    def test_step_point_with_crysalis_creates_subfolder(self):
        output = _make_output(directory="/out", filename="s", use_ext=False, extras=(), use_crysalis=True, file_number_width=4)
        assert output.output_dir(_step_point(), 2) == Path("/out/s_0002")

    def test_map_point_uses_map_folder(self):
        output = _make_output(directory="/out", filename="s", map_ext="scan")
        assert output.output_dir(_map_point(), 1) == Path("/out/s_scan")


class TestConversionDirs:
    """Verify conversion_dirs() maps each extra format to its output subfolder."""

    def test_empty_extras_returns_empty_dict(self):
        output = _make_output(extras=())
        assert output.conversion_dirs(_still_point(), 1) == {}

    def test_still_non_map_extras_are_flat_in_directory(self):
        output = _make_output(directory="/out", extras=("cbf", "tif"))
        dirs = output.conversion_dirs(_still_point(), 1)
        assert dirs == {"cbf": Path("/out"), "tif": Path("/out")}

    def test_wide_non_map_extras_are_flat(self):
        output = _make_output(directory="/out", extras=("cbf",))
        dirs = output.conversion_dirs(_wide_point(), 1)
        assert dirs == {"cbf": Path("/out")}

    def test_step_non_map_extras_in_basename_subfolder(self):
        output = _make_output(directory="/out", filename="s", use_ext=False, extras=("cbf",), file_number_width=4)
        dirs = output.conversion_dirs(_step_point(), 5)
        assert dirs == {"cbf": Path("/out/s_0005/cbf")}

    def test_step_multiple_formats(self):
        output = _make_output(directory="/out", filename="x", use_ext=False, extras=("cbf", "tif"), file_number_width=4)
        dirs = output.conversion_dirs(_step_point(), 1)
        assert dirs["cbf"] == Path("/out/x_0001/cbf")
        assert dirs["tif"] == Path("/out/x_0001/tif")

    def test_map_extras_go_into_conversion_root(self):
        output = _make_output(directory="/out", filename="s", map_ext="map", extras=("cbf",))
        dirs = output.conversion_dirs(_map_point(), 1)
        assert dirs == {"cbf": Path("/out/s_map/s_map/cbf")}

    def test_map_multiple_formats(self):
        output = _make_output(directory="/out", filename="r", map_ext="scan", extras=("cbf", "tif"))
        dirs = output.conversion_dirs(_map_point(), 1)
        assert dirs["cbf"] == Path("/out/r_scan/r_scan/cbf")
        assert dirs["tif"] == Path("/out/r_scan/r_scan/tif")


class TestCrysalisSourceDir:
    """Verify crysalis_source_dir() reads from where the IOC wrote the files."""

    def test_non_map_uses_raw_directory_when_set(self):
        output = _make_output(directory="/out", raw_directory="/raw")
        assert output.crysalis_source_dir(_still_point()) == Path("/raw")

    def test_non_map_step_uses_raw_directory_when_set(self):
        output = _make_output(directory="/out", raw_directory="/raw/somewhere")
        assert output.crysalis_source_dir(_step_point()) == Path("/raw/somewhere")

    def test_non_map_falls_back_to_directory_without_raw(self):
        output = _make_output(directory="/out", raw_directory=None)
        assert output.crysalis_source_dir(_step_point()) == Path("/out")

    def test_map_appends_folder_name_to_directory(self):
        output = _make_output(directory="/out", raw_directory="/raw", filename="s", map_ext="map")
        assert output.crysalis_source_dir(_map_point()) == Path("/out/s_map")

    def test_map_no_raw_still_uses_directory(self):
        output = _make_output(directory="/out", raw_directory=None, filename="s", map_ext="map")
        assert output.crysalis_source_dir(_map_point()) == Path("/out/s_map")


class TestCrysalisOutputDir:
    """Verify crysalis_output_dir() places the crysalis subfolder under the correct basename directory."""

    def test_non_map_is_directory_slash_basename_slash_crysalis(self):
        output = _make_output(directory="/out", filename="s", use_ext=False, file_number_width=4)
        result = output.crysalis_output_dir(_step_point(), 3)
        assert result == Path("/out/s_0003/crysalis")

    def test_non_map_label_included_when_use_ext_true(self):
        output = _make_output(directory="/out", filename="s", use_ext=True, file_number_width=4)
        result = output.crysalis_output_dir(_step_point(label="pt"), 1)
        assert result == Path("/out/s_pt_0001/crysalis")

    def test_map_is_inside_map_conversion_root(self):
        output = _make_output(directory="/out", filename="s", map_ext="map", file_number_width=4)
        point = _map_point(label="map_0005_0007")
        result = output.crysalis_output_dir(point, 999)
        assert result == Path("/out/s_map/s_map/crysalis/s_map_0005_0007")


class TestExpectedFile:
    """Verify expected_file() constructs the full path to the detector output file."""

    def test_non_map_in_source_dir(self):
        output = _make_output(directory="/out", raw_directory=None, filename="s", use_ext=False, file_ext="h5", file_number_width=4)
        f = output.expected_file(_still_point(), 1)
        assert f == Path("/out/s_0001.h5")

    def test_non_map_with_raw_in_raw_dir(self):
        output = _make_output(directory="/out", raw_directory="/raw", filename="s", use_ext=False, file_ext="h5", file_number_width=4)
        f = output.expected_file(_still_point(), 1)
        assert f == Path("/raw/s_0001.h5")

    def test_cbf_extension(self):
        output = _make_output(directory="/out", file_ext="cbf", filename="s", use_ext=False, file_number_width=4, source_format="cbf")
        f = output.expected_file(_still_point(), 2)
        assert f == Path("/out/s_0002.cbf")

    def test_map_in_map_source_dir(self):
        output = _make_output(directory="/out", raw_directory=None, filename="s", map_ext="map", file_ext="h5", file_number_width=4)
        point = _map_point(label="map_0005_0003")
        f = output.expected_file(point, 999)
        assert f == Path("/out/s_map/s_map_0005_0003.h5")


class TestMapFolderName:
    """Verify map_folder_name() combines filename and map_ext with a fallback default."""

    def test_with_filename_and_map_ext(self):
        output = _make_output(filename="sample", map_ext="scan")
        assert output.map_folder_name() == "sample_scan"

    def test_with_filename_and_empty_map_ext_defaults_to_map(self):
        output = _make_output(filename="sample", map_ext="")
        assert output.map_folder_name() == "sample_map"

    def test_without_filename(self):
        output = _make_output(filename="", map_ext="data")
        assert output.map_folder_name() == "data"

    def test_without_filename_and_empty_ext(self):
        output = _make_output(filename="", map_ext="")
        assert output.map_folder_name() == "map"


class TestMapSourceDir:
    """Verify map_source_dir() appends the map folder name to the raw or output directory."""

    def test_without_raw(self):
        output = _make_output(directory="/out", raw_directory=None, filename="s", map_ext="map")
        assert output.map_source_dir() == Path("/out/s_map")

    def test_with_raw(self):
        output = _make_output(directory="/out", raw_directory="/raw", filename="s", map_ext="map")
        assert output.map_source_dir() == Path("/raw/s_map")


class TestMapFlippedDir:
    """Verify map_flipped_dir() returns the flipped subdirectory inside map_source_dir."""

    def test_is_inside_map_source_dir(self):
        output = _make_output(directory="/out", raw_directory=None, filename="s", map_ext="map")
        assert output.map_flipped_dir() == Path("/out/s_map/flipped")

    def test_with_raw_is_inside_raw_map_dir(self):
        output = _make_output(directory="/out", raw_directory="/raw", filename="s", map_ext="map")
        assert output.map_flipped_dir() == Path("/raw/s_map/flipped")


class TestMapCombinedPath:
    """Verify map_combined_path() returns the merged HDF5 output path in the output directory."""

    def test_is_in_output_directory(self):
        output = _make_output(directory="/out", filename="s", map_ext="map")
        assert output.map_combined_path() == Path("/out/s_map.h5")

    def test_uses_file_ext_h5_always(self):
        output = _make_output(directory="/out", filename="s", map_ext="scan")
        assert output.map_combined_path() == Path("/out/s_scan.h5")

    def test_without_filename(self):
        output = _make_output(directory="/out", filename="", map_ext="")
        assert output.map_combined_path() == Path("/out/map.h5")


class TestMapRowPattern:
    """Verify map_row_pattern() returns a glob pattern matching per-row map files."""

    def test_hdf5_uses_h5_extension(self):
        output = _make_output(filename="s", map_ext="map", file_ext="h5")
        assert output.map_row_pattern() == "s_map_*.h5"

    def test_cbf_uses_cbf_extension(self):
        output = _make_output(filename="s", map_ext="scan", file_ext="cbf")
        assert output.map_row_pattern() == "s_scan_*.cbf"

    def test_without_filename(self):
        output = _make_output(filename="", map_ext="", file_ext="h5")
        assert output.map_row_pattern() == "map_*.h5"


class TestMapConversionRoot:
    """Verify _map_conversion_root() nests the map folder twice inside the output directory."""

    def test_is_directory_folder_folder(self):
        output = _make_output(directory="/out", filename="s", map_ext="map")
        assert output._map_conversion_root() == Path("/out/s_map/s_map")

    def test_custom_ext(self):
        output = _make_output(directory="/data", filename="run", map_ext="scan")
        assert output._map_conversion_root() == Path("/data/run_scan/run_scan")


class TestFrozenDataclass:
    """Verify OutputPaths is immutable and rejects field mutation."""

    def test_cannot_mutate_fields(self):
        output = _make_output()
        with pytest.raises((AttributeError, TypeError)):
            output.filename = "new"  # type: ignore[misc]
