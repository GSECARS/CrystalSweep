# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-10-12

### Added

- Added wxPython GUI built on wxutils with a main controller and view, lazy UI loading, and a dark theme
- Added DPI awareness and font scaling for Windows, and a default window size of 1600x900
- Added native menu bar on macOS and a custom menu bar on other platforms, with File menu for loading and saving configs and the active config name shown in the menu bar
- Added dark-themed confirm and message dialogs, a close prompt that blocks exit during a collection, and an aborting dialog that blocks the UI until cleanup completes
- Added application logo, ico and icns assets, and `--make-icon` / `--public` flags to create desktop shortcuts via pyshortcuts
- Added per-user app data directory for beamline configs, hooks script, and the log file
- Added `AppConfig` from wxutils for application name, assets, and shortcuts
- Added TOML-based beamline configuration replacing `.env` files, with a config model, controller, and view
- Added separate General, Detectors, Controllers, and Positioners configuration dialogs, with auto-save on close
- Added persistent motion controller connections on config save, reused during collection
- Added per-motor controller type, XPS group and positioner, soft-limit validation, and EPICS limit monitors
- Added restore PVs, abort PV, and shutter PV configuration with open and close values and a delay after open
- Added raw directory support to decouple detector write paths from output paths, with local-to-remote path mapping
- Added per-detector file template, path mapping, and auto-increment control with live IOC sync
- Added dedicated CrysAlis config dialog with PAR, SET, and CCD calibration file paths and load on startup
- Added configurable CrysAlis rotation axis, image transforms (flip left/right, flip up/down), and reverse frame order per beamline config
- Added beamline-level preview settings (exposure, timeout, image count) and a centering tools enable option
- Allowed saving incomplete beamline configs, with the Collect button gated on readiness
- Added file settings panel for filename, path, frame number, map extension, format flags, and software calibration, with path validation status
- Added collection settings panel with scan type, exposure, rotation range, start/end, and step, with per-type defaults, beam angle offset, and bidirectional range/start/end sync
- Added collection table for queuing runs, virtualized so large map point sets no longer exhaust Windows GDI handles, with active row highlighting and a Use Ext. toggle
- Added still, wide, and step scan types, with step scans in slew and EPICS modes and single-file HDF5 output
- Added map scans with a motor table, presets, per-motor mapping flag, group metadata, per-point file naming, and a subfolder per map
- Added snake and trajectory map scanning with a toggle, XPS line trajectories, keep shutter open options, and a save XPS gathering file checkbox for still map trajectory scans
- Added shutter control for non-still scans and a keep shutter open option for still and wide maps
- Added collect panel with progress bar, point and frame display, live ETA and elapsed time, and sub-status phases (preparing, moving, collecting, readout)
- Added abort handling that stops the detector, runs the post-scan hook, and restores motors and PVs
- Added EPICS online/offline indicator that disables Collect when offline
- Added motor position snapshot on collection start and restore on end or abort
- Added overwrite warning before collection when output files already exist
- Added Get and Move buttons on collection rows
- Added snake combiner that flips and appends map rows incrementally into a combined HDF5 file, with an option to copy step and wide map output to the target directory
- Added `OutputPaths` utility to resolve all output paths for a collection run
- Added script editor with Python syntax highlighting for the user hooks script
- Added `pre_scan`, `post_scan`, `pre_collection`, and `post_collection` hooks, with EDIO routing moved into the hooks script and the test mode flag passed through
- Added area detector viewer with live EPICS streaming through a single p4p monitor, a decoder pool, frame stats, RGB support, and client-side decompression of NTNDArray streams
- Added GPU rendering via PyOpenGL with native dtype upload, throttled histogram, coalesced redraw, and selectable live binning (none, stride, mean)
- Added intensity histogram and colormaps through wxmplot and wxutils
- Added pyFAI azimuthal integration with an ROI integration plot and a View menu option to toggle it
- Added single-crystal centering preview tab with start and stop preview, step-size presets, a custom step in mm, and per-motor jog rows with live readback
- Added original, current, and best position snapshots with Go buttons
- Added auto-optimize sweep with live ROI maximum coloring, restore to original positions on abort, and a default range of 0.005 and step of 0.001
- Added dynamic sizing so the centering tools fit more motors
- Added scan driver architecture with Newport XPS and Aerotech A1 motion controllers and plain EPICS motors
- Added detector models for Eiger and Pilatus with HDF5, TIFF, and CBF saving
- Added `EpicsModel` for PV connectivity checks
- Added multi-format conversion with output organised per basename for step scans and flat for still and wide scans
- Added CrysAlis conversion through esperanto, running in a separate process
- Added direct HDF5 conversion via cryio for non-Eiger detectors
- Added incremental post-scan format conversion that can be toggled for non-native formats
- Added pytest suite and a GitHub Actions workflow to run it
- Added Sphinx documentation with autoapi, MyST, and the PyData theme, deployed to GitHub Pages with GitHub Actions
- Added GitHub Actions workflow to publish to PyPI on new version tags
- Added contribution guide, changelog, pre-commit configuration, and a PyPI version badge in the README

