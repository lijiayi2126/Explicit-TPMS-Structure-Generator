import os
import gc
import abc

import cadquery as cq
import numpy as np
import scipy

from OCP.Geom import Geom_BSplineSurface
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IGESControl import IGESControl_Writer
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.gp import gp_Pnt, gp_Trsf
from OCP.TColgp import TColgp_Array2OfPnt
from OCP.TColStd import TColStd_Array1OfReal, TColStd_Array1OfInteger
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections

_HERE = os.path.dirname(os.path.abspath(__file__))


# =========================================================
#  B-spline 基函数
# =========================================================

def find_span(n, p, u, U):
    if u == U[n + 1]:
        return n
    low, high = p, n + 1
    mid = (low + high) // 2
    while u < U[mid] or u >= U[mid + 1]:
        if u < U[mid]:
            high = mid
        else:
            low = mid
        mid = (low + high) // 2
    return mid


def basis_funs(span, u, p, U):
    N = np.zeros(p + 1)
    left  = np.zeros(p + 1)
    right = np.zeros(p + 1)
    N[0] = 1.0
    for j in range(1, p + 1):
        left[j]  = u - U[span + 1 - j]
        right[j] = U[span + j] - u
        saved = 0.0
        for r in range(j):
            denom = right[r + 1] + left[j - r]
            if abs(denom) < 1e-14:
                continue
            temp  = N[r] / denom
            N[r]  = saved + right[r + 1] * temp
            saved = left[j - r] * temp
        N[j] = saved
    return N


def extract_iso_surface(coefs_list, w_knots, degree_w, w):
    coefs = np.stack(coefs_list, axis=3)
    _, nu, nv, num = coefs.shape
    n_w  = num - 1
    span = find_span(n_w, degree_w, w, w_knots)
    N    = basis_funs(span, w, degree_w, w_knots)
    idx_start = span - degree_w
    relevant  = coefs[:, :, :, idx_start : idx_start + degree_w + 1]
    return np.tensordot(relevant, N, axes=([3], [0]))


# =========================================================
#  节点向量转 OCC 格式
# =========================================================

def convert_knots(knots_flat, degree):
    knots = np.asarray(knots_flat, dtype=float)
    uniq, mult = [], []
    prev, count = knots[0], 1
    for k in knots[1:]:
        if np.isclose(k, prev, atol=1e-12):
            count += 1
        else:
            uniq.append(prev)
            mult.append(count)
            prev, count = k, 1
    uniq.append(prev)
    mult.append(count)
    return np.array(uniq), np.array(mult)


def to_occ_real_array(arr):
    oc = TColStd_Array1OfReal(1, len(arr))
    for i, v in enumerate(arr):
        oc.SetValue(i + 1, float(v))
    return oc


def to_occ_int_array(arr):
    oc = TColStd_Array1OfInteger(1, len(arr))
    for i, v in enumerate(arr):
        oc.SetValue(i + 1, int(v))
    return oc

# =========================================================
#  齐次变换
# =========================================================
def make_location_from_matrix(T: np.ndarray, scale: float = 1.0) -> cq.Location:
    """
    将 4×4 齐次变换矩阵转为 cq.Location。
    平移列单位是"单胞归一化边长"，scale 是实际边长（mm）。
    """
    R = T[:3, :3]
    t = T[:3,  3] * scale
    trsf = gp_Trsf()
    trsf.SetValues(
        R[0,0], R[0,1], R[0,2], t[0],
        R[1,0], R[1,1], R[1,2], t[1],
        R[2,0], R[2,1], R[2,2], t[2],
    )
    return cq.Location(trsf)

def apply_T(shape: cq.Shape, T: np.ndarray, scale: float = 1.0) -> cq.Shape:
    """对 shape 施加齐次变换矩阵 T"""
    return shape.located(make_location_from_matrix(T, scale))

# =========================================================
#  导出工具
# =========================================================

