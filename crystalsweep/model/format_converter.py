#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/format_converter.py
# ----------------------------------------------------------------------------------
# Purpose:
# Standalone entry-point for image-format conversion (HDF5 / CBF / TIF).
# Designed to be spawned as a separate subprocess by CollectController so the
# conversion never blocks the acquisition loop.
#
# Native detector files always stay where the IOC wrote them. For each
# requested extra format the converter writes frames into a caller-specified
# output folder. CollectController chooses the layout: single collections get
# a sibling `<basename>_<fmt>/` folder; map collections share one
# `<base>_<map_ext>_<fmt>/` folder per format inside the map directory.
#
# Usage (spawned by CollectController via subprocess.Popen):
#   python -m crystalsweep.model.format_converter <args_json_path>
#
# `args_dict` schema:
#   {
#       "directory":        "<acquisition directory>",
#       "basename":         "<filename stem with frame number, e.g. sample_0001>",
#       "source_format":    "hdf5" | "cbf" | "tif",
#       "target_formats":   ["cbf", "tif", ...],     # without source_format
#       "file_number_width":4,                       # zero-padding for stack frames
#       "output_dirs":      {"cbf": "<dir>", "tif": "<dir>"},  # one entry per extra
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

__all__ = ["run_conversion", "convert_point"]

_log = logging.getLogger(__name__)

_SUFFIX_MAP: dict[str, tuple[str, ...]] = {
    "hdf5": (".h5", ".hdf5"),
    "cbf": (".cbf",),
    "tif": (".tif", ".tiff"),
}

_PRIMARY_SUFFIX: dict[str, str] = {
    "hdf5": ".h5",
    "cbf": ".cbf",
    "tif": ".tif",
}


def _suffixes_for(fmt: str) -> tuple[str, ...]:
    return _SUFFIX_MAP.get(fmt, ())


def _find_source_files(directory: Path, basename: str, source_format: str) -> list[Path]:
    """Return every file in *directory* that belongs to *basename* in *source_format*."""
    suffixes = _suffixes_for(source_format)
    if not suffixes:
        return []
    matches: list[Path] = []
    for suffix in suffixes:
        matches.extend(directory.glob(f"{basename}{suffix}"))
        matches.extend(directory.glob(f"{basename}_*{suffix}"))
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in sorted(matches):
        if path not in seen and path.is_file():
            seen.add(path)
            unique.append(path)
    return unique


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_frames(path: Path):
    """Yield (frame_index, ndarray) tuples for every frame in *path*."""
    suffix = path.suffix.lower()
    if suffix in (".h5", ".hdf5"):
        yield from _load_hdf5_frames(path)
    else:
        yield from _load_fabio_frames(path)


_PRIMARY_HDF5_PATHS: tuple[str, ...] = (
    "entry/data/data",
    "entry/instrument/detector/data",
)


def _load_hdf5_frames(path: Path):
    try:
        import h5py
        import numpy as np
    except ImportError:
        _log.warning("h5py/numpy not available; skipping %s", path)
        return

    with h5py.File(str(path), "r") as fh:
        primary: str | None = None
        for candidate in _PRIMARY_HDF5_PATHS:
            node = fh.get(candidate)
            if isinstance(node, h5py.Dataset) and node.ndim in (2, 3):
                primary = candidate
                break

        if primary is None:
            candidates: list[tuple[int, str]] = []

            def _visit(name: str, node) -> None:
                if isinstance(node, h5py.Dataset) and node.ndim in (2, 3):
                    candidates.append((int(np.prod(node.shape)), name))

            fh.visititems(_visit)
            if not candidates:
                return
            candidates.sort(reverse=True)
            primary = candidates[0][1]
            _log.info("hdf5: no canonical path found in %s, using largest dataset %r", path, primary)

        ds = fh[primary]
        data = ds[...]
        if data.ndim == 2:
            yield 0, np.asarray(data)
        else:
            for i in range(data.shape[0]):
                yield i, np.asarray(data[i])


def _load_fabio_frames(path: Path):
    try:
        import fabio
    except ImportError:
        _log.warning("fabio not available; skipping %s", path)
        return

    img = fabio.open(str(path))
    nframes = getattr(img, "nframes", 1) or 1
    if nframes <= 1:
        yield 0, img.data
        return
    for i in range(nframes):
        yield i, img.getframe(i).data


def _write_frame(target_format: str, out_path: Path, data) -> None:
    if target_format == "hdf5":
        _write_hdf5(out_path, data)
    elif target_format == "cbf":
        _write_fabio(out_path, data, "cbf")
    elif target_format == "tif":
        _write_fabio(out_path, data, "tif")
    else:
        raise ValueError(f"Unsupported target format: {target_format}")


