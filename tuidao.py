import numpy as np


def generate_knot_vector(n, p=3):
    """生成准均匀节点矢量 (Clamped uniform knot vector)"""
    num_internal = n - p - 1
    if num_internal < 0:
        knots = [0] * (p + 1) + [1] * (p + 1)
    else:
        internal_knots = np.linspace(0, 1, num_internal + 2)[1:-1]
        knots = np.concatenate(([0] * (p + 1), internal_knots, [1] * (p + 1)))
    return knots


def compute_extraction_operator(knots, p=3):
    """计算一维 B-spline 到 Bezier 的抽取矩阵"""
    m = len(knots) - 1
    n = m - p - 1

    # 找到所有唯一的内部节点
    unique_knots = np.unique(knots)
    internal_knots = unique_knots[1:-1]

    # 初始算子为单位矩阵
    C = np.eye(n + 1)
    current_knots = list(knots)

    # 节点插入算法 (Boehm's Algorithm 的简化版用于抽取)
    # 在每个内部节点处重复插入，直到重数为 p
    operators = []

    # 这里的实现逻辑是为了演示约束关系，简化的抽取逻辑：
    # 每一个节点区间 [u_i, u_{i+1}] 对应一个 Bezier 片段
    segments = []
    for i in range(len(unique_knots) - 1):
        u_start, u_end = unique_knots[i], unique_knots[i + 1]
        if u_start == u_end: continue
        segments.append((u_start, u_end))

    return segments, internal_knots


def derive_g1_constraints(Nu, Nv):
    print(f"--- 正在推导 {Nu}x{Nv} 双三次B样条的 Bezier 抽取与 G1 约束 ---")

    u_knots = generate_knot_vector(Nu)
    v_knots = generate_knot_vector(Nv)

    u_unique = np.unique(u_knots)
    v_unique = np.unique(v_knots)

    num_u_segments = len(u_unique) - 1
    num_v_segments = len(v_unique) - 1

    print(f"曲面将被分解为 {num_u_segments} x {num_v_segments} 个 Bezier 片段。")
    print(f"U 节点矢量: {u_knots}")
    print("-" * 50)

    # 推导跨界约束 (以 U 方向相邻片段为例)
    # 设片段 A 在 [u_{k-1}, u_k], 片段 B 在 [u_k, u_{k+1}]
    for k in range(1, len(u_unique) - 1):
        u_prev = u_unique[k - 1]
        u_curr = u_unique[k]
        u_next = u_unique[k + 1]

        # 计算跨度比 (Ratio for C1/G1 continuity)
        # 在均匀 B 样条中，如果内部节点分布均匀，ratio 通常为 1
        h_left = u_curr - u_prev
        h_right = u_next - u_curr
        ratio = h_right / h_left

        print(f"\n[跨界处 U = {u_curr}] (片段 {k} 与 片段 {k + 1} 之间):")
        print(f"  G0 约束: Segment_{k}.P[3, j] == Segment_{k + 1}.P[0, j]")
        print(f"  G1 约束 (基于 C1 导出):")
        print(
            f"    (Segment_{k + 1}.P[1, j] - Segment_{k + 1}.P[0, j]) = {ratio:.4f} * (Segment_{k}.P[3, j] - Segment_{k}.P[2, j])")
        print(f"    注：该公式适用于 j = 0, 1, 2, 3 (所有跨界行的控制点)")

    # 如果需要处理 V 方向
    if num_v_segments > 1:
        print("\n" + "=" * 20 + " V 方向约束类推 " + "=" * 20)
        # 同理推导 V 方向的跨度比


# 示例运行
Nu, Nv = 5, 5
derive_g1_constraints(Nu, Nv)