# Usage

## Launching the Application

CrystalSweep is launched via the command line:

```bash
crystalsweep
```

## Main Interface

The main window provides access to all beamline control and data acquisition features:

- **File Settings** — configure output paths and file naming
- **Collection Settings** — set exposure time, number of frames, oscillation range
- **Collection Table** — queue and manage multiple data collection runs
- **Beamline Config** — hardware connection settings (EPICS PVs, motor names)

## Data Collection

1. Open **Beamline Config** and verify that all hardware connections are active.
2. Set your output directory and file prefix in **File Settings**.
3. Configure scan parameters in **Collection Settings** (exposure, omega range, step size).
4. Add one or more runs to the **Collection Table**.
5. Click **Collect** to start acquisition.

## Image Viewer

The built-in area detector viewer displays live detector images during collection. Use the colormap selector and intensity histogram to adjust the display range.

## Integration

Azimuthal integration is performed via [pyFAI](https://pyfai.readthedocs.io). A calibration file (`.poni`) must be loaded before integration results are displayed.

## Output Formats

| Format | Description |
|--------|-------------|
| HDF5 / NeXus | Default output, one file per dataset |
| CrysAlis | `.ccd` / `.par` files for CrysAlisPro import |
