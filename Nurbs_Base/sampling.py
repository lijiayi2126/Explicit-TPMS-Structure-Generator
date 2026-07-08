# Nurbs_Base/sampling.py
"""
基于 geomdl Volume 对象的等参曲面采样工具。
依赖 volume.py 提供的 build_volume，不直接操作 geomdl 内部细节。
"""

import numpy as np
from geomdl import BSpline as geomdl_BSpline


def sample_iso_surface(vol: geomdl_BSpline.Volume,
                       fixed_axis: str,
                       fixed_val: float,
                       n_samples: int = 30) -> np.ndarray:
    """
    在某个参数方向固定值处，提取等参曲面的采样点网格。

    Parameters
    ----------
    vol : geomdl_BSpline.Volume
        由 build_volume() 构造的 Volume 对象。
    fixed_axis : str
        固定的参数方向，'u' | 'v' | 'w'。
    fixed_val : float
        固定参数值，范围 [0, 1]。
    n_samples : int
        另外两个方向各自的采样数量，输出网格为 (n_samples, n_samples, 3)。

    Returns
    -------
    np.ndarray, shape (n_samples, n_samples, 3)
        等参曲面上的采样点坐标。
    """
    if fixed_axis not in ('u', 'v', 'w'):
        raise ValueError(f"fixed_axis 必须是 'u'、'v' 或 'w'，收到: '{fixed_axis}'")

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
    在三个参数方向均匀采样，生成体内部点云。

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
