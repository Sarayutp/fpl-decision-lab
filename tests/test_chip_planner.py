from __future__ import annotations

from copy import deepcopy

from fpl_mvp.chip_planner import _chip_state, _gameweek_projection, build_chip_planner
from fpl_mvp.models import Player


def player(player_id: int, position: int, team: int, cost: int = 50) -> Player:
    return Player.model_validate(
        {
            "id": player_id,
            "first_name": "Test",
            "second_name": str(player_id),
            "web_name": f"P{player_id}",
            "team": team,
            "element_type": position,
            "now_cost": cost,
            "status": "a",
            "minutes": 360,
            "starts": 4,
        }
    )


def planner_data() -> tuple[list[int], list[Player], list[dict]]:
    positions = [1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4]
    players = [
        player(index, position, ((index - 1) % 8) + 1)
        for index, position in enumerate(positions, start=1)
    ]
    candidates = [(1, 9), (2, 10), (2, 11), (3, 12), (3, 13), (4, 14), (4, 15)]
    players.extend(
        player(index, position, team, 52)
        for index, (position, team) in enumerate(candidates, start=16)
    )
    projections = []
    for item in players:
        base = 3.0 if item.id <= 15 else 5.0
        if item.id == 8:
            base = 8.0
        rows = [
            {
                "gameweek": gameweek,
                "expected_points": base - (0.15 * (gameweek - 3)),
                "ranking_score": base - (0.15 * (gameweek - 3)),
                "expected_minutes": 82.0,
                "fixture_count": 1,
                "opponents": ["TST (H)"],
                "interval": {"lower": max(0.0, base - 2), "upper": base + 3},
                "model_components": {"clean_sheet_probability": 0.3},
            }
            for gameweek in range(3, 8)
        ]
        projections.append(
            {
                "player_id": item.id,
                "availability": 1.0,
                "risk": "low",
                "expected_minutes": 82.0,
                "start_probability": 0.9,
                "projection_confidence": "medium",
                "confidence_score": 0.7,
                "expected_minutes_range": {"lower": 70, "upper": 90},
                "expected_points_range": rows[0]["interval"],
                "data_quality_flags": [],
                "gameweeks": rows,
            }
        )
    return list(range(1, 16)), players, projections


def build(projections: list[dict] | None = None) -> dict:
    ids, players, defaults = planner_data()
    return build_chip_planner(
        current_squad_ids=ids,
        players=players,
        projections=projections or defaults,
        target_gameweek=3,
        chip_history=[{"name": "bboost", "event": 2, "time": "2026-08-28"}],
        bank_tenths=10,
        budget_tenths=750,
        generated_at="2026-08-30T10:00:00+00:00",
    )


def test_used_chip_is_unavailable_and_every_week_has_a_legal_bench() -> None:
    planner = build()

    assert planner["status"] == "ready"
    assert planner["horizon"]["gameweeks"] == [3, 4, 5, 6, 7]
    assert planner["chip_state"]["bench_boost"]["available"] is False
    assert planner["chips"]["bench_boost"]["action"] == "unavailable"
    assert planner["chips"]["bench_boost"]["used_events"] == [2]
    assert all(len(week["picks"]) == 15 for week in planner["weekly"])
    assert all(len(week["bench"]) == 4 for week in planner["weekly"])
    assert planner["safety"]["one_chip_recommendation"] is True


def test_chip_set_refreshes_in_second_half_but_free_hit_cannot_be_consecutive() -> None:
    state = _chip_state(
        target_gameweek=20,
        chip_history=[
            {"name": "bboost", "event": 2},
            {"name": "freehit", "event": 19},
        ],
        active_chip=None,
    )

    assert state["bench_boost"]["available"] is True
    assert state["bench_boost"]["period"] == 2
    assert state["free_hit"]["available"] is False
    assert any("ติดต่อกัน" in item for item in state["free_hit"]["blocked_reasons"])


