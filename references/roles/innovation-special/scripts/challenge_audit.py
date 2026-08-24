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
VALID_CANDIDATE_DISPOSITIONS = {
    "CHALLENGED",
    "FIXED_BY_PROBLEM",
    "EVIDENCE_REJECTED",
    "UNTESTED",
}
VALID_PROXY_COMPARISON_STATUSES = {"CONSISTENT", "DIVERGENT", "NOT_APPLICABLE"}
VALID_STRICT_SEARCH_ACTIONS = {"STRICT_IN_LOOP", "STRICT_REOPTIMIZED", "PROXY_REJECTED"}
LARGE_GAP_TRIGGER = 0.50


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
    if ledger.get("schema_version") != 3:
        _issue(issues, "ledger", "schema_version 必须为 3（精简结构门禁）")
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

        valid_candidate_refs: set[str] = set()
        collapse_records: list[tuple[str, dict[str, Any]]] = []
        candidate_records: list[tuple[str, dict[str, Any]]] = []
        structure_required = False
        decision_audit = question.get("decision_space_audit")
        if not isinstance(decision_audit, dict):
            _issue(issues, label, "缺少 decision_space_audit 决策空间审计")
        else:
            audit_label = f"{label}.decision_space_audit"
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
                    valid_candidate_refs.add(assumption_id)
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

            structure_probe = decision_audit.get("structure_probe")
            structure_triggers = decision_audit.get("structure_triggers", [])
            if not isinstance(structure_triggers, list):
                _issue(issues, audit_label, "structure_triggers 必须是数组")
                structure_triggers = []
            structure_required = bool(entities) or uses_aggregate is True or bool(structure_triggers)
            if structure_required or structure_probe is not None:
                probe_label = f"{audit_label}.structure_probe"
                if not isinstance(structure_probe, dict):
                    _issue(issues, probe_label, "命中结构信号时必须在黑盒搜索前完成结构探针")
                else:
                    if not isinstance(structure_probe.get("observations"), list) or not structure_probe.get("observations"):
                        _issue(issues, probe_label, "observations 必须是非空数组")
                    for error in _check_files(root, structure_probe.get("evidence_files"), "evidence_files"):
                        _issue(issues, probe_label, error)
                    candidates = structure_probe.get("candidates")
                    if not isinstance(candidates, list) or not candidates:
                        _issue(issues, probe_label, "candidates 必须是非空数组")
                        candidates = []
                    seen_candidate_refs: set[str] = set()
                    for candidate_index, candidate in enumerate(candidates, 1):
                        candidate_label = f"{probe_label}.candidates[{candidate_index}]"
                        if not isinstance(candidate, dict):
                            _issue(issues, candidate_label, "必须是对象")
                            continue
                        candidate_ref = str(candidate.get("candidate_ref") or "").strip()
                        if not candidate_ref:
                            _issue(issues, candidate_label, "缺少 candidate_ref")
                        elif candidate_ref in seen_candidate_refs:
                            _issue(issues, candidate_label, f"candidate_ref 重复：{candidate_ref}")
                        else:
                            seen_candidate_refs.add(candidate_ref)
                            valid_candidate_refs.add(candidate_ref)
                        for field in ("hypothesis", "basis"):
                            if not _nonempty(candidate, field):
                                _issue(issues, candidate_label, f"缺少 {field}")
                        disposition = candidate.get("disposition")
                        if disposition not in VALID_CANDIDATE_DISPOSITIONS:
                            _issue(issues, candidate_label, f"disposition 无效：{disposition}")
                        elif disposition == "CHALLENGED" and not _nonempty(candidate, "challenge_id"):
                            _issue(issues, candidate_label, "CHALLENGED 必须提供 challenge_id")
                        elif disposition == "EVIDENCE_REJECTED":
                            for error in _check_files(root, candidate.get("evidence_files"), "evidence_files"):
                                _issue(issues, candidate_label, error)
                        elif disposition == "UNTESTED" and not _nonempty(candidate, "frontier"):
                            _issue(issues, candidate_label, "UNTESTED 必须提供 frontier")
                        candidate_records.append((candidate_label, candidate))

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
                comparison = model_contract.get("proxy_strict_comparison")
                comparison_label = f"{contract_label}.proxy_strict_comparison"
                if not isinstance(comparison, dict):
                    _issue(issues, comparison_label, "使用代理时必须记录代理—严格判据的可行性与排序对照")
                else:
                    ranking_status = comparison.get("ranking_status")
                    feasibility_status = comparison.get("feasibility_status")
                    if ranking_status not in VALID_PROXY_COMPARISON_STATUSES:
                        _issue(issues, comparison_label, "ranking_status 必须为 CONSISTENT/DIVERGENT/NOT_APPLICABLE")
                    if feasibility_status not in VALID_PROXY_COMPARISON_STATUSES:
                        _issue(issues, comparison_label, "feasibility_status 必须为 CONSISTENT/DIVERGENT/NOT_APPLICABLE")
                    if "NOT_APPLICABLE" in {ranking_status, feasibility_status} and not _nonempty(comparison, "not_applicable_basis"):
                        _issue(issues, comparison_label, "NOT_APPLICABLE 必须提供 not_applicable_basis")
                    for error in _check_files(root, comparison.get("evidence_files"), "evidence_files"):
                        _issue(issues, comparison_label, error)
                    if "DIVERGENT" in {ranking_status, feasibility_status}:
                        if comparison.get("strict_search_action") not in VALID_STRICT_SEARCH_ACTIONS:
                            _issue(
                                issues,
                                comparison_label,
                                "代理与严格判据发生排序/可行性分歧时，严格判据必须进入搜索或代理必须被拒绝",
                            )
                        for error in _check_files(
                            root,
                            comparison.get("strict_search_evidence_files"),
                            "strict_search_evidence_files",
                        ):
                            _issue(issues, comparison_label, error)

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
        change_descriptions: set[str] = set()
        challenge_ids: set[str] = set()
        challenge_levels: dict[str, str] = {}
        challenge_candidate_refs: dict[str, str] = {}
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
                challenge_levels[challenge_id] = str(challenge.get("change_level") or "")
            if challenge.get("change_level") not in VALID_CHANGE_LEVELS:
                _issue(issues, ch_label, "change_level 必须是结构、目标、分解、模型、信息或求解结构之一")
            elif challenge.get("change_level") in REPRESENTATION_LEVELS:
                has_representation_level = True
                candidate_ref = str(challenge.get("candidate_ref") or "").strip()
                if not candidate_ref:
                    _issue(issues, ch_label, "表示/分解级挑战缺少 candidate_ref")
                elif candidate_ref not in valid_candidate_refs:
                    _issue(issues, ch_label, f"candidate_ref 未指向结构探针候选或聚合假设：{candidate_ref}")
                elif challenge_id:
                    challenge_candidate_refs[challenge_id] = candidate_ref
                delta = challenge.get("representation_delta")
                delta_label = f"{ch_label}.representation_delta"
                if not isinstance(delta, dict):
                    _issue(issues, delta_label, "表示/分解挑战必须给出基线到挑战空间的决策表示差量")
                else:
                    for field in ("baseline_decisions", "challenger_decisions"):
                        if not isinstance(delta.get(field), list) or not delta.get(field):
                            _issue(issues, delta_label, f"{field} 必须是非空数组")
                    relations = delta.get("added_or_released_relations")
                    if not isinstance(relations, list) or not relations:
                        _issue(issues, delta_label, "added_or_released_relations 必须列出新增或解除的关系/结构")
                    if not _nonempty(delta, "mechanism"):
                        _issue(issues, delta_label, "缺少 mechanism")
                    if _nonempty(delta, "mechanism"):
                        change_descriptions.add(str(delta["mechanism"]).strip())
                    if delta.get("same_space_solver_only") is not False:
                        _issue(issues, delta_label, "同一决策空间内仅更换求解器不构成表示/分解挑战")
                    for error in _check_files(
                        root,
                        delta.get("comparison_evidence_files"),
                        "comparison_evidence_files",
                    ):
                        _issue(issues, delta_label, error)
            if not _nonempty(challenge, "target_bottleneck"):
                _issue(issues, ch_label, "缺少 target_bottleneck")
            if challenge.get("change_level") not in REPRESENTATION_LEVELS and not _nonempty(challenge, "structural_change"):
                _issue(issues, ch_label, "非表示/分解挑战缺少 structural_change")
            if challenge.get("change_level") not in REPRESENTATION_LEVELS and _nonempty(challenge, "structural_change"):
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
            gap_assessment = stop.get("gap_assessment")
            gap_label = f"{stop_label}.gap_assessment"
            if not isinstance(gap_assessment, dict):
                _issue(issues, gap_label, "BUDGET_EXHAUSTED 必须说明 gap 是否可计算及如何处置")
            else:
                computable = gap_assessment.get("computable")
                if not isinstance(computable, bool):
                    _issue(issues, gap_label, "computable 必须为布尔值")
                elif not computable:
                    if not _nonempty(gap_assessment, "unknown_basis"):
                        _issue(issues, gap_label, "gap 不可计算时必须提供 unknown_basis")
                else:
                    gap_value = _number(gap_assessment.get("optimality_gap"))
                    if gap_value is None or gap_value < 0:
                        _issue(issues, gap_label, "optimality_gap 必须为非负数")
                    bound_quality = gap_assessment.get("bound_quality")
                    if bound_quality not in {"INFORMATIVE", "LOOSE"}:
                        _issue(issues, gap_label, "bound_quality 必须为 INFORMATIVE 或 LOOSE")
                    if gap_value is not None and gap_value > LARGE_GAP_TRIGGER:
                        response = gap_assessment.get("response")
                        if bound_quality == "INFORMATIVE":
                            challenge_id = str(gap_assessment.get("challenge_id") or "").strip()
                            if response != "STRUCTURE_CHALLENGE":
                                _issue(issues, gap_label, "大 gap 且标尺有信息量时必须执行结构/表示挑战")
                            elif challenge_levels.get(challenge_id) not in REPRESENTATION_LEVELS:
                                _issue(issues, gap_label, "大 gap 响应的 challenge_id 必须指向表示/分解级挑战")
                        elif bound_quality == "LOOSE":
                            if response != "BOUND_REVISED_OR_RETIRED":
                                _issue(issues, gap_label, "大 gap 来自松界时必须修正或撤销该标尺")
                            for error in _check_files(
                                root,
                                gap_assessment.get("response_evidence_files"),
                                "response_evidence_files",
                            ):
                                _issue(issues, gap_label, error)
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
                elif challenge_levels.get(challenge_id) not in REPRESENTATION_LEVELS:
                    _issue(issues, assumption_label, "challenge_id 必须指向表示/分解级挑战")
                else:
                    assumption_id = str(assumption.get("assumption_id") or "").strip()
                    if challenge_candidate_refs.get(challenge_id) != assumption_id:
                        _issue(issues, assumption_label, "challenge_id 对应挑战的 candidate_ref 未指向该聚合假设")
            elif disposition == "UNTESTED":
                frontier = assumption.get("frontier")
                if frontier not in stop_frontiers:
                    _issue(issues, assumption_label, "UNTESTED 项必须逐字进入 stop_certificate.untested_frontiers")

        for candidate_label, candidate in candidate_records:
            disposition = candidate.get("disposition")
            if disposition == "CHALLENGED":
                challenge_id = str(candidate.get("challenge_id") or "").strip()
                if challenge_id not in challenge_ids:
                    _issue(issues, candidate_label, f"challenge_id 不存在：{challenge_id}")
                elif challenge_levels.get(challenge_id) not in REPRESENTATION_LEVELS:
                    _issue(issues, candidate_label, "challenge_id 必须指向表示/分解级挑战")
                else:
                    candidate_ref = str(candidate.get("candidate_ref") or "").strip()
                    if challenge_candidate_refs.get(challenge_id) != candidate_ref:
                        _issue(issues, candidate_label, "challenge_id 对应挑战的 candidate_ref 未指向该结构候选")
            elif disposition == "UNTESTED":
                frontier = candidate.get("frontier")
                if frontier not in stop_frontiers:
                    _issue(issues, candidate_label, "UNTESTED 结构候选必须逐字进入未探索前沿")

        if structure_required and reason != "PROVEN_OPTIMAL" and not has_representation_level:
            _issue(issues, stop_label, "命中结构信号时在非 PROVEN_OPTIMAL 停止前必须完成至少一次带 candidate_ref 的表示/分解级挑战")

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
