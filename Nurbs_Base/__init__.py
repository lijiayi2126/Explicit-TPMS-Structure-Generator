# Nurbs_Base/__init__.py
from .bspline_func import (
    make_uniform_knots,
    find_span,
    basis_funs,
    extract_iso_surface,
    convert_knots,
    to_occ_real_array,
    to_occ_int_array,
    build_occ_bspline_face,
    make_location_from_matrix,
    apply_T,
    export_shape,
)
from .volume   import build_volume
from .sampling import sample_iso_surface, sample_volume
from Lattice_lib.TPMS_base import TPMSBase          # ← 新增

__all__ = [
    "make_uniform_knots", "find_span", "basis_funs",
    "extract_iso_surface", "convert_knots",
    "to_occ_real_array", "to_occ_int_array",
    "build_occ_bspline_face",
    "make_location_from_matrix", "apply_T",
    "export_shape",
    "build_volume",
    "sample_iso_surface", "sample_volume",
    "TPMSBase",
]