def test_transfer_paths_keep_every_budget_checkpoint_legal() -> None:
    planner = build()

    for path in planner["transfer_paths"].values():
        if not isinstance(path, dict):
            continue
        assert path["valid"] is True
        assert all(item["legal"] for item in path["budget_checkpoints"])
        assert all(item["bank"] >= 0 for item in path["budget_checkpoints"])
        assert len(path["budget_checkpoints"]) == 5
        assert all(item["free_transfers_before"] >= 1 for item in path["budget_checkpoints"])
        assert all(item["hit_cost"] == 0 for item in path["budget_checkpoints"])
        assert path["certified_affordable"] is False
        assert path["gain_basis"] == "legal_XI_plus_captain_vs_roll"
    main_incoming = planner["transfer_paths"]["main"]["moves"][0]["in_player_id"]
    assert all(move["in_player_id"] != main_incoming for move in planner["transfer_paths"]["alternative"]["moves"])


def test_minutes_and_points_assumption_changes_chip_output_visibly() -> None:
    _, _, projections = planner_data()
    baseline = build(projections)
    changed = deepcopy(projections)
    captain = next(item for item in changed if item["player_id"] == 8)
    captain["start_probability"] = 0.4
    captain["expected_minutes"] = 35
    for row in captain["gameweeks"]:
        row["expected_points"] = 1.0
        row["ranking_score"] = 0.8
        row["expected_minutes"] = 35

    revised = build(changed)

    assert baseline["chips"]["triple_captain"]["current_gain"] != revised["chips"]["triple_captain"]["current_gain"]
    assert baseline["weekly"][0]["captain"]["player_id"] != revised["weekly"][0]["captain"]["player_id"]


def test_future_blank_uses_its_own_fixture_and_start_flags() -> None:
    _, _, projections = planner_data()
    item = projections[0]
    item["gameweeks"][1].update(fixture_count=0, expected_minutes=0, expected_points=0, opponents=[], start_probability=0)
    future = _gameweek_projection(item, 4, [3, 4, 5, 6, 7])
    assert future["fixture_count"] == 0
    assert "blank_gameweek" in future["data_quality_flags"]
    assert future["start_probability"] == 0
    assert future["captain_eligible"] is False


def test_free_hit_and_wildcard_are_independent_squad_scenarios() -> None:
    planner = build()
    fh = planner["chips"]["free_hit"]["scenario"]
    wc = planner["chips"]["wildcard"]["scenario"]
    assert fh["objective_mode"] == "single_gameweek"
    assert wc["objective_mode"] == "balanced"
    assert fh["permanent"] is False and wc["permanent"] is True
    assert fh["restores_squad_ids"] == list(range(1, 16))
    assert len(fh["picks"]) == len(wc["picks"]) == 15
    assert fh["validation"]["valid"] and wc["validation"]["valid"]


def test_low_confidence_blocks_full_squad_chips_despite_positive_gain() -> None:
    _, _, projections = planner_data()
    for item in projections:
        item["projection_confidence"] = "low"
    planner = build(projections)
    for chip in ("free_hit", "wildcard"):
        assert planner["chips"][chip]["action"] != "use_now"
        assert planner["chips"][chip]["confidence_gate_passed"] is False


def test_comparison_does_not_treat_next_half_as_the_same_chip() -> None:
    ids, players, projections = planner_data()
    for item in projections:
        for row in item["gameweeks"]:
            row["gameweek"] += 16
            if row["gameweek"] > 19:
                row["expected_points"] *= 2
    planner = build_chip_planner(current_squad_ids=ids, players=players, projections=projections,
        target_gameweek=19, chip_history=[], bank_tenths=10, generated_at="2026-12-28T10:00:00Z")
    for chip in planner["chips"].values():
        assert chip["best_visible_gameweek"] == 19
        assert all(row["gameweek"] == 19 for row in chip["weekly_gains"])
    assert planner["rules"]["checked_at"] == "2026-08-30"


def test_unverified_season_and_missing_owned_projection_are_blocked() -> None:
    ids, players, projections = planner_data()
    kwargs = dict(current_squad_ids=ids, players=players, target_gameweek=3, chip_history=[], generated_at="2027-08-01T10:00:00Z")
    assert build_chip_planner(**kwargs, projections=projections, season="2027-28")["status"] == "unavailable"
    assert build_chip_planner(**kwargs, projections=projections[1:])["status"] == "unavailable"


def test_opening_week_and_pending_chip_obey_one_chip_rule() -> None:
    state = _chip_state(target_gameweek=1, chip_history=[], active_chip="3xc")
    assert state["triple_captain"]["available"] is True
    assert state["bench_boost"]["available"] is False
    assert state["free_hit"]["available"] is False
    assert state["wildcard"]["available"] is False
