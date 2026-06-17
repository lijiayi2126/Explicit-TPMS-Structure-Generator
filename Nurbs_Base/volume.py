# Nurbs_Base/volume.py
"""
Helper functions for constructing geomdl BSpline.Volume objects.
Callers only need to provide control points and knot vectors; this module
handles the required geomdl initialization order.
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
    Build a geomdl BSpline.Volume object.

    Parameters
    ----------
    ctrl_pts : np.ndarray, shape (nu, nv, nw, 3)
        Control point grid in (u, v, w) axis order.
    degree : int
        Uniform B-spline degree for all three parameter directions.
    knots_u/v/w : list | None
        Knot vectors. When omitted, clamped uniform knot vectors are generated.

    Returns
    -------
    geomdl_BSpline.Volume
        Initialized volume object ready for evaluate_single().
    """
    nu, nv, nw, _ = ctrl_pts.shape

    # Generate default knot vectors when none are provided.
    if knots_u is None:
        knots_u = geomdl_kv.generate(degree, nu)
    if knots_v is None:
        knots_v = geomdl_kv.generate(degree, nv)
    if knots_w is None:
        knots_w = geomdl_kv.generate(degree, nw)

    # geomdl expects assignments in this order.
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
