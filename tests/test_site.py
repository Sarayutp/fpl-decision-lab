from __future__ import annotations

import json
from pathlib import Path

import pytest

from fpl_mvp.site import REQUIRED_DASHBOARD_FILES, build_site, validate_chip_plan_safety


def dashboard_fixture_content(relative_path: str) -> str:
    if relative_path == "guide.md":
        return "# User guide\n\n## 01. Start\n\nRead-only plans.\n"
    if relative_path == "guide.html":
        return "<h1>{{guide_title}}</h1>{{guide_toc}}{{guide_body}}{{release}}"
    return relative_path


def test_build_site_copies_dashboard_and_data_atomically(tmp_path) -> None:
    dashboard = tmp_path / "dashboard"
    for relative_path in REQUIRED_DASHBOARD_FILES:
        path = dashboard / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dashboard_fixture_content(relative_path), encoding="utf-8")
    data = tmp_path / "latest.json"
    data.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "generated_at": "2026-08-16T12:00:00+00:00",
                "identity": {
                    "verified": True,
                    "snapshot_team_id": 5_105_794,
                    "team_name": "Sarayut FC",
                    "season": "2026-27",
                    "target_gameweek_id": 1,
                },
                "manager": {"team_id": 5_105_794},
                "gameweek_decision": {
                    "version": "gameweek-decision-5.test",
                    "status": "ready",
                    "team_id": 5_105_794,
                    "target_gameweek": {"id": 1, "name": "Gameweek 1"},
                    "source": {
                        "model_version": "xp-v2.test",
                        "transfer_advisor_version": "transfer-advisor-1.test",
                        "risk_layer_version": "risk-layer-1.test",
                        "chip_planner_version": "chip-planner-1.test",
                    },
                },
                "analysis": {
                    "model": {
                        "version": "xp-v2.test",
                        "score_definitions": {"expected_points": "test", "ranking_score": "test"},
                        "quality": {"guardrails_passed": True, "status": "passed"},
                    },
                    "risk_layer": {
                        "version": "risk-layer-1.test",
                        "status": "ready",
                        "rules": {
                            "every_item_requires_source_and_timestamp": True,
                            "predicted_lineups_are_inference": True,
                            "stale_evidence_can_adjust_projection": False,
                            "manual_override_requires_expiry_gameweek": True,
                        },
                    },
                    "recommendations": {
                        "transfer_advisor": {
                            "version": "transfer-advisor-1.test",
                            "mode": "regular_transfers",
                            "wildcard_separate": True,
                            "rules": {"hit_cost_per_transfer": 4},
                        },
                        "chip_planner": {
                            "version": "chip-planner-1.test",
                            "status": "ready",
                            "horizon": {"count": 3},
                            "rules": {
                                "version": "rules.test",
                                "sets_per_season": 2,
                                "one_chip_per_gameweek": True,
                                "first_set_carries_over": False,
                                "free_hit_consecutive_allowed": False,
                            },
                            "safety": {"one_chip_recommendation": True},
                            "recommendation": {"action": "save"},
                        },
                    },
                },
                "data_quality": {"status": "fresh"},
                "game": {
                    "player_count": 587,
                    "next_gameweek": {"id": 1, "name": "Gameweek 1"},
                },
            }
        ),
        encoding="utf-8",
    )
    briefing = tmp_path / "briefing.md"
    briefing.write_text(
        "# Briefing\n\n- สร้างเมื่อ: 2026-08-16T12:00:00+00:00\n- เป้าหมาย: Gameweek 1\n- Team ID: 5105794\n",
        encoding="utf-8",
    )
    output = tmp_path / "dist"

    info = build_site(
        dashboard_dir=dashboard,
        data_path=data,
        briefing_path=briefing,
        output_dir=output,
    )

    assert info["player_count"] == 587
    assert info["team_id"] == 5_105_794
    assert info["team_name"] == "Sarayut FC"
    assert info["decision_status"] == "ready"
    assert info["chip_planner_version"] == "chip-planner-1.test"
    assert info["chip_recommendation"] == "save"
    assert (output / "data/latest.json").is_file()
    assert (output / "data/briefing.md").is_file()
    assert (output / ".nojekyll").is_file()
    assert not (tmp_path / ".dist.previous").exists()


