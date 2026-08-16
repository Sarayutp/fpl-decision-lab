from __future__ import annotations

from fpl_mvp.models import Player
from fpl_mvp.optimizer import (
    optimize_initial_squad,
    recommend_transfers,
    select_best_lineup,
    validate_squad,
)


def player(player_id: int, position: int, team: int, cost: int) -> Player:
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
            "minutes": 2000,
            "starts": 24,
        }
    )


def candidate_pool() -> tuple[list[Player], list[dict]]:
    players: list[Player] = []
    player_id = 1
    specs = {1: (6, 45), 2: (16, 45), 3: (16, 50), 4: (10, 55)}
    for position, (count, base_cost) in specs.items():
        for index in range(count):
            players.append(player(player_id, position, (index % 10) + 1, base_cost + (index % 5) * 5))
            player_id += 1
    projections = [
        {
            "player_id": item.id,
            "xp_next": round(2.0 + item.now_cost / 30 + (item.id % 7) / 10, 2),
            "xp_horizon": round(10.0 + item.now_cost / 8 + (item.id % 9) / 5, 2),
            "availability": 1.0,
            "risk": "low",
        }
        for item in players
    ]
    return players, projections


def test_optimizer_returns_a_legal_squad_and_lineup() -> None:
    players, projections = candidate_pool()
    result = optimize_initial_squad(players, projections, time_limit_seconds=5)
    ids = [pick["player_id"] for pick in result["picks"]]

    assert result["validation"]["valid"] is True
    assert validate_squad(ids, players)["valid"] is True
    assert len(result["picks"]) == 15
    assert sum(pick["starter"] for pick in result["picks"]) == 11
    assert sum(pick["captain"] for pick in result["picks"]) == 1
    assert sum(pick["vice_captain"] for pick in result["picks"]) == 1
    captain = next(pick for pick in result["picks"] if pick["captain"])
    vice = next(pick for pick in result["picks"] if pick["vice_captain"])
    assert captain["team_id"] != vice["team_id"]


def test_transfer_suggestions_respect_position_and_budget() -> None:
    players, projections = candidate_pool()
    squad = optimize_initial_squad(players, projections, time_limit_seconds=5)
    ids = [pick["player_id"] for pick in squad["picks"]]
    suggestions = recommend_transfers(ids, players, projections, bank_tenths=10)

    for suggestion in suggestions:
        outgoing = next(item for item in players if item.id == suggestion["out_player_id"])
        incoming = next(item for item in players if item.id == suggestion["in_player_id"])
        assert outgoing.element_type == incoming.element_type
        assert incoming.now_cost <= outgoing.now_cost + 10
        assert suggestion["score"] > 0


def test_lineup_rejects_unknown_player_ids() -> None:
    players, projections = candidate_pool()
    squad = optimize_initial_squad(players, projections, time_limit_seconds=5)
    ids = [pick["player_id"] for pick in squad["picks"]]
    ids[-1] = 999_999

    result = select_best_lineup(ids, players, projections)

    assert result["valid"] is False
    assert any("unknown" in violation for violation in result["violations"])
