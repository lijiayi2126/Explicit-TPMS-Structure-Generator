import os
import gc
import abc

import cadquery as cq
import numpy as np
import scipy

# ── 用 geomdl 替换手写的 B-spline 基函数 ──────────────────
from geomdl import knotvector as geomdl_kv
from geomdl import helpers    as geomdl_helpers
from geomdl import BSpline    as geomdl_BSpline

from OCP.Geom           import Geom_BSplineSurface
from OCP.BRepMesh       import BRepMesh_IncrementalMesh
from OCP.IGESControl    import IGESControl_Writer
from OCP.STEPControl    import STEPControl_Writer, STEPControl_AsIs
from OCP.gp             import gp_Pnt, gp_Trsf
from OCP.TColgp         import TColgp_Array2OfPnt
from OCP.TColStd        import TColStd_Array1OfReal, TColStd_Array1OfInteger
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepOffsetAPI  import BRepOffsetAPI_ThruSections

_HERE = os.path.dirname(os.path.abspath(__file__))


# =========================================================
#  B-spline 工具（geomdl 封装）
# =========================================================

def make_uniform_knots(n_ctrl: int, degree: int) -> list:
    """
    生成端点插值型均匀节点向量。
    """
    return geomdl_kv.generate(degree, n_ctrl)


def find_span(n: int, p: int, u: float, U) -> int:
    return geomdl_helpers.find_span_linear(n, p, u, list(U))


def basis_funs(span: int, u: float, p: int, U) -> np.ndarray:
    return np.array(
        geomdl_helpers.basis_function(p, list(U), span, u)
    )

def trivariate_evaluate(ctrl_pts: np.ndarray,
                        knots_u, knots_v, knots_w,
                        degree: int,
                        u: float, v: float, w: float) -> np.ndarray:
    """
    ctrl_pts: shape (nu+1, nv+1, nw+1, 3)，轴序 (u, v, w)
    """
    nu1, nv1, nw1, _ = ctrl_pts.shape   # 各方向控制点数

    vol = geomdl_BSpline.Volume()

    # ── Step 1: 先设 degree ──────────────────────────────
    vol.degree_u = degree
    vol.degree_v = degree
    vol.degree_w = degree

    # ── Step 2: 用 cpsize 一次性设置三个方向的控制点数 ──
    #    注意：不是 ctrlpts_size_u/v/w，而是 cpsize 列表！
    vol.cpsize = [nu1, nv1, nw1]

    # ── Step 3: 展平控制点，geomdl 的顺序是 u→v→w ──────
    #    shape (nu1*nv1*nw1, 3)，行优先展平
    flat_ctrlpts = ctrl_pts.reshape(-1, 3).tolist()
    vol.ctrlpts = flat_ctrlpts

    # ── Step 4: 最后设节点向量 ──────────────────────────
    vol.knotvector_u = list(knots_u)
    vol.knotvector_v = list(knots_v)
    vol.knotvector_w = list(knots_w)

    # ── 求值 ────────────────────────────────────────────
    u_c = float(np.clip(u, 0.0, 1.0))
    v_c = float(np.clip(v, 0.0, 1.0))
    w_c = float(np.clip(w, 0.0, 1.0))

    result = vol.evaluate_single((u_c, v_c, w_c))
    return np.array(result)

# =========================================================
#  等参曲面提取
# =========================================================

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
#  OCC 格式转换
# =========================================================

def convert_knots(knots_flat, degree):
    """展平节点向量"""
    knots = np.asarray(knots_flat, dtype=float)
    uniq, mult = [], []
    prev, count = knots[0], 1
    for k in knots[1:]:
        if np.isclose(k, prev, atol=1e-12):
            count += 1
        else:
            uniq.append(prev); mult.append(count)
            prev, count = k, 1
    uniq.append(prev); mult.append(count)
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


def build_occ_bspline_face(pts_grid: np.ndarray,
                            degree: int = 3):
    """
    (n, n, 3) 点网格 → OCC Geom_BSplineSurface → TopoDS_Face。
    节点向量由 geomdl 生成，OCC 格式转换由本模块负责。
    """
    n     = pts_grid.shape[0]
    knots = make_uniform_knots(n, degree)          # geomdl 生成
    u_uniq, u_mult = convert_knots(knots, degree)  # 转 OCC 格式

    poles = TColgp_Array2OfPnt(1, n, 1, n)
    for i in range(n):
        for j in range(n):
            x, y, z = pts_grid[i, j]
            poles.SetValue(i + 1, j + 1, gp_Pnt(float(x), float(y), float(z)))

    surf = Geom_BSplineSurface(
        poles,
        to_occ_real_array(u_uniq), to_occ_real_array(u_uniq),
        to_occ_int_array(u_mult),  to_occ_int_array(u_mult),
        degree, degree, False, False
    )
    return BRepBuilderAPI_MakeFace(surf, 1e-6).Shape()

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


def apply_T(shape: cq.Shape,
            T: np.ndarray, scale: float = 1.0) -> cq.Shape:
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