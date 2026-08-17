"""国奖主题 cumcm_theme 的合规检查测试。

覆盖四个硬坑中的可测项：刻度上限、禁用原生色图、色板白名单、axis-off 跳过刻度检查，
以及 setup_style() 固定应用国奖主题 / visual_qa.audit_layout() 固定启用主题合规。
"""
import sys
import unittest
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

SCRIPTS = Path(__file__).resolve().parents[1] / "tools" / "figure" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

import cumcm_theme  # noqa: E402
import setup_style  # noqa: E402
import visual_qa  # noqa: E402


def _severities(issues):
    return {sev for sev, _ in issues}


class ThemeConstantsTests(unittest.TestCase):
    def test_brand_palette_hexes(self):
        self.assertEqual(cumcm_theme.PALETTE["primary"], "#2E5EAA")
        self.assertEqual(cumcm_theme.PALETTE["secondary"], "#C84630")
        self.assertEqual(cumcm_theme.PALETTE["accent"], "#E08E45")
        self.assertEqual(cumcm_theme.PALETTE["gray"], "#7A7A7A")

    def test_tints_in_whitelist(self):
        # 浅底衍生色必须被合规白名单接受（硬坑 3）
        from matplotlib.colors import to_hex
        allowed = {to_hex(v, keep_alpha=False).lower() for v in cumcm_theme.PALETTE.values()} \
            | cumcm_theme.ALLOWED_NEUTRALS \
            | {to_hex(v, keep_alpha=False).lower() for v in cumcm_theme.TINTS.values()}
        self.assertIn(to_hex(cumcm_theme.TINTS["primary_tint"], keep_alpha=False).lower(), allowed)

    def test_registered_cmaps(self):
        from matplotlib import colormaps
        self.assertIn("cumcm_diverging", colormaps)
        self.assertIn("cumcm_sequential", colormaps)


class ValidateThemeTests(unittest.TestCase):
    def tearDown(self):
        plt.close("all")

    def _compliant_fig(self):
        fig, ax = plt.subplots()
        ax.bar([0, 1, 2], [1, 2, 3], color=cumcm_theme.PALETTE["primary"])
        ax.set_xticks([0, 1, 2])
        ax.set_yticks([0, 1, 2])
        return fig

    def test_compliant_figure_zero_issues(self):
        self.assertEqual(cumcm_theme.validate_theme_compliance(self._compliant_fig()), [])

    def test_tick_overflow_reported_warn(self):
        fig, ax = plt.subplots()
        ax.bar(range(3), [1, 2, 3], color=cumcm_theme.PALETTE["primary"])
        ax.set_xticks(range(12))
        ax.set_yticks(range(15))
        issues = cumcm_theme.validate_theme_compliance(fig)
        self.assertTrue(any("刻度" in msg for _, msg in issues))
        self.assertEqual(_severities(issues), {"WARN"})

    def test_forbidden_native_cmap_is_fail(self):
        fig, ax = plt.subplots()
        ax.imshow(np.zeros((4, 4)), cmap="viridis")
        issues = cumcm_theme.validate_theme_compliance(fig)
        self.assertTrue(any(sev == "FAIL" and "原生默认色图" in msg for sev, msg in issues))

    def test_non_whitelist_color_is_warn(self):
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1], color="#FF00FF")
        issues = cumcm_theme.validate_theme_compliance(fig)
        self.assertTrue(any("白名单" in msg for _, msg in issues))

    def test_axis_off_skips_tick_check(self):
        # 硬坑 2：axis('off') 只置 axison=False，不翻转 get_visible()
        fig, ax = plt.subplots()
        ax.axis("off")
        ax.set_xticks(range(15))
        ax.set_yticks(range(15))
        issues = cumcm_theme.validate_theme_compliance(fig)
        self.assertFalse(any("刻度" in msg for _, msg in issues))


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        # setup_style(theme='cumcm') 会改全局 rcParams（savefig.bbox、font.family 等），
        # 必须快照并在 tearDown 恢复，避免污染同进程的其他测试。
        self._saved_rc = matplotlib.rcParams.copy()

    def tearDown(self):
        matplotlib.rcParams.clear()
        matplotlib.rcParams.update(self._saved_rc)
        plt.close("all")

    def test_setup_style_hardcodes_cumcm(self):
        info = setup_style.setup_style(journal="general", lang="en")
        self.assertEqual(info["theme"], "cumcm")
        self.assertEqual(info["palette"], "cumcm")
        # 具体字体列表直接进 font.family（硬坑 1），而非经 font.serif 间接
        self.assertIn("SimSun", matplotlib.rcParams["font.family"])
        # 国奖主题固定应用，不再有 theme 参数切换
        with self.assertRaises(TypeError):
            setup_style.setup_style(theme="unknown")

    def test_audit_layout_always_runs_cumcm_theme(self):
        fig, ax = plt.subplots()
        ax.bar([0, 1, 2], [1, 2, 3], color=cumcm_theme.PALETTE["primary"])
        ax.set_xticks([0, 1, 2])
        ax.set_yticks([0, 1, 2])
        # 既有布局检查（缺字/裁切/重叠）+ 主题合规固定一起跑，不抛异常
        issues = visual_qa.audit_layout(fig)
        self.assertIsInstance(issues, list)
        # 合规图（品牌色 + 手动刻度）不应产生主题违规
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
