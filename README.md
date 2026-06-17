# Explicit TPMS

Explicit TPMS is a Python desktop application for generating TPMS lattice structures and exporting CAD/mesh files.

The GUI entry point is `main_ui.py`.

## Features

- Generate Schwarz P, IWP, Gyroid, and Diamond TPMS structures.
- Create shell and solid lattice variants.
- Preview generated geometry in a PyQt/OpenCascade viewer.
- Import CAD/mesh models for Boolean generation.
- Export generated results as STEP, IGES, or STL.

## Project Layout

```text
.
main_ui.py                  # Thin application entry point
ui/                         # PyQt UI modules, viewport, generation thread, and UI helpers
Lattice_lib/                # Four TPMS lattice implementations
  precomputation/           # Precomputed TPMS surface data used by the generators
Nurbs_Base/                 # NURBS and B-spline helper functions
model/                      # STEP sample models for Boolean/model clipping workflows
requirements.txt            # Runtime dependencies
pyproject.toml              # Python project metadata
```

## Code Organization

`Lattice_lib` defines the four supported TPMS lattice families: Schwarz P, IWP,
Gyroid, and Diamond. Each family exposes shell and solid generation functions
used by the GUI.

`Lattice_lib/precomputation` contains the precomputed TPMS surface results. These
`.mat` files are runtime data, not generated output, and the lattice generators
load them when assembling face patches.

`model` stores small STEP models that can be imported from the GUI for Boolean
model clipping/filling tests.

`ui` contains the application interface code:

- `main_window.py`: main window workflow and signal handling.
- `widgets.py`: reusable PyQt widgets and styling helpers.
- `viewport.py`: OpenCascade viewer widget.
- `generation.py`: background lattice generation thread.
- `density.py`: thickness, offset, and relative-density conversions.
- `geometry_io.py`: CAD/mesh model import and shape utilities.
- `constants.py`: UI constants and file filters.

## Installation

Use Python 3.10 to 3.12. CadQuery and OCP wheels are sensitive to Python versions, so avoid Python 3.13 unless your environment has compatible wheels.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

```powershell
python main_ui.py
```

After editable installation, the console script is also available:

```powershell
python -m pip install -e .
explicit-tpms
```

## Notes for GitHub

Generated export files are intentionally ignored by `.gitignore` because STEP/STL/IGES outputs can be very large. Put generated output under `Export/` or `exports/`.

No license has been selected yet. Add a `LICENSE` file before publishing if you want other people to have clear reuse rights.