def _write_hdf5(out_path: Path, data) -> None:
    import h5py

    with h5py.File(str(out_path), "w") as fh:
        fh.create_dataset("entry/data/data", data=data, compression="gzip", compression_opts=4)


def _write_fabio(out_path: Path, data, target_format: str) -> None:
    if target_format == "tif":
        from PIL import Image
        import numpy as np

        arr = np.asarray(data)
        Image.fromarray(arr).save(str(out_path))
        return
    import fabio

    if target_format == "cbf":
        image = fabio.cbfimage.CbfImage(data=data)
    else:
        image = fabio.tifimage.TifImage(data=data)
    image.write(str(out_path))


def _convert_to(
    sources: list[Path],
    target_dir: Path,
    basename: str,
    target_format: str,
    file_number_width: int,
) -> int:
    """Write *sources* to *target_dir* in *target_format*. Returns frame count."""
    _ensure_dir(target_dir)
    suffix = _PRIMARY_SUFFIX[target_format]
    written = 0
    global_index = 0
    for src in sources:
        frames = list(_load_frames(src))
        if not frames:
            _log.warning("No frames found in %s", src)
            continue
        if len(frames) == 1 and len(sources) == 1:
            out_path = target_dir / f"{basename}{suffix}"
            if out_path.exists():
                _log.warning("Skipping existing file: %s", out_path)
                continue
            _write_frame(target_format, out_path, frames[0][1])
            written += 1
            continue
        for _, data in frames:
            global_index += 1
            frame_label = f"{global_index:0{max(1, file_number_width)}d}"
            out_path = target_dir / f"{basename}_{frame_label}{suffix}"
            if out_path.exists():
                _log.warning("Skipping existing file: %s", out_path)
                continue
            try:
                _write_frame(target_format, out_path, data)
                written += 1
            except Exception:
                _log.exception("Failed writing frame %s", out_path)
    return written


def convert_point(
    directory: Path,
    basename: str,
    source_format: str,
    target_formats: list[str],
    file_number_width: int = 4,
    output_dirs: dict[str, Path] | None = None,
) -> None:
    """Convert detector source files for *basename* into the requested formats.

    Source files are read in place and never moved. For each entry in
    *target_formats* (excluding *source_format*) the output goes to
    ``output_dirs[fmt]`` if provided, otherwise to ``directory / f"{basename}_{fmt}"``.
    """
    extras = [fmt for fmt in target_formats if fmt and fmt != source_format]
    if not extras:
        _log.info("convert_point: no extra formats requested, nothing to do")
        return

    directory = Path(directory)
    if not directory.is_dir():
        _log.warning("convert_point: directory does not exist: %s", directory)
        return

    sources = _find_source_files(directory, basename, source_format)
    if not sources:
        _log.warning("convert_point: no source files found for %s in %s", basename, directory)
        return

    outputs = output_dirs or {}
    for fmt in extras:
        target_dir = Path(outputs[fmt]) if fmt in outputs else directory / f"{basename}_{fmt}"
        try:
            written = _convert_to(sources, target_dir, basename, fmt, file_number_width)
            _log.info("convert_point: wrote %d %s frame(s) -> %s", written, fmt, target_dir)
        except Exception:
            _log.exception("convert_point: %s conversion failed", fmt)


def run_conversion(args: dict) -> None:
    """Entry point used by ``multiprocessing.Process`` / CLI invocations."""
    directory = args.get("directory", "")
    basename = args.get("basename", "")
    source_format = args.get("source_format", "hdf5")
    target_formats = list(args.get("target_formats", []))
    file_number_width = int(args.get("file_number_width", 4))
    raw_output_dirs = args.get("output_dirs") or {}
    output_dirs = {fmt: Path(path) for fmt, path in raw_output_dirs.items() if path}

    _log.info(
        "run_conversion: directory=%r basename=%r source=%r targets=%r output_dirs=%r",
        directory,
        basename,
        source_format,
        target_formats,
        {k: str(v) for k, v in output_dirs.items()},
    )

    if not directory or not basename:
        _log.warning("run_conversion: missing directory or basename, aborting")
        return

    convert_point(
        Path(directory),
        basename,
        source_format,
        target_formats,
        file_number_width,
        output_dirs=output_dirs,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m crystalsweep.model.format_converter <json_args_file>", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    args_file = sys.argv[1]
    with open(args_file, "r") as fh:
        args_payload = json.load(fh)

    try:
        run_conversion(args_payload)
    except Exception:
        _log.exception("format_converter: unhandled exception")
