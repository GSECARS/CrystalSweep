# Installation

## Requirements

- Python 3.14
- wxPython 4.2.5+
- A working EPICS environment (for beamline control)

## Install from PyPI

```bash
pip install crystalsweep
```

## Install from Source

```bash
git clone https://github.com/GSECARS/CrystalSweep.git
cd CrystalSweep
pip install .
```

### Using uv (recommended for development)

```bash
git clone https://github.com/GSECARS/CrystalSweep.git
cd CrystalSweep
uv sync
uv run crystalsweep --gui
```

## Platform Notes

CrystalSweep is developed and tested on macOS and Windows. Linux may work but is not officially supported.

## Verifying the Installation

```bash
crystalsweep --help
```

You should see the CLI help output. To launch the full GUI:

```bash
crystalsweep --gui
```
