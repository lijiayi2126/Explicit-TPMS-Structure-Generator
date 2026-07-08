import cadquery as cq
# -----------------------------
# 示例晶格函数 1：简单立方体晶格
# -----------------------------
def cubic(size_1:float, size_2:float, size_3:float, Nx: int, Ny: int, Nz: int):
    """返回一个简单的立方体晶格"""
    # 生成每个单元的坐标
    Cell_pnts = [(i * size_1, j * size_2, k * size_3)
               for i in range(Nx) for j in range(Ny) for k in range(Nz)]

    # 创建空的 Workplane
    result = cq.Workplane().tag('base')

    # 将单元放置在每个点
    for pt in Cell_pnts:
        result = result.union(cq.Workplane().box(size_1, size_2, size_3)
                              .translate(pt))

    return result

# -----------------------------
# 示例晶格函数 2：带圆角的立方体晶格
# -----------------------------
def lattice_2(unit_cell_size: float, thickness: float, Nx: int, Ny: int, Nz: int) -> cq.Workplane:
    UC_pnts = [(i * unit_cell_size, j * unit_cell_size, k * unit_cell_size)
               for i in range(Nx) for j in range(Ny) for k in range(Nz)]
    result = cq.Workplane().tag('base')
    for pt in UC_pnts:
        result = result.union(cq.Workplane().box(unit_cell_size, unit_cell_size, unit_cell_size)
                              .edges().fillet(thickness)
                              .translate(pt))
    return result


# -----------------------------
# 示例晶格函数 3：带孔立方体晶格
# -----------------------------
def lattice_3(unit_cell_size: float, thickness: float, Nx: int, Ny: int, Nz: int) -> cq.Workplane:
    UC_pnts = [(i * unit_cell_size, j * unit_cell_size, k * unit_cell_size)
               for i in range(Nx) for j in range(Ny) for k in range(Nz)]
    result = cq.Workplane().tag('base')
    for pt in UC_pnts:
        wp = cq.Workplane().box(unit_cell_size, unit_cell_size, unit_cell_size)
        # 在每个单元中开孔
        wp = wp.faces(">Z").workplane().hole(thickness * unit_cell_size)
        result = result.union(wp.translate(pt))
    return result


# -----------------------------
# 可动态调用的字典
# -----------------------------
available_lattices = {
    "lattice_1": cubic,
    "lattice_2": lattice_2,
    "lattice_3": lattice_3,
}