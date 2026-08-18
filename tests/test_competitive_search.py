import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "references" / "roles" / "innovation-special" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import challenge_audit


def valid_question(root: Path) -> dict:
    evidence = root / "evidence.json"
    evidence.write_text('{"ok": true}\n', encoding="utf-8")
    files = ["evidence.json"]
    return {
        "question_id": "q4",
        "completion_mode": "competitive",
        "state": "CHALLENGE_CLOSED",
        "hard_constraints": [
            {"name": "可行性", "status": "PASS", "evidence_files": files}
        ],
        "soft_objectives": [
            {"name": "总成本", "direction": "min", "unit": "元", "incumbent_value": 100.0}
        ],
        "baseline": {
            "description": "规则基线",
            "metrics": {"总成本": 130.0},
            "evidence_files": files,
        },
        "rulers": [
            {"type": "lower_bound", "description": "松弛下界", "evidence_files": files}
        ],
        "incumbent": {
            "description": "当前最好可行方案",
            "metrics": {"总成本": 100.0},
            "evidence_files": files,
        },
        "challenges": [
            {
                "challenge_id": "q4-c1",
                "change_level": "decomposition",
                "target_bottleneck": "全局结构受局部最差点支配",
                "structural_change": "全局统一方案改为分区方案",
                "status": "PROMOTED",
                "feasibility_status": "PASS",
                "metrics": {"总成本": 100.0},
                "evidence_files": files,
            }
        ],
        "budget": {"allocated": 10, "used": 8, "unit": "min"},
        "stop_certificate": {
            "reason": "GAP_TARGET",
            "summary": "相对下界的 gap 已达预设精度",
            "optimality_gap": 0.01,
            "gap_threshold": 0.02,
            "remaining_gap_or_unknown": "1%",
            "untested_frontiers": [],
            "evidence_files": files,
        },
    }


class CompetitiveSearchAuditTests(unittest.TestCase):
    def write_ledger(self, root: Path, questions: list[dict]) -> Path:
        results = root / "results"
        results.mkdir(exist_ok=True)
        ledger = results / "竞争性搜索账本.json"
        ledger.write_text(
            json.dumps({"schema_version": 1, "questions": questions}, ensure_ascii=False),
            encoding="utf-8",
        )
        return ledger

    def test_valid_gap_certificate_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = self.write_ledger(root, [valid_question(root)])
            report = challenge_audit.audit_ledger(ledger, root, ["q4"])
        self.assertTrue(report["ok"], report["issues"])

    def test_first_feasible_solution_cannot_close_without_challenge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            question = valid_question(root)
            question["challenges"] = []
            ledger = self.write_ledger(root, [question])
            report = challenge_audit.audit_ledger(ledger, root, ["q4"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("结构性挑战" in issue["message"] for issue in report["issues"]))

    def test_budget_exhaustion_requires_declared_frontier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            question = valid_question(root)
            question["budget"] = {"allocated": 10, "used": 10, "unit": "min"}
            question["stop_certificate"] = {
                "reason": "BUDGET_EXHAUSTED",
                "summary": "预分配预算已耗尽",
                "remaining_gap_or_unknown": "无可计算下界",
                "untested_frontiers": [],
                "evidence_files": ["evidence.json"],
            }
            ledger = self.write_ledger(root, [question])
            report = challenge_audit.audit_ledger(ledger, root, ["q4"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("未探索前沿" in issue["message"] for issue in report["issues"]))

    def test_diminishing_returns_requires_distinct_structural_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            question = valid_question(root)
            question["challenges"].append(deepcopy(question["challenges"][0]))
            question["challenges"][1]["challenge_id"] = "q4-c2"
            question["stop_certificate"] = {
                "reason": "DIMINISHING_RETURNS",
                "summary": "两轮挑战的边际改进不足",
                "marginal_gain": 0.01,
                "marginal_gain_threshold": 0.02,
                "remaining_gap_or_unknown": "无可计算下界",
                "untested_frontiers": ["更高成本的联合分解"],
                "evidence_files": ["evidence.json"],
            }
            ledger = self.write_ledger(root, [question])
            report = challenge_audit.audit_ledger(ledger, root, ["q4"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("结构实质不同" in issue["message"] for issue in report["issues"]))

    def test_declared_competitive_questions_must_match_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = self.write_ledger(root, [valid_question(root)])
            report = challenge_audit.audit_ledger(ledger, root, ["q3", "q4"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("q3" in issue["message"] for issue in report["issues"]))

    def test_infeasible_challenger_cannot_be_promoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            question = valid_question(root)
            question["challenges"][0]["feasibility_status"] = "FAIL"
            ledger = self.write_ledger(root, [question])
            report = challenge_audit.audit_ledger(ledger, root, ["q4"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("PROMOTED" in issue["message"] for issue in report["issues"]))


class CompetitiveSearchPolicyTests(unittest.TestCase):
    def test_dual_track_is_wired_into_all_stages(self):
        paths = [
            ROOT / "SKILL.md",
            ROOT / "references" / "roles" / "建模手" / "SKILL.md",
            ROOT / "references" / "roles" / "编程手" / "SKILL.md",
            ROOT / "references" / "roles" / "论文手" / "SKILL.md",
        ]
        texts = [path.read_text(encoding="utf-8") for path in paths]
        for path, text in zip(paths, texts):
            self.assertIn("competitive", text, path)
        self.assertIn("竞争性搜索账本.json", texts[0])
        self.assertIn("竞争性搜索账本.json", texts[2])
        self.assertIn("竞争性搜索账本.json", texts[3])
        self.assertIn("challenge_audit.py", texts[2])
        self.assertIn("challenge_audit.py", texts[3])

    def test_first_feasible_is_explicitly_not_completion(self):
        root_skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        protocol = (ROOT / "references" / "竞争型问题协议.md").read_text(encoding="utf-8")
        temperature = (ROOT / "references" / "温度策略.md").read_text(encoding="utf-8")
        self.assertIn("首个可行解只建立 incumbent", root_skill)
        self.assertIn("首个可行解", protocol)
        self.assertIn("首个可行解", temperature)

    def test_version_matches_release_notes(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(version, "2.3.0")
        self.assertIn("## 2.3.0", changelog)
        self.assertIn("version-2.3.0", readme)


if __name__ == "__main__":
    unittest.main()
