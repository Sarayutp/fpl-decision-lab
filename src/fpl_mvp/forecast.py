from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from math import prod, sqrt
from statistics import median
from typing import Any

from .models import BootstrapStatic, Fixture, Player, Team


MODEL_VERSION = "xp-v2.0"
DEFAULT_HORIZON = 5
PERFORMANCE_PRIOR_MINUTES = 900
ROLE_PRIOR_MATCHES = 4


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def availability(player: Player) -> tuple[float, str]:
    """Return an explainable availability multiplier and risk label."""

    if not player.can_select or player.status in {"u", "n"}:
        return 0.0, "unavailable"

    chance = player.chance_of_playing_next_round
    if chance is not None:
        multiplier = _clamp(chance / 100, 0.0, 1.0)
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


def position_price_prior(player: Player) -> dict[str, float]:
    """Return conservative price/position priors for points and role."""

    price = player.now_cost / 10
    if player.element_type == 1:
        points_per_90 = 3.15 + 0.32 * (price - 4.0)
        minutes = 58 + 12 * (price - 4.0)
        xgi_per_90 = 0.01
    elif player.element_type == 2:
        points_per_90 = 2.75 + 0.48 * (price - 4.0)
        minutes = 54 + 12 * (price - 4.0)
        xgi_per_90 = 0.10 + 0.025 * max(0.0, price - 4.0)
    elif player.element_type == 3:
        points_per_90 = 2.65 + 0.42 * (price - 4.5)
        minutes = 55 + 5.5 * (price - 4.5)
        xgi_per_90 = 0.22 + 0.045 * max(0.0, price - 4.5)
    else:
        points_per_90 = 2.85 + 0.40 * (price - 4.5)
        minutes = 45 + 5.0 * (price - 4.5)
        xgi_per_90 = 0.28 + 0.05 * max(0.0, price - 4.5)

    return {
        "points_per_90": round(_clamp(points_per_90, 2.1, 7.2), 4),
        "minutes": round(_clamp(minutes, 24.0, 85.0), 2),
        "xgi_per_90": round(_clamp(xgi_per_90, 0.0, 0.85), 4),
    }


def _expected_role(
    player: Player,
    completed_matches: int,
    availability_factor: float,
) -> dict[str, float]:
    prior = position_price_prior(player)
    role_weight = completed_matches / (completed_matches + ROLE_PRIOR_MATCHES)
    observed_minutes = (
        _clamp(player.minutes / completed_matches, 0.0, 90.0)
        if completed_matches
        else prior["minutes"]
    )
    observed_start_rate = (
        _clamp(player.starts / completed_matches, 0.0, 1.0)
        if completed_matches
        else _clamp((prior["minutes"] - 12) / 72, 0.05, 0.97)
    )
    prior_start_rate = _clamp((prior["minutes"] - 12) / 72, 0.05, 0.97)
    start_probability = (
        prior_start_rate * (1 - role_weight)
        + observed_start_rate * role_weight
    )
    blended_minutes = (
        prior["minutes"] * (1 - role_weight) + observed_minutes * role_weight
    )
    start_based_minutes = start_probability * 78 + (1 - start_probability) * 12
    expected_minutes = 0.65 * blended_minutes + 0.35 * start_based_minutes

    if completed_matches >= 2 and player.minutes == 0:
        expected_minutes *= 0.40
        start_probability *= 0.40
    elif (
        completed_matches >= 2
        and player.starts == 0
        and observed_minutes < 20
    ):
        expected_minutes *= 0.75
        start_probability *= 0.75

    expected_minutes = _clamp(expected_minutes * availability_factor, 0.0, 90.0)
    start_probability = _clamp(start_probability * availability_factor, 0.0, 1.0)
    role_uncertainty = 22 * (1 - role_weight) + 8 * (1 - availability_factor)
    return {
        "expected_minutes": round(expected_minutes, 2),
        "start_probability": round(start_probability, 4),
        "minutes_lower": round(max(0.0, expected_minutes - role_uncertainty), 1),
        "minutes_upper": round(min(90.0, expected_minutes + role_uncertainty), 1),
        "prior_minutes": prior["minutes"],
        "observed_minutes_per_match": round(observed_minutes, 2),
        "role_evidence": round(role_weight, 4),
    }


