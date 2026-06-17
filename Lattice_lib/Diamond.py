import numpy as np
import cadquery as cq
from Lattice_lib.TPMS_base import TPMSBase
from Nurbs_Base.bspline_func import make_location_from_matrix


class Diamond(TPMSBase):

    # Normalized unit-cell edge length.
    _eta = 1.0

    # Three base rotation matrices.
    @staticmethod
    def _build_O():
        O = [None] * 4          # One-based indexing; O[0] is unused.
        O[1] = np.array([[ 1,  0,  0,  0],
                         [ 0,  1,  0,  0],
                         [ 0,  0,  1,  0],
                         [ 0,  0,  0,  1]], dtype=float)
        O[2] = np.array([[ 0, -1,  0,  0],
                         [ 0,  0, -1,  0],
                         [ 1,  0,  0,  0],
                         [ 0,  0,  0,  1]], dtype=float)
        O[3] = np.array([[ 0,  0,  1,  0],
                         [-1,  0,  0,  0],
                         [ 0, -1,  0,  0],
                         [ 0,  0,  0,  1]], dtype=float)
        return O

    # Four transform matrices in group A.
    @staticmethod
    def _build_A():
        A = [None] * 5          # One-based indexing; index 0 is unused.
        A[1] = np.eye(4, dtype=float)
        A[2] = np.array([[-1,  0,  0, -1],
                         [ 0, -1,  0,  1],
                         [ 0,  0,  1,  0],
                         [ 0,  0,  0,  1]], dtype=float)
        A[3] = np.array([[-1,  0,  0, -1],
                         [ 0,  1,  0,  0],
                         [ 0,  0, -1, -1],
                         [ 0,  0,  0,  1]], dtype=float)
        A[4] = np.array([[ 1,  0,  0,  0],
                         [ 0, -1,  0,  1],
                         [ 0,  0, -1, -1],
                         [ 0,  0,  0,  1]], dtype=float)
        return A

    # Four transform matrices in group B.
    @staticmethod
    def _build_B():
        B = [None] * 5          # One-based indexing; index 0 is unused.
        B[1] = np.array([[-1,  0,  0,  0],
                         [ 0,  0, -1,  1],
                         [ 0, -1,  0,  1],
                         [ 0,  0,  0,  1]], dtype=float)
        B[2] = np.array([[ 1,  0,  0, -1],
                         [ 0,  0,  1,  0],
                         [ 0, -1,  0,  1],
                         [ 0,  0,  0,  1]], dtype=float)
        B[3] = np.array([[ 1,  0,  0, -1],
                         [ 0,  0, -1,  1],
                         [ 0,  1,  0,  2],
                         [ 0,  0,  0,  1]], dtype=float)
        B[4] = np.array([[-1,  0,  0,  0],
                         [ 0,  0,  1,  0],
                         [ 0,  1,  0,  2],
                         [ 0,  0,  0,  1]], dtype=float)
        return B

    # Six translation matrices.
    @staticmethod
    def _build_C():
        C = [None] * 7          # One-based indexing; index 0 is unused.
        C[1] = np.array([[ 1,  0,  0,  2],
                         [ 0,  1,  0,  0],
                         [ 0,  0,  1, -2],
                         [ 0,  0,  0,  1]], dtype=float)
        C[2] = np.array([[ 1,  0,  0,  2],
                         [ 0,  1,  0,  0],
                         [ 0,  0,  1,  2],
                         [ 0,  0,  0,  1]], dtype=float)
        C[3] = np.array([[ 1,  0,  0,  0],
                         [ 0,  1,  0,  2],
                         [ 0,  0,  1, -2],
                         [ 0,  0,  0,  1]], dtype=float)
        C[4] = np.array([[ 1,  0,  0,  0],
                         [ 0,  1,  0,  2],
                         [ 0,  0,  1,  2],
                         [ 0,  0,  0,  1]], dtype=float)
        C[5] = np.array([[ 1,  0,  0,  2],
                         [ 0,  1,  0,  2],
                         [ 0,  0,  1,  0],
                         [ 0,  0,  0,  1]], dtype=float)
        C[6] = np.array([[ 1,  0,  0,  2],
                         [ 0,  1,  0,  2],
                         [ 0,  0,  1,  0],
                         [ 0,  0,  0,  1]], dtype=float)
        return C

    # Build all 96 transform matrices following the MATLAB reference order.
    @classmethod
    def _build_all_T(cls):
        O = cls._build_O()
        A = cls._build_A()
        B = cls._build_B()
        C = cls._build_C()
        T = []

        # kk = 1~12A{1..4} * O{1..3}
        for j in range(1, 5):
            for i in range(1, 4):
                T.append(A[j] @ O[i])

        # kk = 13~24B{1..4} * O{1..3}
        for j in range(1, 5):
            for i in range(1, 4):
                T.append(B[j] @ O[i])

        # kk = 25~36C{1} * B{1..4} * O{1..3}
        for j in range(1, 5):
            for i in range(1, 4):
                T.append(C[1] @ B[j] @ O[i])

        # kk = 37~48C{2} * A{1..4} * O{1..3}
        for j in range(1, 5):
            for i in range(1, 4):
                T.append(C[2] @ A[j] @ O[i])

        # kk = 49~60C{3} * B{1..4} * O{1..3}
        for j in range(1, 5):
            for i in range(1, 4):
                T.append(C[3] @ B[j] @ O[i])

        # kk = 61~72C{4} * A{1..4} * O{1..3}
        for j in range(1, 5):
            for i in range(1, 4):
                T.append(C[4] @ A[j] @ O[i])

        # kk = 73~84C{5} * A{1..4} * O{1..3}
        for j in range(1, 5):
            for i in range(1, 4):
                T.append(C[5] @ A[j] @ O[i])

        # kk = 85~96C{6} * B{1..4} * O{1..3}
        for j in range(1, 5):
            for i in range(1, 4):
                T.append(C[6] @ B[j] @ O[i])

        assert len(T) == 96, f"Expected 96 transform matrices, got {len(T)}."
        return T

    # TPMSBase implementation

    @property
    def d_values(self):
        return [-0.2, -0.15, -0.1, -0.05, 0.0, 0.05, 0.1, 0.15, 0.2]

    @property
    def mat_prefix(self):
        return "srf_D_1_"

    @property
    def mat_prefix_2(self):
        return "srf_D_2_"

    @property
    def cell_period(self):
        return 4.0 * self._eta   # Diamond period = 4 * eta.

    @property
    def cell_period(self):
        return 4.0


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

def diamond_Shell(unit_cell_size, w, Nx, Ny, Nz, export_type=None):
    return Diamond().make_shell(unit_cell_size, w, Nx, Ny, Nz, export_type)

def diamond_Solid(unit_cell_size, w_bottom, w_top, Nx, Ny, Nz, export_type=None):
    return Diamond().make_solid(unit_cell_size, w_bottom, w_top, Nx, Ny, Nz, export_type)
