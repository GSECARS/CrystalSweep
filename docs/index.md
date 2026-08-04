# CrystalSweep

**CrystalSweep** is beamline control and data acquisition software for single-crystal X-ray diffraction experiments at synchrotron facilities. It provides an integrated interface for controlling beamline hardware and collecting diffraction data.

## Features

- Integrated GUI for beamline hardware control
- Single-crystal X-ray diffraction data acquisition
- Support for EPICS-based motor and detector control
- Newport XPS and Aerotech A1 motion controller support
- Real-time image display and intensity visualization
- pyFAI-based azimuthal integration
- CrysAlis and HDF5 output format support

## Quick Start

```bash
# Install
pip install crystalsweep

# Launch the GUI
crystalsweep --gui
```

See [Installation](installation.md) for full setup instructions.

## License

CrystalSweep is distributed under the [MIT License](https://github.com/GSECARS/CrystalSweep/blob/main/LICENSE).
Developed at [GSECARS](https://gsecars.uchicago.edu), The University of Chicago.
