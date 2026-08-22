#!/usr/bin/env python3
"""Audit competitive-search effort without requiring a winning innovation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


VALID_CHANGE_LEVELS = {
    "representation",
    "decomposition",
    "objective",
    "model",
    "solver_structure",
    "information",
}
# 布局/结构/拓扑类题（problem_class="layout_structure"）在非 PROVEN_OPTIMAL 停止前，
# 必须完成至少一次表示/分解级挑战，否则挑战审计 FAIL（见 竞争型问题协议.md 四、决策表示）。
REPRESENTATION_LEVELS = {"representation", "decomposition"}
REQUIRED_FREEDOM_FAMILIES = {"magnitude", "timing", "structure", "information"}
VALID_COLLAPSE_DISPOSITIONS = {
    "CHALLENGED",
    "FIXED_BY_PROBLEM",
    "EVIDENCE_REJECTED",
    "UNTESTED",
}
VALID_CHALLENGE_STATES = {"PROMOTED", "REJECTED", "INCONCLUSIVE"}
VALID_RULERS = {
    "lower_bound",
    "upper_bound",
    "exact_small",
    "oracle",
    "pareto",
    "baseline",
    "nested_space",
}
VALID_STOP_REASONS = {
    "PROVEN_OPTIMAL",
    "GAP_TARGET",
    "BUDGET_EXHAUSTED",
    "DIMINISHING_RETURNS",
    "BLOCKED_BY_CONSTRAINT",
}
VALID_CONTRACT_SOURCES = {"PROBLEM", "DERIVED", "EXTERNAL", "MODELING_CHOICE"}
VALID_PROXY_GAP_STATUSES = {"NOT_USED", "PASS", "FAIL", "UNRESOLVED"}


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


def _resolve_project_file(root: Path, raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return "路径不能为空"
    candidate = Path(raw.strip())
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if not _inside(root, resolved):
        return f"路径越出 PROJECT_ROOT：{raw}"
    if not resolved.is_file():
        return f"文件不存在：{raw}"
    return None


def _check_files(root: Path, raw_files: Any, label: str) -> list[str]:
    if not isinstance(raw_files, list) or not raw_files:
        return [f"{label} 必须是非空数组"]
    errors: list[str] = []
    for raw in raw_files:
        error = _resolve_project_file(root, raw)
        if error:
            errors.append(error)
    return errors


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _issue(issues: list[dict[str, str]], label: str, message: str) -> None:
    issues.append({"severity": "FAIL", "message": f"{label} {message}"})


def audit_ledger(
    ledger_path: str | Path,
    project_root: str | Path,
    expected_questions: list[str] | None = None,
) -> dict[str, Any]:
    ledger_file = Path(ledger_path).expanduser().resolve()
    root = Path(project_root).expanduser().resolve()
    issues: list[dict[str, str]] = []

    if not root.is_dir():
        return {"ok": False, "issues": [{"severity": "FAIL", "message": "PROJECT_ROOT 不存在"}]}
    if not ledger_file.is_file():
        return {"ok": False, "issues": [{"severity": "FAIL", "message": "竞争性搜索账本不存在"}]}
    if not _inside(root, ledger_file):
        return {"ok": False, "issues": [{"severity": "FAIL", "message": "竞争性搜索账本必须位于 PROJECT_ROOT"}]}

    try:
        ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "issues": [{"severity": "FAIL", "message": f"无法读取竞争性搜索账本：{exc}"}]}

    if not isinstance(ledger, dict):
        return {"ok": False, "issues": [{"severity": "FAIL", "message": "账本根节点必须是对象"}]}
    if ledger.get("schema_version") != 2:
        _issue(issues, "ledger", "schema_version 必须为 2（新增 model_contract_audit）")
    questions = ledger.get("questions")
    if not isinstance(questions, list) or not questions:
        _issue(issues, "ledger", "questions 必须是非空数组")
        questions = []

    seen: set[str] = set()
    for index, question in enumerate(questions, 1):
        label = f"questions[{index}]"
        if not isinstance(question, dict):
            _issue(issues, label, "必须是对象")
            continue

        question_id = str(question.get("question_id", "")).strip()
        if not question_id:
            _issue(issues, label, "缺少 question_id")
        elif question_id in seen:
            _issue(issues, label, f"question_id 重复：{question_id}")
        else:
            seen.add(question_id)

        if question.get("completion_mode") != "competitive":
            _issue(issues, label, "completion_mode 必须为 competitive")
        if question.get("state") != "CHALLENGE_CLOSED":
            _issue(issues, label, "state 必须为 CHALLENGE_CLOSED")
        problem_class = str(question.get("problem_class") or "").strip()
        if not problem_class:
            _issue(issues, label, "缺少 problem_class")

        representation_risk = ""
        valid_freedom_refs: set[str] = set()
        collapse_records: list[tuple[str, dict[str, Any]]] = []
        decision_audit = question.get("decision_space_audit")
        if not isinstance(decision_audit, dict):
            _issue(issues, label, "缺少 decision_space_audit 决策空间审计")
        else:
            audit_label = f"{label}.decision_space_audit"
            representation_risk = str(decision_audit.get("representation_risk") or "").strip()
            if representation_risk not in {"high", "low"}:
                _issue(issues, audit_label, "representation_risk 必须为 high 或 low")
            if not _nonempty(decision_audit, "risk_basis"):
                _issue(issues, audit_label, "缺少 risk_basis")

            families = decision_audit.get("freedom_families")
            seen_families: set[str] = set()
            if not isinstance(families, list):
                _issue(issues, audit_label, "freedom_families 必须是数组")
                families = []
            for family_index, family in enumerate(families, 1):
                family_label = f"{audit_label}.freedom_families[{family_index}]"
                if not isinstance(family, dict):
                    _issue(issues, family_label, "必须是对象")
                    continue
                family_name = str(family.get("family") or "").strip()
                if family_name in seen_families:
                    _issue(issues, family_label, f"family 重复：{family_name}")
                elif family_name:
                    seen_families.add(family_name)
                    valid_freedom_refs.add(family_name)
                for field in ("family", "assessment", "basis"):
                    if not _nonempty(family, field):
                        _issue(issues, family_label, f"缺少 {field}")
            missing_families = sorted(REQUIRED_FREEDOM_FAMILIES - seen_families)
            extra_families = sorted(seen_families - REQUIRED_FREEDOM_FAMILIES)
            if missing_families:
                _issue(issues, audit_label, f"freedom_families 缺少：{', '.join(missing_families)}")
            if extra_families:
                _issue(issues, audit_label, f"freedom_families 含无效类别：{', '.join(extra_families)}")

            entities = decision_audit.get("added_or_repeated_entities")
            if not isinstance(entities, list):
                _issue(issues, audit_label, "added_or_repeated_entities 必须是数组（无则空数组）")
                entities = []
            for entity_index, entity in enumerate(entities, 1):
                entity_label = f"{audit_label}.added_or_repeated_entities[{entity_index}]"
                if not isinstance(entity, dict):
                    _issue(issues, entity_label, "必须是对象")
                    continue
                for field in ("change", "entities", "relative_relations", "model_mapping"):
                    if not _nonempty(entity, field):
                        _issue(issues, entity_label, f"缺少 {field}")
                if not isinstance(entity.get("entities"), list):
                    _issue(issues, entity_label, "entities 必须是非空数组")
                if not isinstance(entity.get("relative_relations"), list):
                    _issue(issues, entity_label, "relative_relations 必须是非空数组")

            uses_aggregate = decision_audit.get("uses_aggregate_model")
            if not isinstance(uses_aggregate, bool):
                _issue(issues, audit_label, "uses_aggregate_model 必须为布尔值")
            assumptions = decision_audit.get("collapse_assumptions")
            if not isinstance(assumptions, list):
                _issue(issues, audit_label, "collapse_assumptions 必须是数组（无则空数组）")
                assumptions = []
            if uses_aggregate is True and not assumptions:
                _issue(issues, audit_label, "uses_aggregate_model=true 时 collapse_assumptions 不得为空")
            assumption_ids: set[str] = set()
            for assumption_index, assumption in enumerate(assumptions, 1):
                assumption_label = f"{audit_label}.collapse_assumptions[{assumption_index}]"
                if not isinstance(assumption, dict):
                    _issue(issues, assumption_label, "必须是对象")
                    continue
                assumption_id = str(assumption.get("assumption_id") or "").strip()
                if not assumption_id:
                    _issue(issues, assumption_label, "缺少 assumption_id")
                elif assumption_id in assumption_ids:
                    _issue(issues, assumption_label, f"assumption_id 重复：{assumption_id}")
                else:
                    assumption_ids.add(assumption_id)
                    valid_freedom_refs.add(assumption_id)
                for field in ("expression", "assumption", "alternative"):
                    if not _nonempty(assumption, field):
                        _issue(issues, assumption_label, f"缺少 {field}")
                disposition = assumption.get("disposition")
                if disposition not in VALID_COLLAPSE_DISPOSITIONS:
                    _issue(issues, assumption_label, f"disposition 无效：{disposition}")
                elif disposition == "CHALLENGED" and not _nonempty(assumption, "challenge_id"):
                    _issue(issues, assumption_label, "CHALLENGED 必须提供 challenge_id")
                elif disposition == "FIXED_BY_PROBLEM" and not _nonempty(assumption, "basis"):
                    _issue(issues, assumption_label, "FIXED_BY_PROBLEM 必须提供题面/硬约束 basis")
                elif disposition == "EVIDENCE_REJECTED":
                    if not _nonempty(assumption, "basis"):
                        _issue(issues, assumption_label, "EVIDENCE_REJECTED 必须提供 basis")
                    for error in _check_files(root, assumption.get("evidence_files"), "evidence_files"):
                        _issue(issues, assumption_label, error)
                elif disposition == "UNTESTED" and not _nonempty(assumption, "frontier"):
                    _issue(issues, assumption_label, "UNTESTED 必须提供 frontier")
                collapse_records.append((assumption_label, assumption))

        model_contract = question.get("model_contract_audit")
        if not isinstance(model_contract, dict):
            _issue(issues, label, "缺少 model_contract_audit 判据语义与边界审计")
        else:
            contract_label = f"{label}.model_contract_audit"
            criterion = model_contract.get("criterion_semantics")
            if not isinstance(criterion, dict):
                _issue(issues, contract_label, "criterion_semantics 必须是对象")
            else:
                criterion_label = f"{contract_label}.criterion_semantics"
                for field in ("subject", "object_extent", "quantifier", "acceptance_test", "basis"):
                    if not _nonempty(criterion, field):
                        _issue(issues, criterion_label, f"缺少 {field}")
                if criterion.get("source") not in VALID_CONTRACT_SOURCES:
                    _issue(
                        issues,
                        criterion_label,
                        "source 必须为 PROBLEM/DERIVED/EXTERNAL/MODELING_CHOICE 之一",
                    )
                elif criterion.get("source") == "MODELING_CHOICE":
                    if not _nonempty(criterion, "alternative_contract"):
                        _issue(issues, criterion_label, "MODELING_CHOICE 缺少 alternative_contract")
                    for error in _check_files(
                        root,
                        criterion.get("alternative_evidence_files"),
                        "alternative_evidence_files",
                    ):
                        _issue(issues, criterion_label, error)

            boundaries = model_contract.get("state_boundary_conditions")
            if not isinstance(boundaries, list):
                _issue(issues, contract_label, "state_boundary_conditions 必须是数组（无则空数组）")
                boundaries = []
            if not boundaries and not _nonempty(model_contract, "no_boundary_basis"):
                _issue(issues, contract_label, "边界表为空时必须提供 no_boundary_basis")
            for boundary_index, boundary in enumerate(boundaries, 1):
                boundary_label = f"{contract_label}.state_boundary_conditions[{boundary_index}]"
                if not isinstance(boundary, dict):
                    _issue(issues, boundary_label, "必须是对象")
                    continue
                for field in ("state", "domain", "boundary", "behavior", "basis"):
                    if not _nonempty(boundary, field):
                        _issue(issues, boundary_label, f"缺少 {field}")
                if boundary.get("source") not in VALID_CONTRACT_SOURCES:
                    _issue(
                        issues,
                        boundary_label,
                        "source 必须为 PROBLEM/DERIVED/EXTERNAL/MODELING_CHOICE 之一",
                    )
                elif boundary.get("source") == "MODELING_CHOICE":
                    if not _nonempty(boundary, "alternative_behavior"):
                        _issue(issues, boundary_label, "MODELING_CHOICE 缺少 alternative_behavior")
                    for error in _check_files(
                        root,
                        boundary.get("alternative_evidence_files"),
                        "alternative_evidence_files",
                    ):
                        _issue(issues, boundary_label, error)

            uses_proxy = model_contract.get("uses_proxy_or_surrogate")
            if not isinstance(uses_proxy, bool):
                _issue(issues, contract_label, "uses_proxy_or_surrogate 必须为布尔值")
            elif uses_proxy:
                for field in ("proxy_relation", "strict_contract"):
                    if not _nonempty(model_contract, field):
                        _issue(issues, contract_label, f"使用代理时缺少 {field}")
                for error in _check_files(
                    root,
                    model_contract.get("proxy_validation_evidence_files"),
                    "proxy_validation_evidence_files",
                ):
                    _issue(issues, contract_label, error)

            certification = model_contract.get("incumbent_certification")
            certification_label = f"{contract_label}.incumbent_certification"
            if not isinstance(certification, dict):
                _issue(issues, certification_label, "必须是对象")
            else:
                for field in (
                    "strict_contract_pass",
                    "boundary_crossings_checked",
                    "active_constraints_checked",
                ):
                    if certification.get(field) is not True:
                        _issue(issues, certification_label, f"{field} 必须为 true")
                proxy_gap_status = certification.get("proxy_gap_status")
                if proxy_gap_status not in VALID_PROXY_GAP_STATUSES:
                    _issue(
                        issues,
                        certification_label,
                        "proxy_gap_status 必须为 NOT_USED/PASS/FAIL/UNRESOLVED 之一",
                    )
                elif uses_proxy is True and proxy_gap_status != "PASS":
                    _issue(issues, certification_label, "使用代理时 proxy_gap_status 必须为 PASS")
                elif uses_proxy is False and proxy_gap_status != "NOT_USED":
                    _issue(issues, certification_label, "未使用代理时 proxy_gap_status 必须为 NOT_USED")
                for error in _check_files(root, certification.get("evidence_files"), "evidence_files"):
                    _issue(issues, certification_label, error)

        constraints = question.get("hard_constraints")
        if not isinstance(constraints, list) or not constraints:
            _issue(issues, label, "hard_constraints 必须是非空数组")
        else:
            for c_index, constraint in enumerate(constraints, 1):
                c_label = f"{label}.hard_constraints[{c_index}]"
                if not isinstance(constraint, dict):
                    _issue(issues, c_label, "必须是对象")
                    continue
                if not _nonempty(constraint, "name"):
                    _issue(issues, c_label, "缺少 name")
                if constraint.get("status") != "PASS":
                    _issue(issues, c_label, "status 必须为 PASS")
                for error in _check_files(root, constraint.get("evidence_files"), "evidence_files"):
                    _issue(issues, c_label, error)

        objectives = question.get("soft_objectives")
        objective_names: list[str] = []
        if not isinstance(objectives, list) or not objectives:
            _issue(issues, label, "soft_objectives 必须是非空数组")
        else:
            for o_index, objective in enumerate(objectives, 1):
                o_label = f"{label}.soft_objectives[{o_index}]"
                if not isinstance(objective, dict):
                    _issue(issues, o_label, "必须是对象")
                    continue
                for field in ("name", "unit", "incumbent_value"):
                    if not _nonempty(objective, field):
                        _issue(issues, o_label, f"缺少 {field}")
                if _nonempty(objective, "name"):
                    objective_names.append(str(objective["name"]).strip())
                if objective.get("direction") not in {"min", "max"}:
                    _issue(issues, o_label, "direction 必须为 min 或 max")

        for section in ("baseline", "incumbent"):
            record = question.get(section)
            s_label = f"{label}.{section}"
            if not isinstance(record, dict):
                _issue(issues, s_label, "必须是对象")
                continue
            if not _nonempty(record, "description"):
                _issue(issues, s_label, "缺少 description")
            if not isinstance(record.get("metrics"), dict) or not record.get("metrics"):
                _issue(issues, s_label, "metrics 必须是非空对象")
            else:
                for objective_name in objective_names:
                    if objective_name not in record["metrics"]:
                        _issue(issues, s_label, f"metrics 缺少软目标：{objective_name}")
            for error in _check_files(root, record.get("evidence_files"), "evidence_files"):
                _issue(issues, s_label, error)

        rulers = question.get("rulers")
        if not isinstance(rulers, list) or not rulers:
            _issue(issues, label, "rulers 必须是非空数组")
            rulers = []
        for r_index, ruler in enumerate(rulers, 1):
            r_label = f"{label}.rulers[{r_index}]"
            if not isinstance(ruler, dict):
                _issue(issues, r_label, "必须是对象")
                continue
            if ruler.get("type") not in VALID_RULERS:
                _issue(issues, r_label, f"type 无效：{ruler.get('type')}")
            if not _nonempty(ruler, "description"):
                _issue(issues, r_label, "缺少 description")
            for error in _check_files(root, ruler.get("evidence_files"), "evidence_files"):
                _issue(issues, r_label, error)

        challenges = question.get("challenges")
        if not isinstance(challenges, list) or not challenges:
            _issue(issues, label, "challenges 必须至少包含一个结构性挑战")
            challenges = []
        has_representation_level = False
        representation_refs: set[str] = set()
        change_descriptions: set[str] = set()
        challenge_ids: set[str] = set()
        for ch_index, challenge in enumerate(challenges, 1):
            ch_label = f"{label}.challenges[{ch_index}]"
            if not isinstance(challenge, dict):
                _issue(issues, ch_label, "必须是对象")
                continue
            challenge_id = str(challenge.get("challenge_id", "")).strip()
            if not challenge_id:
                _issue(issues, ch_label, "缺少 challenge_id")
            elif challenge_id in challenge_ids:
                _issue(issues, ch_label, f"challenge_id 重复：{challenge_id}")
            else:
                challenge_ids.add(challenge_id)
            if challenge.get("change_level") not in VALID_CHANGE_LEVELS:
                _issue(issues, ch_label, "change_level 必须是结构、目标、分解、模型、信息或求解结构之一")
            elif challenge.get("change_level") in REPRESENTATION_LEVELS:
                has_representation_level = True
                freedom_ref = str(challenge.get("freedom_ref") or "").strip()
                if not freedom_ref:
                    _issue(issues, ch_label, "表示/分解级挑战缺少 freedom_ref")
                elif freedom_ref not in valid_freedom_refs:
                    _issue(issues, ch_label, f"freedom_ref 未指向决策空间审计项：{freedom_ref}")
                else:
                    representation_refs.add(freedom_ref)
            for field in ("target_bottleneck", "structural_change"):
                if not _nonempty(challenge, field):
                    _issue(issues, ch_label, f"缺少 {field}")
            if _nonempty(challenge, "structural_change"):
                change_descriptions.add(str(challenge["structural_change"]).strip())
            if challenge.get("status") not in VALID_CHALLENGE_STATES:
                _issue(issues, ch_label, f"status 无效：{challenge.get('status')}")
            if challenge.get("feasibility_status") not in {"PASS", "FAIL"}:
                _issue(issues, ch_label, "feasibility_status 必须为 PASS 或 FAIL")
            if challenge.get("status") == "PROMOTED" and challenge.get("feasibility_status") != "PASS":
                _issue(issues, ch_label, "PROMOTED 挑战者必须先通过真实性/可行性门禁")
            if not isinstance(challenge.get("metrics"), dict) or not challenge.get("metrics"):
                _issue(issues, ch_label, "metrics 必须是非空对象")
            elif challenge.get("feasibility_status") == "PASS":
                for objective_name in objective_names:
                    if objective_name not in challenge["metrics"]:
                        _issue(issues, ch_label, f"metrics 缺少软目标：{objective_name}")
            for error in _check_files(root, challenge.get("evidence_files"), "evidence_files"):
                _issue(issues, ch_label, error)

        budget = question.get("budget")
        if not isinstance(budget, dict):
            _issue(issues, f"{label}.budget", "必须是对象")
            allocated = used = None
        else:
            allocated = _number(budget.get("allocated"))
            used = _number(budget.get("used"))
            if allocated is None or allocated <= 0:
                _issue(issues, f"{label}.budget", "allocated 必须为正数")
            if used is None or used < 0:
                _issue(issues, f"{label}.budget", "used 必须为非负数")
            if not _nonempty(budget, "unit"):
                _issue(issues, f"{label}.budget", "缺少 unit")
            if allocated is not None and used is not None and used > allocated and not _nonempty(budget, "overrun_reason"):
                _issue(issues, f"{label}.budget", "预算超支时必须提供 overrun_reason")

        stop = question.get("stop_certificate")
        stop_label = f"{label}.stop_certificate"
        if not isinstance(stop, dict):
            _issue(issues, stop_label, "必须是对象")
            continue
        reason = stop.get("reason")
        if reason not in VALID_STOP_REASONS:
            _issue(issues, stop_label, f"reason 无效：{reason}")
        for field in ("summary", "remaining_gap_or_unknown", "untested_frontiers"):
            if field not in stop or (field != "untested_frontiers" and not _nonempty(stop, field)):
                _issue(issues, stop_label, f"缺少 {field}")
        if not isinstance(stop.get("untested_frontiers"), list):
            _issue(issues, stop_label, "untested_frontiers 必须是数组")
        for error in _check_files(root, stop.get("evidence_files"), "evidence_files"):
            _issue(issues, stop_label, error)

        if reason in {"PROVEN_OPTIMAL", "GAP_TARGET"}:
            gap = _number(stop.get("optimality_gap"))
            threshold = _number(stop.get("gap_threshold"))
            if gap is None or gap < 0:
                _issue(issues, stop_label, "optimality_gap 必须为非负数")
            if threshold is None or threshold < 0:
                _issue(issues, stop_label, "gap_threshold 必须为非负数")
            if gap is not None and threshold is not None and gap > threshold:
                _issue(issues, stop_label, "optimality_gap 超过 gap_threshold")
            if reason == "PROVEN_OPTIMAL" and gap not in {0, 0.0}:
                _issue(issues, stop_label, "PROVEN_OPTIMAL 要求 optimality_gap=0")
            if not any(isinstance(r, dict) and r.get("type") in {"lower_bound", "upper_bound", "exact_small"} for r in rulers):
                _issue(issues, stop_label, "证优或 gap 停止缺少界或精确标尺")
        elif reason == "BUDGET_EXHAUSTED":
            if allocated is None or used is None or used < allocated:
                _issue(issues, stop_label, "BUDGET_EXHAUSTED 要求 used>=allocated")
            if not stop.get("untested_frontiers"):
                _issue(issues, stop_label, "预算耗尽时必须列出未探索前沿")
        elif reason == "DIMINISHING_RETURNS":
            marginal = _number(stop.get("marginal_gain"))
            threshold = _number(stop.get("marginal_gain_threshold"))
            if len(change_descriptions) < 2:
                _issue(issues, stop_label, "边际收益停止至少需要两条结构实质不同的挑战")
            if marginal is None or threshold is None or marginal > threshold:
                _issue(issues, stop_label, "边际收益必须不超过预设阈值")
        elif reason == "BLOCKED_BY_CONSTRAINT" and not _nonempty(stop, "blocking_constraint"):
            _issue(issues, stop_label, "缺少 blocking_constraint")

        stop_frontiers = stop.get("untested_frontiers")
        stop_frontiers = stop_frontiers if isinstance(stop_frontiers, list) else []
        for assumption_label, assumption in collapse_records:
            disposition = assumption.get("disposition")
            if disposition == "CHALLENGED":
                challenge_id = str(assumption.get("challenge_id") or "").strip()
                if challenge_id not in challenge_ids:
                    _issue(issues, assumption_label, f"challenge_id 不存在：{challenge_id}")
                assumption_id = str(assumption.get("assumption_id") or "").strip()
                if assumption_id and assumption_id not in representation_refs:
                    _issue(issues, assumption_label, "CHALLENGED 聚合假设未被表示/分解挑战的 freedom_ref 引用")
            elif disposition == "UNTESTED":
                frontier = assumption.get("frontier")
                if frontier not in stop_frontiers:
                    _issue(issues, assumption_label, "UNTESTED 项必须逐字进入 stop_certificate.untested_frontiers")

        if representation_risk == "high" and reason != "PROVEN_OPTIMAL" and not has_representation_level:
            _issue(issues, stop_label, "representation_risk=high 时在非 PROVEN_OPTIMAL 停止前必须完成至少一次带 freedom_ref 的表示/分解级挑战")

    expected = {str(q).strip() for q in (expected_questions or []) if str(q).strip()}
    missing = sorted(expected - seen)
    extra = sorted(seen - expected) if expected_questions is not None else []
    if missing:
        _issue(issues, "ledger", f"缺少竞赛型子问题：{', '.join(missing)}")
    if extra:
        _issue(issues, "ledger", f"账本含未声明的子问题：{', '.join(extra)}")

    return {
        "ok": not issues,
        "ledger": str(ledger_file),
        "project_root": str(root),
        "questions": sorted(seen),
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查竞赛型子问题的内部标尺、结构挑战、预算与停止证书")
    parser.add_argument("ledger", help="PROJECT_ROOT/results/竞争性搜索账本.json")
    parser.add_argument("--project-root", required=True, help="项目根目录")
    parser.add_argument("--questions", nargs="*", help="预期竞赛型子问题，如 q3 q4")
    parser.add_argument("--strict", action="store_true", help="保留接口兼容；FAIL 始终阻断")
    parser.add_argument("--json-output", help="可选审计报告路径")
    args = parser.parse_args(argv)

    report = audit_ledger(args.ledger, args.project_root, args.questions)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    if args.json_output:
        Path(args.json_output).write_text(output + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
