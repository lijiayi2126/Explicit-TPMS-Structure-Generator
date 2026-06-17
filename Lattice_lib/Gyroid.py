import numpy as np
import cadquery as cq
from Lattice_lib.TPMS_base import TPMSBase
from Nurbs_Base.bspline_func import make_location_from_matrix   # 从基类文件导出


class Gyroid(TPMSBase):

    # ── eta2 = 1（单胞归一化边长）────────────────────
    _eta = 1.0

    # ── TA：6 个旋转矩阵 ─────────────────────────────
    @staticmethod
    def _build_TA(e):
        TA = [None] * 7          # 下标从 1 开始，TA[0] 不用
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

    # ── TB：8 个平移/反射矩阵 ─────────────────────────
    @staticmethod
    def _build_TB(e):
        TB = [None] * 9          # 下标从 1 开始
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

    # ── 按 MATLAB 循环生成全部 24 个变换矩阵 ──────────
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

        return T                                  # 长度 = 24

    # ── TPMSBase 必须实现的接口 ───────────────────────

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

    # ── 核心：make_cell ───────────────────────────────
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


# ── 向后兼容入口 ──────────────────────────────────────

def gyroid_Shell(unit_cell_size, w, Nx, Ny, Nz, export_type=None):
    return Gyroid().make_shell(unit_cell_size, w, Nx, Ny, Nz, export_type)

def gyroid_Solid(unit_cell_size, w_bottom, w_top, Nx, Ny, Nz, export_type=None):
    return Gyroid().make_solid(unit_cell_size, w_bottom, w_top, Nx, Ny, Nz, export_type)
