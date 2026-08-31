from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any
from .release import RELEASE_VERSION


REQUIRED_DASHBOARD_FILES = (
    "index.html",
    "assets/app.js",
    "assets/runtime.js",
    "assets/decision-log.js",
    "assets/styles.css",
    "manifest.webmanifest",
    "sw.js",
)


def validate_chip_plan_safety(planner: dict[str, Any]) -> None:
    chips = planner.get("chips", {})
    chosen = [name for name, item in chips.items() if item.get("action") == "use_now"]
    if len(chosen) > 1:
        raise ValueError("Chip Planner recommends more than one chip")
    for name in chosen:
        if not planner.get("chip_state", {}).get(name, {}).get("available"):
            raise ValueError("Chip Planner recommends an unavailable chip")
    recommendation = planner.get("recommendation", {})
    if recommendation.get("action") == "use_now" and recommendation.get("chip") not in chosen:
        raise ValueError("Chip Planner recommendation does not match chip evaluations")
    for name in ("main", "alternative"):
        path = planner.get("transfer_paths", {}).get(name)
        if path and (not path.get("valid") or any(not item.get("legal") or float(item.get("bank", -1)) < 0 for item in path.get("budget_checkpoints", []))):
            raise ValueError("Chip Planner transfer path violates its budget or squad rules")


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
        # Keep the reviewable source pretty-printed; ship a smaller wire payload.
        (data_output_dir / "latest.json").write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        identity = snapshot.get("identity", {})
        manager = snapshot.get("manager", {})
        if not identity.get("verified"):
            raise ValueError("Refusing to build a site with an unverified team identity")
        if identity.get("snapshot_team_id") != manager.get("team_id"):
            raise ValueError("Snapshot identity does not match manager Team ID")
        next_gameweek = snapshot.get("game", {}).get("next_gameweek")
        target_gameweek_id = next_gameweek.get("id") if next_gameweek else None
        if identity.get("target_gameweek_id") != target_gameweek_id:
            raise ValueError("Snapshot identity does not match target Gameweek")
        decision = snapshot.get("gameweek_decision", {})
        decision_gameweek = decision.get("target_gameweek")
        decision_gameweek_id = decision_gameweek.get("id") if decision_gameweek else None
        if not decision.get("version"):
            raise ValueError("Snapshot does not include a versioned Gameweek decision")
        if not str(decision.get("version", "")).startswith("gameweek-decision-5"):
            raise ValueError("Snapshot does not include the Phase 5 Gameweek decision")
        if decision.get("team_id") != manager.get("team_id"):
            raise ValueError("Gameweek decision does not match manager Team ID")
        if decision_gameweek_id != target_gameweek_id:
            raise ValueError("Gameweek decision does not match target Gameweek")
        model = snapshot.get("analysis", {}).get("model", {})
        model_quality = model.get("quality", {})
        if not str(model.get("version", "")).startswith("xp-v2"):
            raise ValueError("Snapshot does not include the Phase 2 xP model")
        if not model.get("score_definitions"):
            raise ValueError("xP model does not define expected points and ranking score")
        if model_quality.get("guardrails_passed") is not True:
            raise ValueError("xP model quality guardrails did not pass")
        if decision.get("source", {}).get("model_version") != model.get("version"):
            raise ValueError("Gameweek decision does not match xP model version")
        transfer_advisor = (
            snapshot.get("analysis", {})
            .get("recommendations", {})
            .get("transfer_advisor", {})
        )
        if not str(transfer_advisor.get("version", "")).startswith(
            "transfer-advisor-1"
        ):
            raise ValueError("Snapshot does not include the Phase 3 Transfer Advisor")
        if transfer_advisor.get("mode") != "regular_transfers":
            raise ValueError("Transfer Advisor is not isolated from Wildcard Lab")
        if transfer_advisor.get("wildcard_separate") is not True:
            raise ValueError("Transfer Advisor mixes regular transfers with Wildcard Lab")
        if transfer_advisor.get("rules", {}).get("hit_cost_per_transfer") != 4:
            raise ValueError("Transfer Advisor hit rule is invalid")
        if decision.get("source", {}).get(
            "transfer_advisor_version"
        ) != transfer_advisor.get("version"):
            raise ValueError("Gameweek decision does not match Transfer Advisor version")
        risk_layer = snapshot.get("analysis", {}).get("risk_layer", {})
        if not str(risk_layer.get("version", "")).startswith("risk-layer-1"):
            raise ValueError("Snapshot does not include the Phase 4 Risk Layer")
        risk_rules = risk_layer.get("rules", {})
        if (
            risk_rules.get("every_item_requires_source_and_timestamp") is not True
            or risk_rules.get("predicted_lineups_are_inference") is not True
            or risk_rules.get("stale_evidence_can_adjust_projection") is not False
            or risk_rules.get("manual_override_requires_expiry_gameweek") is not True
        ):
            raise ValueError("Risk Layer source and expiry guardrails are invalid")
        if decision.get("source", {}).get("risk_layer_version") != risk_layer.get(
            "version"
        ):
            raise ValueError("Gameweek decision does not match Risk Layer version")
        chip_planner = (
            snapshot.get("analysis", {})
            .get("recommendations", {})
            .get("chip_planner", {})
        )
        chip_rules = chip_planner.get("rules", {})
        if not str(chip_planner.get("version", "")).startswith("chip-planner-1"):
            raise ValueError("Snapshot does not include the Phase 5 Chip Planner")
        if chip_planner.get("status") != "ready":
            raise ValueError("Chip Planner is not ready")
        if (
            chip_rules.get("sets_per_season") != 2
            or chip_rules.get("one_chip_per_gameweek") is not True
            or chip_rules.get("first_set_carries_over") is not False
            or chip_rules.get("free_hit_consecutive_allowed") is not False
        ):
            raise ValueError("Chip Planner rules are invalid")
        if chip_planner.get("safety", {}).get("one_chip_recommendation") is not True:
            raise ValueError("Chip Planner recommends more than one chip")
        validate_chip_plan_safety(chip_planner)
        if decision.get("source", {}).get("chip_planner_version") != chip_planner.get(
            "version"
        ):
            raise ValueError("Gameweek decision does not match Chip Planner version")
        briefing_content = briefing_path.read_text(encoding="utf-8")
        briefing_match = re.search(
            r"^\s*-\s*Team ID:\s*(\d+)\s*$", briefing_content, flags=re.MULTILINE
        )
        if briefing_match is None or int(briefing_match.group(1)) != manager.get("team_id"):
            raise ValueError("AI briefing does not match snapshot Team ID")
        briefing_gameweek_match = re.search(
            r"^\s*-\s*เป้าหมาย:\s*(.+?)\s*$", briefing_content, flags=re.MULTILINE
        )
        expected_gameweek_name = (
            next_gameweek.get("name") if next_gameweek else "ไม่ทราบ Gameweek"
        )
        if (
            briefing_gameweek_match is None
            or briefing_gameweek_match.group(1) != expected_gameweek_name
        ):
            raise ValueError("AI briefing does not match snapshot Gameweek")
        briefing_time = re.search(r"^- สร้างเมื่อ:\s*(.+)$", briefing_content, re.MULTILINE)
        if briefing_time is None or briefing_time.group(1).strip() != snapshot["generated_at"]:
            raise ValueError("AI briefing does not match snapshot timestamp")
        if snapshot["schema_version"] != 2:
            raise ValueError("Unsupported snapshot schema")
        critical_files = [*REQUIRED_DASHBOARD_FILES, "data/latest.json", "data/briefing.md"]
        # Immutable asset URLs also recover clients controlled by an older cache-first worker.
        for shell in ("index.html", "sw.js"):
            path = temporary_dir / shell
            content = path.read_text(encoding="utf-8")
            for asset in ("assets/app.js", "assets/runtime.js", "assets/decision-log.js", "assets/styles.css"):
                digest = hashlib.sha256((temporary_dir / asset).read_bytes()).hexdigest()[:12]
                content = re.sub(re.escape(asset) + r"\?v=[\w.-]+", f"{asset}?v={digest}", content)
            path.write_text(content, encoding="utf-8")
        fingerprint = hashlib.sha256()
        for relative in sorted(critical_files):
            fingerprint.update(relative.encode())
            fingerprint.update((temporary_dir / relative).read_bytes())
        build_id = fingerprint.hexdigest()[:16]
        worker_path = temporary_dir / "sw.js"
        worker_path.write_text(worker_path.read_text(encoding="utf-8").replace("__BUILD_ID__", build_id), encoding="utf-8")
        build_info = {
            "release_version": RELEASE_VERSION,
            "build_id": build_id,
            "asset_sha256": {relative: hashlib.sha256((temporary_dir / relative).read_bytes()).hexdigest() for relative in critical_files},
            "schema_version": snapshot["schema_version"],
            "data_generated_at": snapshot["generated_at"],
            "player_count": snapshot["game"]["player_count"],
            "team_id": manager["team_id"],
            "team_name": identity.get("team_name"),
            "season": identity.get("season"),
            "data_status": snapshot.get("data_quality", {}).get("status"),
            "decision_version": decision["version"],
            "decision_status": decision.get("status"),
            "model_version": model["version"],
            "model_quality_status": model_quality.get("status"),
            "transfer_advisor_version": transfer_advisor["version"],
            "transfer_advisor_status": transfer_advisor.get("status"),
            "risk_layer_version": risk_layer["version"],
            "risk_layer_status": risk_layer.get("status"),
            "risk_adjusted_player_count": risk_layer.get(
                "adjusted_player_count", 0
            ),
            "chip_planner_version": chip_planner["version"],
            "chip_planner_status": chip_planner.get("status"),
            "chip_rules_version": chip_rules.get("version"),
            "chip_recommendation": chip_planner.get("recommendation", {}).get(
                "action"
            ),
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
