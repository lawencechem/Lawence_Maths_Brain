import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "tools" / "figure" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import visual_qa


@unittest.skipUnless(importlib.util.find_spec("matplotlib"), "需要 matplotlib")
class VisualQaTextOverlapTests(unittest.TestCase):
    def _figure(self, figsize=(3.0, 2.2)):
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        fig, axis = plt.subplots(figsize=figsize, constrained_layout=False)
        axis.plot([0, 1], [0, 1])
        return fig, axis

    def test_detects_overlapping_annotation_text_blocks(self):
        fig, axis = self._figure()
        axis.text(0.5, 0.5, "annotation text A", fontsize=8)
        axis.text(0.52, 0.48, "annotation text B", fontsize=8)
        issues = visual_qa.audit_layout(fig)
        plt_close(fig)

        messages = "\n".join(msg for _, msg in issues)
        self.assertIn("文字块互相重叠", messages)
        self.assertIn("annotation text A", messages)
        self.assertIn("annotation text B", messages)

    def test_tick_overlap_not_reported_as_text_overlap(self):
        """刻度-刻度重叠只由刻度检测上报，不得被文字块重叠重复上报。"""
        fig, axis = self._figure(figsize=(2, 1.5))
        axis.set_xticks(range(8), [f"very-long-category-{index}" for index in range(8)])
        issues = visual_qa.audit_layout(fig)
        plt_close(fig)

        messages = [msg for _, msg in issues]
        self.assertTrue(any("刻度标签重叠" in msg for msg in messages), messages)
        self.assertFalse(any("文字块互相重叠" in msg for msg in messages), messages)

    def test_clean_layout_reports_no_text_overlap(self):
        fig, axis = self._figure(figsize=(6, 4))
        axis.set_xlabel("Time (s)")
        axis.set_ylabel("Value")
        axis.set_title("Clean title")
        issues = visual_qa.audit_layout(fig)
        plt_close(fig)

        messages = [msg for _, msg in issues]
        self.assertFalse(any("文字块互相重叠" in msg for msg in messages), messages)

    def test_demo_figure_flags_all_three_warns(self):
        """_demo() 的坏版面应同时触发裁切、刻度重叠、文字块重叠。"""
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            visual_qa._demo()
        output = buffer.getvalue()

        self.assertIn("[WARN] 以下文字可能超出画布", output)
        self.assertIn("刻度标签重叠", output)
        self.assertIn("文字块互相重叠", output)


def plt_close(fig):
    import matplotlib.pyplot as plt

    plt.close(fig)


if __name__ == "__main__":
    unittest.main()
