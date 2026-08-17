#!/usr/bin/env python3
"""检查数模非数据图的 Python 与可选 GeoGebra 环境。"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import sys
from pathlib import Path


PYTHON_PACKAGES = ("matplotlib", "networkx", "numpy")


def _geogebra_candidates() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.environ.get("GEOGEBRA_EXE")
    if explicit:
        candidates.append(Path(explicit))
    for command in ("GeoGebra", "GeoGebra.exe"):
        resolved = shutil.which(command)
        if resolved:
            candidates.append(Path(resolved))
    roots = [
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("LOCALAPPDATA"),
    ]
    relative_paths = (
        Path("GeoGebra 5.0") / "GeoGebra.exe",
        Path("GeoGebra 5.4") / "GeoGebra.exe",
        Path("GeoGebra_5.0") / "GeoGebra.exe",
        Path("GeoGebra_6") / "GeoGebra.exe",
        Path("Programs") / "GeoGebra 5.0" / "GeoGebra.exe",
    )
    for root in roots:
        if root:
            candidates.extend(Path(root) / relative for relative in relative_paths)
    return list(dict.fromkeys(path.expanduser() for path in candidates))


def inspect_environment() -> dict:
    packages: dict[str, str] = {}
    missing: list[str] = []
    for package in PYTHON_PACKAGES:
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            missing.append(package)
    geogebra = next((path.resolve() for path in _geogebra_candidates() if path.is_file()), None)
    return {
        "python": sys.version.split()[0],
        "packages": packages,
        "missing_python_packages": missing,
        "geogebra": str(geogebra) if geogebra else None,
        "python_ready": not missing,
        "geogebra_ready": geogebra is not None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 Matplotlib/NetworkX/NumPy 与 GeoGebra")
    parser.add_argument(
        "--require-geogebra",
        action="store_true",
        help="几何任务需要本轮自动渲染时，GeoGebra 缺失返回非零退出码",
    )
    args = parser.parse_args()
    report = inspect_environment()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["python_ready"]:
        return 1
    if args.require_geogebra and not report["geogebra_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
