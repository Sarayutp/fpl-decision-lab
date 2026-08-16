from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .models import BootstrapStatic, Fixture, Player


MODEL_VERSION = "xp-lite-1.0"
DEFAULT_HORIZON = 5


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def availability(player: Player) -> tuple[float, str]:
    """Return an explainable availability multiplier and risk label."""

    if not player.can_select or player.status in {"u", "n"}:
        return 0.0, "unavailable"

    chance = player.chance_of_playing_next_round
    if chance is not None:
        multiplier = max(0.0, min(1.0, chance / 100))
    else:
        multiplier = {
            "a": 1.0,
            "d": 0.75,
            "i": 0.10,
            "s": 0.05,
        }.get(player.status, 0.60)

    if multiplier >= 0.9:
        risk = "low"
    elif multiplier >= 0.5:
        risk = "medium"
    else:
        risk = "high"
    return multiplier, risk


def _difficulty_factor(position_id: int, difficulty: int | None) -> float:
    difficulty = difficulty or 3
    if position_id in {1, 2}:
        return {1: 1.20, 2: 1.10, 3: 1.00, 4: 0.88, 5: 0.75}.get(
            difficulty, 1.0
        )
    return {1: 1.15, 2: 1.08, 3: 1.00, 4: 0.92, 5: 0.84}.get(
        difficulty, 1.0
    )


def _base_points(player: Player, completed_matches: int) -> dict[str, float]:
    raw_appearances_rate = _number(player.points_per_game)
    season_denominator = completed_matches if completed_matches > 0 else 38
    season_rate = player.total_points / max(1, season_denominator)
    official_next = _number(player.ep_next)
    appearance_equivalents = max(float(player.starts), player.minutes / 90)
    reliability = min(1.0, appearance_equivalents / 12)
    appearances_rate = (
        reliability * raw_appearances_rate + (1 - reliability) * season_rate
    )

    if official_next > 0:
        base = 0.45 * appearances_rate + 0.35 * season_rate + 0.20 * official_next
    else:
        base = 0.55 * appearances_rate + 0.45 * season_rate

    return {
        "base": max(0.0, base),
        "points_per_game": appearances_rate,
        "raw_points_per_game": raw_appearances_rate,
        "season_rate": season_rate,
        "official_ep_next": official_next,
        "reliability": reliability,
    }


def upcoming_gameweeks(
    bootstrap: BootstrapStatic,
    now: datetime,
    horizon: int = DEFAULT_HORIZON,
) -> list[int]:
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return [
        event.id
        for event in sorted(bootstrap.events, key=lambda item: item.deadline_time)
        if event.deadline_time > now
    ][:horizon]


def project_players(
    bootstrap: BootstrapStatic,
    fixtures: list[Fixture],
    *,
    now: datetime | None = None,
    horizon: int = DEFAULT_HORIZON,
) -> list[dict[str, Any]]:
    """Create transparent FPL projections using only public, free data.

    The model deliberately stays simple: historical scoring, FPL's public next-GW
    estimate, fixture difficulty, home advantage, doubles/blanks, and availability.
    It is a decision aid rather than a claim of statistical certainty.
    """

    generated_at = now or datetime.now(UTC)
    gameweeks = upcoming_gameweeks(bootstrap, generated_at, horizon)
    team_names = {team.id: team.short_name for team in bootstrap.teams}

    fixtures_by_team_event: dict[tuple[int, int], list[dict[str, Any]]] = {}
    completed_by_team: dict[int, int] = {team.id: 0 for team in bootstrap.teams}
    for fixture in fixtures:
        if fixture.finished:
            completed_by_team[fixture.team_h] = completed_by_team.get(fixture.team_h, 0) + 1
            completed_by_team[fixture.team_a] = completed_by_team.get(fixture.team_a, 0) + 1
        if fixture.event is None:
            continue
        fixtures_by_team_event.setdefault((fixture.team_h, fixture.event), []).append(
            {
                "opponent_id": fixture.team_a,
                "venue": "H",
                "difficulty": fixture.team_h_difficulty,
            }
        )
        fixtures_by_team_event.setdefault((fixture.team_a, fixture.event), []).append(
            {
                "opponent_id": fixture.team_h,
                "venue": "A",
                "difficulty": fixture.team_a_difficulty,
            }
        )

    projections: list[dict[str, Any]] = []
    for player in bootstrap.elements:
        base_inputs = _base_points(player, completed_by_team.get(player.team, 0))
        availability_factor, risk = availability(player)
        gameweek_rows: list[dict[str, Any]] = []

        for index, gameweek in enumerate(gameweeks):
            player_fixtures = fixtures_by_team_event.get((player.team, gameweek), [])
            fixture_points = 0.0
            opponent_labels: list[str] = []

            for fixture in player_fixtures:
                difficulty_factor = _difficulty_factor(
                    player.element_type, fixture["difficulty"]
                )
                home_factor = 1.03 if fixture["venue"] == "H" else 0.98
                adjusted = base_inputs["base"] * difficulty_factor * home_factor
                if index == 0 and base_inputs["official_ep_next"] > 0:
                    adjusted = (
                        0.65 * adjusted + 0.35 * base_inputs["official_ep_next"]
                    )
                fixture_points += adjusted * availability_factor
                opponent_labels.append(
                    f"{team_names.get(fixture['opponent_id'], fixture['opponent_id'])} "
                    f"({fixture['venue']})"
                )

            gameweek_rows.append(
                {
                    "gameweek": gameweek,
                    "xp": round(fixture_points, 2),
                    "fixture_count": len(player_fixtures),
                    "opponents": opponent_labels,
                }
            )

        xp_next = gameweek_rows[0]["xp"] if gameweek_rows else 0.0
        xp_horizon = round(sum(row["xp"] for row in gameweek_rows), 2)
        price = player.now_cost / 10
        projections.append(
            {
                "player_id": player.id,
                "xp_next": xp_next,
                "xp_horizon": xp_horizon,
                "value_score": round(xp_horizon / price, 2) if price else 0.0,
                "availability": round(availability_factor, 2),
                "risk": risk,
                "gameweeks": gameweek_rows,
                "model_inputs": {
                    "historical_points_per_game": round(
                        base_inputs["points_per_game"], 2
                    ),
                    "raw_points_per_game": round(
                        base_inputs["raw_points_per_game"], 2
                    ),
                    "historical_points_per_fixture": round(
                        base_inputs["season_rate"], 2
                    ),
                    "fpl_ep_next": round(base_inputs["official_ep_next"], 2),
                    "sample_reliability": round(base_inputs["reliability"], 2),
                },
            }
        )

    return projections


def model_metadata(horizon: int, gameweeks: list[int]) -> dict[str, Any]:
    return {
        "name": "Explainable xP Lite",
        "version": MODEL_VERSION,
        "horizon": horizon,
        "gameweeks": gameweeks,
        "inputs": [
            "FPL points per game",
            "points per team fixture",
            "FPL public ep_next",
            "fixture difficulty and venue",
            "double/blank gameweeks",
            "availability status",
        ],
        "limitations": [
            "Does not include predicted lineups or live press-conference news.",
            "Current price is used when estimating transfer affordability.",
            "Expected points express ranking preference, not guaranteed returns.",
        ],
    }
