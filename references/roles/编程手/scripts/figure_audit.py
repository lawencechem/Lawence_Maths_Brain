#!/usr/bin/env python3
"""依赖标准库的论文图文件与视觉论证清单审计器。"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
LEGACY_CATEGORIES = ("raw_", "process_", "result_")
VALID_CARRIERS = {"figure", "table", "equation", "text"}
VALID_DECISIONS = {"KEEP", "MERGE", "APPENDIX", "DROP", "PENDING_RENDER"}
VALID_VISUAL_ROLES = {
    "mechanism",
    "geometry",
    "flow",
    "architecture",
    "topology",
    "result",
    "validation",
    "robustness",
}


def _png_metadata(path: Path) -> dict:
    width = height = None
    dpi_x = dpi_y = None
    with path.open("rb") as stream:
        if stream.read(8) != PNG_SIGNATURE:
            raise ValueError("不是有效的 PNG 文件")
        while True:
            header = stream.read(8)
            if len(header) != 8:
                break
            length, chunk_type = struct.unpack(">I4s", header)
            data = stream.read(length)
            stream.read(4)
            if chunk_type == b"IHDR":
                width, height = struct.unpack(">II", data[:8])
            elif chunk_type == b"pHYs" and len(data) >= 9:
                pixels_x, pixels_y, unit = struct.unpack(">IIB", data[:9])
                if unit == 1:
                    dpi_x = pixels_x * 0.0254
                    dpi_y = pixels_y * 0.0254
            elif chunk_type == b"IEND":
                break
    if width is None or height is None:
        raise ValueError("PNG 缺少 IHDR")
    metadata = {
        "width_px": width,
        "height_px": height,
        "dpi_x": dpi_x,
        "dpi_y": dpi_y,
    }
    if dpi_x and dpi_y:
        metadata["width_in"] = width / dpi_x
        metadata["height_in"] = height / dpi_y
    return metadata


def _svg_metadata(path: Path) -> dict:
    root = ET.parse(path).getroot()
    elements = list(root.iter())
    text_count = sum(element.tag.rsplit("}", 1)[-1] == "text" for element in elements)
    embedded_raster = any(
        element.tag.rsplit("}", 1)[-1] == "image"
        and "base64" in " ".join(str(value) for value in element.attrib.values()).lower()
        for element in elements
    )
    return {"text_count": text_count, "embedded_raster": embedded_raster}


def _normalise_questions(questions: tuple[str, ...]) -> tuple[str, ...]:
    result = tuple(dict.fromkeys(question.strip().casefold() for question in questions))
    if any(not re.fullmatch(r"q[1-9]\d*", question) for question in result):
        raise ValueError("子问题标识必须使用 q1、q2 等格式")
    return result


def _nonempty(item: dict, field: str) -> bool:
    return isinstance(item.get(field), str) and bool(item[field].strip())


def _audit_manifest(
    manifest_path: str | Path,
    *,
    figures_dir: Path,
    figure_stems: set[str],
    questions: tuple[str, ...],
) -> tuple[dict, list[dict[str, str]], dict[str, bool]]:
    issues: list[dict[str, str]] = []
    path = Path(manifest_path).expanduser().resolve()
    if not path.is_file():
        return {}, [{"severity": "FAIL", "message": f"图表论证清单不存在：{path}"}], {}

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [{"severity": "FAIL", "message": f"无法读取图表论证清单：{exc}"}], {}

    if not isinstance(manifest, dict):
        return manifest, [{"severity": "FAIL", "message": "图表论证清单根节点必须是对象"}], {}
    items = manifest.get("items")
    if not isinstance(items, list):
        return manifest, [{"severity": "FAIL", "message": "图表论证清单必须包含 items 数组"}], {}

    declared = manifest.get("questions")
    if not isinstance(declared, list) or not all(isinstance(q, str) for q in declared):
        issues.append({"severity": "FAIL", "message": "图表论证清单必须包含 questions 字符串数组"})
        declared_questions: tuple[str, ...] = ()
    else:
        try:
            declared_questions = _normalise_questions(tuple(declared))
        except ValueError as exc:
            issues.append({"severity": "FAIL", "message": str(exc)})
            declared_questions = ()

    if questions and set(declared_questions) != set(questions):
        issues.append({
            "severity": "FAIL",
            "message": (
                "清单 questions 与 --questions 不一致："
                f"清单={list(declared_questions)}，命令={list(questions)}"
            ),
        })

    coverage = {question: False for question in questions}
    seen_claims: set[str] = set()
    listed_stems: set[str] = set()

    for index, item in enumerate(items, 1):
        label = f"items[{index}]"
        if not isinstance(item, dict):
            issues.append({"severity": "FAIL", "message": f"{label} 必须是对象"})
            continue

        for field in ("claim_id", "question_id", "reader_gap", "claim", "evidence_source", "carrier", "decision"):
            if not _nonempty(item, field):
                issues.append({"severity": "FAIL", "message": f"{label} 缺少非空字段 {field}"})

        claim_id = str(item.get("claim_id", "")).strip()
        if claim_id:
            if claim_id in seen_claims:
                issues.append({"severity": "FAIL", "message": f"重复 claim_id：{claim_id}"})
            seen_claims.add(claim_id)

        question = str(item.get("question_id", "")).strip().casefold()
        if question and not re.fullmatch(r"q[1-9]\d*", question):
            issues.append({"severity": "FAIL", "message": f"{label} 的 question_id 无效：{question}"})
        elif questions and question not in questions:
            issues.append({"severity": "FAIL", "message": f"{label} 引用了未声明子问题：{question}"})

        carrier = str(item.get("carrier", "")).strip().casefold()
        if carrier and carrier not in VALID_CARRIERS:
            issues.append({"severity": "FAIL", "message": f"{label} 的 carrier 无效：{carrier}"})

        decision = str(item.get("decision", "")).strip().upper()
        if decision and decision not in VALID_DECISIONS:
            issues.append({"severity": "FAIL", "message": f"{label} 的 decision 无效：{decision}"})

        if decision == "PENDING_RENDER":
            issues.append({"severity": "FAIL", "message": f"{label} 仍为 PENDING_RENDER，不能通过 P2"})
            if not _nonempty(item, "instruction_file"):
                issues.append({"severity": "FAIL", "message": f"{label} 缺少 GeoGebra instruction_file"})
        elif decision == "DROP" and not _nonempty(item, "drop_reason"):
            issues.append({"severity": "FAIL", "message": f"{label} 为 DROP 但缺少 drop_reason"})
        elif decision == "MERGE" and not _nonempty(item, "merge_target"):
            issues.append({"severity": "FAIL", "message": f"{label} 为 MERGE 但缺少 merge_target"})

        if decision == "KEEP" and question in coverage:
            coverage[question] = True

        if decision in {"KEEP", "APPENDIX"}:
            if not _nonempty(item, "placement"):
                issues.append({"severity": "FAIL", "message": f"{label} 缺少 placement"})
            if carrier == "figure":
                for field in ("visual_role", "file_stem", "lead_in", "post_observation", "post_implication"):
                    if not _nonempty(item, field):
                        issues.append({"severity": "FAIL", "message": f"{label} 的正式图缺少 {field}"})

        if carrier == "figure":
            role = str(item.get("visual_role", "")).strip().casefold()
            if role and role not in VALID_VISUAL_ROLES:
                issues.append({"severity": "FAIL", "message": f"{label} 的 visual_role 无效：{role}"})
            file_stem = str(item.get("file_stem", "")).strip()
            if file_stem:
                stem = Path(file_stem).stem
                listed_stems.add(stem)
                if decision in {"KEEP", "APPENDIX"} and stem not in figure_stems:
                    issues.append({
                        "severity": "FAIL",
                        "message": f"{label} 引用的正式图不存在或缺少 SVG/PNG：{stem}",
                    })

    for question, covered in coverage.items():
        if not covered:
            issues.append({"severity": "FAIL", "message": f"子问题 {question} 缺少 decision=KEEP 的正式证据单元"})

    unlisted = sorted(stem for stem in figure_stems if stem not in listed_stems and not stem.endswith("_grayscale"))
    if unlisted:
        issues.append({
            "severity": "FAIL",
            "message": "以下逻辑图未登记到图表论证清单：" + "、".join(unlisted),
        })

    return manifest, issues, coverage


def audit_figure_directory(
    figures_dir: str | Path,
    *,
    min_dpi: int = 300,
    require_categories: bool = False,
    min_per_category: int = 3,
    questions: tuple[str, ...] = (),
    manifest_path: str | Path | None = None,
) -> dict:
    if min_per_category < 1:
        raise ValueError("每类候选图最低数量必须大于等于 1")
    normalized_questions = _normalise_questions(questions)
    directory = Path(figures_dir).expanduser().resolve()
    issues: list[dict[str, str]] = []
    files: dict[str, dict] = {}
    if not directory.is_dir():
        return {
            "ok": False,
            "directory": str(directory),
            "questions": list(normalized_questions),
            "files": files,
            "issues": [{"severity": "FAIL", "message": "figures 目录不存在"}],
        }

    candidates = sorted(path for path in directory.iterdir() if path.is_file())
    by_stem: dict[str, set[str]] = {}
    for path in candidates:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            issues.append({"severity": "FAIL", "message": f"数据图禁止使用 JPEG：{path.name}"})
        if suffix not in {".svg", ".png", ".ggb"}:
            continue
        by_stem.setdefault(path.stem, set()).add(suffix)
        if suffix == ".ggb":
            files[path.name] = {"source": "geogebra"}
            continue
        try:
            metadata = _png_metadata(path) if suffix == ".png" else _svg_metadata(path)
        except (OSError, ValueError, ET.ParseError) as exc:
            issues.append({"severity": "FAIL", "message": f"无法解析 {path.name}：{exc}"})
            continue
        files[path.name] = metadata
        if suffix == ".png":
            dpi_values = [metadata["dpi_x"], metadata["dpi_y"]]
            if any(value is None for value in dpi_values):
                issues.append({"severity": "FAIL", "message": f"{path.name} 缺少 DPI 元数据"})
            elif min(dpi_values) + 0.5 < min_dpi:
                issues.append({"severity": "FAIL", "message": f"{path.name} 低于 {min_dpi} DPI"})
        elif metadata["text_count"] == 0:
            issues.append({"severity": "FAIL", "message": f"{path.name} 没有可编辑文本节点"})
        elif metadata["embedded_raster"]:
            issues.append({"severity": "WARN", "message": f"{path.name} 含嵌入位图，请确认确有必要"})

    logical_stems: set[str] = set()
    for stem, suffixes in by_stem.items():
        if stem.endswith("_grayscale"):
            continue
        logical_stems.add(stem)
        required = {".png"} if ".ggb" in suffixes else {".svg", ".png"}
        missing = required - suffixes
        if missing:
            issues.append({
                "severity": "FAIL",
                "message": f"{stem} 缺少配对格式：{', '.join(sorted(missing))}",
            })

    if require_categories:
        for prefix in LEGACY_CATEGORIES:
            count = sum(stem.startswith(prefix) for stem in logical_stems)
            if count < min_per_category:
                issues.append({
                    "severity": "FAIL",
                    "message": f"{prefix} 类候选图仅 {count} 张，低于每类最低 {min_per_category} 张",
                })

    manifest = None
    coverage: dict[str, bool] = {}
    if manifest_path is not None:
        if not normalized_questions:
            issues.append({"severity": "FAIL", "message": "使用 --manifest 时必须通过 --questions 声明全部子问题"})
        manifest, manifest_issues, coverage = _audit_manifest(
            manifest_path,
            figures_dir=directory,
            figure_stems=logical_stems,
            questions=normalized_questions,
        )
        issues.extend(manifest_issues)
    elif normalized_questions:
        issues.append({"severity": "FAIL", "message": "声明 --questions 时必须同时提供 --manifest"})

    return {
        "ok": not any(item["severity"] == "FAIL" for item in issues),
        "directory": str(directory),
        "questions": list(normalized_questions),
        "evidence_coverage": coverage,
        "manifest": manifest,
        "files": files,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="检查图文件、图表论证清单和子问题证据覆盖")
    parser.add_argument("figures_dir", help="PROJECT_ROOT 下的 figures 目录")
    parser.add_argument("--manifest", help="PROJECT_ROOT/results/图表论证清单.json")
    parser.add_argument("--min-dpi", type=int, default=300)
    parser.add_argument("--min-per-category", type=int, default=3, help="旧三类图审计的每类最低数量")
    parser.add_argument(
        "--questions",
        nargs="+",
        default=(),
        metavar="Q",
        help="题目全部子问题标识，例如 q1 q2 q3",
    )
    parser.add_argument(
        "--legacy-category-check",
        action="store_true",
        help="兼容旧项目：额外检查 raw/process/result 每类最低数量",
    )
    parser.add_argument("--no-category-check", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--strict", action="store_true", help="存在 FAIL 时返回非零退出码")
    args = parser.parse_args()
    report = audit_figure_directory(
        args.figures_dir,
        min_dpi=args.min_dpi,
        require_categories=args.legacy_category_check and not args.no_category_check,
        min_per_category=args.min_per_category,
        questions=tuple(args.questions),
        manifest_path=args.manifest,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.strict and not report["ok"] else 0


if __name__ == "__main__":
    sys.exit(main())
