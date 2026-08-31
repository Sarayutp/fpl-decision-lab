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
            results.append(check("Schema", snapshot.get("schema_version") == 2, str(snapshot.get("schema_version"))))
            squad = snapshot.get("analysis", {}).get("recommendations", {}).get("initial_squad", {})
            results.append(check("Optimizer", squad.get("validation", {}).get("valid") is True, squad.get("status", "missing")))
            model = snapshot.get("analysis", {}).get("model", {})
            model_quality = model.get("quality", {})
            results.append(
                check(
                    "xP v2",
                    str(model.get("version", "")).startswith("xp-v2")
                    and bool(model.get("score_definitions")),
                    str(model.get("version", "missing")),
                )
            )
            results.append(
                check(
                    "Model guardrails",
                    model_quality.get("guardrails_passed") is True,
                    f"{model_quality.get('status', 'missing')} / max {model_quality.get('distribution', {}).get('max', '-')}",
                )
            )
            decision = snapshot.get("gameweek_decision", {})
            manager_team_id = snapshot.get("manager", {}).get("team_id")
            decision_ready = (
                str(decision.get("version", "")).startswith("gameweek-decision-5")
                and decision.get("team_id") == manager_team_id
                and decision.get("status") in {"ready", "review_required"}
            )
            results.append(
                check(
                    "Gameweek decision",
                    decision_ready,
                    f"{decision.get('version', 'missing')} / {decision.get('status', 'missing')}",
                )
            )
            transfer_advisor = (
                snapshot.get("analysis", {})
                .get("recommendations", {})
                .get("transfer_advisor", {})
            )
            advisor_valid = (
                str(transfer_advisor.get("version", "")).startswith(
                    "transfer-advisor-1"
                )
                and transfer_advisor.get("mode") == "regular_transfers"
                and transfer_advisor.get("wildcard_separate") is True
                and transfer_advisor.get("rules", {}).get("hit_cost_per_transfer")
                == 4
                and transfer_advisor.get("rules", {}).get("max_free_transfers")
                == 5
            )
            results.append(
                check(
                    "Transfer Advisor",
                    advisor_valid,
                    f"{transfer_advisor.get('version', 'missing')} / "
                    f"{transfer_advisor.get('candidate_count', 0)} candidates / "
                    f"{transfer_advisor.get('price_certainty', 'missing')}",
                )
            )
            risk_layer = snapshot.get("analysis", {}).get("risk_layer", {})
            risk_rules = risk_layer.get("rules", {})
            risk_valid = (
                str(risk_layer.get("version", "")).startswith("risk-layer-1")
                and risk_layer.get("status") in {"ready", "degraded"}
                and risk_rules.get("every_item_requires_source_and_timestamp")
                is True
                and risk_rules.get("predicted_lineups_are_inference") is True
                and risk_rules.get("stale_evidence_can_adjust_projection") is False
                and risk_rules.get("manual_override_requires_expiry_gameweek")
                is True
            )
            results.append(
                check(
                    "Risk Layer",
                    risk_valid,
                    f"{risk_layer.get('version', 'missing')} / "
                    f"{risk_layer.get('status', 'missing')} / "
                    f"{risk_layer.get('adjusted_player_count', 0)} adjusted",
                )
            )
            chip_planner = (
                snapshot.get("analysis", {})
                .get("recommendations", {})
                .get("chip_planner", {})
            )
            chip_rules = chip_planner.get("rules", {})
            chip_valid = (
                str(chip_planner.get("version", "")).startswith("chip-planner-1")
                and chip_planner.get("status") == "ready"
                and 3 <= int(chip_planner.get("horizon", {}).get("count", 0)) <= 6
                and chip_rules.get("sets_per_season") == 2
                and chip_rules.get("one_chip_per_gameweek") is True
                and chip_planner.get("safety", {}).get("one_chip_recommendation")
                is True
            )
            results.append(
                check(
                    "Chip Planner",
                    chip_valid,
                    f"{chip_planner.get('version', 'missing')} / "
                    f"{chip_planner.get('status', 'missing')} / "
                    f"{chip_planner.get('horizon', {}).get('count', 0)} GW",
                )
            )
            if decision_ready:
                lineup = decision.get("starting_xi", {})
                bench = decision.get("bench", {})
                legal_selection = (
                    len(lineup.get("players", [])) == 11
                    and len(lineup.get("squad", [])) == 15
                    and len(bench.get("players", [])) == 4
                    and lineup.get("formation")
                    and decision.get("captaincy", {}).get("captain")
                    and decision.get("captaincy", {}).get("vice_captain")
                )
                results.append(
                    check(
                        "Owned-squad plan",
                        bool(legal_selection),
                        f"XI {len(lineup.get('players', []))} / squad {len(lineup.get('squad', []))} / bench {len(bench.get('players', []))}",
                    )
                )
        except (OSError, ValueError) as error:
            results.append(check("Snapshot JSON", False, str(error)))
    backtest_path = ROOT / "data/model-backtest.json"
    if backtest_path.is_file():
        try:
            backtest = json.loads(backtest_path.read_text(encoding="utf-8"))
            results.append(
                check(
                    "Backtest leakage",
                    backtest.get("leakage_violations") == 0,
                    f"{backtest.get('status', 'missing')} / {backtest.get('sample_count', 0)} samples",
                )
            )
        except (OSError, ValueError) as error:
            results.append(check("Backtest JSON", False, str(error)))
    else:
        results.append(check("Backtest", False, "data/model-backtest.json"))
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
