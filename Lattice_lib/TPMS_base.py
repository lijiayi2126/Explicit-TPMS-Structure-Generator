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
# B-spline basis functions
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
# Convert knot vectors to OCC arrays
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
# Export helper
# =========================================================
def make_location_from_matrix(T: np.ndarray, scale: float = 1.0) -> cq.Location:
    """
    Convert a 4x4 homogeneous transform matrix to a CadQuery location.
    The translation column is scaled by the unit-cell size in millimeters.
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
    """Apply a homogeneous transform matrix to a shape."""
    return shape.located(make_location_from_matrix(T, scale))

# =========================================================
# Abstract base class
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
            0.01,  # Linear deflection; smaller values create denser meshes.
            False,  # Use absolute, not relative, deflection.
            0.1,  # Angular deflection in radians.
            True  # Enable parallel meshing.
        )
        mesh.Perform()
        cq.Shape(wp_shape).exportStl(filename)

    else:
        raise ValueError(
            f"Unsupported export format: '{export_type}'. Use STEP, IGES, or STL."
        )

    print(f"Exported: {os.path.abspath(filename)}")


# =========================================================
# Geometry helper
# =========================================================

class TPMSBase(abc.ABC):
    """
    Abstract base class for TPMS lattice generators.

    Subclasses must provide the offset values, the precomputed .mat prefix,
    and the symmetry operation that assembles one complete unit cell.
    Dual-surface families such as Gyroid and Diamond also provide
    mat_prefix_2 for the second surface family.
    """

    # Required subclass API.

    @property
    @abc.abstractmethod
    def d_values(self) -> list:
        """Precomputed offset values, for example [-0.2, ..., 0.2]."""

    @property
    @abc.abstractmethod
    def mat_prefix(self) -> str:
        """Primary precomputed .mat filename prefix."""

    @abc.abstractmethod
    def make_cell(self, w: float, location=None) -> cq.Compound:
        """Assemble the base face patch into a complete unit cell."""

    # Optional dual-surface API.

    @property
    def mat_prefix_2(self) -> str | None:
        """
        Optional second precomputed .mat prefix.

        Single-surface families return None. Dual-surface families override this.
        """
        return None

    # Optional configuration hook.

    @property
    def precomp_dir(self) -> str:
        """Directory containing precomputed surface data."""
        return "precomputation"

    # Internal helpers.

    def _mat_path(self, d: float, prefix: str) -> str:
        """Build the absolute path for a precomputed .mat file."""
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
        Load precomputed surfaces for the selected prefix, interpolate along
        the w direction, and return the base face patch.
        """
        # 1. Load all precomputed surfaces.
        coefs_list = []
        for d in self.d_values:
            mat = scipy.io.loadmat(self._mat_path(d, prefix))
            coefs_list.append(mat['off_srf']['coefs'][0, 0])

        nu = coefs_list[0].shape[1]
        nv = coefs_list[0].shape[2]

        # 2. Interpolate the requested iso-surface control points.
        w_knots = self._build_w_knots(len(coefs_list))
        coefs   = extract_iso_surface(coefs_list, w_knots, 3, w)

        # 3. Load u/v knot vectors.
        ref_d = self.d_values[len(self.d_values) // 2]
        srf   = scipy.io.loadmat(self._mat_path(ref_d, prefix))['off_srf']
        kc    = srf['knots'][0, 0]
        u_kf  = kc[0][0].flatten()
        v_kf  = kc[0][1].flatten()
        order = srf['order'][0, 0].flatten()
        deg_u = int(order[0]) - 1
        deg_v = int(order[1]) - 1

        # 4. Build OCC control points after dehomogenization.
        poles = TColgp_Array2OfPnt(1, nu, 1, nv)
        for i in range(nu):
            for j in range(nv):
                wx, wy, wz, ww = coefs[:, i, j]
                x, y, z = (wx/ww, wy/ww, wz/ww) if abs(ww) > 1e-10 else (wx, wy, wz)
                poles.SetValue(i + 1, j + 1, gp_Pnt(float(x), float(y), float(z)))

        # 5. Convert knot vectors to OCC format.
        u_uniq, u_mult = convert_knots(u_kf, deg_u)
        v_uniq, v_mult = convert_knots(v_kf, deg_v)

        # 6. Build and return the B-spline face.
        surface = Geom_BSplineSurface(
            poles,
            to_occ_real_array(u_uniq), to_occ_real_array(v_uniq),
            to_occ_int_array(u_mult),  to_occ_int_array(v_mult),
            deg_u, deg_v,
            False, False
        )
        return cq.Shape(BRepBuilderAPI_MakeFace(surface, 1e-6).Face())

    # Public face-patch API.

    def make_FP(self, w: float) -> cq.Shape:
        """
        Read the first surface family identified by mat_prefix.
        Single-surface families use this method directly; dual-surface
        families use it for the positive-w side.
        """
        return self._make_FP_from_prefix(w, self.mat_prefix)

    def make_FP_2(self, w: float) -> cq.Shape:
        """
        Read the second surface family identified by mat_prefix_2.
        Only dual-surface families implement this.
        """
        if self.mat_prefix_2 is None:
            raise NotImplementedError(
                f"{self.__class__.__name__} does not define mat_prefix_2; do not call make_FP_2()."
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
                            print(f"Warning: loft failed for cell ({i}, {j}, {k})")

        if not solids:
            raise RuntimeError(
                "All face lofts failed. Check w_bottom, w_top, and the precomputed data."
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
