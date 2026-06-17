import cadquery as cq
from Lattice_lib.cube import cubic

size_1 = 10 # cubic尺寸
size_2 = 10
size_3 = 5
Nx = 2 # cubic数量
Ny = 1
Nz = 1
model = cubic(size_1, size_2, size_3, Nx, Ny, Nz)