# import time
# from cadquery.vis import show_object
# from Lattice_lib.TPMS import schwarzP_Shell
# from Lattice_lib.TPMS import schwarzP_Solid
#
# start = time.perf_counter()
# Shell = schwarzP_Shell(
#     10,         # 单胞尺寸
#     0.4,        # 生成指定曲面
#     2, 2, 2,    # 阵列
#     "STL"
# )
# elapsed = time.perf_counter() - start
# print(f"建模时间：{elapsed:.3f} s")
#
# start = time.perf_counter()
# Solid = schwarzP_Solid(
#     10,           # 单胞尺寸
#     0,          # 生成有厚度的实体
#     1,
#     1, 1, 1,      # 阵列
# )
# elapsed = time.perf_counter() - start
# print(f"建模时间：{elapsed:.3f} s")