def _performance_rate(player: Player) -> dict[str, float]:
    prior = position_price_prior(player)
    observed_rate = (
        _clamp(player.total_points / player.minutes * 90, 0.0, 14.0)
        if player.minutes > 0
        else prior["points_per_90"]
    )
    observed_weight = player.minutes / (player.minutes + PERFORMANCE_PRIOR_MINUTES)
    shrunk_rate = (
        prior["points_per_90"] * (1 - observed_weight)
        + observed_rate * observed_weight
    )

    observed_xgi = max(0.0, _number(player.expected_goal_involvements_per_90))
    set_piece_bonus = 0.0
    if player.penalties_order == 1:
        set_piece_bonus += 0.25
    elif player.penalties_order == 2:
        set_piece_bonus += 0.10
    if player.direct_freekicks_order == 1:
        set_piece_bonus += 0.10
    if player.corners_and_indirect_freekicks_order == 1:
        set_piece_bonus += 0.08
    set_piece_bonus = min(0.43, set_piece_bonus)
    underlying_rate = prior["points_per_90"] + set_piece_bonus + _clamp(
        (observed_xgi - prior["xgi_per_90"]) * 2.0,
        -0.8,
        1.1,
    )
    underlying_weight = min(0.20, observed_weight * 0.20)
    rate = shrunk_rate * (1 - underlying_weight) + underlying_rate * underlying_weight
    return {
        "points_per_90": round(_clamp(rate, 0.0, 9.0), 4),
        "prior_points_per_90": prior["points_per_90"],
        "observed_points_per_90": round(observed_rate, 4),
        "observed_weight": round(observed_weight, 4),
        "prior_xgi_per_90": prior["xgi_per_90"],
        "observed_xgi_per_90": round(observed_xgi, 4),
        "underlying_weight": round(underlying_weight, 4),
        "set_piece_bonus_per_90": round(set_piece_bonus, 4),
    }


def neutral_expected_points(
    player: Player,
    completed_matches: int,
) -> dict[str, float]:
    """Return a fixture-neutral estimate for rolling backtests.

    Callers must pass a player object containing only information available before
    the target Gameweek. This function deliberately excludes current `ep_next`,
    fixtures and future status so a backtest cannot time-travel through them.
    """

    role = _expected_role(player, completed_matches, 1.0)
    performance = _performance_rate(player)
    expected_points = performance["points_per_90"] * role["expected_minutes"] / 90
    return {
        "expected_points": round(max(0.0, expected_points), 4),
        "expected_minutes": role["expected_minutes"],
        "start_probability": role["start_probability"],
        "prior_points_per_90": performance["prior_points_per_90"],
        "current_season_weight": performance["observed_weight"],
    }


def _difficulty_factor(position_id: int, difficulty: int | None) -> float:
    difficulty = difficulty or 3
    if position_id in {1, 2}:
        return {1: 1.12, 2: 1.06, 3: 1.00, 4: 0.94, 5: 0.88}.get(
            difficulty, 1.0
        )
    return {1: 1.10, 2: 1.05, 3: 1.00, 4: 0.95, 5: 0.90}.get(
        difficulty, 1.0
    )


def _clean_sheet_probability(
    position_id: int,
    difficulty: int | None,
    venue: str,
    strength_factor: float,
) -> float | None:
    if position_id not in {1, 2}:
        return None
    difficulty = difficulty or 3
    base = {1: 0.46, 2: 0.37, 3: 0.29, 4: 0.21, 5: 0.14}.get(
        difficulty, 0.29
    )
    venue_adjustment = 0.02 if venue == "H" else -0.02
    return round(_clamp((base + venue_adjustment) * strength_factor, 0.08, 0.58), 3)


def _team_strength_factor(
    player: Player,
    team: Team | None,
    opponent: Team | None,
    venue: str,
) -> tuple[float, bool]:
    """Return a small attack/defence adjustment when FPL publishes strengths."""

    if team is None or opponent is None:
        return 1.0, False
    home = venue == "H"
    if player.element_type in {1, 2}:
        own = team.strength_defence_home if home else team.strength_defence_away
        opposing = (
            opponent.strength_attack_away if home else opponent.strength_attack_home
        )
    else:
        own = team.strength_attack_home if home else team.strength_attack_away
        opposing = (
            opponent.strength_defence_away if home else opponent.strength_defence_home
        )
    if not own or not opposing:
        return 1.0, False
    ratio = own / max(1.0, opposing)
    return round(_clamp(1 + (ratio - 1) * 0.12, 0.90, 1.10), 4), True


