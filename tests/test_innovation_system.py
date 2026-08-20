import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "references" / "roles" / "innovation-special" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import innovation_audit


def base_item(**updates):
    item = {
        "innovation_id": "Q1-I1",
        "question_id": "q1",
        "status": "HYPOTHESIS",
        "innovation_type": "model_simplification",
        "source_lens": "structure",
        "domain_tension": "重复状态导致不必要维度",
        "baseline": "完整状态模型",
        "baseline_limitation": "包含冗余状态",
        "proposed_change": "利用守恒关系消元",
        "mechanism": "总量守恒使一个状态可由其余状态恢复",
        "failure_boundary": "存在外部流入时守恒关系失效",
        "evidence_files": [],
    }
    item.update(updates)
    return item


def verified_geometry_item(root: Path) -> dict:
    code = root / "model.py"
    proof = root / "proof.md"
    result = root / "result.json"
    code.write_text("def reduce_axisymmetry():\n    return 0\n", encoding="utf-8")
    proof.write_text("# 轴对称映射证明\n", encoding="utf-8")
    result.write_text("{\"error\": 0}\n", encoding="utf-8")
    return base_item(
        status="VERIFIED",
        innovation_type="geometric_simplification",
        code_entry="model.py:reduce_axisymmetry",
        reproduce_command="python model.py",
        evidence_files=["result.json", "proof.md"],
        verification={
            "kind": "exact_equivalence",
            "baseline": "三维轴对称模型",
            "metric": "判定量差值",
            "result": "差值为 0",
            "limitations": "只适用于轴对称几何",
        },
        simplification={
            "original_model": "三维轴对称实体",
            "decision_quantity": "截面半径",
            "preserved_property": "旋转对称下的径向距离",
            "discarded_effect": "非轴对称扰动",
            "mapping": "映射到母线平面",
            "proof_level": "G1",
            "proof_file": "proof.md",
            "error_or_bound": "精确等价，误差为 0",
            "counterexample_test": "非轴对称形状不适用",
            "failure_condition": "旋转对称性破坏",
        },
    )


