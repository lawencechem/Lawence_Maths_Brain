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
        "problem_class": "layout_structure",
        "completion_mode": "competitive",
        "state": "CHALLENGE_CLOSED",
        "decision_space_audit": {
            "representation_risk": "high",
            "risk_basis": "全局统一方案可能排除分区表示",
            "freedom_families": [
                {"family": "magnitude", "assessment": "资源量可调", "basis": "题面目标"},
                {"family": "timing", "assessment": "无动态过程", "basis": "静态题"},
                {"family": "structure", "assessment": "全局或分区待比较", "basis": "存在空间异质性"},
                {"family": "information", "assessment": "全部输入已知", "basis": "确定性数据"},
            ],
            "added_or_repeated_entities": [],
            "uses_aggregate_model": False,
            "collapse_assumptions": [],
        },
        "model_contract_audit": {
            "criterion_semantics": {
                "subject": "备选方案",
                "object_extent": "全部需求节点与完整评价期",
                "quantifier": "全部硬约束满足，总成本最小",
                "acceptance_test": "all(constraints) and objective == recomputed_cost",
                "source": "PROBLEM",
                "basis": "题面明示全部需求须满足并最小化总成本",
            },
            "state_boundary_conditions": [],
            "no_boundary_basis": "静态资源分配问题，没有时间演化状态",
            "uses_proxy_or_surrogate": False,
            "incumbent_certification": {
                "strict_contract_pass": True,
                "boundary_crossings_checked": True,
                "active_constraints_checked": True,
                "proxy_gap_status": "NOT_USED",
                "evidence_files": files,
            },
        },
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
                "freedom_ref": "structure",
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
            json.dumps({"schema_version": 2, "questions": questions}, ensure_ascii=False),
            encoding="utf-8",
        )
        return ledger

    def test_valid_gap_certificate_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = self.write_ledger(root, [valid_question(root)])
            report = challenge_audit.audit_ledger(ledger, root, ["q4"])
        self.assertTrue(report["ok"], report["issues"])

    def test_missing_decision_space_audit_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            question = valid_question(root)
            question.pop("decision_space_audit")
            ledger = self.write_ledger(root, [question])
            report = challenge_audit.audit_ledger(ledger, root, ["q4"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("decision_space_audit" in issue["message"] for issue in report["issues"]))

    def test_decision_space_audit_requires_all_four_freedom_families(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            question = valid_question(root)
            question["decision_space_audit"]["freedom_families"] = question["decision_space_audit"]["freedom_families"][:-1]
            ledger = self.write_ledger(root, [question])
            report = challenge_audit.audit_ledger(ledger, root, ["q4"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("information" in issue["message"] for issue in report["issues"]))

    def test_missing_model_contract_audit_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            question = valid_question(root)
            question.pop("model_contract_audit")
            ledger = self.write_ledger(root, [question])
            report = challenge_audit.audit_ledger(ledger, root, ["q4"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("model_contract_audit" in issue["message"] for issue in report["issues"]))

    def test_boundary_condition_requires_source_and_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            question = valid_question(root)
            contract = question["model_contract_audit"]
            contract.pop("no_boundary_basis")
            contract["state_boundary_conditions"] = [{
                "state": "z",
                "domain": "z>=0",
                "boundary": "z=0",
                "behavior": "到达后停止",
                "basis": "程序中使用 maximum",
            }]
            ledger = self.write_ledger(root, [question])
            report = challenge_audit.audit_ledger(ledger, root, ["q4"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("source" in issue["message"] for issue in report["issues"]))

    def test_proxy_cannot_certify_incumbent_without_strict_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            question = valid_question(root)
            contract = question["model_contract_audit"]
            contract["uses_proxy_or_surrogate"] = True
            contract["proxy_relation"] = "代表点距离代替完整对象判据"
            contract["strict_contract"] = "对完整对象范围计算判据"
            contract["proxy_validation_evidence_files"] = ["evidence.json"]
            contract["incumbent_certification"]["proxy_gap_status"] = "UNRESOLVED"
            ledger = self.write_ledger(root, [question])
            report = challenge_audit.audit_ledger(ledger, root, ["q4"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("proxy_gap_status" in issue["message"] for issue in report["issues"]))

    def test_modeling_choice_boundary_requires_alternative_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            question = valid_question(root)
            contract = question["model_contract_audit"]
            contract.pop("no_boundary_basis")
            contract["state_boundary_conditions"] = [{
                "state": "z",
                "domain": "z>=0",
                "boundary": "z=0",
                "behavior": "到达后夹取在地面",
                "source": "MODELING_CHOICE",
                "basis": "物理地面限制",
            }]
            ledger = self.write_ledger(root, [question])
            report = challenge_audit.audit_ledger(ledger, root, ["q4"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("alternative_behavior" in issue["message"] for issue in report["issues"]))

    def test_representation_risk_is_enforced_independent_of_problem_class_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            question = valid_question(root)
            question["problem_class"] = "dynamic_control"
            question["challenges"][0]["change_level"] = "model"
            question["challenges"][0].pop("freedom_ref")
            ledger = self.write_ledger(root, [question])
            report = challenge_audit.audit_ledger(ledger, root, ["q4"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("representation_risk=high" in issue["message"] for issue in report["issues"]))

    def test_aggregate_assumption_must_link_to_representation_challenge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            question = valid_question(root)
            audit = question["decision_space_audit"]
            audit["added_or_repeated_entities"] = [{
                "change": "增加同类执行器",
                "entities": ["a", "b"],
                "relative_relations": ["相对时序"],
                "model_mapping": "独立控制量",
            }]
            audit["uses_aggregate_model"] = True
            audit["collapse_assumptions"] = [{
                "assumption_id": "a-sync",
                "expression": "y=2u",
                "assumption": "完全同步",
                "alternative": "y=u1+u2(t-tau)",
                "disposition": "CHALLENGED",
                "challenge_id": "q4-c1",
            }]
            question["challenges"][0]["freedom_ref"] = "a-sync"
            ledger = self.write_ledger(root, [question])
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
        self.assertEqual(version, "2.5.0")
        self.assertIn("## 2.5.0", changelog)
        self.assertIn("version-2.5.0", readme)


if __name__ == "__main__":
    unittest.main()