def export_shape(wp_shape, export_dir, stem, export_type):
    os.makedirs(export_dir, exist_ok=True)
    ext = export_type.upper()

    if ext == "STEP":
        filename = os.path.join(export_dir, f"{stem}.step")
        writer = STEPControl_Writer()
        writer.Transfer(wp_shape, STEPControl_AsIs)
        writer.Write(filename)

    elif ext == "IGES":
        filename = os.path.join(export_dir, f"{stem}.igs")
        writer = IGESControl_Writer()
        writer.AddShape(wp_shape)
        writer.Write(filename)

    elif ext == "STL":
        filename = os.path.join(export_dir, f"{stem}.stl")
        mesh = BRepMesh_IncrementalMesh(
            wp_shape,
            0.01,  # linear deflection：越小越精细
            False,  # isRelative：False=绝对偏差，True=相对偏差
            0.1,  # angular deflection（弧度）：控制曲率处的细分密度
            True  # parallel：多线程加速
        )
        mesh.Perform()
        cq.Shape(wp_shape).exportStl(filename)

    else:
        raise ValueError(
            f"不支持的导出格式: '{export_type}'，请使用 STEP / IGES / STL"
        )

    print(f"[导出成功] {os.path.abspath(filename)}")


# =========================================================
#  抽象基类
# =========================================================

