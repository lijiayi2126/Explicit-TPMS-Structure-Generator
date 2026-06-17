import numpy as np
import cadquery as cq
from Lattice_lib.TPMS_base import TPMSBase
from Nurbs_Base.bspline_func import make_location_from_matrix


class Gyroid(TPMSBase):

    # Normalized unit-cell edge length.
    _eta = 1.0

    # Six rotation matrices.
    @staticmethod
    def _build_TA(e):
        TA = [None] * 7          # One-based indexing; TA[0] is unused.
        TA[1] = np.array([[1, 0, 0, 0],
                          [0, 1, 0, 0],
                          [0, 0, 1, 0],
                          [0, 0, 0, 1]], dtype=float)
        TA[2] = np.array([[0, 1, 0, 0],
                          [0, 0, 1, 0],
                          [-1, 0, 0, e],
                          [0, 0, 0, 1]], dtype=float)
        TA[3] = np.array([[0, 0, 1, 0],
                          [-1, 0, 0, e],
                          [0, -1, 0, e],
                          [0, 0, 0, 1]], dtype=float)
        TA[4] = np.array([[-1, 0, 0, e],
                          [0, -1, 0, e],
                          [0, 0, -1, e],
                          [0, 0, 0, 1]], dtype=float)
        TA[5] = np.array([[0, -1, 0, e],
                          [0, 0, -1, e],
                          [1, 0, 0, 0],
                          [0, 0, 0, 1]], dtype=float)
        TA[6] = np.array([[0, 0, -1, e],
                          [1, 0, 0, 0],
                          [0, 1, 0, 0],
                          [0, 0, 0, 1]], dtype=float)
        return TA

    # Eight translation/reflection matrices.
    @staticmethod
    def _build_TB(e):
        TB = [None] * 9          # One-based indexing; index 0 is unused.
        TB[1] = np.array([[1, 0, 0, 0],
                          [0, 1, 0, 0],
                          [0, 0, 1, 0],
                          [0, 0, 0, 1]], dtype=float)
        TB[2] = np.array([[-1, 0, 0, 2*e],
                          [0, -1, 0, e],
                          [0, 0, 1, 0],
                          [0, 0, 0, 1]], dtype=float)
        TB[3] = np.array([[-1, 0, 0, e],
                          [0, 1, 0, e],
                          [0, 0, 1, 0],
                          [0, 0, 0, 1]], dtype=float)
        TB[4] = np.array([[1, 0, 0, e],
                          [0, -1, 0, 2*e],
                          [0, 0, 1, 0],
                          [0, 0, 0, 1]], dtype=float)
        TB[5] = np.array([[1, 0, 0, 0],
                          [0, -1, 0, e],
                          [0, 0, 1, -e],
                          [0, 0, 0, 1]], dtype=float)
        TB[6] = np.array([[-1, 0, 0, 2*e],
                          [0, 1, 0, 0],
                          [0, 0, 1, -e],
                          [0, 0, 0, 1]], dtype=float)
        TB[7] = np.array([[-1, 0, 0, e],
                          [0, -1, 0, 2*e],
                          [0, 0, 1, -e],
                          [0, 0, 0, 1]], dtype=float)
        TB[8] = np.array([[1, 0, 0, e],
                          [0, 1, 0, e],
                          [0, 0, 1, -e],
                          [0, 0, 0, 1]], dtype=float)
        return TB

    # Build all 24 transform matrices following the MATLAB reference order.
    @classmethod
    def _build_all_T(cls):
        e  = cls._eta
        TA = cls._build_TA(e)
        TB = cls._build_TB(e)
        T  = []

        for j in [1, 2]:
            for i in [1, 3, 5]:
                T.append(TB[j] @ TA[i])          # k = 1~6

        for j in [3, 4, 5, 6]:
            for i in [2, 4, 6]:
                T.append(TB[j] @ TA[i])          # k = 7~18

        for j in [7, 8]:
            for i in [1, 3, 5]:
                T.append(TB[j] @ TA[i])          # k = 19~24

        return T                                  # length = 24

    # TPMSBase implementation

    @property
    def d_values(self):
        return [-0.2, -0.15, -0.1, -0.05, 0.0, 0.05, 0.1, 0.15, 0.2]

    @property
    def mat_prefix(self):
        return "srf_G_1_"

    @property
    def mat_prefix_2(self):
        return "srf_G_2_"

    @property
    def cell_period(self):
        return 2.0

    # Assemble one complete unit cell.
    def make_cell(self, w: float, location=None) -> cq.Compound:
        fp_1 = self.make_FP(w)
        fp_2 = self.make_FP_2(1 - w)

        T_list = self._build_all_T()

        patches = []
        for T in T_list:
            patches.append(fp_1.located(make_location_from_matrix(T)))
        for T in T_list:
            patches.append(fp_2.located(make_location_from_matrix(T)))

        result = cq.Compound.makeCompound(patches)

        if location is not None:
            result = result.located(location)
        return result


# Backward-compatible function entry points.

def gyroid_Shell(unit_cell_size, w, Nx, Ny, Nz, export_type=None):
    return Gyroid().make_shell(unit_cell_size, w, Nx, Ny, Nz, export_type)

def gyroid_Solid(unit_cell_size, w_bottom, w_top, Nx, Ny, Nz, export_type=None):
    return Gyroid().make_solid(unit_cell_size, w_bottom, w_top, Nx, Ny, Nz, export_type)
