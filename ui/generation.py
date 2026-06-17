import math
import time

from PyQt5.QtCore import QThread, pyqtSignal

from Lattice_lib.schwarzP import schwarzP_Shell, schwarzP_Solid
from Lattice_lib.IWP import IWP_Shell, IWP_Solid
from Lattice_lib.Gyroid import gyroid_Shell, gyroid_Solid
from Lattice_lib.Diamond import diamond_Shell, diamond_Solid

from .geometry_io import as_cq_shape, import_model_shape, translate_shape_to_bbox


class GenerateThread(QThread):
    finished = pyqtSignal(float)
    error    = pyqtSignal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params
        self.result = None

    def run(self):
        try:
            t0 = time.perf_counter()
            self.result = self._build(self.params)
            self.finished.emit(time.perf_counter() - t0)
        except Exception:
            import traceback
            self.error.emit(traceback.format_exc())

    def _build(self, p):
        t  = p['type']
        if p.get('bool_enabled'):
            target = import_model_shape(p['model_path'])
            bbox = target.BoundingBox()
            if min(bbox.xlen, bbox.ylen, bbox.zlen) <= 0:
                raise ValueError("Imported model has an invalid bounding box.")
            s1 = float(p['cell_size'])
            if s1 <= 0:
                raise ValueError("Unit cell size must be positive.")
            nx = max(1, math.ceil(bbox.xlen / s1))
            ny = max(1, math.ceil(bbox.ylen / s1))
            nz = max(1, math.ceil(bbox.zlen / s1))
            lattice = self._build_lattice(t, s1, nx, ny, nz, p)
            lattice = as_cq_shape(lattice)
            lattice = translate_shape_to_bbox(lattice, bbox)
            return lattice.intersect(target)

        nx, ny, nz = int(p['nx']), int(p['ny']), int(p['nz'])
        s1 = float(p['cell_size'])
        return self._build_lattice(t, s1, nx, ny, nz, p)

    def _build_lattice(self, t, s1, nx, ny, nz, p):
        if t == "SchwarzP-Shell":
            return schwarzP_Shell(s1, float(p['t']), nx, ny, nz)
        elif t == "SchwarzP-Solid":
            return schwarzP_Solid(s1, float(p['w_bot']), float(p['w_top']), nx, ny, nz)
        elif t == "IWP-Shell":
            return IWP_Shell(s1, float(p['t']), nx, ny, nz)
        elif t == "IWP-Solid":
            return IWP_Solid(s1, float(p['w_bot']), float(p['w_top']), nx, ny, nz)
        elif t == "Gyroid-Shell":
            return gyroid_Shell(s1, float(p['t']), nx, ny, nz)
        elif t == "Gyroid-Solid":
            return gyroid_Solid(s1, float(p['w_bot']), float(p['w_top']), nx, ny, nz)
        elif t == "Diamond-Shell":
            return diamond_Shell(s1, float(p['t']), nx, ny, nz)
        elif t == "Diamond-Solid":
            return diamond_Solid(s1, float(p['w_bot']), float(p['w_top']), nx, ny, nz)
        else:
            raise ValueError(f"Unknown lattice type: {t}")
