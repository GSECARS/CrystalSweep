#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/snake_combiner.py
# ----------------------------------------------------------------------------------
# Purpose:
# Standalone entry-point that takes a folder of snake-scan per-row HDF5 files
# and produces a single combined map HDF5 file. Designed to be spawned as a
# separate subprocess by CollectController so the combine never blocks the
# acquisition loop, mirroring the pattern used by format_converter.py.
#
# Acquisition convention:
#     - Each input .h5 file is one row of the map.
#     - Files are sorted alphabetically (the zero-padded numeric suffix in the
#       row filename also sorts them by row index).
#     - Frames within a file form the columns of that row.
#     - Snake pattern: row 1 forward, row 2 reversed, row 3 forward, ...
#       ("even rows reversed", 1-indexed). Pass ``first_row_reversed=True``
#       for the opposite convention.
#
# Output file schema mirrors the per-row files: every dataset whose leading
# dimension equals the per-row frame count gets its leading axis grown from
# ``frame_count`` to ``rows*frame_count``. Groups, attributes and non per-frame
# datasets are copied once from the first row file.
#
# Usage (spawned by CollectController via subprocess.Popen):
#   python -m crystalsweep.model.snake_combiner <args_json_path>
#
# ``args_dict`` schema:
#   {
#       "input_dir":           "<folder with per-row .h5 files>",
#       "output_path":         "<combined .h5 file to write>",
#       "pattern":             "*.h5",                 # optional, glob filter
#       "first_row_reversed":  false,                  # optional, opposite snake
#       "skip_flip":           false,                  # optional, assume flipped_dir already populated
#       "flipped_dir":         "<folder>",             # optional, default <input>_flipped
#       "data_path":           "entry/data/data",      # optional, for per-frame detection
#   }
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Callable

try:
    import hdf5plugin  # noqa: F401  registers bitshuffle/LZ4 etc. with libhdf5
except ImportError:
    hdf5plugin = None  # type: ignore[assignment]

__all__ = ["run_combine", "combine_snake_map"]

_log = logging.getLogger(__name__)

_DEFAULT_DATA_PATH = "entry/data/data"

# HDF5 filter id -> hdf5plugin "compression kwargs" factory. Used when we need
# to re-create a dataset that uses one of these external filters. Skipped when
# hdf5plugin is not installed (the fallback path uses h5py's native filters).
if hdf5plugin is not None:
    _PLUGIN_FILTERS: dict[int, Callable[[tuple], dict]] = {
        32008: lambda _cd: dict(hdf5plugin.Bitshuffle(cname="lz4")),
        32004: lambda _cd: dict(hdf5plugin.LZ4()),
        32001: lambda _cd: dict(hdf5plugin.Blosc()),
        32015: lambda _cd: dict(hdf5plugin.Zstd()),
        32000: lambda _cd: dict(hdf5plugin.BZip2()),
    }
else:
    _PLUGIN_FILTERS = {}


def _list_row_files(input_dir: Path, pattern: str) -> list[Path]:
    files = sorted(input_dir.glob(pattern))
    if not files:
        raise RuntimeError(f"No files matching {pattern!r} found in {input_dir}")
    return files


def _detect_frame_count(path: Path, data_path: str) -> int:
    import h5py

    with h5py.File(str(path), "r") as fh:
        if data_path not in fh:
            raise RuntimeError(f"Dataset {data_path!r} not found in {path}")
        return int(fh[data_path].shape[0])


def _dataset_create_kwargs(dset) -> dict:
    """Return create_dataset kwargs that reproduce src's storage layout."""
    kw: dict = {"dtype": dset.dtype}
    if dset.chunks is not None:
        kw["chunks"] = dset.chunks
    if dset.fletcher32:
        kw["fletcher32"] = True

    plist = dset.id.get_create_plist()
    nf = plist.get_nfilters()
    handled_plugin = False
    for i in range(nf):
        filt_id, _flags, cd_values, _name = plist.get_filter(i)
        if filt_id in _PLUGIN_FILTERS:
            kw.update(_PLUGIN_FILTERS[filt_id](cd_values))
            handled_plugin = True

    if not handled_plugin:
        if dset.compression is not None and dset.compression != "unknown":
            kw["compression"] = dset.compression
            if dset.compression_opts is not None:
                kw["compression_opts"] = dset.compression_opts
        if dset.shuffle:
            kw["shuffle"] = True

    return kw


def _copy_attrs(src, dst) -> None:
    for k, v in src.attrs.items():
        dst.attrs[k] = v


def _write_flipped_row(src_path: Path, dst_path: Path, frame_count: int, reverse: bool) -> None:
    """Copy ``src_path`` to ``dst_path``, reversing the leading axis on any
    dataset whose leading dimension equals ``frame_count`` when ``reverse`` is
    True. Groups, attrs, dtypes, chunking and compression are preserved."""
    import h5py

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(str(src_path), "r") as src, h5py.File(str(dst_path), "w") as dst:
        _copy_attrs(src, dst)

        def visit(name: str, obj) -> None:
            if isinstance(obj, h5py.Group):
                g = dst.require_group(name)
                _copy_attrs(obj, g)
                return
            if isinstance(obj, h5py.Dataset):
                is_per_frame = bool(obj.shape) and obj.shape[0] == frame_count
                kw = _dataset_create_kwargs(obj)
                out = dst.create_dataset(name, shape=obj.shape, **kw)
                _copy_attrs(obj, out)
                if is_per_frame and reverse:
                    n = obj.shape[0]
                    for i in range(n):
                        out[i] = obj[n - 1 - i]
                elif is_per_frame:
                    n = obj.shape[0]
                    for i in range(n):
                        out[i] = obj[i]
                else:
                    out[...] = obj[...]

        src.visititems(visit)