def test_build_site_rejects_a_briefing_for_another_team(tmp_path) -> None:
    dashboard = tmp_path / "dashboard"
    for relative_path in REQUIRED_DASHBOARD_FILES:
        path = dashboard / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dashboard_fixture_content(relative_path), encoding="utf-8")
    data = tmp_path / "latest.json"
    data.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "generated_at": "2026-08-16T12:00:00+00:00",
                "identity": {
                    "verified": True,
                    "snapshot_team_id": 5_105_794,
                    "target_gameweek_id": 1,
                },
                "manager": {"team_id": 5_105_794},
                "gameweek_decision": {
                    "version": "gameweek-decision-5.test",
                    "status": "ready",
                    "team_id": 5_105_794,
                    "target_gameweek": {"id": 1, "name": "Gameweek 1"},
                    "source": {
                        "model_version": "xp-v2.test",
                        "transfer_advisor_version": "transfer-advisor-1.test",
                        "risk_layer_version": "risk-layer-1.test",
                        "chip_planner_version": "chip-planner-1.test",
                    },
                },
                "analysis": {
                    "model": {
                        "version": "xp-v2.test",
                        "score_definitions": {"expected_points": "test", "ranking_score": "test"},
                        "quality": {"guardrails_passed": True, "status": "passed"},
                    },
                    "risk_layer": {
                        "version": "risk-layer-1.test",
                        "status": "ready",
                        "rules": {
                            "every_item_requires_source_and_timestamp": True,
                            "predicted_lineups_are_inference": True,
                            "stale_evidence_can_adjust_projection": False,
                            "manual_override_requires_expiry_gameweek": True,
                        },
                    },
                    "recommendations": {
                        "transfer_advisor": {
                            "version": "transfer-advisor-1.test",
                            "mode": "regular_transfers",
                            "wildcard_separate": True,
                            "rules": {"hit_cost_per_transfer": 4},
                        },
                        "chip_planner": {
                            "version": "chip-planner-1.test",
                            "status": "ready",
                            "horizon": {"count": 3},
                            "rules": {
                                "version": "rules.test",
                                "sets_per_season": 2,
                                "one_chip_per_gameweek": True,
                                "first_set_carries_over": False,
                                "free_hit_consecutive_allowed": False,
                            },
                            "safety": {"one_chip_recommendation": True},
                            "recommendation": {"action": "save"},
                        },
                    },
                },
                "game": {
                    "player_count": 587,
                    "next_gameweek": {"id": 1, "name": "Gameweek 1"},
                },
            }
        ),
        encoding="utf-8",
    )
    briefing = tmp_path / "briefing.md"
    briefing.write_text(
        "# Briefing\n\n- เป้าหมาย: Gameweek 1\n- Team ID: 3647781\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="briefing does not match"):
        build_site(
            dashboard_dir=dashboard,
            data_path=data,
            briefing_path=briefing,
            output_dir=tmp_path / "dist",
        )


def test_build_site_rejects_a_briefing_for_another_gameweek(tmp_path) -> None:
    dashboard = tmp_path / "dashboard"
    for relative_path in REQUIRED_DASHBOARD_FILES:
        path = dashboard / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dashboard_fixture_content(relative_path), encoding="utf-8")
    data = tmp_path / "latest.json"
    data.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "generated_at": "2026-08-16T12:00:00+00:00",
                "identity": {
                    "verified": True,
                    "snapshot_team_id": 5_105_794,
                    "target_gameweek_id": 1,
                },
                "manager": {"team_id": 5_105_794},
                "gameweek_decision": {
                    "version": "gameweek-decision-5.test",
                    "status": "ready",
                    "team_id": 5_105_794,
                    "target_gameweek": {"id": 1, "name": "Gameweek 1"},
                    "source": {
                        "model_version": "xp-v2.test",
                        "transfer_advisor_version": "transfer-advisor-1.test",
                        "risk_layer_version": "risk-layer-1.test",
                        "chip_planner_version": "chip-planner-1.test",
                    },
                },
                "analysis": {
                    "model": {
                        "version": "xp-v2.test",
                        "score_definitions": {"expected_points": "test", "ranking_score": "test"},
                        "quality": {"guardrails_passed": True, "status": "passed"},
                    },
                    "risk_layer": {
                        "version": "risk-layer-1.test",
                        "status": "ready",
                        "rules": {
                            "every_item_requires_source_and_timestamp": True,
                            "predicted_lineups_are_inference": True,
                            "stale_evidence_can_adjust_projection": False,
                            "manual_override_requires_expiry_gameweek": True,
                        },
                    },
                    "recommendations": {
                        "transfer_advisor": {
                            "version": "transfer-advisor-1.test",
                            "mode": "regular_transfers",
                            "wildcard_separate": True,
                            "rules": {"hit_cost_per_transfer": 4},
                        },
                        "chip_planner": {
                            "version": "chip-planner-1.test",
                            "status": "ready",
                            "horizon": {"count": 3},
                            "rules": {
                                "version": "rules.test",
                                "sets_per_season": 2,
                                "one_chip_per_gameweek": True,
                                "first_set_carries_over": False,
                                "free_hit_consecutive_allowed": False,
                            },
                            "safety": {"one_chip_recommendation": True},
                            "recommendation": {"action": "save"},
                        },
                    },
                },
                "game": {
                    "player_count": 587,
                    "next_gameweek": {"id": 1, "name": "Gameweek 1"},
                },
            }
        ),
        encoding="utf-8",
    )
    briefing = tmp_path / "briefing.md"
    briefing.write_text(
        "# Briefing\n\n- เป้าหมาย: Gameweek 2\n- Team ID: 5105794\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="briefing does not match snapshot Gameweek"):
        build_site(
            dashboard_dir=dashboard,
            data_path=data,
            briefing_path=briefing,
            output_dir=tmp_path / "dist",
        )


def test_dashboard_namespaces_local_squad_by_season_and_team() -> None:
    root = Path(__file__).parents[1]
    app_source = (root / "dashboard/assets/app.js").read_text(encoding="utf-8")
    page_source = (root / "dashboard/index.html").read_text(encoding="utf-8")

    assert "`${STORAGE_PREFIX}:${season}:${state.data.manager.team_id}`" in app_source
    assert "Number(legacy.teamId) === state.data.manager.team_id" in app_source
    assert "briefingMatches" in app_source
    assert "gameweekMatches" in app_source
    assert "renderDecisionCenter" in app_source
    assert "`${RISK_STORAGE_PREFIX}:${season}:${state.data.manager.team_id}`" in app_source
    assert "`${PLANNER_STORAGE_PREFIX}:${season}:${state.data.manager.team_id}`" in app_source
    assert "riskEntryStatus" in app_source
    assert "predicted_lineup" in app_source
    assert "stale_after_hours" in app_source
    assert 'id="decision-grid"' in page_source
    assert 'id="risk-desk"' in page_source
    assert 'id="risk-evidence-form"' in page_source
    assert 'id="chip-planner"' in page_source
    assert 'id="team-id-input"' in page_source
    assert 'id="identity-alert"' in page_source


def test_build_gate_checks_actual_chip_and_budget_safety() -> None:
    with pytest.raises(ValueError, match="unavailable chip"):
        validate_chip_plan_safety({"chips": {"bench_boost": {"action": "use_now"}}, "chip_state": {"bench_boost": {"available": False}}})
    with pytest.raises(ValueError, match="more than one"):
        validate_chip_plan_safety({"chips": {"bench_boost": {"action": "use_now"}, "wildcard": {"action": "use_now"}}})
    with pytest.raises(ValueError, match="budget"):
        validate_chip_plan_safety({"transfer_paths": {"main": {"valid": True, "budget_checkpoints": [{"legal": True, "bank": -0.1}]}}})
