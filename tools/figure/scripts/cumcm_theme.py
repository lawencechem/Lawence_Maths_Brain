"""
scipilot-figure-skill :: cumcm_theme.py
=======================================
国奖评阅审美的参数化主题预设（数据图与示意图共用）。

把「人工调试质感」转成程序可查项：
- 品牌四色 + 手动写死的衍生浅底（TINTS），同一物理量跨图同色；
- 注册命名 colormap（hex 锚点），不裸用 matplotlib 内置色图；
- 全手动参数（刻度上限 x≤8 / y≤6、线宽、网格样式）写死；
- validate_theme_compliance() 把规则量化为 [(severity, msg), ...]，
  供 visual_qa.audit_layout 以可选主题检查接入。

用法
----
    import sys, os
    sys.path.insert(0, os.path.join(SKILL_ROOT, 'tools', 'figure', 'scripts'))
    import cumcm_theme as theme

    theme.apply()                       # 覆盖 rcParams
    fig, ax = plt.subplots(figsize=...) # 画图，全部颜色取自 theme.PALETTE / TINTS
    issues = theme.validate_theme_compliance(fig)   # [(WARN|FAIL, msg), ...]

setup_style() 固定应用本主题（唯一主题，无 theme 参数切换）；本文件只读参考，
不改变 skill 现有默认行为。

踩坑记录（见 design_theory.md「国奖主题落地的四个硬坑」）：
1. mpl 3.11 不跨 font.serif 列表做字形回退——具体字体列表必须直接进 font.family。
2. mpl 3.11 的 axis('off') 置 axison=False，但不翻转 xaxis.get_visible()——
   合规检查用 getattr(ax, 'axison', True) 判轴是否关闭。
3. 流程框/拓扑节点用品牌色浅底衍生色，必须手动写死进 TINTS 并进合规白名单。
4. 合规检查必须在 plt.close(fig) 之前跑，否则空 axes 静默通过。
"""
from __future__ import annotations

from matplotlib import rcParams, colormaps
from matplotlib.colors import LinearSegmentedColormap, to_hex

# ---------------------------------------------------------------------------
# 品牌四色（全文同一物理量同色）
# ---------------------------------------------------------------------------
PALETTE = {
    "primary": "#2E5EAA",    # 主色：主数据序列 / 分布
    "secondary": "#C84630",  # 辅色：关键高亮 / 风险
    "accent": "#E08E45",     # 强调色：核心结果
    "gray": "#7A7A7A",       # 基准灰：基准线 / 次要信息
}

# 品牌色衍生（手动写死，非运行时混色）：流程框 / 拓扑节点浅底与深描边
TINTS = {
    "primary_tint": "#D8E4F4",     # 主色浅底（配件/普通节点填充）
    "secondary_tint": "#EFD6D2",   # 辅色浅底（风险/中间节点填充）
    "accent_tint": "#F7E0C3",      # 强调色浅底
    "accent_dark": "#8A5A2B",      # 强调色深描边 / 深色文字
    "primary_dark": "#1F4E8C",     # 主色深（与 diverging 锚点一致）
    "secondary_dark": "#A62C1A",   # 辅色深（与 diverging 锚点一致）
}

# 白名单：允许非品牌色的中性色（文本、轴、网格、极浅填充、透明）
ALLOWED_NEUTRALS = {
    "#000000", "#FFFFFF", "#333333", "#444444", "#666666",
    "#C9C9C9", "#E6E6E6", "#F2F2F2", "#EFEFEF", "#999999", "#DDDDDD",
    "#FFFFFF00",
}

# 刻度上限（国奖审美：手动刻度 x≤8 / y≤6）
TICK_LIMITS = {"x": 8, "y": 6}