class TPMSBase(abc.ABC):
    """
    所有 TPMS 结构的抽象基类。

    子类必须实现
    ------------
    d_values   : property → list[float]    预计算偏置参数列表
    mat_prefix : property → str            主 .mat 文件名前缀（单曲面结构 / 双曲面结构的第一族）
    make_cell  : method                    FP → 完整单胞

    双曲面结构（Gyroid、Diamond 等）额外覆盖
    ----------------------------------------
    mat_prefix_2 : property → str          第二族曲面的 .mat 文件名前缀
                                           默认返回 None，表示单曲面结构
    """

    # ── 子类必须实现 ──────────────────────────────────

    @property
    @abc.abstractmethod
    def d_values(self) -> list:
        """预计算偏置参数列表，如 [-0.2, -0.15, ..., 0.2]"""

    @property
    @abc.abstractmethod
    def mat_prefix(self) -> str:
        """主曲面 mat 文件名前缀"""

    @abc.abstractmethod
    def make_cell(self, w: float, location=None) -> cq.Compound:
        """将基础面片拼合为完整单胞，各结构对称操作不同，子类自行实现"""

    # ── 双曲面结构子类可覆盖 ──────────────────────────

    @property
    def mat_prefix_2(self) -> str | None:
        """
        第二族曲面前缀。
        - 单曲面结构（SchwarzP、IWP 等）：返回 None（默认）
        - 双曲面结构（Gyroid、Diamond 等）：子类覆盖，返回前缀字符串
        """
        return None

    # ── 子类可选覆盖 ──────────────────────────────────

    @property
    def precomp_dir(self) -> str:
        """预计算文件夹，默认 'precomputation'"""
        return "precomputation"

    # ── 内部工具 ──────────────────────────────────────

    def _mat_path(self, d: float, prefix: str) -> str:
        """根据指定前缀构造 .mat 文件路径"""
        return os.path.join(
            _HERE, self.precomp_dir,
            f"{prefix}{d:.2f}.mat"
        )

    def _build_w_knots(self, num: int, pw: int = 3) -> np.ndarray:
        n_inner = num - pw - 1
        return np.concatenate([
            np.zeros(pw + 1),
            np.linspace(0, 1, n_inner + 2)[1:-1] if n_inner > 0 else np.array([]),
            np.ones(pw + 1)
        ])

    def _make_FP_from_prefix(self, w: float, prefix: str) -> cq.Shape:
        """
        用指定前缀读取预计算库，在 w 方向插值，返回基础面片。
        所有实际读取逻辑集中在这里，make_FP / make_FP_2 都调用它。
        """
        # 1. 读取所有预计算曲面
        coefs_list = []
        for d in self.d_values:
            mat = scipy.io.loadmat(self._mat_path(d, prefix))
            coefs_list.append(mat['off_srf']['coefs'][0, 0])

        nu = coefs_list[0].shape[1]
        nv = coefs_list[0].shape[2]

        # 2. 插值提取等值面控制点
        w_knots = self._build_w_knots(len(coefs_list))
        coefs   = extract_iso_surface(coefs_list, w_knots, 3, w)

        # 3. 读取 u/v 节点向量
        ref_d = self.d_values[len(self.d_values) // 2]
        srf   = scipy.io.loadmat(self._mat_path(ref_d, prefix))['off_srf']
        kc    = srf['knots'][0, 0]
        u_kf  = kc[0][0].flatten()
        v_kf  = kc[0][1].flatten()
        order = srf['order'][0, 0].flatten()
        deg_u = int(order[0]) - 1
        deg_v = int(order[1]) - 1

        # 4. 构造 OCC 控制点（去齐次化）
        poles = TColgp_Array2OfPnt(1, nu, 1, nv)
        for i in range(nu):
            for j in range(nv):
                wx, wy, wz, ww = coefs[:, i, j]
                x, y, z = (wx/ww, wy/ww, wz/ww) if abs(ww) > 1e-10 else (wx, wy, wz)
                poles.SetValue(i + 1, j + 1, gp_Pnt(float(x), float(y), float(z)))

        # 5. 节点向量转 OCC 格式
        u_uniq, u_mult = convert_knots(u_kf, deg_u)
        v_uniq, v_mult = convert_knots(v_kf, deg_v)

        # 6. 构造 B-spline 曲面并返回
        surface = Geom_BSplineSurface(
            poles,
            to_occ_real_array(u_uniq), to_occ_real_array(v_uniq),
            to_occ_int_array(u_mult),  to_occ_int_array(v_mult),
            deg_u, deg_v,
            False, False
        )
        return cq.Shape(BRepBuilderAPI_MakeFace(surface, 1e-6).Face())

    # ── 公共接口 ──────────────────────────────────────

    def make_FP(self, w: float) -> cq.Shape:
        """
        读取第一族曲面（mat_prefix）。
        单曲面结构（P、IWP）只调用这一个；
        双曲面结构（Gyroid、Diamond）的 +w 面也调用这个。
        """
        return self._make_FP_from_prefix(w, self.mat_prefix)

    def make_FP_2(self, w: float) -> cq.Shape:
        """
        读取第二族曲面（mat_prefix_2）。
        仅双曲面结构（Gyroid、Diamond）使用。
        单曲面结构调用此方法会抛出 NotImplementedError。
        """
        if self.mat_prefix_2 is None:
            raise NotImplementedError(
                f"{self.__class__.__name__} 是单曲面结构，没有 mat_prefix_2，"
                f"请勿调用 make_FP_2()"
            )
        return self._make_FP_from_prefix(w, self.mat_prefix_2)

    def make_shell(
        self,
        unit_cell_size: float,
        w: float,
        Nx: int, Ny: int, Nz: int,
        export_type: str = None
    ) -> cq.Compound:
        gc.collect()
        scale = unit_cell_size / self.cell_period

        cells = []
        for i in range(Nx):
            for j in range(Ny):
                for k in range(Nz):
                    cells.append(
                        self.make_cell(w).scale(scale).located(
                            cq.Location(cq.Vector(
                                i * unit_cell_size,
                                j * unit_cell_size,
                                k * unit_cell_size
                            ))
                        )
                    )

        compound = cq.Compound.makeCompound(cells)

        if export_type:
            export_shape(
                compound.wrapped,
                os.path.join(_HERE, "..", "Export"),
                f"{self.__class__.__name__}_Shell",
                export_type
            )
        return compound

    def make_solid(
        self,
        unit_cell_size: float,
        w_bottom: float,
        w_top: float,
        Nx: int, Ny: int, Nz: int,
        export_type: str = None
    ) -> cq.Compound:
        gc.collect()
        scale = unit_cell_size / self.cell_period

        solids = []
        for i in range(Nx):
            for j in range(Ny):
                for k in range(Nz):
                    loc = cq.Location(cq.Vector(
                        i * unit_cell_size,
                        j * unit_cell_size,
                        k * unit_cell_size
                    ))
                    cell_bot = self.make_cell(w_bottom).scale(scale).located(loc)
                    cell_top = self.make_cell(w_top   ).scale(scale).located(loc)

                    for fb, ft in zip(cell_bot.faces(), cell_top.faces()):
                        loft = BRepOffsetAPI_ThruSections(True, True)
                        loft.AddWire(fb.outerWire().wrapped)
                        loft.AddWire(ft.outerWire().wrapped)
                        loft.Build()
                        if loft.IsDone():
                            solids.append(cq.Shape(loft.Shape()))
                        else:
                            print(f"[警告] loft 失败：cell ({i},{j},{k})")

        if not solids:
            raise RuntimeError(
                "所有面片 loft 均失败，请检查 w_bottom / w_top 参数或预计算数据。"
            )

        compound = cq.Compound.makeCompound(solids)

        if export_type:
            export_shape(
                compound.wrapped,
                os.path.join(_HERE, "..", "Export"),
                f"{self.__class__.__name__}_Solid",
                export_type
            )
        return compound