class InnovationAuditTests(unittest.TestCase):
    def write_manifest(self, root: Path, items):
        results = root / "results"
        results.mkdir(exist_ok=True)
        path = results / "创新证据清单.json"
        path.write_text(
            json.dumps({"schema_version": 1, "items": items}, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_empty_manifest_is_valid_and_does_not_force_innovation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = innovation_audit.audit_manifest(self.write_manifest(root, []), root)
        self.assertTrue(report["ok"])
        self.assertEqual(sum(report["counts"].values()), 0)

    def test_hypothesis_can_be_bold_without_fake_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = innovation_audit.audit_manifest(self.write_manifest(root, [base_item()]), root)
        self.assertTrue(report["ok"])

    def test_hypothesis_cannot_claim_completed_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = base_item(paper_claim="本文提出降维模型并显著提升效率")
            report = innovation_audit.audit_manifest(self.write_manifest(root, [item]), root)
        self.assertFalse(report["ok"])

    def test_high_competitive_candidate_cannot_be_dropped_without_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = base_item(
                status="DROPPED",
                competitive_relevance="high",
                drop_reason="实现复杂，暂不采用",
            )
            report = innovation_audit.audit_manifest(self.write_manifest(root, [item]), root)
        self.assertFalse(report["ok"])
        self.assertTrue(any("高竞争价值候选" in issue["message"] for issue in report["issues"]))

    def test_high_competitive_candidate_accepts_prototype_drop_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "candidate.json"
            evidence.write_text("{}\n", encoding="utf-8")
            item = base_item(
                status="DROPPED",
                competitive_relevance="high",
                drop_reason="公平原型被 incumbent 支配",
                drop_evidence={
                    "kind": "prototype",
                    "summary": "相同预算下目标更差",
                    "evidence_files": ["candidate.json"],
                },
            )
            report = innovation_audit.audit_manifest(self.write_manifest(root, [item]), root)
        self.assertTrue(report["ok"], report["issues"])

    def test_adopted_item_requires_real_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = base_item(status="ADOPTED", paper_claim="守恒消元降低了维度", answer_value="提高可解释性")
            report = innovation_audit.audit_manifest(self.write_manifest(root, [item]), root)
        self.assertFalse(report["ok"])

    def test_verified_geometry_requires_and_accepts_proof_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = verified_geometry_item(root)
            item["parameter_rationale"] = {
                "physical_meaning": "未引入无文献依据的自由参数",
                "residual_contribution": "不适用（无自由参数）",
                "lower_level_explanation": "不适用（无自由参数）",
                "degeneracy_check": "不适用（无自由参数）",
            }
            report = innovation_audit.audit_manifest(self.write_manifest(root, [item]), root)
        self.assertTrue(report["ok"], report["issues"])

    def test_verified_geometry_without_parameter_rationale_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = verified_geometry_item(root)
            report = innovation_audit.audit_manifest(self.write_manifest(root, [item]), root)
        self.assertFalse(report["ok"])
        self.assertTrue(any("parameter_rationale" in issue["message"] for issue in report["issues"]))

    def test_exact_problem_rejects_default_multi_solver_innovation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = root / "solve.py"
            result = root / "result.json"
            code.write_text("def solve():\n    return 1\n", encoding="utf-8")
            result.write_text("{}\n", encoding="utf-8")
            item = base_item(
                status="VERIFIED",
                innovation_type="solver_improvement",
                code_entry="solve.py:solve",
                reproduce_command="python solve.py",
                evidence_files=["result.json"],
                verification={
                    "kind": "multi_solver",
                    "baseline": "完全枚举",
                    "metric": "目标值",
                    "result": "一致",
                    "limitations": "无",
                },
                solver_route={
                    "problem_class": "exact_discrete",
                    "baseline_solver": "完全枚举",
                    "bottleneck": "无",
                    "fairness": "相同输入",
                    "multi_solver_trigger": "仅为增加算法数量",
                },
            )
            report = innovation_audit.audit_manifest(self.write_manifest(root, [item]), root)
        self.assertFalse(report["ok"])

    def test_uncertainty_innovation_requires_joint_decision_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = root / "robust.py"
            result = root / "result.json"
            code.write_text("def endpoints():\n    return 0\n", encoding="utf-8")
            result.write_text("{}\n", encoding="utf-8")
            item = base_item(
                status="VERIFIED",
                innovation_type="uncertainty",
                code_entry="robust.py:endpoints",
                reproduce_command="python robust.py",
                evidence_files=["result.json"],
                verification={
                    "kind": "endpoint_scan",
                    "baseline": "点估计",
                    "metric": "利润区间",
                    "result": "得到两个对角端点",
                    "limitations": "未覆盖混合端点",
                },
            )
            report = innovation_audit.audit_manifest(self.write_manifest(root, [item]), root)
        self.assertFalse(report["ok"])
        self.assertTrue(any("uncertainty_contract" in issue["message"] for issue in report["issues"]))

    def test_model_simplification_requires_equivalence_or_error_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = root / "reduce.py"
            result = root / "result.json"
            code.write_text("def reduce_state():\n    return 0\n", encoding="utf-8")
            result.write_text("{}\n", encoding="utf-8")
            item = base_item(
                status="VERIFIED",
                code_entry="reduce.py:reduce_state",
                reproduce_command="python reduce.py",
                evidence_files=["result.json"],
                verification={
                    "kind": "dimension_comparison",
                    "baseline": "完整状态",
                    "metric": "变量数量",
                    "result": "减少一个变量",
                    "limitations": "未证明等价",
                },
            )
            report = innovation_audit.audit_manifest(self.write_manifest(root, [item]), root)
        self.assertFalse(report["ok"])
        self.assertTrue(any("simplification" in issue["message"] for issue in report["issues"]))


class InnovationPolicyTests(unittest.TestCase):
    def test_legacy_fixed_innovation_quotas_are_removed(self):
        paths = [
            ROOT / "SKILL.md",
            ROOT / "references" / "roles" / "innovation-special" / "SKILL.md",
            ROOT / "references" / "roles" / "innovation-special" / "元能力.md",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for legacy in ("全文核心创新 **3-4 个**", "变量>10 必用", "创新6处", "机制异构≥3 类"):
            self.assertNotIn(legacy, text)

    def test_root_and_roles_require_innovation_evidence_gate(self):
        root = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        programming = (ROOT / "references" / "roles" / "编程手" / "SKILL.md").read_text(encoding="utf-8")
        writing = (ROOT / "references" / "roles" / "论文手" / "SKILL.md").read_text(encoding="utf-8")
        for text in (root, programming, writing):
            self.assertIn("创新证据清单.json", text)
        self.assertIn("innovation_audit.py", programming)
        self.assertIn("innovation_audit.py", writing)
        self.assertLess(programming.index("innovation_audit.py"), programming.index("执行 `P2`"))
        self.assertLess(writing.index("`P2` 审计回执"), writing.index("执行 `W1`"))

    def test_physical_geometry_requires_proof_not_just_a_figure(self):
        text = (
            ROOT
            / "references"
            / "roles"
            / "innovation-special"
            / "references"
            / "物理几何简化.md"
        ).read_text(encoding="utf-8")
        for token in ("G1 精确等价", "G2 保守逼近", "G3 可控近似", "G4 经验降阶", "不能代替证明"):
            self.assertIn(token, text)

    def test_creativity_and_evidence_are_separate_states(self):
        text = (
            ROOT / "references" / "roles" / "innovation-special" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("探索环：自由发散", text)
        self.assertIn("证据环：严格收敛", text)
        self.assertIn("允许最终没有核心创新", text)
        for state in ("HYPOTHESIS", "PROTOTYPED", "VERIFIED", "ADOPTED", "DROPPED"):
            self.assertIn(state, text)


if __name__ == "__main__":
    unittest.main()
