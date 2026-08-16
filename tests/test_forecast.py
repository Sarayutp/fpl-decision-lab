from __future__ import annotations

from datetime import UTC, datetime

from fpl_mvp.forecast import availability, project_players
from fpl_mvp.models import BootstrapStatic, Fixture, Player


NOW = datetime(2026, 8, 16, tzinfo=UTC)


def make_bootstrap() -> BootstrapStatic:
    return BootstrapStatic.model_validate(
        {
            "events": [
                {"id": gameweek, "name": f"GW{gameweek}", "deadline_time": f"2026-08-{20 + gameweek}T17:30:00Z"}
                for gameweek in range(1, 4)
            ],
            "teams": [
                {"id": 1, "name": "Alpha", "short_name": "ALP"},
                {"id": 2, "name": "Beta", "short_name": "BET"},
                {"id": 3, "name": "Gamma", "short_name": "GAM"},
            ],
            "element_types": [
                {"id": 3, "singular_name": "Midfielder", "singular_name_short": "MID", "squad_select": 5, "squad_min_play": 2, "squad_max_play": 5}
            ],
            "elements": [
                {
                    "id": 10,
                    "first_name": "Model",
                    "second_name": "Player",
                    "web_name": "Model",
                    "team": 1,
                    "element_type": 3,
                    "now_cost": 70,
                    "status": "a",
                    "points_per_game": "4.0",
                    "total_points": 152,
                    "minutes": 3420,
                    "starts": 38,
                    "ep_next": "4.0",
                }
            ],
        }
    )


def test_projection_handles_double_and_blank_gameweeks() -> None:
    fixtures = [
        Fixture.model_validate({"id": 1, "event": 1, "team_h": 1, "team_a": 2, "team_h_difficulty": 2, "team_a_difficulty": 4}),
        Fixture.model_validate({"id": 2, "event": 2, "team_h": 1, "team_a": 2, "team_h_difficulty": 3, "team_a_difficulty": 3}),
        Fixture.model_validate({"id": 3, "event": 2, "team_h": 3, "team_a": 1, "team_h_difficulty": 3, "team_a_difficulty": 3}),
    ]

    result = project_players(make_bootstrap(), fixtures, now=NOW, horizon=3)[0]

    assert result["gameweeks"][0]["fixture_count"] == 1
    assert result["gameweeks"][1]["fixture_count"] == 2
    assert result["gameweeks"][1]["xp"] > result["gameweeks"][0]["xp"]
    assert result["gameweeks"][2]["xp"] == 0
    assert result["xp_horizon"] == round(sum(row["xp"] for row in result["gameweeks"]), 2)


def test_availability_uses_public_chance() -> None:
    player = Player.model_validate(
        {
            "id": 1,
            "first_name": "Risky",
            "second_name": "Player",
            "web_name": "Risky",
            "team": 1,
            "element_type": 3,
            "now_cost": 50,
            "status": "d",
            "chance_of_playing_next_round": 25,
        }
    )

    assert availability(player) == (0.25, "high")
