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
├── main_ui.py                  # Main GUI application
├── Lattice_lib/                # TPMS geometry implementations
│   └── precomputation/         # Required precomputed surface data
├── Nurbs_Base/                 # NURBS and B-spline helpers
├── model/                      # Small example input models
├── Scripts/                    # Development/test scripts
├── pcell/                      # Example unit-cell CAD assets
├── requirements.txt            # Runtime dependencies
└── pyproject.toml              # Python project metadata
```

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