### Changed

- Changed to wxutils for all custom widgets (buttons, checkboxes, text controls, combos, scroll bars, tables, tabbed panel, progress bar, menu bar, dialogs), replacing the in-house dark widgets
- Changed hardcoded theme constants to an `AppTheme` 
- Changed ROI integration plot from VisPy to a wxmplot line plot subclass, and image canvas and histogram to wxmplot
- Changed AD viewer polling to a single p4p monitor and moved the viewer into epicsapps, then to the public release of epicsapps
- Changed the scan package into `model/` and `ui/controller/`
- Changed `motor_limits.py` to `utils/limits.py` and `validator.py` to `utils/validators.py`
- Changed icons to the wxutils equivalents
- Changed output layout so converted files sit inside the map folder, without a `_converted` suffix
- Changed map labels to frame number plus point index
- Changed CrysAlis conversion to use `eiger2crysalis` with a fully config-driven geometry
- Changed packaging to Hatchling with versions from git tags
- Changed LICENSE to LICENSE.txt and file headers to SPDX identifiers
- Changed collection to move all sample motors to point positions before each scan, and non-map motors per column during maps
- Changed still scans to collect at the current position
- Changed scan time estimates to include shutter delay and per-scan overhead
- Changed required scan parameters to be enforced instead of silently defaulting
- Changed scan types order to still, wide, step
- Changed the hooks module to be pinned for the duration of a collection so pre and post collection hooks share state
- Changed output conflict checks to use the target directory instead of the raw directory
- Changed docs to Sphinx and the tests workflow file to `tests.yml`
- Changed p4p error handling and polling default

### Fixed

- Fixed overlay rendering and dropdown issues on Windows by switching to popup windows with focus-based dismissal
- Fixed libca conflict between pyepics and p4p
- Fixed collection loop skipping points after the first scan
- Fixed abort reliability with sequential PV writes, a shared abort event, and abort checks throughout the scan workers
- Fixed map motor moves, map origins read from live positions, and map step and points edits not syncing to the model
- Fixed XPS wide and step scans, pulse count, trajectory group selection, and moving omega to the start position
- Fixed wide scan flip to alternate by row and use a backward trajectory on XPS for reversed scans
- Fixed progress bar for map groups, still trajectory maps, step scans, Eiger, and Pilatus
- Fixed still trajectory map file numbering on snake-reversed rows
- Fixed CrysAlis, raw, and target directory resolution for output, conversion, and conflict checks
- Fixed mkdir failures on Windows network shares and deep output directories
- Fixed cbf format to use the TIFF1 plugin with a cbf file template
- Fixed frame number handling for non-map collections and file copy and conversion frame capture
- Fixed per-row map combine for HDF5 detectors and double-nested map folders
- Fixed startup delay and shutter opening order
- Fixed centering tools layout, ROI guard, soft limits on jog and sweep, and the preview button
- Fixed label visibility in dark mode and the frame number control collapsing
- Fixed test mode row collection errors and acquire timeout issues

### Removed

- Removed `python-dotenv` configuration, hdf5plugin decompression, and the step buttons from the centering tools
- Removed row shift control from collection settings
- Removed MkDocs configuration and hand-written API reference pages
