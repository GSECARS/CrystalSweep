# CrystalSweep

Beamline control and data acquisition software for single-crystal X-ray diffraction experiments at synchrotron facilities. It provides an integrated interface for controlling beamline hardware and collecting diffraction data.

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
pip install crystalsweep   # install
crystalsweep               # launch the GUI
```

## Guides

::::{grid} 1 2 2 2
:gutter: 3

:::{grid-item-card} Installation
:link: installation
:link-type: doc

Requirements, installing from PyPI or source, and verifying the installation.
:::

:::{grid-item-card} Usage
:link: usage
:link-type: doc

The main interface, data collection workflow, image viewer, integration, and output formats.
:::

:::{grid-item-card} API Reference
:link: autoapi/index
:link-type: doc

Auto-generated reference for all public classes and functions.
:::

::::

## License

CrystalSweep is distributed under the [MIT License](https://github.com/gsecars/crystalsweep/blob/main/LICENSE.txt). Developed at [GSECARS](https://gsecars.uchicago.edu), The University of Chicago.

```{toctree}
:maxdepth: 2
:hidden:

installation
usage
API Reference <autoapi/index>
```
