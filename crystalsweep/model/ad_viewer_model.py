#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: crystalsweep/model/ad_viewer_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# This file is used to implement the AD Viewer model.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import ctypes
import logging
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Thread
from time import sleep
from typing import Protocol

import hdf5plugin
import numpy as np
from p4p.client.thread import Context, Subscription

__all__ = ["ADViewerModel"]

_log = logging.getLogger(__name__)

_SCALAR_TYPE_MAP: dict[int, tuple[str, int]] = {
    1: ("int8", 1),
    2: ("int16", 2),
    3: ("int32", 4),
    4: ("int64", 8),
    5: ("uint8", 1),
    6: ("uint16", 2),
    7: ("uint32", 4),
    8: ("uint64", 8),
    9: ("float32", 4),
    10: ("float64", 8),
}

_PLUGIN_DIR = Path(hdf5plugin.__file__).parent / "plugins"
_EXT = "dll" if sys.platform == "win32" else ("dylib" if sys.platform == "darwin" else "so")

_HDFPLUGIN_LIBS = {
    "bitshuffle": str(_PLUGIN_DIR / f"libh5bshuf.{_EXT}"),
    "blosc": str(_PLUGIN_DIR / f"libh5blosc.{_EXT}"),
}

_lib_cache: dict[str, ctypes.CDLL] = {}


def _load_lib(name: str) -> ctypes.CDLL:
    """Load a codec shared library bundled with hdf5plugin."""
    if name in _lib_cache:
        return _lib_cache[name]
    path = _HDFPLUGIN_LIBS[name]
    lib = ctypes.cdll.LoadLibrary(path)
    _lib_cache[name] = lib
    return lib


class FrameCallback(Protocol):
    """Protocol for callbacks that receive a new detector frame."""

    def __call__(self, frame: np.ndarray) -> None: ...