def _projection_confidence(
    player: Player,
    completed_matches: int,
    availability_factor: float,
    official_available: bool,
) -> tuple[float, str]:
    sample_score = min(1.0, player.minutes / PERFORMANCE_PRIOR_MINUTES)
    role_score = min(1.0, completed_matches / 6) * (
        0.45 + 0.55 * min(1.0, player.minutes / max(1, completed_matches * 60))
    )
    availability_certainty = (
        1.0
        if player.status == "a" and player.chance_of_playing_next_round is None
        else availability_factor
    )
    score = _clamp(
        0.18
        + 0.42 * sample_score
        + 0.18 * role_score
        + 0.12 * availability_certainty
        + 0.10 * float(official_available),
        0.10,
        0.95,
    )
    label = "high" if score >= 0.78 else "medium" if score >= 0.55 else "low"
    return round(score, 4), label


def _uncertainty_interval(
    expected_points: float,
    confidence_score: float,
    fixture_count: int,
) -> dict[str, float]:
    width = (1.35 + 0.33 * expected_points + 2.4 * (1 - confidence_score)) * sqrt(
        max(1, fixture_count)
    )
    return {
        "lower": round(max(0.0, expected_points - width), 2),
        "upper": round(expected_points + width, 2),
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
    """Project points with conservative priors, minutes and uncertainty.

    `expected_points_*` is the forecast in FPL points. `ranking_score_*` adds a
    modest confidence penalty for ordering players. The legacy `xp_*` fields are
    aliases of expected points so downstream consumers remain compatible.
    """

    generated_at = now or datetime.now(UTC)
    gameweeks = upcoming_gameweeks(bootstrap, generated_at, horizon)
    team_by_id = {team.id: team for team in bootstrap.teams}
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
        completed_matches = completed_by_team.get(player.team, 0)
        availability_factor, risk = availability(player)
        role = _expected_role(player, completed_matches, availability_factor)
        performance = _performance_rate(player)
        official_raw = _number(player.ep_next, default=-1.0)
        official_available = official_raw >= 0
        official_next = _clamp(official_raw, 0.0, 12.0) if official_available else 0.0
        confidence_score, confidence = _projection_confidence(
            player,
            completed_matches,
            availability_factor,
            official_available,
        )
        gameweek_rows: list[dict[str, Any]] = []
        any_strength_used = False

        for index, gameweek in enumerate(gameweeks):
            player_fixtures = fixtures_by_team_event.get((player.team, gameweek), [])
            internal_points = 0.0
            expected_minutes_total = 0.0
            opponent_labels: list[str] = []
            fixture_factors: list[float] = []
            clean_sheet_probabilities: list[float] = []

            for fixture_index, fixture in enumerate(player_fixtures):
                difficulty_factor = _difficulty_factor(
                    player.element_type, fixture["difficulty"]
                )
                home_factor = 1.04 if fixture["venue"] == "H" else 0.98
                strength_factor, strength_used = _team_strength_factor(
                    player,
                    team_by_id.get(player.team),
                    team_by_id.get(fixture["opponent_id"]),
                    fixture["venue"],
                )
                any_strength_used = any_strength_used or strength_used
                fatigue_factor = 1.0 if fixture_index == 0 else 0.90
                expected_minutes_fixture = role["expected_minutes"] * fatigue_factor
                fixture_factor = difficulty_factor * home_factor * strength_factor
                clean_sheet_probability = _clean_sheet_probability(
                    player.element_type,
                    fixture["difficulty"],
                    fixture["venue"],
                    strength_factor,
                )
                if clean_sheet_probability is not None:
                    clean_sheet_probabilities.append(clean_sheet_probability)
                internal_points += (
                    performance["points_per_90"]
                    * expected_minutes_fixture
                    / 90
                    * fixture_factor
                )
                expected_minutes_total += expected_minutes_fixture
                fixture_factors.append(fixture_factor)
                opponent_labels.append(
                    f"{team_names.get(fixture['opponent_id'], fixture['opponent_id'])} "
                    f"({fixture['venue']})"
                )

            expected_points = internal_points
            official_weight = 0.0
            if index == 0 and player_fixtures and official_available:
                official_weight = 0.25
                expected_points = (
                    (1 - official_weight) * internal_points
                    + official_weight * official_next
                )
            expected_points = round(max(0.0, expected_points), 2)
            interval = _uncertainty_interval(
                expected_points,
                confidence_score,
                len(player_fixtures),
            )
            ranking_score = expected_points * (0.82 + 0.18 * confidence_score)
            ranking_score += 0.04 * interval["upper"]
            gameweek_rows.append(
                {
                    "gameweek": gameweek,
                    "expected_points": expected_points,
                    "xp": expected_points,
                    "ranking_score": round(ranking_score, 2),
                    "expected_minutes": round(expected_minutes_total, 1),
                    "start_probability": role["start_probability"],
                    "interval": interval,
                    "fixture_count": len(player_fixtures),
                    "opponents": opponent_labels,
                    "model_components": {
                        "internal_points": round(internal_points, 2),
                        "fpl_ep_next": round(official_next, 2),
                        "fpl_blend_weight": official_weight,
                        "average_fixture_factor": round(
                            sum(fixture_factors) / len(fixture_factors), 3
                        )
                        if fixture_factors
                        else 0.0,
                        "clean_sheet_probability": round(
                            1
                            - prod(1 - value for value in clean_sheet_probabilities),
                            3,
                        )
                        if clean_sheet_probabilities
                        else None,
                    },
                }
            )

        expected_points_next = (
            gameweek_rows[0]["expected_points"] if gameweek_rows else 0.0
        )
        expected_points_horizon = round(
            sum(row["expected_points"] for row in gameweek_rows), 2
        )
        ranking_score_next = (
            gameweek_rows[0]["ranking_score"] if gameweek_rows else 0.0
        )
        ranking_score_horizon = round(
            sum(row["ranking_score"] for row in gameweek_rows), 2
        )
        next_interval = (
            gameweek_rows[0]["interval"]
            if gameweek_rows
            else {"lower": 0.0, "upper": 0.0}
        )
        flags: list[str] = []
        if player.minutes < 270:
            flags.append("small_sample")
        if completed_matches < 4:
            flags.append("early_season")
        if player.minutes == 0:
            flags.append("no_minutes")
        if not official_available:
            flags.append("official_estimate_missing")
        if not any_strength_used:
            flags.append("team_strength_unavailable")
        if gameweek_rows and gameweek_rows[0]["fixture_count"] > 1:
            flags.append("double_gameweek")
        if gameweek_rows and gameweek_rows[0]["fixture_count"] == 0:
            flags.append("blank_gameweek")

        attacking_signal = performance["observed_xgi_per_90"]
        attacking_role_bonus = min(0.8, attacking_signal * 0.65)
        position_penalty = 0.55 if player.element_type in {1, 2} else 0.0
        captain_score = (
            expected_points_next * (0.70 + 0.30 * role["start_probability"])
            + attacking_role_bonus
            + 0.06 * next_interval["upper"]
            - position_penalty
        )
        captain_eligible = (
            role["expected_minutes"] >= 60
            and role["start_probability"] >= 0.65
            and availability_factor >= 0.75
            and expected_points_next > 0
        )
        price = player.now_cost / 10
        projections.append(
            {
                "player_id": player.id,
                "expected_points_next": expected_points_next,
                "expected_points_horizon": expected_points_horizon,
                "xp_next": expected_points_next,
                "xp_horizon": expected_points_horizon,
                "ranking_score_next": ranking_score_next,
                "ranking_score_horizon": ranking_score_horizon,
                "captain_score": round(max(0.0, captain_score), 2),
                "captain_eligible": captain_eligible,
                "value_score": round(ranking_score_horizon / price, 2) if price else 0.0,
                "expected_minutes": role["expected_minutes"],
                "expected_minutes_range": {
                    "lower": role["minutes_lower"],
                    "upper": role["minutes_upper"],
                },
                "start_probability": round(role["start_probability"], 2),
                "projection_confidence": confidence,
                "confidence_score": confidence_score,
                "expected_points_range": next_interval,
                "clean_sheet_probability_next": (
                    gameweek_rows[0]["model_components"]["clean_sheet_probability"]
                    if gameweek_rows
                    else None
                ),
                "availability": round(availability_factor, 2),
                "risk": risk,
                "data_quality_flags": flags,
                "gameweeks": gameweek_rows,
                "feature_contributions": {
                    "price_role_prior": round(performance["prior_points_per_90"], 2),
                    "observed_form": round(
                        performance["points_per_90"]
                        - performance["prior_points_per_90"],
                        2,
                    ),
                    "expected_minutes": role["expected_minutes"],
                    "fpl_ep_next": round(official_next, 2),
                    "fixture_and_venue": (
                        gameweek_rows[0]["model_components"]["average_fixture_factor"]
                        if gameweek_rows
                        else 0.0
                    ),
                    "availability": round(availability_factor, 2),
                    "set_piece_role": performance["set_piece_bonus_per_90"],
                },
                "model_inputs": {
                    "completed_team_matches": completed_matches,
                    "prior_points_per_90": round(
                        performance["prior_points_per_90"], 2
                    ),
                    "observed_points_per_90": round(
                        performance["observed_points_per_90"], 2
                    ),
                    "current_season_weight": round(
                        performance["observed_weight"], 2
                    ),
                    "observed_xgi_per_90": round(
                        performance["observed_xgi_per_90"], 2
                    ),
                    "set_piece_bonus_per_90": performance[
                        "set_piece_bonus_per_90"
                    ],
                    "projected_points_per_90": performance["points_per_90"],
                    "expected_minutes": role["expected_minutes"],
                    "observed_minutes_per_match": role[
                        "observed_minutes_per_match"
                    ],
                    "role_evidence": role["role_evidence"],
                    "fpl_ep_next": round(official_next, 2),
                },
            }
        )

    return projections


def projection_quality_report(projections: list[dict[str, Any]]) -> dict[str, Any]:
    values = sorted(float(item["expected_points_next"]) for item in projections)
    low_sample_high = [
        item
        for item in projections
        if "small_sample" in item.get("data_quality_flags", [])
        and float(item["expected_points_next"]) > 10
    ]
    confidence_counts = Counter(
        str(item.get("projection_confidence", "unavailable")) for item in projections
    )
    if not values:
        return {
            "status": "unavailable",
            "player_count": 0,
            "guardrails_passed": False,
        }
    p90_index = min(len(values) - 1, int(len(values) * 0.90))
    p99_index = min(len(values) - 1, int(len(values) * 0.99))
    single_fixture_max = max(
        (
            float(item["expected_points_next"])
            for item in projections
            if item.get("gameweeks")
            and item["gameweeks"][0].get("fixture_count") == 1
        ),
        default=0.0,
    )
    guardrails_passed = single_fixture_max <= 12 and not low_sample_high
    return {
        "status": "passed" if guardrails_passed else "review_required",
        "player_count": len(values),
        "guardrails_passed": guardrails_passed,
        "distribution": {
            "median": round(median(values), 2),
            "p90": round(values[p90_index], 2),
            "p99": round(values[p99_index], 2),
            "max": round(max(values), 2),
            "single_fixture_max": round(single_fixture_max, 2),
        },
        "low_sample_above_10_count": len(low_sample_high),
        "confidence_counts": dict(sorted(confidence_counts.items())),
    }


def model_metadata(
    horizon: int,
    gameweeks: list[int],
    projections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "name": "Explainable xP v2",
        "version": MODEL_VERSION,
        "horizon": horizon,
        "gameweeks": gameweeks,
        "score_definitions": {
            "expected_points": "Forecast FPL points before captain multiplier.",
            "ranking_score": "Expected points with a modest confidence adjustment for ordering.",
        },
        "inputs": [
            "position and price role prior",
            "current-season minutes, starts and points with Bayesian shrinkage",
            "expected goal involvements per 90 when populated",
            "penalty, direct-free-kick and corner order when populated",
            "FPL public ep_next blended once per Gameweek",
            "expected minutes and start probability",
            "fixture difficulty, venue, clean-sheet heuristic and team strength when populated",
            "double/blank Gameweeks and availability status",
        ],
        "quality": projection_quality_report(projections) if projections is not None else None,
        "limitations": [
            "Price/position is used as the universal prior when previous-season history is unavailable.",
            "Team attack/defence strength is ignored when FPL publishes zero or missing values.",
            "Predicted lineups and curated press-conference evidence are handled by the separate risk layer.",
            "Current price is used when estimating transfer affordability.",
            "Intervals are decision ranges, not statistically calibrated probabilities yet.",
        ],
    }