# 禁用的 matplotlib 原生默认色图（native colormap 一票否决）
FORBIDDEN_CMAPS = {
    "viridis", "plasma", "inferno", "magma", "cividis", "jet", "rainbow",
    "hsv", "YlGnBu", "YlOrRd", "YlOrBr", "YlGn", "GnBu", "RdYlGn", "RdYlBu",
    "Blues", "Reds", "Greens", "Purples", "Oranges", "coolwarm", "seismic",
    "twilight", "turbo", "gist_rainbow", "brg", "gnuplot", "CMRmap",
}

# 注册命名 colormap（hex 锚点，非 matplotlib 内置）
DIVERGING_ANCHORS = ["#1F4E8C", "#7FA3C9", "#FFFFFF", "#E2A28C", "#A62C1A"]   # 蓝-白-红
SEQUENTIAL_ANCHORS = ["#F7E7C0", "#EBCB7E", "#D9A441", "#A86E28", "#6E4218"]  # 浅黄→深棕


def _register_cmaps() -> None:
    for name, anchors in (("cumcm_diverging", DIVERGING_ANCHORS),
                          ("cumcm_sequential", SEQUENTIAL_ANCHORS)):
        if name not in colormaps:
            colormaps.register(
                LinearSegmentedColormap.from_list(name, anchors, N=256))


_register_cmaps()

# ---------------------------------------------------------------------------
# rcParams：全手动参数，写死
# ---------------------------------------------------------------------------
RC = {
    # 硬坑 1：具体字体列表直接给 font.family——CJK 字体必须置于首位。
    # 经验教训（2026-08）：西文（Times）在前时，mpl 3.11.1 在同一进程连续渲染
    # 多张图会对列表字形回退失效，中文退化成豆腐块（"Font 'default' does not
    # have a glyph"）。CJK 字体自带拉丁字形，置于首位即可同时覆盖中/西文，
    # 稳定 0 缺失；不能经 font.serif 间接，也不可靠依赖逐字形回退。
    "font.family": ["SimSun", "Times New Roman", "SimHei"],
    "font.serif": ["SimSun", "Times New Roman"],   # 其他代码路径的兜底
    "mathtext.fontset": "stix",                    # 公式字形与 Times 一致
    "axes.unicode_minus": False,
    "font.size": 9,
    "axes.labelsize": 9.5,
    "axes.titlesize": 9.5,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "axes.linewidth": 0.8,
    "axes.edgecolor": "#333333",
    "xtick.direction": "in",
    "ytick.direction": "in",
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "lines.linewidth": 1.8,
    "grid.color": "#C9C9C9",
    "grid.linestyle": "--",
    "grid.linewidth": 0.6,
    "figure.dpi": 110,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "legend.frameon": False,
    "legend.fontsize": 8,
}

# 与 visual_qa / check_figure 一致的 severity 序
_SEVERITY = {"INFO": 0, "WARN": 1, "FAIL": 2}
_GRID_OK_COLORS = {"#c9c9c9", "#999999"}
_GRID_OK_LS = ("--", (0, (3, 3)), (0, (4, 2)))


def apply() -> None:
    """应用国奖主题 rcParams。"""
    rcParams.update(RC)


def _hex(rgba) -> str | None:
    if rgba is None:
        return None
    try:
        return to_hex(rgba, keep_alpha=False).lower()
    except (ValueError, TypeError):
        return None


