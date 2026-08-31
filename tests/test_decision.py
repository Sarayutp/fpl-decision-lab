from __future__ import annotations

from fpl_mvp.decision import build_gameweek_decision


def pick(
    player_id: int,
    position_id: int,
    *,
    starter: bool,
    captain: bool = False,
    vice: bool = False,
    bench_order: int | None = None,
    xp: float = 4.0,
) -> dict:
    return {
        "player_id": player_id,
        "name": f"P{player_id}",
        "team_id": (player_id % 5) + 1,
        "position_id": position_id,
        "position": {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}[position_id],
        "price": 5.0,
        "starter": starter,
        "captain": captain,
        "vice_captain": vice,
        "bench_order": bench_order,
        "xp_next": xp,
        "xp_horizon": xp * 5,
        "risk": "low",
    }


def current_squad() -> dict:
    picks = [
        pick(1, 1, starter=True, xp=4.0),
        pick(2, 2, starter=True, xp=4.5),
        pick(3, 2, starter=True, xp=4.4),
        pick(4, 2, starter=True, xp=4.3),
        pick(5, 3, starter=True, captain=True, xp=8.0),
        pick(6, 3, starter=True, vice=True, xp=7.0),
        pick(7, 3, starter=True, xp=5.0),
        pick(8, 3, starter=True, xp=4.8),
        pick(9, 4, starter=True, xp=6.0),
        pick(10, 4, starter=True, xp=5.8),
        pick(11, 4, starter=True, xp=5.5),
        pick(12, 2, starter=False, bench_order=1, xp=3.0),
        pick(13, 3, starter=False, bench_order=2, xp=2.5),
        pick(14, 2, starter=False, bench_order=3, xp=2.0),
        pick(15, 1, starter=False, bench_order=4, xp=1.5),
    ]
    return {
        "valid": True,
        "formation": "3-4-3",
        "captain_id": 5,
        "vice_captain_id": 6,
        "xp_with_captain": 67.3,
        "picks": picks,
    }


def projections() -> list[dict]:
    return [
        {
            "player_id": player["player_id"],
            "availability": 1.0,
            "risk": player["risk"],
            "gameweeks": [
                {"gameweek": 2, "opponents": [f"OPP{player['player_id']} (H)"]}
            ],
        }
        for player in current_squad()["picks"]
    ]


def build(**overrides: object) -> dict:
    values = {
        "team_id": 5_105_794,
        "target_gameweek": {
            "id": 2,
            "name": "Gameweek 2",
            "deadline_time": "2026-08-28T17:30:00+00:00",
        },
        "generated_at": "2026-08-28T12:00:00+00:00",
        "identity_verified": True,
        "data_quality": {"status": "fresh", "is_stale": False},
        "published_gameweek": 1,
        "team_source_status": "published",
        "current_squad": current_squad(),
        "transfer_suggestions": [
            {
                "out_player_id": 12,
                "out_name": "P12",
                "in_player_id": 99,
                "in_name": "Upgrade",
                "position": "DEF",
                "cost_change": 0.0,
                "xp_next_gain": 2.5,
                "xp_horizon_gain": 8.0,
            }
        ],
        "projections": projections(),
    }
    values.update(overrides)
    return build_gameweek_decision(**values)  # type: ignore[arg-type]


def test_decision_uses_only_the_owned_squad_for_all_five_actions() -> None:
    decision = build()

    assert decision["status"] == "ready"
    assert decision["team_id"] == 5_105_794
    assert decision["transfer"]["action"] == "consider"
    assert decision["transfer"]["hit_recommended"] is False
    assert decision["starting_xi"]["formation"] == "3-4-3"
    assert len(decision["starting_xi"]["players"]) == 11
    assert len(decision["starting_xi"]["squad"]) == 15
    assert decision["captaincy"]["captain"]["player_id"] == 5
    assert decision["captaincy"]["vice_captain"]["player_id"] == 6
    assert len(decision["bench"]["players"]) == 4
    assert len(decision["bench"]["outfield_order"]) == 3
    assert decision["bench"]["goalkeeper"]["position"] == "GKP"
    assert decision["chip"]["action"] == "save"
    assert len(decision["alternatives"]) == 2


def test_decision_is_unavailable_without_a_published_owned_squad() -> None:
    decision = build(current_squad=None, published_gameweek=None)

    assert decision["status"] == "unavailable"
    assert decision["starting_xi"]["headline"] == "ยังแนะนำไม่ได้"
    assert decision["captaincy"]["status"] == "unavailable"


def test_stale_data_requires_review_and_reduces_confidence() -> None:
    decision = build(data_quality={"status": "stale", "is_stale": True})

    assert decision["status"] == "review_required"
    assert decision["confidence"] == "low"
    assert decision["starting_xi"]["confidence"] == "low"
    assert "เกิน 24 ชั่วโมง" in decision["warnings"][0]


def test_phase3_transfer_decision_waits_for_private_budget_inputs() -> None:
    advisor = {
        "version": "transfer-advisor-1.0",
        "status": "needs_user_input",
        "candidate_count": 120,
        "inputs": {"bank": 0.4},
    }

    decision = build(transfer_advisor=advisor)

    assert decision["version"] == "gameweek-decision-5.0"
    assert decision["source"]["transfer_advisor_version"] == "transfer-advisor-1.0"
    assert decision["transfer"]["action"] == "configure"
    assert decision["transfer"]["status"] == "needs_user_input"
    assert decision["transfer"]["hit_recommended"] is False
    assert decision["transfer"]["requires_confirmation"] == [
        "free_transfers",
        "selling_prices",
        "latest_news",
    ]


def test_phase4_decision_records_risk_layer_and_requires_review_when_degraded() -> None:
    risk_layer = {
        "version": "risk-layer-1.0",
        "status": "degraded",
        "adjusted_player_count": 1,
        "warnings": ["FPL availability source is older than 24 hours."],
    }

    decision = build(risk_layer=risk_layer)

    assert decision["version"] == "gameweek-decision-5.0"
    assert decision["source"]["risk_layer_version"] == "risk-layer-1.0"
    assert decision["source"]["risk_layer_status"] == "degraded"
    assert decision["status"] == "review_required"
    assert any("older than 24 hours" in warning for warning in decision["warnings"])


def test_phase5_decision_uses_the_multi_gameweek_chip_recommendation() -> None:
    planner = {
        "version": "chip-planner-1.0",
        "status": "ready",
        "recommendation": {
            "action": "use_now",
            "chip": "triple_captain",
            "label": "ใช้ Triple Captain",
            "headline": "ใช้ใน GW2 ตามเงื่อนไขก่อน deadline",
            "confidence": "medium",
            "gain": 8.0,
            "opportunity_cost": 0.2,
            "reasons": [{"kind": "estimate", "text": "ผ่านเกณฑ์"}],
        },
        "chips": {
            "triple_captain": {"best_visible_gameweek": 2}
        },
    }

    decision = build(chip_planner=planner)

    assert decision["source"]["chip_planner_version"] == "chip-planner-1.0"
    assert decision["chip"]["action"] == "use_now"
    assert decision["chip"]["chip"] == "triple_captain"
    assert decision["chip"]["estimated_gain"] == 8.0
    assert decision["chip"]["opportunity_cost"] == 0.2
