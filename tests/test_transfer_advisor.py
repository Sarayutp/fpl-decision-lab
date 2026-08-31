from __future__ import annotations

from fpl_mvp.models import Player
from fpl_mvp.transfer_advisor import (
    build_transfer_advisor,
    evaluate_transfer_scenario,
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
            "minutes": 1800,
            "starts": 22,
        }
    )


def data() -> tuple[list[int], list[Player], list[dict]]:
    positions = [1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4]
    players = [
        player(index, position, ((index - 1) % 5) + 1, 50)
        for index, position in enumerate(positions, start=1)
    ]
    players.extend(
        [
            player(16, 2, 6, 55),
            player(17, 3, 6, 60),
            player(18, 4, 6, 55),
            player(19, 1, 2, 50),
        ]
    )
    projections = []
    for item in players:
        base = 2.0 if item.id <= 15 else 5.0
        projections.append(
            {
                "player_id": item.id,
                "availability": 1.0,
                "risk": "low",
                "expected_minutes": 80.0,
                "start_probability": 0.9,
                "projection_confidence": "medium",
                "gameweeks": [
                    {"expected_points": base},
                    {"expected_points": base},
                    {"expected_points": base},
                    {"expected_points": base},
                    {"expected_points": base},
                ],
            }
        )
    return list(range(1, 16)), players, projections


def test_contract_requires_ft_and_selling_prices_before_certification() -> None:
    ids, players, projections = data()

    contract = build_transfer_advisor(
        ids, players, projections, bank_tenths=5
    )

    assert contract["version"] == "transfer-advisor-1.0"
    assert contract["status"] == "needs_user_input"
    assert contract["required_inputs"] == ["free_transfers", "selling_prices"]
    assert contract["inputs"]["bank"] == 0.5
    assert contract["candidate_count"] > 0
    assert contract["wildcard_separate"] is True


def test_exact_selling_price_certifies_an_affordable_one_ft_move() -> None:
    ids, players, projections = data()

    result = evaluate_transfer_scenario(
        transfers=[(3, 16)],
        player_ids=ids,
        players=players,
        projections=projections,
        bank_tenths=5,
        free_transfers=1,
        selling_prices_tenths={3: 50},
    )

    assert result["valid"] is True
    assert result["certified_affordable"] is True
    assert result["price_status"] == "confirmed"
    assert result["bank_after"] == 0.0
    assert result["hit_cost"] == 0
    assert result["gross_gains"] == {"1": 3.0, "3": 9.0, "5": 15.0}
    assert result["free_transfers_next_deadline"] == 1
    assert result["free_transfer_opportunity_cost"] == 1
    assert result["recommendation"] == "Do"


def test_unknown_selling_price_never_certifies_affordability() -> None:
    ids, players, projections = data()

    result = evaluate_transfer_scenario(
        transfers=[(3, 16)],
        player_ids=ids,
        players=players,
        projections=projections,
        bank_tenths=5,
        free_transfers=1,
    )

    assert result["valid"] is True
    assert result["certified_affordable"] is False
    assert result["price_status"] == "unconfirmed"
    assert result["missing_selling_price_player_ids"] == [3]
    assert result["recommendation"] == "Needs input"


def test_extra_transfer_deducts_four_points_from_every_horizon() -> None:
    ids, players, projections = data()

    result = evaluate_transfer_scenario(
        transfers=[(3, 16), (8, 17)],
        player_ids=ids,
        players=players,
        projections=projections,
        bank_tenths=15,
        free_transfers=1,
        selling_prices_tenths={3: 50, 8: 50},
    )

    assert result["valid"] is True
    assert result["hit_cost"] == 4
    assert result["net_gains"]["1"] == 2.0
    assert result["net_gains"]["3"] == 14.0
    assert result["net_gains"]["5"] == 26.0
    assert result["downside_net_gains"]["5"] > 0
    assert result["recommendation"] == "Do"


def test_budget_and_club_quota_are_checked_after_all_moves() -> None:
    ids, players, projections = data()

    over_budget = evaluate_transfer_scenario(
        transfers=[(3, 16)],
        player_ids=ids,
        players=players,
        projections=projections,
        bank_tenths=0,
        free_transfers=1,
        selling_prices_tenths={3: 49},
    )
    club_quota = evaluate_transfer_scenario(
        transfers=[(1, 19)],
        player_ids=ids,
        players=players,
        projections=projections,
        bank_tenths=0,
        free_transfers=1,
        selling_prices_tenths={1: 50},
    )

    assert over_budget["valid"] is False
    assert any("over budget" in item for item in over_budget["violations"])
    assert club_quota["valid"] is False
    assert any("three players" in item for item in club_quota["violations"])


def test_roll_scenario_preserves_budget_and_banks_an_ft() -> None:
    ids, players, projections = data()

    result = evaluate_transfer_scenario(
        transfers=[],
        player_ids=ids,
        players=players,
        projections=projections,
        bank_tenths=3,
        free_transfers=2,
    )

    assert result["valid"] is True
    assert result["certified_affordable"] is True
    assert result["bank_after"] == 0.3
    assert result["free_transfers_next_deadline"] == 3
    assert result["free_transfer_opportunity_cost"] == 0
    assert result["recommendation"] == "Roll"