def _build_combined(flipped_files: list[Path], combined_path: Path, frame_count: int) -> None:
    """Combine all flipped row files into a single map file that keeps the SAME
    dataset schema as a per-row file: per-frame datasets just have their
    leading axis grown from ``frame_count`` to ``rows*frame_count``."""
    import h5py

    rows = len(flipped_files)
    total_frames = rows * frame_count
    template = flipped_files[0]
    combined_path.parent.mkdir(parents=True, exist_ok=True)

    with h5py.File(str(template), "r") as tmpl, h5py.File(str(combined_path), "w") as out:
        _copy_attrs(tmpl, out)

        per_frame_names: list[str] = []

        def visit(name: str, obj) -> None:
            if isinstance(obj, h5py.Group):
                g = out.require_group(name)
                _copy_attrs(obj, g)
                return
            if isinstance(obj, h5py.Dataset):
                is_per_frame = bool(obj.shape) and obj.shape[0] == frame_count
                kw = _dataset_create_kwargs(obj)
                if is_per_frame:
                    new_shape = (total_frames,) + tuple(obj.shape[1:])
                    d = out.create_dataset(name, shape=new_shape, **kw)
                    _copy_attrs(obj, d)
                    per_frame_names.append(name)
                else:
                    d = out.create_dataset(name, shape=obj.shape, **kw)
                    d[...] = obj[...]
                    _copy_attrs(obj, d)

        tmpl.visititems(visit)

        for row_idx, fpath in enumerate(flipped_files):
            start = row_idx * frame_count
            stop = start + frame_count
            with h5py.File(str(fpath), "r") as fin:
                for name in per_frame_names:
                    src = fin[name]
                    dst = out[name]
                    if src.shape[0] != frame_count:
                        raise RuntimeError(
                            f"{fpath}: dataset {name} has leading dim {src.shape[0]}, expected {frame_count}"
                        )
                    if src.ndim == 1:
                        dst[start:stop] = src[...]
                    else:
                        for c in range(frame_count):
                            dst[start + c] = src[c]


def combine_snake_map(
    input_dir: Path,
    output_path: Path,
    pattern: str = "*.h5",
    first_row_reversed: bool = False,
    skip_flip: bool = False,
    flipped_dir: Path | None = None,
    data_path: str = _DEFAULT_DATA_PATH,
) -> None:
    """Flip per-row .h5 files according to the snake convention and combine
    them into a single map file. The combined output preserves the schema of a
    single per-row file (per-frame leading axis grown by a factor of rows)."""
    if not input_dir.is_dir():
        raise RuntimeError(f"Input directory not found: {input_dir}")

    target_flipped_dir = flipped_dir or input_dir.with_name(f"{input_dir.name}_flipped")

    # ``glob`` is non-recursive so files inside ``target_flipped_dir`` are not
    # rediscovered; we only need to skip a combined output that may have been
    # written next to the row files from a previous run.
    output_resolved = output_path.resolve()
    row_files = [p for p in _list_row_files(input_dir, pattern) if p.resolve() != output_resolved]
    if not row_files:
        raise RuntimeError(f"No row files matching {pattern!r} in {input_dir}")
    frame_count = _detect_frame_count(row_files[0], data_path)
    _log.info(
        "snake_combiner: %d row files, %d frames/row, flipped_dir=%s, output=%s",
        len(row_files),
        frame_count,
        target_flipped_dir,
        output_path,
    )

    flipped_files: list[Path] = []
    for i, src in enumerate(row_files):
        row_one_based = i + 1
        if first_row_reversed:
            reverse = row_one_based % 2 == 1
        else:
            reverse = row_one_based % 2 == 0
        dst = target_flipped_dir / src.name
        flipped_files.append(dst)
        if skip_flip:
            if not dst.exists():
                raise RuntimeError(f"skip_flip set but flipped row missing: {dst}")
            continue
        _log.info("snake_combiner: row %d %s %s -> %s", row_one_based, "REVERSE" if reverse else "keep   ", src.name, dst)
        _write_flipped_row(src, dst, frame_count=frame_count, reverse=reverse)

    _log.info("snake_combiner: building combined map file %s", output_path)
    _build_combined(flipped_files, output_path, frame_count=frame_count)
    _log.info("snake_combiner: done")


def run_combine(args: dict) -> None:
    """Entry point used by subprocess / CLI invocations."""
    input_dir = args.get("input_dir", "")
    output_path = args.get("output_path", "")
    pattern = args.get("pattern") or "*.h5"
    first_row_reversed = bool(args.get("first_row_reversed", False))
    skip_flip = bool(args.get("skip_flip", False))
    flipped_dir_raw = args.get("flipped_dir") or ""
    data_path = args.get("data_path") or _DEFAULT_DATA_PATH

    _log.info(
        "run_combine: input_dir=%r output_path=%r pattern=%r first_row_reversed=%s skip_flip=%s flipped_dir=%r",
        input_dir,
        output_path,
        pattern,
        first_row_reversed,
        skip_flip,
        flipped_dir_raw,
    )

    if not input_dir or not output_path:
        _log.warning("run_combine: missing input_dir or output_path, aborting")
        return

    combine_snake_map(
        input_dir=Path(input_dir),
        output_path=Path(output_path),
        pattern=pattern,
        first_row_reversed=first_row_reversed,
        skip_flip=skip_flip,
        flipped_dir=Path(flipped_dir_raw) if flipped_dir_raw else None,
        data_path=data_path,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m crystalsweep.model.snake_combiner <json_args_file>", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    args_file = sys.argv[1]
    with open(args_file, "r") as fh:
        args_payload = json.load(fh)

    try:
        run_combine(args_payload)
    except Exception:
        _log.exception("snake_combiner: unhandled exception")
