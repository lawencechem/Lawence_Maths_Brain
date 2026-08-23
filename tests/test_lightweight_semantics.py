import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LightweightSemanticPolicyTests(unittest.TestCase):
    def test_root_entry_uses_global_story_before_local_work(self):
        root = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(root.splitlines()), 150)
        self.assertIn("目标语义卡.md", root)
        self.assertIn("第一步：先建立全局故事", root)
        self.assertIn("整体任务失败", root)
        self.assertIn("不要读一段就立刻填表、看结果模板或选择模型", root)
        self.assertIn("普通题到此直接自由建模", root)
        self.assertIn("禁止一次性遍历或读取整个", root)
        self.assertLess(root.index("第一步：先建立全局故事"), root.index("渐进式加载"))

    def test_semantic_reference_tests_global_goal_against_local_output(self):
        card = (
            ROOT
            / "references"
            / "roles"
            / "建模手"
            / "references"
            / "目标语义卡.md"
        ).read_text(encoding="utf-8")
        for token in (
            "最终被保护、评价、预测或优化的主体",
            "整体失败",
            "局部对象是独立计分对象",
            "模板按对象分行",
            "才读取结果模板和选择算法",
        ):
            self.assertIn(token, card)
        self.assertIn("求和 vs 交集", card)

    def test_m1_semantic_failure_precedes_secondary_audit(self):
        modeling = (
            ROOT / "references" / "roles" / "建模手" / "SKILL.md"
        ).read_text(encoding="utf-8")
        subagent = (ROOT / "references" / "Subagent调度.md").read_text(encoding="utf-8")
        for text in (modeling, subagent):
            self.assertIn("区分反例", text)
            self.assertIn("语义", text)
            self.assertIn("FAIL", text)


if __name__ == "__main__":
    unittest.main()