def validate_theme_compliance(fig) -> list[tuple[str, str]]:
    """
    把国奖审美规则量化为可查项。返回 [(severity, msg), ...]（空 = 合规）。

    检查项：
      - 轴关闭（拓扑图/示意图）→ 跳过刻度上限检查；
      - 刻度上限 x≤8 / y≤6（WARN，密度偏好）；
      - 禁止原生色图（FAIL，viridis/turbo/YlGnBu…一票否决）；
      - 非白名单颜色（WARN，含衍生浅底需进 TINTS）；
      - 网格仅横向浅灰虚线（WARN）。

    只报告，不抛异常；调用方（如 visual_qa.audit_layout）决定是否 hard fail。
    """
    issues: list[tuple[str, str]] = []
    pal_hex = {to_hex(v, keep_alpha=False).lower() for v in PALETTE.values()}
    allowed = pal_hex | ALLOWED_NEUTRALS | {to_hex(v, keep_alpha=False).lower()
                                            for v in TINTS.values()}

    for idx, ax in enumerate(fig.axes):
        # 硬坑 2：mpl 3.11 中 axis('off') 置 axison=False，不翻转 xaxis.get_visible()
        axis_off = (not getattr(ax, "axison", True)
                    or not (ax.xaxis.get_visible() and ax.yaxis.get_visible()))

        if not axis_off:
            nxt = len(ax.get_xticks())
            nyt = len(ax.get_yticks())
            if nxt > TICK_LIMITS["x"]:
                issues.append((
                    "WARN",
                    f"ax{idx} 刻度密度 xticks={nxt} > {TICK_LIMITS['x']}。"
                    "国奖审美要求手动刻度，用 ax.set_xticks(...) 收敛。",
                ))
            if nyt > TICK_LIMITS["y"]:
                issues.append((
                    "WARN",
                    f"ax{idx} 刻度密度 yticks={nyt} > {TICK_LIMITS['y']}。"
                    "用 ax.set_yticks(...) 收紧。",
                ))

        for im in ax.images:
            cmap_name = im.get_cmap().name
            if cmap_name in FORBIDDEN_CMAPS:
                issues.append((
                    "FAIL",
                    f"ax{idx} 使用原生默认色图 {cmap_name}，"
                    "改用手动构造的 cumcm_diverging / cumcm_sequential。",
                ))

        for line in ax.lines:
            c = _hex(line.get_color())
            if c and c not in allowed:
                issues.append((
                    "WARN",
                    f"ax{idx} 线条颜色 {c} 不在国奖主题白名单。"
                    "改用 PALETTE / TINTS / ALLOWED_NEUTRALS。",
                ))

        for patch in ax.patches:
            c = _hex(patch.get_facecolor())
            if c and c not in allowed:
                issues.append((
                    "WARN",
                    f"ax{idx} 色块颜色 {c} 不在国奖主题白名单。"
                    "浅底/深描边请用 TINTS 中的写死值。",
                ))

        # 只审计实际可见的网格线。mpl 3.11 中 get_gridlines() 只要轴有刻度就返回对象，
        # 但 grid 关闭时 get_visible() 为 False——按存在性判断会把默认轴误判成网格。
        visible_grid = [gl for gl in (*ax.get_ygridlines(), *ax.get_xgridlines())
                        if gl.get_visible()]
        if visible_grid:
            gl = visible_grid[0]
            if gl.get_linestyle() not in _GRID_OK_LS:
                issues.append((
                    "WARN",
                    f"ax{idx} 网格线型 {gl.get_linestyle()} 非浅灰虚线。",
                ))
            col = _hex(gl.get_color())
            if col and col not in _GRID_OK_COLORS:
                issues.append((
                    "WARN",
                    f"ax{idx} 网格色 {col} 非浅灰。"
                    "国奖审美仅允许横向浅灰虚线。",
                ))
    return issues


def issues_verdict(issues: list[tuple[str, str]]) -> str:
    """把合规结果压成 PASS / WARN / FAIL（供调用方展示）。"""
    if not issues:
        return "PASS"
    worst = max(_SEVERITY[s] for s, _ in issues)
    return {2: "FAIL", 1: "WARN", 0: "INFO"}[worst]


__all__ = [
    "ALLOWED_NEUTRALS", "DIVERGING_ANCHORS", "FORBIDDEN_CMAPS", "PALETTE",
    "RC", "SEQUENTIAL_ANCHORS", "TICK_LIMITS", "TINTS", "apply",
    "issues_verdict", "validate_theme_compliance",
]
