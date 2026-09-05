#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/model/test_snake_combiner.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for combine_snake_map() HDF5 row-flip logic and incremental file growth.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from pathlib import Path

import h5py
import numpy as np

from crystalsweep.model.snake_combiner import combine_snake_map

_DATA_PATH = "entry/data/data"
_FRAME_COUNT = 2


def _make_row_file(path: Path, row_idx: int) -> np.ndarray:
    """Write a synthetic row HDF5 file and return the frame data written.

    Each frame is a 1-D array of 4 integers with values that uniquely identify
    the row and frame so failures are easy to read.
    """
    data = np.array(
        [[row_idx * 100 + f * 10 + j for j in range(4)] for f in range(_FRAME_COUNT)],
        dtype=np.int32,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(str(path), "w") as fh:
        fh.create_dataset(_DATA_PATH, data=data, chunks=(1, 4))
    return data


def _read_combined(path: Path) -> np.ndarray:
    with h5py.File(str(path), "r") as fh:
        return fh[_DATA_PATH][...]


def _run_combine(input_dir: Path, output: Path, flipped_dir: Path) -> None:
    combine_snake_map(
        input_dir=input_dir,
        output_path=output,
        pattern="row_*.h5",
        first_row_reversed=False,
        flipped_dir=flipped_dir,
    )


class TestFlipDirection:
    """Verify even-indexed rows are reversed and odd-indexed rows are kept forward."""

    def test_odd_rows_kept_even_rows_reversed(self, tmp_path):
        """Row 0 and row 2 (1-indexed: 1 and 3) stay forward; row 1 (1-indexed: 2) is reversed."""
        input_dir = tmp_path / "rows"
        flipped_dir = tmp_path / "flipped"
        output = tmp_path / "combined.h5"

        row0 = _make_row_file(input_dir / "row_001.h5", 0)
        row1 = _make_row_file(input_dir / "row_002.h5", 1)
        row2 = _make_row_file(input_dir / "row_003.h5", 2)

        _run_combine(input_dir, output, flipped_dir)

        np.testing.assert_array_equal(_read_combined(flipped_dir / "row_001.h5"), row0)
        np.testing.assert_array_equal(_read_combined(flipped_dir / "row_002.h5"), row1[::-1])
        np.testing.assert_array_equal(_read_combined(flipped_dir / "row_003.h5"), row2)


class TestSkipAlreadyFlipped:
    """Verify flipped files are not rewritten on a second combine call."""

    def test_flipped_files_not_rewritten_on_second_call(self, tmp_path):
        input_dir = tmp_path / "rows"
        flipped_dir = tmp_path / "flipped"
        output = tmp_path / "combined.h5"

        for i in range(3):
            _make_row_file(input_dir / f"row_{i + 1:03d}.h5", i)

        _run_combine(input_dir, output, flipped_dir)
        mtimes = {p.name: p.stat().st_mtime_ns for p in sorted(flipped_dir.iterdir())}

        _run_combine(input_dir, output, flipped_dir)

        for name, original_mtime in mtimes.items():
            assert (flipped_dir / name).stat().st_mtime_ns == original_mtime, f"{name} was re-written on the second call"


class TestIncrementalCombine:
    """Verify the combined output grows by one row per call and matches snake order."""

    def test_combined_file_grows_by_one_row_per_call(self, tmp_path):
        """Simulate per-row collection: create one file at a time and combine after each."""
        input_dir = tmp_path / "rows"
        flipped_dir = tmp_path / "flipped"
        output = tmp_path / "combined.h5"

        for i in range(3):
            _make_row_file(input_dir / f"row_{i + 1:03d}.h5", i)
            _run_combine(input_dir, output, flipped_dir)
            frames = _read_combined(output)
            expected_frames = (i + 1) * _FRAME_COUNT
            assert frames.shape[0] == expected_frames, f"after row {i}: expected {expected_frames} frames, got {frames.shape[0]}"

    def test_final_data_matches_snake_order(self, tmp_path):
        """After all rows the combined data should follow the snake convention."""
        input_dir = tmp_path / "rows"
        flipped_dir = tmp_path / "flipped"
        output = tmp_path / "combined.h5"

        rows = []
        for i in range(3):
            data = _make_row_file(input_dir / f"row_{i + 1:03d}.h5", i)
            rows.append(data)
            _run_combine(input_dir, output, flipped_dir)

        combined = _read_combined(output)
        expected = np.concatenate([rows[0], rows[1][::-1], rows[2]])
        np.testing.assert_array_equal(combined, expected)
