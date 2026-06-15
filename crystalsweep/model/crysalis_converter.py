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
#     "par_file":    "<path to .par calibration file>",
#     "set_file":    "<explicit path to .set file; if empty, derived from par_file path>",
#     "ccd_file":    "<explicit path to .ccd file; if empty, derived from par_file path>",
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


def _make_directory(filepath: str, basename: str, output_dir: str | None = None) -> str:
    new_directory = os.path.normpath(output_dir) if output_dir else os.path.normpath(os.path.join(filepath, basename + "_crys"))
    if os.path.isdir(new_directory):
        shutil.rmtree(new_directory)
    os.makedirs(new_directory)
    return new_directory


def _copy_set_ccd(new_directory: str, basename: str, par_file: str, set_file: str = "", ccd_file: str = "") -> None:
    par_path = Path(par_file)
    explicit = {".set": set_file, ".ccd": ccd_file}
    for ext in (".set", ".ccd"):
        explicit_path = explicit[ext]
        if explicit_path:
            src = Path(explicit_path)
        else:
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
        from dataclasses import dataclass, field as dc_field
        from fabio.app import eiger2crysalis
        from fabio.nexus import get_isotime
        import h5py
        import numexpr
        import numpy
    except ImportError:
        _log.warning("fabio/h5py/numexpr not available; skipping HDF5 conversion")
        return

    full_basename = f"{basename}_{filenumber:04d}"
    h5_path = os.path.join(filepath, f"{full_basename}.h5")
    _log.info("Converting HDF5 via eiger2crysalis: %s", h5_path)

    omega_start = scan_info.get("omega_start", 0.0)
    domega = scan_info.get("domega", 1.0)
    wavelength = scan_info.get("wavelength", 0.2952)
    distance = scan_info.get("dist", 200.0)
    center_x = scan_info.get("center_x", 0.0)
    center_y = scan_info.get("center_y", 0.0)
    alpha = scan_info.get("alpha", 50.0)
    polarization = scan_info.get("mono", 0.99)
    pixel_size = scan_info.get("pixel_size", 0.075)
    exposure = scan_info.get("Exposure_time", 1.0)

    @dataclass
    class Options:
        output: str
        wavelength: float
        distance: float
        beam: list
        rotation: int
        transpose: bool
        flip_ud: bool
        flip_lr: bool
        alpha: float
        kappa: str
        theta: str
        phi: str
        omega: str
        polarization: float
        energy: float = dc_field(default=0)
        offset: int = dc_field(default=1)
        dry_run: bool = dc_field(default=False)
        debug: bool = dc_field(default=False)
        dummy: int = dc_field(default=-1)
        images: list = dc_field(default_factory=list)
        verbose: bool = dc_field(default=False)

    options = Options(
        output=os.path.join(new_directory, f"{full_basename}_1_{{index}}.esperanto"),
        wavelength=wavelength,
        distance=distance,
        beam=[center_x, center_y],
        rotation=180,
        transpose=False,
        flip_ud=False,
        flip_lr=True,
        alpha=alpha,
        kappa=str(scan_info.get("kappa", 0.0)),
        theta=str(scan_info.get("theta", 0.0)),
        phi=str(scan_info.get("phi", 0.0)),
        omega=f"{omega_start} + {domega} * i",
        polarization=polarization,
        images=[h5_path],
    )

    class _Converter(eiger2crysalis.Converter):
        def common_headers(self):
            with h5py.File(h5_path, "r") as f:
                shape = f["entry/data/data"].shape[1:]
                dtype = f["entry/data/data"].dtype
            self.mask = numpy.zeros(shape, dtype=dtype)

            cx, cy = self.new_beam_center(center_x, center_y, shape)
            omega_expr = numexpr.NumExpr(self.options.omega)
            self.scan_type = "omega"

            return {
                "delectronsperadu": 1,
                "ldarkcorrectionswitch": 0,
                "lfloodfieldcorrectionswitch/mode": 0,
                "dsystemdcdb2gain": 1.0,
                "ddarksignal": 0,
                "dreadnoiserms": 0,
                "ioverflowflag": 0,
                "ioverflowafterremeasureflag": 0,
                "inumofdarkcurrentimages": 0,
                "inumofmultipleimages": 0,
                "loverflowthreshold": 1000000,
                "doverflowtimeinsec": 0,
                "doverflowfilter": 0,
                "dsithicknessmmforpixeldetector": 1,
                "timestampstring": get_isotime(),
                "dbeam2indeg": 0,
                "dbeam3indeg": 0,
                "detectorrotindeg_x": 0,
                "detectorrotindeg_y": 0,
                "detectorrotindeg_z": 0,
                "dalphaindeg": alpha,
                "dbetaindeg": 0,
                "ddvalue-prepolfac": polarization,
                "orientation-type": "SYNCHROTRON",
                "drealpixelsizex": pixel_size,
                "drealpixelsizey": pixel_size,
                "dexposuretimeinsec": exposure,
                "ddistanceinmm": distance,
                "dalpha1": wavelength,
                "dalpha2": wavelength,
                "dalpha12": wavelength,
                "dbeta1": wavelength,
                "dxorigininpix": cx,
                "dyorigininpix": cy,
                "dom_s": omega_expr,
                "dom_e": numexpr.NumExpr(f"{omega_start} + {domega} * (i + 1)"),
                "dth_s": float(self.options.theta),
                "dth_e": float(self.options.theta),
                "dka_s": float(self.options.kappa),
                "dka_e": float(self.options.kappa),
                "dph_s": float(self.options.phi),
                "dph_e": float(self.options.phi),
            }

    try:
        converter = _Converter(options=options)
        converter.convert_all()
        converter.finish()
        _log.info("HDF5 conversion complete: %s", full_basename)
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
    set_file = args.get("set_file", "")
    ccd_file = args.get("ccd_file", "")
    scan_info = args.get("scan_info", {})
    file_format = args.get("file_format", "hdf5")
    output_dir = args.get("output_dir") or None

    full_basename = f"{basename}_{filenumber:04d}"
    _log.info("run_conversion: filepath=%r full_basename=%r file_format=%r output_dir=%r", filepath, full_basename, file_format, output_dir)

    new_directory = _make_directory(filepath, full_basename, output_dir)

    if par_file and os.path.isfile(par_file):
        _create_par_file(new_directory, full_basename, par_file)
        _copy_set_ccd(new_directory, full_basename, par_file, set_file=set_file, ccd_file=ccd_file)
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
