#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/image_loader_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Model for loading detector images from HDF5 files.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

try:
    import h5py
    import hdf5plugin as _hdf5plugin  # noqa: F401 - imported for compression filter side effects

    HAS_H5PY = True
except ImportError:
    HAS_H5PY = False

__all__ = ["ImageLoaderModel", "HAS_H5PY"]


@dataclass()
class ImageLoaderModel:
    """Handles loading detector images from HDF5 files."""

    _loaded_file: Path | None = field(init=False, compare=False, repr=False, default=None)
    _hdf5_dataset_path: str | None = field(init=False, compare=False, repr=False, default=None)
    _hdf5_frame_count: int = field(init=False, compare=False, repr=False, default=0)
    _hdf5_filepath: Path | None = field(init=False, compare=False, repr=False, default=None)

    @property
    def frame_count(self) -> int:
        """Number of frames in the currently loaded HDF5 file (0 if not multi-frame)."""
        return self._hdf5_frame_count

    @property
    def loaded_file(self) -> Path | None:
        """Returns the path of the currently loaded file."""
        return self._loaded_file

    def load_hdf5(self, filepath: Path) -> np.ndarray:
        """Loads the first 2D image from an HDF5 file and caches multi-frame metadata."""
        if not HAS_H5PY:
            raise ImportError("h5py is not installed. Cannot load HDF5 files.")

        self._hdf5_frame_count = 0
        self._hdf5_dataset_path = None
        self._hdf5_filepath = None

        with h5py.File(filepath, "r") as f:
            dataset = self._find_dataset(f)

            if dataset is None:
                raise ValueError(
                    "Could not find image data in HDF5 file.\n\nTried common dataset paths: data, images, entry/data/data, exchange/data, entry/instrument/detector/data"
                )

            if len(dataset.shape) == 2:
                frame = dataset[:]
            elif len(dataset.shape) == 3:
                self._hdf5_frame_count = dataset.shape[0]
                self._hdf5_dataset_path = dataset.name
                self._hdf5_filepath = filepath
                frame = dataset[0]
            else:
                raise ValueError(f"Unsupported data shape: {dataset.shape}\n\nExpected 2D or 3D array.")

        self._loaded_file = filepath
        return frame.astype(np.float32)

    def load_hdf5_frame(self, index: int) -> np.ndarray:
        """Loads a specific frame by index from the currently open HDF5 file."""
        if self._hdf5_filepath is None or self._hdf5_dataset_path is None:
            raise ValueError("No multi-frame HDF5 file is currently loaded.")
        if not (0 <= index < self._hdf5_frame_count):
            raise ValueError(f"Frame index {index} out of range [0, {self._hdf5_frame_count}).")

        with h5py.File(self._hdf5_filepath, "r") as f:
            frame = f[self._hdf5_dataset_path][index]

        return frame.astype(np.float32)

    @staticmethod
    def _find_dataset(f) -> "h5py.Dataset | None":
        """Searches an HDF5 file for the first suitable 2D+ dataset."""
        common_paths = [
            "data",
            "images",
            "entry/data/data",
            "exchange/data",
            "entry/instrument/detector/data",
        ]

        for name in common_paths:
            if name in f:
                return f[name]

        for key in f.keys():
            obj = f[key]
            if isinstance(obj, h5py.Dataset) and len(obj.shape) >= 2:
                return obj
            elif isinstance(obj, h5py.Group):
                for subkey in obj.keys():
                    subobj = obj[subkey]
                    if isinstance(subobj, h5py.Dataset) and len(subobj.shape) >= 2:
                        return subobj

        return None
