#!/usr/bin/env python3
"""合成数据回收检验（三明治架构）：正向生成 → 加噪注入 → 反向回收 → 报偏差。

这是本地 P4（`../references/验证完备性.md`）的教学演示，只展示“已知真值 →
加噪 → 回收 → 报告”的结构。正式项目必须在 PROJECT_ROOT 实现题目专用正向模型、
噪声机制和回收链；本演示不能证明其他题目的算法或物理模型正确。

判定口径（关键）：
  - Δd 取多噪声实现下回收值的**均值偏差** mean(d_recovered) − d_true（系统偏差），
    不是单次观测偏差（单次偏差混入随机噪声）；
  - 报告不确定度取回收值的**单次弥散 σ_d**（不是 SEM）；
  - 本演示用 |Δd| < σ_d / 3 作为示例判据；正式阈值由题目精度和决策裕度确定。

内置示例（单层薄膜厚度反演）：
  - 正向生成：Airy 反射谱（含弱色散 n2(λ)），真值 d_true；
  - 加噪注入：按 --snr 加高斯噪声（默认峰值信噪比 50 dB）；
  - 反向回收：方法 A = 忽略相位色散的间距法（两光束一阶，选最深谷对）；
              方法 B = 含色散的 Airy 最小二乘拟合（多光束全阶）；
  - 报告 Δd、无偏判定、谷对漂移、可辨识带。

要点：
  - 方法 A 的回收厚度若在不同谷对间**单调漂移**（跨度远大于噪声），本身就是
    相位色散的内在证据——比「拟合好坏」更早暴露系统偏差。
  - 高阶拟合会**混叠**：fringe 对比度大时，RMSE 对厚度异常尖锐，粗网格会把
    真值"掉进网格缝里"而选中混叠阶。因此方法 B 用间距法（低阶）做初始种子、
    Airy 拟合（高阶）做精化——低阶不是没用，它是粗定位器（模型族继承）。
  - 本脚本保留为只读教学示例。换题时在 PROJECT_ROOT 新建项目专用验证脚本，
    不要原地修改本文件，也不要把 --demo 输出当作项目证据。

用法：
    python synthetic_recovery.py --demo
    python synthetic_recovery.py --demo --report results/回收检验.json
    python synthetic_recovery.py --demo --seed 7 --snr 45 --d 8100
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np


# Windows GBK 终端下 print 中文会 UnicodeEncodeError。
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


# ---------------------------------------------------------------------------
# 正向模型：单层薄膜 Airy 反射率（正入射，n2 可选弱色散）
# ---------------------------------------------------------------------------
def airy_reflectance(wavelengths: np.ndarray, d: float, n1: float,
                     n2_ref: float, n3: float, disp: float = 0.0) -> np.ndarray:
    """Airy 反射率（多光束全阶）。

    R(λ) = (r01² + r12² + 2·r01·r12·cosδ) / (1 + (r01·r12)² + 2·r01·r12·cosδ)
    δ = 4π·n2(λ)·d/λ；n2(λ) = n2_ref·(1 + disp·(λ−λ_ref)/λ_ref)

    间距法一阶近似是它在公比 ρ→0 时的极限，本函数为高阶版本。
    """
    lam_ref = float(np.mean(wavelengths))
    n2 = n2_ref * (1.0 + disp * (wavelengths - lam_ref) / lam_ref)
    r01 = (n1 - n2) / (n1 + n2)
    r12 = (n2 - n3) / (n2 + n3)
    delta = 4.0 * np.pi * n2 * d / wavelengths
    c = np.cos(delta)
    num = r01**2 + r12**2 + 2.0 * r01 * r12 * c
    den = 1.0 + (r01 * r12)**2 + 2.0 * r01 * r12 * c
    return num / np.maximum(den, 1e-12)


# ---------------------------------------------------------------------------
# 反向回收方法 A：间距法（两光束一阶，忽略相位色散）
# ---------------------------------------------------------------------------
def _smooth_spectrum(reflectance: np.ndarray, window: int = 13) -> np.ndarray:
    """盒式平滑（边沿镜像填充，消边缘伪谷）。供谷位检测前滤除噪声细纹。"""
    w = int(window)
    if w % 2 == 0:
        w += 1
    pad_n = w // 2
    padded = np.pad(reflectance, (pad_n, pad_n), mode="edge")
    kernel = np.ones(w) / w
    return np.convolve(padded, kernel, mode="same")[pad_n:-pad_n]


def _valley_indices(reflectance: np.ndarray, noise_sigma: float | None = None,
                    smooth: int = 13) -> list[int]:
    """真谷位检测：平滑 → 低于中值的局部极小 → P0 3σ 谷深过滤。

    顺序有讲究：
      1. 先平滑，噪声细纹（8~25 nm）按构造消失，真谷（~290 nm 宽）不动；
         否则噪声把一条真谷劈成多条细谷，中值间距被污染，间距法崩掉。
      2. 再按 P0 过滤：谷必须比邻域窗口内最高点低至少 **3σ**，否则视为
         噪声凹陷不计数。这条把"反幻想"落到谷位检测本身。
    noise_sigma 给 None 时跳过第 2 步（真实数据请估计平坦区残差 σ）。
    """
    if smooth and smooth > 1:
        reflectance = _smooth_spectrum(reflectance, smooth)
    med = float(np.median(reflectance))
    idx = []
    for i in range(1, len(reflectance) - 1):
        if (reflectance[i] < reflectance[i - 1]
                and reflectance[i] <= reflectance[i + 1]
                and reflectance[i] < med):
            idx.append(i)
    if noise_sigma is not None and noise_sigma > 0:
        win = 15  # 邻域窗口（样本数）：对照本谷两侧最近峰
        keep = []
        for i in idx:
            lo = max(0, i - win)
            hi = min(len(reflectance), i + win + 1)
            local_peak = float(np.max(reflectance[lo:hi]))
            if local_peak - reflectance[i] >= 3.0 * noise_sigma:
                keep.append(i)
        idx = keep
    return idx


def spacing_recover(wavelengths: np.ndarray, reflectance: np.ndarray,
                    n2: float, noise_sigma: float | None = None):
    """间距法回收厚度（线性/一阶估计）。

    相邻同型谷往返相位差 2π：δ(λ2) − δ(λ1) = 4π·n2·d·(1/λ2 − 1/λ1) = 2π
    ⇒  d = λ1·λ2 / (2·n2·|λ2 − λ1|)

    返回 (pairs, best_k, deepest_lambda)：
      pairs       每个相邻谷对的厚度估计（按中值间距自过滤，去伪谷对）；
      best_k      最深处谷所在谷对的下标（「挑某条深谷算厚度」的常见做法）；
      deepest_lambda  最深处谷的波长。
    noise_sigma 非 None 时谷位检测走平滑 + P0 3σ 谷深过滤（见 _valley_indices）。
    """
    mins = _valley_indices(reflectance, noise_sigma=noise_sigma)
    if len(mins) < 2:
        raise ValueError("间距法未找到足够多的谷位，无法回收")
    raw = []
    for a, b in zip(mins[:-1], mins[1:]):
        l1, l2 = float(wavelengths[a]), float(wavelengths[b])
        dl = abs(l2 - l1)
        if dl > 1e-9:
            raw.append((dl, l1, l2))
    if not raw:
        raise ValueError("间距法谷位间距过小，无法回收")
    med_dl = float(np.median([r[0] for r in raw]))
    pairs, pair_wl = [], []
    for dl, l1, l2 in raw:
        if 0.4 * med_dl <= dl <= 1.6 * med_dl:  # 丢弃与中值间距偏离过大的伪谷对
            pairs.append(l1 * l2 / (2.0 * n2 * dl))
            pair_wl.append(0.5 * (l1 + l2))
    if not pairs:
        raise ValueError("间距法谷位过乱，无法回收")
    deepest = min(mins, key=lambda i: reflectance[i])
    dl_deepest = float(wavelengths[deepest])
    best_k = int(np.argmin([abs(w - dl_deepest) for w in pair_wl]))
    return np.asarray(pairs), best_k, dl_deepest


# ---------------------------------------------------------------------------
# 反向回收方法 B：含色散 Airy 最小二乘拟合（多光束全阶）
# ---------------------------------------------------------------------------
def fit_airy(wavelengths: np.ndarray, reflectance: np.ndarray, n1: float,
             n2_ref: float, n3: float, d_seed: float,
             disp_range=(-0.06, 0.10), n_disp: int = 9):
    """含色散 Airy 拟合。d_seed 由低阶线性估计（间距法）提供。

    返回 (d_fit, disp_fit, rmse)。

    混叠与采样（关键）：
      fringe 对比度大时 RMSE 对 d 异常尖锐，粗网格会把真值"掉进网格缝"而
      选中混叠阶（d + λ_ref/(2·n2)）。因此本函数：
      1. 用 d_seed ± 1.5 个混叠周期做窗口——覆盖整数阶歧义；
      2. 窗口内步长 ≈ 4 nm 的粗扫——足以解析尖锐最小，选中正确阶；
      3. 精细 2D 网格 + 交替三分搜索收敛到机器精度（d 与 disp 都精化，
         否则 disp 网格量化会在高 SNR 下成为残留系统偏差）。
    """
    lam_ref = float(np.mean(wavelengths))
    period = lam_ref / (2.0 * n2_ref)              # 混叠周期（一整干涉级）
    lo, hi = d_seed - 1.5 * period, d_seed + 1.5 * period

    ds = np.linspace(lo, hi, int(max(300, (hi - lo) / 4.0)))
    disps = np.linspace(disp_range[0], disp_range[1], n_disp)

    def _rmse_at(d_val, dp):
        R = airy_reflectance(wavelengths, np.asarray([d_val])[:, None],
                             n1, n2_ref, n3, dp)
        return float(np.sqrt(np.mean((R[0] - reflectance) ** 2)))

    def _ternary(func, lo0, hi0, iters=80):
        """单参数三分搜索，收敛到括号内唯一极小。"""
        lo_t, hi_t = lo0, hi0
        for _ in range(iters):
            m1 = lo_t + (hi_t - lo_t) / 3.0
            m2 = hi_t - (hi_t - lo_t) / 3.0
            if func(m1) < func(m2):
                hi_t = m2
            else:
                lo_t = m1
        return 0.5 * (lo_t + hi_t)

    # 阶段 1：粗扫（步长 ≈ 4 nm）
    best = None
    for dp in disps:
        R = airy_reflectance(wavelengths, ds[:, None], n1, n2_ref, n3, dp)
        rmse = np.sqrt(np.mean((R - reflectance[None, :]) ** 2, axis=1))
        j = int(np.argmin(rmse))
        if best is None or rmse[j] < best[0]:
            best = (float(rmse[j]), float(ds[j]), float(dp))
    d0, dp0 = best[1], best[2]

    # 阶段 2：围绕 (d0, dp0) 的精细 2D 网格
    d_step = ds[1] - ds[0]
    dp_step = (disp_range[1] - disp_range[0]) / (n_disp - 1)
    df = np.linspace(d0 - d_step, d0 + d_step, 41)
    pf = np.linspace(dp0 - dp_step, dp0 + dp_step, 7)
    best = None
    for dp in pf:
        R = airy_reflectance(wavelengths, df[:, None], n1, n2_ref, n3, dp)
        rmse = np.sqrt(np.mean((R - reflectance[None, :]) ** 2, axis=1))
        j = int(np.argmin(rmse))
        if best is None or rmse[j] < best[0]:
            best = (float(rmse[j]), float(df[j]), float(dp))
    d_fit, disp_fit = best[1], best[2]

    # 阶段 3：d 与 disp 交替三分搜索——消除两层网格量化残留。
    # 只精化 d 而把 disp 留在粗网格上时，disp 的量化偏差会平移最优 d，
    # 高 SNR 下 σ_B 缩到 0.01 nm 量级，这个残留就超过 σ_B/3。
    d_lo, d_hi = d_fit - 2.0, d_fit + 2.0
    p_lo, p_hi = disp_fit - dp_step, disp_fit + dp_step
    for _ in range(3):
        d_fit = _ternary(lambda dd: _rmse_at(dd, disp_fit), d_lo, d_hi)
        disp_fit = _ternary(lambda dp: _rmse_at(d_fit, dp), p_lo, p_hi)
    d_fit = _ternary(lambda dd: _rmse_at(dd, disp_fit), d_lo, d_hi)

    return d_fit, disp_fit, _rmse_at(d_fit, disp_fit)


# ---------------------------------------------------------------------------
# 加噪、触发、判定
# ---------------------------------------------------------------------------
def add_noise(reflectance: np.ndarray, snr_db: float, rng: np.random.Generator):
    """高斯加噪；σ = 峰值 × 10^(−SNR/20)（峰值信噪比）。"""
    sigma = float(np.max(reflectance)) * 10.0 ** (-snr_db / 20.0)
    return reflectance + rng.normal(0.0, sigma, size=reflectance.shape), sigma


def discordance_trigger(d1: float, sem1: float, d2: float, sem2: float,
                        covariance: float = 0.0):
    """演示用差异警戒线；同数据估计应传入两估计均值的协方差。"""
    delta_variance = max(sem1**2 + sem2**2 - 2.0 * covariance, 0.0)
    threshold = 2.0 * np.sqrt(delta_variance)
    return bool(abs(d1 - d2) > threshold), float(threshold)


def judge_bias(systematic_delta: float, uncertainty: float) -> bool:
    """|Δd_系统| < 报告不确定度/3 才可称无偏。"""
    return bool(abs(systematic_delta) < uncertainty / 3.0)


# ---------------------------------------------------------------------------
# 演示：薄膜厚度反演的三明治回收
# ---------------------------------------------------------------------------
def run_demo(seed: int = 7, snr_db: float = 50.0, d_true: float = 8100.0,
             n_reps: int = 100):
    """跑一遍完整流程，返回 (打印文本, 结构化报告 dict)。

    默认 SNR = 50 dB 的原因：本配置谷深约 0.021（对比 0.30 峰值），
    要让谷底高出噪声底 ≥ 3σ（P0），需 σ ≲ 0.021/3，即 SNR ≳ 40 dB；
    50 dB 留足裕量。SNR 降到 ~35 dB 时谷底被噪声淹没、间距法退化，
    脚本会给出明确警告而非悄悄输出垃圾值。实测噪声水平不同时用 --snr 覆盖。

    默认 n_reps = 100 的原因：系统偏差 Δd 是 N 个噪声实现回收值的**均值**，
    该均值本身带抽样误差 SEM = σ/√N。若 N 太小（如 12），SEM ≈ σ/3.46，
    与门禁 σ/3 同量级——门禁测的是自己的抽样噪声。N = 100 时 SEM ≈ σ/10，
    门禁才测的是真实系统偏差。
    """
    n1, n2_ref, n3 = 1.0, 1.60, 3.42
    disp_true = 0.04
    wavelengths = np.linspace(1500.0, 4000.0, 600)  # nm

    R_true = airy_reflectance(wavelengths, d_true, n1, n2_ref, n3, disp_true)

    # P0 可测性守卫（兜底）：噪声底达到整个谷幅深度 → 任何谷位检测都不可信，
    # 先警告再继续。谷位检测内的平滑 + 3σ 过滤已把退化点压到远低于此处，
    # 故本守卫只在真正退化（SNR 个位数）时触发。
    sigma_check = float(np.max(R_true)) * 10.0 ** (-snr_db / 20.0)
    valley_depth = float(np.max(R_true) - np.min(R_true))
    if 3.0 * sigma_check > valley_depth:
        print(f"[P0 守卫] SNR = {snr_db:.0f} dB：噪声底已接近整个谷幅"
              f"（σ·3 = {3*sigma_check:.3f}，谷幅 = {valley_depth:.3f}），"
              "谷位检测不可信，请提高 --snr 再跑；本报告仅供参考。")

    # 对每个噪声实现同时回收 A、B 两法，累积统计
    dA_reps, dB_reps, sigma_last = [], [], 0.0
    for k in range(n_reps):
        Rk, sigma = add_noise(R_true, snr_db, np.random.default_rng(seed + 1000 + k))
        sigma_last = sigma
        pairs, best_k, _ = spacing_recover(wavelengths, Rk, n2_ref,
                                           noise_sigma=sigma)
        dA_reps.append(float(pairs[best_k]))                 # A：选最深处谷对
        seed_b = float(np.median(pairs))                     # 低阶粗定位 → 高阶种子
        dB_reps.append(fit_airy(wavelengths, Rk, n1, n2_ref, n3, seed_b)[0])

    dA = float(np.mean(dA_reps))          # 系统偏差口径：多实现均值
    dB = float(np.mean(dB_reps))
    sigma_A = float(np.std(dA_reps, ddof=1))  # 报告不确定度口径：单次弥散
    sigma_B = float(np.std(dB_reps, ddof=1))
    semA = sigma_A / np.sqrt(n_reps)
    semB = sigma_B / np.sqrt(n_reps)

    dA_bias = dA - d_true                 # 系统偏差（均值减真值）
    dB_bias = dB - d_true
    okA = judge_bias(dA_bias, sigma_A)
    okB = judge_bias(dB_bias, sigma_B)

    covariance_mean = float(np.cov(dA_reps, dB_reps, ddof=1)[0, 1] / n_reps)
    trigger, threshold = discordance_trigger(
        dA, semA, dB, semB, covariance=covariance_mean)

    # P7 物理矛盾锁定：两光束一阶 vs 全阶 Airy 对谷深的预测差异
    r01_avg = (n1 - n2_ref) / (n1 + n2_ref)
    r12_avg = (n2_ref - n3) / (n2_ref + n3)
    rho = abs(r01_avg * r12_avg)
    two_beam_min = (r01_avg - r12_avg) ** 2
    airy_min = two_beam_min / (1.0 - rho) ** 2

    # 谷对漂移与可辨识带：对最后一次含噪实现实测
    R_last, _ = add_noise(R_true, snr_db,
                          np.random.default_rng(seed + 1000 + n_reps))
    pairs_final, _, _ = spacing_recover(wavelengths, R_last, n2_ref,
                                        noise_sigma=sigma_last)
    drift = [float(pairs_final.min()), float(pairs_final.max())]
    band = list(drift)

    report = {
        "schema_version": 1,
        "problem": "单层薄膜厚度反演（Airy 多光束）",
        "random_seed": seed,
        "snr_db": snr_db,
        "noise_sigma": sigma_last,
        "true_params": {
            "d_true_nm": d_true, "n1": n1, "n2_ref": n2_ref,
            "n3": n3, "disp_true": disp_true,
        },
        "methods": {
            "A": {
                "name": "间距法（忽略相位色散，两光束一阶，选最深谷对）",
                "d_nm": dA, "sigma_nm": sigma_A, "sem_nm": semA,
                "systematic_delta_nm": dA_bias, "unbiased": okA,
            },
            "B": {
                "name": "Airy 拟合（含色散，多光束全阶，间距法种子）",
                "d_nm": dB, "sigma_nm": sigma_B, "sem_nm": semB,
                "systematic_delta_nm": dB_bias, "unbiased": okB,
            },
        },
        "trigger": {
            "fired": trigger,
            "threshold_nm": threshold,
            "covariance_of_means_nm2": covariance_mean,
            "rule": "|dA-dB| > 2*sqrt(SEM_A^2+SEM_B^2-2*covariance)",
        },
        "valley_drift_nm": {
            "min": drift[0], "max": drift[1],
            "note": "A 法回收厚度随所选谷对单调漂移，跨度即相位色散系统偏差的来源",
        },
        "identifiability_band_nm": band,
        "band_dominated_by": "方法A忽略相位色散导致谷对漂移；带宽由该系统偏差主导",
        "physics_lock": {
            "round_trip_amplitude_rho": rho,
            "two_beam_min_prediction": two_beam_min,
            "airy_min_prediction": airy_min,
            "note": "两光束一阶与全阶 Airy 对谷深的预测存在系统差异，多光束贡献不可忽略",
        },
        "verdict": (
            "方法A存在系统偏差（谷对漂移），未通过无偏判定；方法B通过。"
            "结论采用方法B，并以可辨识带披露A的偏差区间。"
            if trigger and (not okA) and okB else
            "两方法均已通过：按题目适配择优，合并报告。"
            if okA and okB else
            "方法B也未通过无偏判定：必须修正回收方法，禁止直接输出点估计。"
        ),
    }

    lines = []
    a = report["methods"]["A"]
    b = report["methods"]["B"]
    t = report["trigger"]
    vd = report["valley_drift_nm"]
    ph = report["physics_lock"]
    lines.append("=== 合成数据回收检验（三明治架构）===")
    lines.append(f"真值 d_true = {d_true:.1f} nm | SNR = {snr_db:.0f} dB | "
                 f"种子 = {seed} | 重复 {n_reps} 次")
    lines.append(f"  方法A {a['name']}")
    lines.append(f"      d = {a['d_nm']:.1f} ± {a['sigma_nm']:.2f} nm | "
                 f"系统偏差 Δd = {a['systematic_delta_nm']:+.1f} nm | 无偏? {a['unbiased']}")
    lines.append(f"      谷对漂移 [{vd['min']:.1f}, {vd['max']:.1f}] nm —— "
                 f"选不同深谷得到的厚度跨度，即相位色散目检信号")
    if a['sigma_nm'] < 0.5:
        lines.append("      (σ_A=0：高 SNR 下谷位对噪声不动，间距法统计弥散被平滑地板压到零；"
                     "其不确定度全部是系统性的，见 P5 可辨识带)")
    lines.append(f"  方法B {b['name']}")
    lines.append(f"      d = {b['d_nm']:.3f} ± {b['sigma_nm']:.3f} nm | "
                 f"系统偏差 Δd = {b['systematic_delta_nm']:+.3f} nm | 无偏? {b['unbiased']}")
    lines.append(f"  P4 触发: |dA-dB| = {abs(a['d_nm']-b['d_nm']):.1f} nm > "
                 f"2u_Δ(含配对协方差) = {t['threshold_nm']:.2f} nm → {t['fired']}")
    lines.append(f"  P5 可辨识带: [{band[0]:.1f}, {band[1]:.1f}] nm（A 法谷对漂移区间）")
    lines.append(f"  P7 物理矛盾锁定: ρ = {ph['round_trip_amplitude_rho']:.3f} | "
                 f"谷深 两光束一阶 = {ph['two_beam_min_prediction']:.4f} vs "
                 f"全阶 Airy = {ph['airy_min_prediction']:.4f}")
    lines.append(f"  结论: {report['verdict']}")
    return "\n".join(lines), report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="合成数据回收检验：验证参数反演/估计算法无偏性（本地 P4）")
    parser.add_argument("--demo", action="store_true",
                        help="跑一次薄膜厚度反演的三明治演示")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--snr", type=float, default=50.0,
                        help="峰值信噪比 dB（默认 50，保证特征高出噪声底 ≥3σ；实测噪声水平不同时覆盖）")
    parser.add_argument("--d", type=float, default=8100.0,
                        help="真值厚度 nm（默认 8100）")
    parser.add_argument("--reps", type=int, default=100,
                        help="系统偏差/不确定度重抽样次数（默认 100，让 SEM 降到 σ/10 以下）")
    parser.add_argument("--report", metavar="OUT.json",
                        help="把结构化报告写入此路径")
    args = parser.parse_args()

    if not args.demo:
        parser.error("本文件仅提供 --demo 教学演示；正式验证请在 PROJECT_ROOT 编写题目专用脚本。")
    report_dir = os.path.dirname(args.report) if args.report else ""
    if report_dir and not os.path.exists(report_dir):
        raise FileNotFoundError(f"报告目录不存在: {report_dir}")

    text, report = run_demo(seed=args.seed, snr_db=args.snr,
                            d_true=args.d, n_reps=args.reps)
    print(text)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print(f"\n报告已写出: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
