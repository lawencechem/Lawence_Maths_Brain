#!/usr/bin/env python3
"""Audit innovation evidence without imposing an innovation quota."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


VALID_STATES = {"HYPOTHESIS", "PROTOTYPED", "VERIFIED", "ADOPTED", "DROPPED"}
VALID_COMPETITIVE_RELEVANCE = {"high", "medium", "low"}
VALID_DROP_EVIDENCE = {"prototype", "hard_constraint"}
VALID_TYPES = {
    "problem_reframing",
    "model_simplification",
    "physical_simplification",
    "geometric_simplification",
    "model_structure",
    "cross_question",
    "algorithm_simplification",
    "solver_improvement",
    "information_design",
    "uncertainty",
    "theoretical",
    "decision_rule",
}
PROOF_LEVELS = {"G1", "G2", "G3", "G4"}
SIMPLIFICATION_TYPES = {"model_simplification", "physical_simplification", "geometric_simplification"}
SOLVER_TYPES = {"algorithm_simplification", "solver_improvement"}
BASE_FIELDS = (
    "innovation_id",
    "question_id",
    "status",
    "innovation_type",
    "source_lens",
    "domain_tension",
    "baseline",
    "baseline_limitation",
    "proposed_change",
    "mechanism",
    "failure_boundary",
)
VERIFICATION_FIELDS = ("kind", "baseline", "metric", "result", "limitations")
SIMPLIFICATION_FIELDS = (
    "original_model",
    "decision_quantity",
    "preserved_property",
    "discarded_effect",
    "mapping",
    "proof_level",
    "proof_file",
    "error_or_bound",
    "counterexample_test",
    "failure_condition",
)
SOLVER_ROUTE_FIELDS = (
    "problem_class",
    "baseline_solver",
    "bottleneck",
    "fairness",
)
UNCERTAINTY_FIELDS = (
    "uncertain_parameters",
    "joint_set_or_distribution",
    "coverage_or_calibration",
    "decision_metric",
    "evaluation_method",
    "limitations",
)
PARAMETER_RATIONALE_TYPES = SIMPLIFICATION_TYPES | {"model_structure"}
PARAMETER_RATIONALE_FIELDS = (
    "physical_meaning",
    "residual_contribution",
    "lower_level_explanation",
    "degeneracy_check",
)
COMPLETION_WORDS = ("本文提出", "验证表明", "显著提升", "证明了", "优于")


def _nonempty(mapping: dict[str, Any], key: str) -> bool:
    value = mapping.get(key)
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


def _inside(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _resolve_project_file(root: Path, raw: str) -> tuple[Path | None, str | None]:
    if not isinstance(raw, str) or not raw.strip():
        return None, "路径不能为空"
    candidate = Path(raw.strip())
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (root / candidate).resolve()
    if not _inside(root, resolved):
        return None, f"路径越出 PROJECT_ROOT：{raw}"
    if not resolved.is_file():
        return None, f"文件不存在：{raw}"
    return resolved, None


def _check_code_entry(root: Path, raw: Any) -> list[str]:
    if not isinstance(raw, str) or ":" not in raw:
        return ["code_entry 必须使用 相对路径:符号"]
    path_text, symbol = raw.rsplit(":", 1)
    path, error = _resolve_project_file(root, path_text)
    if error:
        return [error]
    if not symbol.strip():
        return ["code_entry 缺少函数、类或脚本入口符号"]
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not re.search(rf"\b{re.escape(symbol.strip())}\b", text):
        return [f"代码入口符号不存在：{raw}"]
    return []


def _check_files(root: Path, raw_files: Any, label: str) -> list[str]:
    if not isinstance(raw_files, list) or not raw_files:
        return [f"{label} 必须是非空数组"]
    errors: list[str] = []
    for raw in raw_files:
        _, error = _resolve_project_file(root, raw)
        if error:
            errors.append(error)
    return errors


def _check_solver_route(item: dict[str, Any]) -> list[str]:
    route = item.get("solver_route")
    if not isinstance(route, dict):
        return ["solver_improvement 缺少 solver_route 对象"]
    errors = [f"solver_route 缺少 {field}" for field in SOLVER_ROUTE_FIELDS if not _nonempty(route, field)]
    verification = item.get("verification")
    if isinstance(verification, dict) and verification.get("kind") == "multi_solver":
        if not _nonempty(route, "multi_solver_trigger"):
            errors.append("多求解器验证缺少会影响结论的 multi_solver_trigger")
        if route.get("problem_class") in {"exact_discrete", "closed_form", "convex"}:
            errors.append("已有精确或凸性保证时不得把多求解器作为默认创新证据")
    return errors


def _check_simplification(root: Path, item: dict[str, Any]) -> list[str]:
    simplification = item.get("simplification")
    if not isinstance(simplification, dict):
        return ["物理或几何简化缺少 simplification 证明合同"]
    errors = [
        f"simplification 缺少 {field}"
        for field in SIMPLIFICATION_FIELDS
        if not _nonempty(simplification, field)
    ]
    proof_level = str(simplification.get("proof_level", "")).upper()
    if proof_level and proof_level not in PROOF_LEVELS:
        errors.append(f"无效 proof_level：{proof_level}")
    if _nonempty(simplification, "proof_file"):
        _, error = _resolve_project_file(root, simplification["proof_file"])
        if error:
            errors.append(error)
    if _nonempty(simplification, "figure_file"):
        _, error = _resolve_project_file(root, simplification["figure_file"])
        if error:
            errors.append(error)
    return errors


def _check_uncertainty(item: dict[str, Any]) -> list[str]:
    contract = item.get("uncertainty_contract")
    if not isinstance(contract, dict):
        return ["uncertainty 创新缺少 uncertainty_contract"]
    return [
        f"uncertainty_contract 缺少 {field}"
        for field in UNCERTAINTY_FIELDS
        if not _nonempty(contract, field)
    ]


def _check_parameter_rationale(item: dict[str, Any]) -> list[str]:
    rationale = item.get("parameter_rationale")
    if not isinstance(rationale, dict):
        return ["引入自由参数但缺少 parameter_rationale 对象（本地 P10 四问）"]
    return [
        f"parameter_rationale 缺少 {field}"
        for field in PARAMETER_RATIONALE_FIELDS
        if not _nonempty(rationale, field)
    ]


def audit_manifest(manifest_path: str | Path, project_root: str | Path) -> dict[str, Any]:
    manifest_file = Path(manifest_path).expanduser().resolve()
    root = Path(project_root).expanduser().resolve()
    issues: list[dict[str, str]] = []

    if not root.is_dir():
        return {"ok": False, "issues": [{"severity": "FAIL", "message": "PROJECT_ROOT 不存在"}]}
    if not manifest_file.is_file():
        return {"ok": False, "issues": [{"severity": "FAIL", "message": "创新证据清单不存在"}]}
    if not _inside(root, manifest_file):
        return {"ok": False, "issues": [{"severity": "FAIL", "message": "创新证据清单必须位于 PROJECT_ROOT"}]}

    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "issues": [{"severity": "FAIL", "message": f"无法读取创新证据清单：{exc}"}]}

    if not isinstance(manifest, dict):
        return {"ok": False, "issues": [{"severity": "FAIL", "message": "清单根节点必须是对象"}]}
    if manifest.get("schema_version") != 1:
        issues.append({"severity": "FAIL", "message": "schema_version 必须为 1"})
    items = manifest.get("items")
    if not isinstance(items, list):
        issues.append({"severity": "FAIL", "message": "items 必须是数组"})
        items = []

    seen_ids: set[str] = set()
    counts = {state: 0 for state in VALID_STATES}

    for index, item in enumerate(items, 1):
        label = f"items[{index}]"
        if not isinstance(item, dict):
            issues.append({"severity": "FAIL", "message": f"{label} 必须是对象"})
            continue

        for field in BASE_FIELDS:
            if not _nonempty(item, field):
                issues.append({"severity": "FAIL", "message": f"{label} 缺少 {field}"})

        innovation_id = str(item.get("innovation_id", "")).strip()
        if innovation_id:
            if innovation_id in seen_ids:
                issues.append({"severity": "FAIL", "message": f"重复 innovation_id：{innovation_id}"})
            seen_ids.add(innovation_id)

        status = str(item.get("status", "")).upper()
        innovation_type = str(item.get("innovation_type", "")).strip()
        competitive_relevance = str(item.get("competitive_relevance", "")).strip().lower()
        if status not in VALID_STATES:
            issues.append({"severity": "FAIL", "message": f"{label} 状态无效：{status}"})
            continue
        counts[status] += 1
        if innovation_type not in VALID_TYPES:
            issues.append({"severity": "FAIL", "message": f"{label} innovation_type 无效：{innovation_type}"})
        if competitive_relevance and competitive_relevance not in VALID_COMPETITIVE_RELEVANCE:
            issues.append({"severity": "FAIL", "message": f"{label} competitive_relevance 无效：{competitive_relevance}"})

        paper_claim = str(item.get("paper_claim", ""))
        if status == "HYPOTHESIS" and paper_claim:
            issues.append({"severity": "FAIL", "message": f"{label} HYPOTHESIS 不得设置 paper_claim"})
        if status == "DROPPED":
            if not _nonempty(item, "drop_reason"):
                issues.append({"severity": "FAIL", "message": f"{label} DROPPED 缺少 drop_reason"})
            if paper_claim:
                issues.append({"severity": "FAIL", "message": f"{label} DROPPED 不得保留 paper_claim"})
            if competitive_relevance == "high":
                drop_evidence = item.get("drop_evidence")
                if not isinstance(drop_evidence, dict):
                    issues.append({
                        "severity": "FAIL",
                        "message": f"{label} 高竞争价值候选不得无证据 DROPPED；预算不足时保留 HYPOTHESIS 并登记未探索前沿",
                    })
                else:
                    if drop_evidence.get("kind") not in VALID_DROP_EVIDENCE:
                        issues.append({"severity": "FAIL", "message": f"{label} drop_evidence.kind 必须为 prototype 或 hard_constraint"})
                    if not _nonempty(drop_evidence, "summary"):
                        issues.append({"severity": "FAIL", "message": f"{label} drop_evidence 缺少 summary"})
                    for error in _check_files(root, drop_evidence.get("evidence_files"), "drop_evidence.evidence_files"):
                        issues.append({"severity": "FAIL", "message": f"{label} {error}"})

        if status == "PROTOTYPED":
            if not (_nonempty(item, "code_entry") or _nonempty(item, "proof_file")):
                issues.append({"severity": "FAIL", "message": f"{label} PROTOTYPED 缺少代码入口或证明草稿"})
            for error in _check_files(root, item.get("evidence_files"), "evidence_files"):
                issues.append({"severity": "FAIL", "message": f"{label} {error}"})

        if status in {"VERIFIED", "ADOPTED"}:
            if not _nonempty(item, "reproduce_command"):
                issues.append({"severity": "FAIL", "message": f"{label} 缺少 reproduce_command"})
            if not (_nonempty(item, "code_entry") or _nonempty(item, "proof_file")):
                issues.append({"severity": "FAIL", "message": f"{label} 缺少代码入口或证明文件"})
            if _nonempty(item, "code_entry"):
                for error in _check_code_entry(root, item["code_entry"]):
                    issues.append({"severity": "FAIL", "message": f"{label} {error}"})
            if _nonempty(item, "proof_file"):
                _, error = _resolve_project_file(root, item["proof_file"])
                if error:
                    issues.append({"severity": "FAIL", "message": f"{label} {error}"})
            for error in _check_files(root, item.get("evidence_files"), "evidence_files"):
                issues.append({"severity": "FAIL", "message": f"{label} {error}"})
            verification = item.get("verification")
            if not isinstance(verification, dict):
                issues.append({"severity": "FAIL", "message": f"{label} 缺少 verification 对象"})
            else:
                for field in VERIFICATION_FIELDS:
                    if not _nonempty(verification, field):
                        issues.append({"severity": "FAIL", "message": f"{label} verification 缺少 {field}"})
            if any(word in paper_claim for word in COMPLETION_WORDS) and not isinstance(verification, dict):
                issues.append({"severity": "FAIL", "message": f"{label} 宣传性主张缺少验证证据"})

        if status == "ADOPTED":
            if not _nonempty(item, "paper_claim"):
                issues.append({"severity": "FAIL", "message": f"{label} ADOPTED 缺少克制的 paper_claim"})
            if not _nonempty(item, "answer_value"):
                issues.append({"severity": "FAIL", "message": f"{label} ADOPTED 缺少 answer_value"})

        if innovation_type in SIMPLIFICATION_TYPES and status in {"PROTOTYPED", "VERIFIED", "ADOPTED"}:
            for error in _check_simplification(root, item):
                issues.append({"severity": "FAIL", "message": f"{label} {error}"})

        if innovation_type in SOLVER_TYPES and status in {"VERIFIED", "ADOPTED"}:
            for error in _check_solver_route(item):
                issues.append({"severity": "FAIL", "message": f"{label} {error}"})

        if innovation_type == "uncertainty" and status in {"VERIFIED", "ADOPTED"}:
            for error in _check_uncertainty(item):
                issues.append({"severity": "FAIL", "message": f"{label} {error}"})

        if innovation_type == "cross_question" and status in {"VERIFIED", "ADOPTED"}:
            related = item.get("related_questions")
            if not isinstance(related, list) or len({str(q).strip() for q in related if str(q).strip()}) < 2:
                issues.append({"severity": "FAIL", "message": f"{label} cross_question 至少关联两个不同子问题"})

        if status in {"VERIFIED", "ADOPTED"} and innovation_type in PARAMETER_RATIONALE_TYPES:
            for error in _check_parameter_rationale(item):
                issues.append({"severity": "FAIL", "message": f"{label} {error}"})
        elif status in {"VERIFIED", "ADOPTED"} and isinstance(item.get("parameter_rationale"), dict):
            for error in _check_parameter_rationale(item):
                issues.append({"severity": "FAIL", "message": f"{label} {error}"})

    return {
        "ok": not any(issue["severity"] == "FAIL" for issue in issues),
        "manifest": str(manifest_file),
        "project_root": str(root),
        "counts": counts,
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查创新候选、证明和复现证据，不设置创新数量配额")
    parser.add_argument("manifest", help="PROJECT_ROOT/results/创新证据清单.json")
    parser.add_argument("--project-root", required=True, help="项目根目录")
    parser.add_argument("--strict", action="store_true", help="保留接口兼容；FAIL 始终阻断")
    parser.add_argument("--json-output", help="可选审计报告路径")
    args = parser.parse_args(argv)

    report = audit_manifest(args.manifest, args.project_root)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    if args.json_output:
        Path(args.json_output).write_text(output + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
