from __future__ import annotations

import json
import platform
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def check(label: str, passed: bool, detail: str) -> bool:
    print(f"{'PASS' if passed else 'FAIL'}  {label}: {detail}")
    return passed


def main() -> int:
    results = [
        check("Python", sys.version_info >= (3, 11), platform.python_version()),
        check("Dashboard source", (ROOT / "dashboard/index.html").is_file(), "dashboard/index.html"),
        check("Snapshot", (ROOT / "data/latest.json").is_file(), "data/latest.json"),
        check("Briefing", (ROOT / "data/briefing.md").is_file(), "data/briefing.md"),
        check("Built site", (ROOT / "dist/index.html").is_file(), "dist/index.html"),
    ]
    snapshot_path = ROOT / "data/latest.json"
    if snapshot_path.is_file():
        try:
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            results.append(check("Schema", snapshot.get("schema_version") == 1, str(snapshot.get("schema_version"))))
            squad = snapshot.get("analysis", {}).get("recommendations", {}).get("initial_squad", {})
            results.append(check("Optimizer", squad.get("validation", {}).get("valid") is True, squad.get("status", "missing")))
        except (OSError, ValueError) as error:
            results.append(check("Snapshot JSON", False, str(error)))
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

