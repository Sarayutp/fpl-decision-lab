from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


REQUIRED_DASHBOARD_FILES = (
    "index.html",
    "assets/app.js",
    "assets/styles.css",
    "manifest.webmanifest",
    "sw.js",
)


def validate_dashboard_source(dashboard_dir: Path) -> None:
    missing = [
        relative_path
        for relative_path in REQUIRED_DASHBOARD_FILES
        if not (dashboard_dir / relative_path).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "Dashboard source is incomplete: " + ", ".join(sorted(missing))
        )


def build_site(
    *,
    dashboard_dir: Path,
    data_path: Path,
    briefing_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Assemble a static, GitHub Pages-ready site using an atomic directory swap."""

    validate_dashboard_source(dashboard_dir)
    if not data_path.is_file():
        raise FileNotFoundError(f"Snapshot not found: {data_path}")
    if not briefing_path.is_file():
        raise FileNotFoundError(f"AI briefing not found: {briefing_path}")

    resolved_output = output_dir.resolve()
    if resolved_output == Path(resolved_output.anchor) or resolved_output == Path.home():
        raise ValueError(f"Unsafe site output directory: {resolved_output}")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.build-", dir=output_dir.parent)
    )
    backup_dir = output_dir.parent / f".{output_dir.name}.previous"
    try:
        shutil.copytree(dashboard_dir, temporary_dir, dirs_exist_ok=True)
        data_output_dir = temporary_dir / "data"
        data_output_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(data_path, data_output_dir / "latest.json")
        shutil.copy2(briefing_path, data_output_dir / "briefing.md")
        (temporary_dir / ".nojekyll").touch()

        snapshot = json.loads(data_path.read_text(encoding="utf-8"))
        build_info = {
            "schema_version": snapshot["schema_version"],
            "data_generated_at": snapshot["generated_at"],
            "player_count": snapshot["game"]["player_count"],
        }
        (temporary_dir / "build-info.json").write_text(
            json.dumps(build_info, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        if output_dir.exists():
            os.replace(output_dir, backup_dir)
        os.replace(temporary_dir, output_dir)
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        return build_info
    except Exception:
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir)
        if backup_dir.exists() and not output_dir.exists():
            os.replace(backup_dir, output_dir)
        raise
