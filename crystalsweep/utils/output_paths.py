# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["OutputPaths"]

_FORMAT_EXT: dict[str, str] = {"hdf5": "h5", "cbf": "cbf", "tif": "tif"}


@dataclass(frozen=True, slots=True)
class OutputPaths:
    """Resolves all output paths for a single collection run.

    Constructed once from the current FileSettingsModel and active beamline
    config, then queried per-point by the spawn helpers in CollectController.
    All Path values are absolute.
    """

    directory: Path
    raw_directory: Path | None
    filename: str
    map_ext: str
    use_ext: bool
    file_ext: str
    file_number_width: int
    source_format: str
    extras: tuple[str, ...]
    use_crysalis: bool

    @staticmethod
    def ext_for_format(fmt: str) -> str:
        return _FORMAT_EXT.get(fmt, fmt)

    def stem(self, point) -> str:
        """Filename stem without zero-padded frame number."""
        if point.map_group:
            return self.map_folder_name()
        label = point.label.strip() if self.use_ext else ""
        parts = [p for p in [self.filename, label] if p]
        return "_".join(parts) if parts else self.filename

    def basename(self, point, frame_number: int) -> str:
        """Full filename with zero-padded frame number.

        For map points the label is used directly as the filename component
        and the frame number is always 1 (one acquisition per map position).
        """
        w = max(1, self.file_number_width)
        if point.map_group:
            row = max(1, point.map_row + 1) if point.map_row >= 0 else 1
            col = max(1, point.map_col + 1) if point.map_col >= 0 else frame_number
            map_ext = self.map_ext or "map"
            parts = [p for p in [self.filename, map_ext, f"{row:0{w}d}"] if p]
            return f"{'_'.join(parts)}_{col:0{w}d}"
        num = frame_number
        return f"{self.stem(point)}_{int(num):0{w}d}"

    def source_dir(self, point) -> Path:
        """Directory where the IOC writes detector output."""
        root = self.raw_directory if self.raw_directory else self.directory
        if point.map_group:
            return root / self.map_folder_name()
        return root

    def output_dir(self, point, frame_number: int) -> Path:
        """Directory where the primary file lands after copying/processing."""
        if point.map_group:
            return self.directory / self.map_folder_name()
        if self.extras or (point.scan_type == "step" and self.use_crysalis):
            return self.directory / self.basename(point, frame_number)
        return self.directory

    def conversion_dirs(self, point, frame_number: int, target: Path | None = None) -> dict[str, Path]:
        """Per-format output directory for each extra-format conversion.

        target overrides self.directory as the destination root so callers can
        supply the live model directory instead of the snapshot captured at
        collection start.
        """
        if not self.extras:
            return {}
        dest = target if target is not None else self.directory
        if point.map_group:
            root = dest / self.map_folder_name()
            return {fmt: root / fmt for fmt in self.extras}
        root = dest / self.basename(point, frame_number)
        if point.scan_type == "step":
            return {fmt: root / fmt for fmt in self.extras}
        # still or wide: converted files go in the same subfolder as the original
        return {fmt: root for fmt in self.extras}

    def crysalis_source_dir(self, point) -> Path:
        """Source directory for CrysAlis conversion.

        Returns the directory where the IOC wrote the detector files - raw_directory
        when configured, otherwise the primary output directory. Reading directly from
        the write location avoids any race with the async file-copy thread.
        """
        if point.map_group:
            return self.map_source_dir()
        return self.source_dir(point)

    def crysalis_output_dir(self, point, frame_number: int) -> Path:
        """Directory where CrysAlis writes its output."""
        bn = self.basename(point, frame_number)
        if point.map_group:
            return self.map_dir() / "crysalis" / bn
        return self.directory / bn / "crysalis"

    def expected_file(self, point, frame_number: int) -> Path:
        """Exact path the IOC would write - used for pre-collection conflict detection."""
        return self.source_dir(point) / f"{self.basename(point, frame_number)}.{self.file_ext}"

    def map_folder_name(self) -> str:
        """Subdirectory name used for all map row files."""
        suffix = self.map_ext or "map"
        return f"{self.filename}_{suffix}" if self.filename else suffix

    def map_source_dir(self) -> Path:
        """Directory where the IOC writes map row files."""
        root = self.raw_directory if self.raw_directory else self.directory
        return root / self.map_folder_name()

    def map_flipped_dir(self) -> Path:
        """Directory for snake-flipped copies of map row files."""
        return self.map_source_dir() / "flipped"

    def map_combined_path(self) -> Path:
        """Output path for the combined HDF5 map file, inside the map folder."""
        folder = self.map_folder_name()
        return self.directory / folder / f"{folder}.h5"

    def map_row_pattern(self) -> str:
        """Glob pattern matching all row files written by the IOC."""
        return f"{self.map_folder_name()}_*.{self.file_ext}"

    def map_row_file_pattern(self, row: int) -> str:
        """Glob pattern matching files written by the IOC for a single map row (0-indexed)."""
        w = max(1, self.file_number_width)
        suffix = self.map_ext or "map"
        row1 = max(1, row + 1)
        parts = [p for p in [self.filename, suffix, f"{row1:0{w}d}"] if p]
        return f"{'_'.join(parts)}_*.{self.file_ext}"

    def map_dir(self) -> Path:
        """Target directory for map output files."""
        return self.directory / self.map_folder_name()

    def map_raw_dir(self) -> Path:
        """Target subdirectory for raw files within the map output folder (still+trajectory maps)."""
        return self.map_dir() / "raw"
