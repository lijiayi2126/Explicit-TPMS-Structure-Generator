# Nurbs_Base/volume.py
"""
封装 geomdl BSpline.Volume 的构造逻辑。
调用方只需传入控制点和节点向量，无需关心 geomdl 的初始化顺序。
"""

import numpy as np
from geomdl import BSpline as geomdl_BSpline
from geomdl import knotvector as geomdl_kv


def build_volume(ctrl_pts: np.ndarray,
                 degree: int,
                 knots_u=None,
                 knots_v=None,
                 knots_w=None) -> geomdl_BSpline.Volume:
    """
    构造 geomdl BSpline.Volume 对象。

    Parameters
    ----------
    ctrl_pts : np.ndarray, shape (nu, nv, nw, 3)
        控制点网格，轴序为 (u, v, w)。
    degree : int
        三个方向统一的 B-spline 阶数。
    knots_u/v/w : list | None
        节点向量。传 None 时自动生成均匀节点向量。

    Returns
    -------
    geomdl_BSpline.Volume
        已完成初始化、可直接调用 evaluate_single() 的 Volume 对象。
    """
    nu, nv, nw, _ = ctrl_pts.shape

    # 未传入节点向量时自动生成
    if knots_u is None:
        knots_u = geomdl_kv.generate(degree, nu)
    if knots_v is None:
        knots_v = geomdl_kv.generate(degree, nv)
    if knots_w is None:
        knots_w = geomdl_kv.generate(degree, nw)

    # ── 严格按照 degree → cpsize → ctrlpts → knotvector 顺序赋值 ──
    vol = geomdl_BSpline.Volume()
    vol.degree_u     = degree
    vol.degree_v     = degree
    vol.degree_w     = degree
    vol.cpsize       = [nu, nv, nw]
    vol.ctrlpts      = ctrl_pts.reshape(-1, 3).tolist()
    vol.knotvector_u = list(knots_u)
    vol.knotvector_v = list(knots_v)
    vol.knotvector_w = list(knots_w)

    return vol
