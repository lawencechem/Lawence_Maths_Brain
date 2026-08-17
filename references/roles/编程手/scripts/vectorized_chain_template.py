# -*- coding: utf-8 -*-
"""
跨时间步向量化模板（"步内串行、步间并行"）。
适用于串行链 + 时间步并行的负载结构（如链式机构、逐节递推、时序积分的扫描）。
零依赖（numpy）。批规模 >1e4 且装有 torch/cupy 时，可将 np 数组换成 GPU 张量。

用法：把"单步链式递推"写成 f(s_prev, target) 的批量形式，外层按 i 循环。
验证：与串行基线逐点对比，相对差 < 1e-9 才算通过。
"""
import numpy as np

def chain_batch_skeleton(f_step_batch, s_head, T, N, d_len):
    """
    f_step_batch(s_prev, target) -> s_next：对 T 个时间步批量求下一把手弧长。
    s_head: (T,) 头部弧长；N: 步内节点数；d_len: (N-1,) 相邻链节长。
    返回 sig (T,N)。
    """
    sig = np.zeros((T, N))
    sig[:, 0] = s_head
    for i in range(1, N):
        prev = sig[:, i - 1].copy()
        sig[:, i] = f_step_batch(prev, d_len[i - 1])
    return sig

def newton_batch_example(path_point, path_tangent, prev_sig, target, d):
    """批量牛顿求 |P(s)-target|=d 的根（紧括区间 [prev-2d, prev-0.4d]）。"""
    s = prev_sig - d
    lo = prev_sig - 2.0 * d
    hi = prev_sig - 0.4 * d
    for _ in range(6):
        p = path_point(s)
        chord = np.hypot(p[..., 0] - target[..., 0], p[..., 1] - target[..., 1])
        Tt = path_tangent(s)
        denom = (p[..., 0] - target[..., 0]) * Tt[..., 0] + (p[..., 1] - target[..., 1]) * Tt[..., 1]
        safe = np.where(np.abs(denom) > 1e-12, denom, 1.0)
        g = chord - d
        s = np.clip(s - g * chord / safe, lo, hi)
        if np.all(np.abs(g * chord / safe) < 1e-12 * np.maximum(1.0, np.abs(s))):
            break
    return s

# ---- GPU 切换（装有 torch 且 GPU 可用时）----
# xp = np
# try:
#     import torch
#     if torch.cuda.is_available():
#         xp = torch
#         def hyp(a, b): return torch.hypot(a, b)
#         # 其余 np.einsum/clip/maximum 用 xp 对应写法；张量一次性整批放 GPU，
#         # 避免小批 cpu()/cuda() 往返。
# except ImportError:
#     pass