@dataclass()
class ADViewerModel:
    """Streams images from an EPICS PVA NTNDArray PV using p4p. Compressed streams are decompressed client-side."""

    use_polling: bool = field(default=True)
    poll_interval: float = field(default=0.1)
    poll_join_timeout: float = field(default=1.0)
    default_request: str = field(default="field(value,codec,compressedSize,uncompressedSize,dimension,uniqueId)")
    monitor_request: str = field(default="field(value,codec,compressedSize,uncompressedSize,dimension)")

    _context: Context = field(init=False, compare=False, repr=False, default_factory=lambda: Context("pva"))
    _pv_name: str = field(init=False, compare=False, repr=False, default="")
    _frame_callback: FrameCallback | None = field(init=False, compare=False, repr=False, default=None)
    _subscription: Subscription | None = field(init=False, compare=False, repr=False, default=None)
    _polling_thread: Thread | None = field(init=False, compare=False, repr=False, default=None)
    _stop_polling: Event = field(init=False, compare=False, repr=False, default_factory=Event)

    def subscribe(self, pv_name: str, frame_callback: FrameCallback) -> None:
        """Start monitoring *pv_name* and deliver frames to *frame_callback*."""
        self.unsubscribe()

        self._pv_name = pv_name
        self._frame_callback = frame_callback

        if self.use_polling:
            _log.info("AD viewer subscribing to %s (polling @ %.0f Hz)", pv_name, 1.0 / self.poll_interval)
            self._stop_polling.clear()
            self._polling_thread = Thread(target=self._poll_loop, name="ADViewerPollThread", daemon=True)
            self._polling_thread.start()
        else:
            _log.info("AD viewer subscribing to %s (monitor mode)", pv_name)
            self._subscription = self._context.monitor(
                name=self._pv_name,
                cb=self._on_ntndarray,
                request=self.monitor_request,
            )

    def unsubscribe(self) -> None:
        """Stop monitoring the current PV, if any."""
        if self.use_polling:
            self._stop_polling.set()
            if self._polling_thread is not None and self._polling_thread.is_alive():
                self._polling_thread.join(timeout=self.poll_join_timeout)
            self._polling_thread = None
        else:
            if self._subscription is not None:
                self._subscription.close()
                self._subscription = None

    def _poll_loop(self) -> None:
        """Background loop: fetch latest PV value at ``poll_interval`` Hz."""
        last_unique_id: object = None

        while not self._stop_polling.is_set():
            try:
                value = self._context.get(self._pv_name, request=self.default_request)
                current_id = value.get("uniqueId", None)

                if current_id is not None and current_id == last_unique_id:
                    sleep(self.poll_interval)
                    continue

                last_unique_id = current_id
                _log.debug("New frame received via polling (uniqueId=%s)", current_id)
                self._process_image(value)

            except Exception:
                _log.exception("Error polling PV %s", self._pv_name)

            sleep(self.poll_interval)

    def _on_ntndarray(self, value: object) -> None:
        """Callback invoked by the p4p monitor on each PV update."""
        _log.debug("New frame received via PV monitor")
        self._process_image(value)

    def _decompress_lz4hdf5(self, data: bytes, dtype: str) -> np.ndarray:
        """Decompress the lz4hdf5 block format (HDF5 filter 32004)."""
        lib = _load_lib("bitshuffle")
        pos = 0
        orig_size = int.from_bytes(data[pos : pos + 8], "big")
        pos += 8
        block_size = int.from_bytes(data[pos : pos + 4], "big")
        pos += 4

        out = bytearray(orig_size)
        write_pos = 0

        while write_pos < orig_size:
            comp_block_size = int.from_bytes(data[pos : pos + 4], "big")
            pos += 4
            current_block = min(block_size, orig_size - write_pos)

            if comp_block_size == current_block:
                out[write_pos : write_pos + current_block] = data[pos : pos + current_block]
            else:
                in_block = (ctypes.c_ubyte * comp_block_size).from_buffer_copy(data[pos : pos + comp_block_size])
                out_block = (ctypes.c_ubyte * current_block).from_buffer(out, write_pos)
                lib.LZ4_decompress_fast(in_block, out_block, ctypes.c_int(current_block))

            pos += comp_block_size
            write_pos += current_block

        return np.frombuffer(bytes(out), dtype=dtype)

    def _decompress(self, compressed_bytes: bytes, codec_name: str, scalar_type: int, compressed_size: int, uncompressed_size: int) -> np.ndarray:
        """Decompress a compressed NTNDArray payload using hdf5plugin bundled libs."""
        dtype, elem_size = _SCALAR_TYPE_MAP.get(scalar_type, ("uint8", 1))

        if codec_name == "lz4hdf5":
            return self._decompress_lz4hdf5(compressed_bytes[:compressed_size], dtype)

        if codec_name == "zlib":
            return np.frombuffer(zlib.decompress(compressed_bytes[:compressed_size]), dtype=dtype)

        in_buf = (ctypes.c_ubyte * compressed_size).from_buffer_copy(compressed_bytes[:compressed_size])
        out_data = bytearray(uncompressed_size)
        out_buf = (ctypes.c_ubyte * uncompressed_size).from_buffer(out_data)

        if codec_name == "blosc":
            lib = _load_lib("blosc")
            lib.blosc_decompress(in_buf, out_buf, ctypes.c_size_t(uncompressed_size))

        elif codec_name == "lz4":
            lib = _load_lib("bitshuffle")
            lib.LZ4_decompress_fast(in_buf, out_buf, ctypes.c_int(uncompressed_size))

        elif codec_name == "bslz4":
            lib = _load_lib("bitshuffle")
            n_elem = uncompressed_size // elem_size
            lib.bshuf_decompress_lz4(in_buf, out_buf, ctypes.c_size_t(n_elem), ctypes.c_size_t(elem_size), ctypes.c_size_t(0))

        else:
            raise RuntimeError(f"Unsupported codec: {codec_name!r}")

        return np.frombuffer(bytes(out_data), dtype=dtype)

    def _process_image(self, value: object) -> None:
        """Decode an NTNDArray *value* and forward the resulting frame to the callback."""
        if self._frame_callback is None:
            return

        try:
            raw = value["value"]
            if raw is None:
                return

            dims: list[int] = [d["size"] for d in value["dimension"] if d["size"] > 0]
            if not dims:
                return

            flat = np.array(raw, copy=False)
            if flat.size == 0:
                return

            codec_name: str = ""
            try:
                codec_name = value["codec"]["name"] or ""
            except Exception:
                pass

            if codec_name:
                compressed_size: int = int(value["compressedSize"])
                uncompressed_size: int = int(value["uncompressedSize"])
                raw_param = value["codec"]["parameters"]
                scalar_type: int = int(raw_param) if raw_param is not None else 5
                _log.debug("Decompressing codec=%s scalar_type=%d compressed=%d uncompressed=%d", codec_name, scalar_type, compressed_size, uncompressed_size)
                flat = self._decompress(flat.tobytes(), codec_name, scalar_type, compressed_size, uncompressed_size)

            image = flat.reshape(dims[::-1])
            _log.debug("Delivering frame shape=%s dtype=%s", image.shape, image.dtype)
            self._frame_callback(image)
        except Exception:
            _log.exception("Error processing NTNDArray frame")
