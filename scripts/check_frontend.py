"""Deterministic payload, version and accessibility-source regression gates."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    baseline = json.loads((ROOT / "tests/fixtures/frontend-budget.json").read_text())
    metrics = {"javascript_bytes": sum(path.stat().st_size for path in (ROOT / "dashboard/assets").glob("*.js")),
               "css_bytes": (ROOT / "dashboard/assets/styles.css").stat().st_size,
               "snapshot_bytes": (ROOT / "dist/data/latest.json").stat().st_size}
    for key, value in metrics.items():
        assert value <= baseline["budgets"][key], f"{key} exceeds budget: {value}"
    index = (ROOT / "dashboard/index.html").read_text()
    css = (ROOT / "dashboard/assets/styles.css").read_text()
    assert 'lang="th"' in index and 'class="skip-link"' in index
    assert ":focus-visible" in css and "prefers-reduced-motion" in css
    ids = re.findall(r'\bid="([^\"]+)"', index)
    assert len(ids) == len(set(ids)), "Duplicate static IDs"
    from fpl_mvp.release import RELEASE_VERSION
    assert f'APP_RELEASE = "{RELEASE_VERSION}"' in (ROOT / "dashboard/assets/runtime.js").read_text()
    print(json.dumps({"status": "passed", "metrics": metrics, "baseline": baseline}, indent=2))


if __name__ == "__main__":
    main()
