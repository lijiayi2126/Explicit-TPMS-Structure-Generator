# Nurbs_Base/sampling.py
"""
Sampling helpers for geomdl Volume objects.
This module depends on build_volume() and avoids direct access to geomdl
internal state.
"""

import numpy as np
from geomdl import BSpline as geomdl_BSpline


def sample_iso_surface(vol: geomdl_BSpline.Volume,
                       fixed_axis: str,
                       fixed_val: float,
                       n_samples: int = 30) -> np.ndarray:
    """
    Sample an iso-parametric surface from a volume.

    Parameters
    ----------
    vol : geomdl_BSpline.Volume
        Volume object created by build_volume().
    fixed_axis : str
        'u' | 'v' | 'w'
    fixed_val : float
        Fixed parameter value in [0, 1].
    n_samples : int
        Number of samples in each free direction.

    Returns
    -------
    np.ndarray, shape (n_samples, n_samples, 3)
        Sampled point grid on the iso-parametric surface.
    """
    if fixed_axis not in ('u', 'v', 'w'):
        raise ValueError(f"fixed_axis must be 'u', 'v', or 'w'; got '{fixed_axis}'")

    fixed_val = float(np.clip(fixed_val, 0.0, 1.0))
    t = np.linspace(0.0, 1.0, n_samples)
    grid = np.zeros((n_samples, n_samples, 3))

    for i, t1 in enumerate(t):
        for j, t2 in enumerate(t):
            if fixed_axis == 'u':
                params = (fixed_val, t1, t2)
            elif fixed_axis == 'v':
                params = (t1, fixed_val, t2)
            else:  # 'w'
                params = (t1, t2, fixed_val)

            grid[i, j] = vol.evaluate_single(params)

    return grid


def sample_volume(vol: geomdl_BSpline.Volume,
                  n_samples: int = 10) -> np.ndarray:
    """
    Uniformly sample points inside the volume.

    Returns
    -------
    np.ndarray, shape (n_samples^3, 3)
    """
    t = np.linspace(0.0, 1.0, n_samples)
    pts = []
    for u in t:
        for v in t:
            for w in t:
                pts.append(vol.evaluate_single((u, v, w)))
    return np.array(pts)
