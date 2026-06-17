import cadquery as cq
from Nurbs_Base import TPMSBase

class SchwarzP(TPMSBase):
    @property
    def d_values(self) -> list:
        return [-0.2, -0.15, -0.1, -0.05, 0.0, 0.05, 0.1, 0.15, 0.2]

    @property
    def mat_prefix(self) -> str:
        return "srf_P_"

    @property
    def cell_period(self):
        return 2.0

    def make_cell(self, w: float, location=None) -> cq.Compound:
        fp = self.make_FP(w)

        # Step 1: 6 face patches -> one senior patch.
        FP_0 = fp
        FP_1 = fp.mirror((0,  1, -1), (0, 0, 0))
        FP_2 = FP_1.mirror((1,  0, -1), (0, 0, 0))
        FP_3 = FP_2.mirror((1, -1,  0), (0, 0, 0))
        FP_4 = FP_3.mirror((0, -1,  1), (0, 0, 0))
        FP_5 = FP_4.mirror((1,  0, -1), (0, 0, 0))

        SP_0 = cq.Compound.makeCompound([FP_0, FP_1, FP_2, FP_3, FP_4, FP_5])

        # Step 2: 8 senior patches -> one full unit cell.
        SP_1 = SP_0.mirror((0, 0, 1), (0, 0, 0))
        SP_2 = SP_1.mirror((0, 1, 0), (0, 0, 0))
        SP_3 = SP_2.mirror((0, 0, 1), (0, 0, 0))
        SP_4 = SP_3.mirror((1, 0, 0), (0, 0, 0))
        SP_5 = SP_4.mirror((0, 0, 1), (0, 0, 0))
        SP_6 = SP_5.mirror((0, 1, 0), (0, 0, 0))
        SP_7 = SP_6.mirror((0, 0, 1), (0, 0, 0))

        result = cq.Compound.makeCompound(
            [SP_0, SP_1, SP_2, SP_3, SP_4, SP_5, SP_6, SP_7]
        )

        if location is not None:
            result = result.located(location)
        return result


# =========================================================
# Backward-compatible function entry points.
# =========================================================

def schwarzP_Shell(
    unit_cell_size: float,
    w: float,
    Nx: int, Ny: int, Nz: int,
    export_type: str = None
) -> cq.Compound:
    return SchwarzP().make_shell(unit_cell_size, w, Nx, Ny, Nz, export_type)


def schwarzP_Solid(
    unit_cell_size: float,
    w_bottom: float,
    w_top: float,
    Nx: int, Ny: int, Nz: int,
    export_type: str = None
) -> cq.Compound:
    return SchwarzP().make_solid(unit_cell_size, w_bottom, w_top, Nx, Ny, Nz, export_type)
