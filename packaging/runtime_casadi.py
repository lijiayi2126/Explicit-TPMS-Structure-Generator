"""Make bundled CasADi DLLs discoverable before CadQuery imports CasADi."""

import os
import sys


if sys.platform == "win32" and hasattr(sys, "_MEIPASS"):
    casadi_dir = os.path.join(sys._MEIPASS, "casadi")
    if os.path.isdir(casadi_dir):
        os.environ["PATH"] = casadi_dir + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            sys._casadi_dll_directory = os.add_dll_directory(casadi_dir)
