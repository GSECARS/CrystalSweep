#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/crysalis_converter.py
# ----------------------------------------------------------------------------------
# Purpose:
# Standalone entry-point for CrysAlis format conversion. Intended to be spawned as
# a separate subprocess by CollectController so the conversion never blocks the
# acquisition loop.
#
# Usage (spawned by CollectController):
#   python -m crystalsweep.model.crysalis_converter <json_args_file>
#
# The JSON args file contains:
#   {
#     "filepath":    "<local directory containing the data files>",
#     "basename":    "<filename stem WITHOUT frame number, e.g. t1_pos1>",
#     "filenumber":  1,
#     "par_file":    "<path to .par calibration file; .ccd and .set are siblings>",
#     "scan_info":   {<esperanto_scan_info dict>},
#     "file_format": "hdf5" | "cbf"
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
import os
import shutil
import sys
from pathlib import Path

_log = logging.getLogger(__name__)


def _make_directory(filepath: str, basename: str) -> str:
    new_directory = os.path.normpath(os.path.join(filepath, basename + "_crys"))
    if os.path.isdir(new_directory):
        shutil.rmtree(new_directory)
    os.makedirs(new_directory)
    return new_directory


def _copy_set_ccd(new_directory: str, basename: str, par_file: str) -> None:
    par_path = Path(par_file)
    for ext in (".set", ".ccd"):
        src = par_path.with_suffix(ext)
        if not src.is_file():
            _log.warning("Companion %s file not found: %s", ext, src)
            continue
        shutil.copy(str(src), os.path.join(new_directory, basename + ext))


def _create_par_file(new_directory: str, basename: str, par_file: str) -> None:
    new_par = os.path.join(new_directory, basename + ".par")
    with open(new_par, "w") as new_file, open(par_file, "r") as old_file:
        for line in old_file:
            if line.startswith("FILE CHIP"):
                new_file.write("FILE CHIP " + basename + ".ccd \n")
            else:
                new_file.write(line)


def _create_crysalis_run(new_directory: str, basename: str, scan_info: dict) -> None:
    try:
        from cryio import crysalis
    except ImportError:
        _log.warning("cryio not available; skipping .run file creation")
        return

    run_header = crysalis.RunHeader(basename.encode(), new_directory.encode(), 1)
    run_name = os.path.join(new_directory, basename)
    run_file = []

    dscr = crysalis.RunDscr(0)
    dscr.axis = crysalis.SCAN_AXIS["OMEGA"]
    dscr.kappa = scan_info.get("kappa", 0.0)
    dscr.omegaphi = 0
    dscr.start = scan_info.get("omega_start", 0.0)
    dscr.end = scan_info.get("omega_end", 0.0)
    dscr.width = scan_info.get("domega", 1.0)
    dscr.todo = dscr.done = scan_info.get("count", 1)
    dscr.exposure = 1
    run_file.append(dscr)

    crysalis.saveRun(run_name, run_header, run_file)
    crysalis.saveCrysalisExpSettings(new_directory)


def _convert_hdf5(filepath: str, basename: str, filenumber: int, new_directory: str, scan_info: dict) -> None:
    try:
        import h5py
        import numpy as np
        from cryio import esperanto
    except ImportError:
        _log.warning("h5py/numpy/cryio not available; skipping HDF5 conversion")
        return

    h5_path = os.path.join(filepath, f"{basename}_{filenumber:04d}.h5")
    full_basename = f"{basename}_{filenumber:04d}"
    _log.info("Converting HDF5: %s", h5_path)

    try:
        with h5py.File(h5_path, "r") as f:
            data = f["entry/data/data"]
            count = data.shape[0]
            _log.info("Found %d frames in %s", count, h5_path)
            for i in range(count):
                try:
                    frame = data[i]
                    frame = np.flipud(frame)
                    frame = np.fliplr(frame)
                    esp_file = os.path.join(new_directory, f"{full_basename}_1_{i + 1}.esperanto")
                    rot = dict(scan_info)
                    rot["omega"] = rot.get("omega_start", 0.0) + rot.get("domega", 1.0) * i
                    esp = esperanto.EsperantoImage()
                    esp.save(esp_file, frame, **rot)
                    _log.debug("Wrote frame %d -> %s", i + 1, esp_file)
                except Exception:
                    _log.exception("HDF5 frame %d conversion failed", i + 1)
                    break
        _log.info("HDF5 conversion complete: %d frames", count)
    except Exception:
        _log.exception("HDF5 conversion failed")


def _convert_cbf(filepath: str, basename: str, filenumber: int, new_directory: str, scan_info: dict) -> None:
    try:
        import numpy as np
        from cryio import cbfimage, esperanto
    except ImportError:
        _log.warning("cryio/numpy not available; skipping CBF conversion")
        return

    count = scan_info.get("count", 1)

    def _padarray(array):
        a = np.empty((1043, 31), dtype=array.dtype)
        b = np.empty((1043, 32), dtype=array.dtype)
        a.fill(-1)
        b.fill(-1)
        array = np.hstack((array, a))
        array = np.hstack((b, array))
        c = np.empty((1, 1044), dtype=array.dtype)
        c.fill(-1)
        return np.vstack((array, c))

    for i in range(count):
        try:
            cbf_file = os.path.normpath(os.path.join(filepath, f"{basename}_{filenumber:04d}_{i + 1:05d}.cbf"))
            esp_file = os.path.normpath(os.path.join(new_directory, f"{basename}_{filenumber:04d}_1_{i + 1}.esperanto"))
            image = cbfimage.CbfImage(cbf_file)
            array_trans = np.flip(image.array, 0)
            new_image_array = _padarray(array_trans)
            rot = dict(scan_info)
            rot["omega"] = rot.get("omega_start", 0.0) + rot.get("domega", 1.0) * i
            esp = esperanto.EsperantoImage()
            esp.save(esp_file, new_image_array, **rot)
        except Exception:
            _log.exception("CBF frame %d conversion failed", i + 1)
            break


def run_conversion(args: dict) -> None:
    filepath = args["filepath"]
    basename = args["basename"]
    filenumber = int(args.get("filenumber", 1))
    par_file = args.get("par_file", "")
    scan_info = args.get("scan_info", {})
    file_format = args.get("file_format", "hdf5")

    full_basename = f"{basename}_{filenumber:04d}"
    _log.info("run_conversion: filepath=%r full_basename=%r file_format=%r", filepath, full_basename, file_format)

    new_directory = _make_directory(filepath, full_basename)

    if par_file and os.path.isfile(par_file):
        _create_par_file(new_directory, full_basename, par_file)
        _copy_set_ccd(new_directory, full_basename, par_file)
    else:
        _log.warning("Par file not found: %s", par_file)

    _create_crysalis_run(new_directory, full_basename, scan_info)

    if file_format == "hdf5":
        _convert_hdf5(filepath, basename, filenumber, new_directory, scan_info)
    else:
        _convert_cbf(filepath, basename, filenumber, new_directory, scan_info)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m crystalsweep.model.crysalis_converter <json_args_file>", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    args_file = sys.argv[1]
    with open(args_file, "r") as fh:
        args = json.load(fh)

    try:
        run_conversion(args)
    except Exception:
        _log.exception("crysalis_converter: unhandled exception")
