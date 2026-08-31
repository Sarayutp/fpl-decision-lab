from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from .models import Player


OPTIMIZER_VERSION = "milp-1.0"
POSITION_LIMITS = {1: 2, 2: 5, 3: 5, 4: 3}
POSITION_NAMES = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
VALID_FORMATIONS = (
    (3, 4, 3),
    (3, 5, 2),
    (4, 3, 3),
    (4, 4, 2),
    (4, 5, 1),
    (5, 2, 3),
    (5, 3, 2),
    (5, 4, 1),
)


def validate_squad(
    player_ids: Iterable[int],
    players: Iterable[Player],
    *,
    budget_tenths: int = 1_000,
) -> dict[str, Any]:
    by_id = {player.id: player for player in players}
    ids = list(player_ids)
    selected = [by_id[player_id] for player_id in ids if player_id in by_id]
    position_counts = Counter(player.element_type for player in selected)
    team_counts = Counter(player.team for player in selected)
    total_cost = sum(player.now_cost for player in selected)
    violations: list[str] = []

    if len(ids) != len(set(ids)):
        violations.append("Squad contains duplicate players.")
    if len(selected) != len(ids):
        violations.append("Squad contains an unknown player ID.")
    if len(ids) != 15:
        violations.append(f"Squad must contain 15 players (currently {len(ids)}).")
    for position_id, required in POSITION_LIMITS.items():
        actual = position_counts.get(position_id, 0)
        if actual != required:
            violations.append(
                f"{POSITION_NAMES[position_id]} requires {required} players (currently {actual})."
            )
    if total_cost > budget_tenths:
        violations.append(
            f"Squad costs {total_cost / 10:.1f}, above the {budget_tenths / 10:.1f} budget."
        )
    if max(team_counts.values(), default=0) > 3:
        violations.append("A squad may contain no more than three players from one club.")

    return {
        "valid": not violations,
        "violations": violations,
        "player_count": len(ids),
        "total_cost": total_cost / 10,
        "remaining_budget": (budget_tenths - total_cost) / 10,
        "position_counts": {
            POSITION_NAMES[position_id]: position_counts.get(position_id, 0)
            for position_id in POSITION_LIMITS
        },
        "max_from_one_team": max(team_counts.values(), default=0),
    }


def _projection_map(projections: Iterable[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(item["player_id"]): item for item in projections}


def _ranking_next(projection: dict[str, Any]) -> float:
    return float(projection.get("ranking_score_next", projection["xp_next"]))


def _ranking_horizon(projection: dict[str, Any]) -> float:
    return float(projection.get("ranking_score_horizon", projection["xp_horizon"]))


def _captain_score(projection: dict[str, Any]) -> float:
    return float(projection.get("captain_score", _ranking_next(projection)))


def _player_payload(
    player: Player,
    projection: dict[str, Any],
    *,
    starter: bool,
    captain: bool,
    vice_captain: bool,
    bench_order: int | None,
) -> dict[str, Any]:
    return {
        "player_id": player.id,
        "name": player.web_name,
        "team_id": player.team,
        "position_id": player.element_type,
        "position": POSITION_NAMES[player.element_type],
        "price": player.now_cost / 10,
        "starter": starter,
        "captain": captain,
        "vice_captain": vice_captain,
        "bench_order": bench_order,
        "xp_next": projection["xp_next"],
        "xp_horizon": projection["xp_horizon"],
        "expected_points_next": projection.get(
            "expected_points_next", projection["xp_next"]
        ),
        "expected_points_horizon": projection.get(
            "expected_points_horizon", projection["xp_horizon"]
        ),
        "ranking_score_next": projection.get(
            "ranking_score_next", projection["xp_next"]
        ),
        "ranking_score_horizon": projection.get(
            "ranking_score_horizon", projection["xp_horizon"]
        ),
        "captain_score": projection.get("captain_score", projection["xp_next"]),
        "expected_minutes": projection.get("expected_minutes"),
        "expected_minutes_range": projection.get("expected_minutes_range"),
        "start_probability": projection.get("start_probability"),
        "projection_confidence": projection.get("projection_confidence"),
        "confidence_score": projection.get("confidence_score"),
        "expected_points_range": projection.get("expected_points_range"),
        "clean_sheet_probability_next": projection.get(
            "clean_sheet_probability_next"
        ),
        "data_quality_flags": projection.get("data_quality_flags", []),
        "risk": projection["risk"],
        "risk_context": projection.get("risk_context"),
    }


def optimize_initial_squad(
    players: list[Player],
    projections: list[dict[str, Any]],
    *,
    budget_tenths: int = 1_000,
    time_limit_seconds: float = 15.0,
    objective_mode: str = "balanced",
) -> dict[str, Any]:
    """Optimize a legal 15-player squad, XI, captain and vice-captain."""

    if objective_mode not in {"balanced", "single_gameweek"}:
        raise ValueError("Unknown squad objective mode")
    projection_by_id = _projection_map(projections)
    candidates = [player for player in players if player.id in projection_by_id]
    count = len(candidates)
    if count == 0:
        raise ValueError("No players are available for optimization")

    squad_offset = 0
    lineup_offset = count
    captain_offset = count * 2
    vice_offset = count * 3
    variable_count = count * 4

    objective = np.zeros(variable_count)
    upper_bounds = np.ones(variable_count)
    for index, player in enumerate(candidates):
        projection = projection_by_id[player.id]
        ranking_next = _ranking_next(projection)
        ranking_horizon = _ranking_horizon(projection)
        captain_score = _captain_score(projection)
        objective[squad_offset + index] = -0.28 * ranking_horizon
        objective[lineup_offset + index] = -0.72 * ranking_next
        objective[captain_offset + index] = -(
            0.85 * captain_score + 0.05 * ranking_horizon
        )
        objective[vice_offset + index] = -0.03 * captain_score
        if objective_mode == "single_gameweek":
            expected = float(projection["xp_next"])
            objective[squad_offset + index] = -0.0001 * expected
            objective[lineup_offset + index] = -expected
            objective[captain_offset + index] = -expected
            objective[vice_offset + index] = -0.0001 * captain_score
        if (
            not player.can_select
            or player.status in {"u", "n"}
            or float(projection["availability"]) < 0.25
        ):
            upper_bounds[index] = 0
            upper_bounds[lineup_offset + index] = 0
            upper_bounds[captain_offset + index] = 0
            upper_bounds[vice_offset + index] = 0
        elif not projection.get("captain_eligible", True):
            upper_bounds[captain_offset + index] = 0
            if float(projection.get("expected_minutes", 90)) < 50:
                upper_bounds[vice_offset + index] = 0

    constraint_rows: list[list[tuple[int, float]]] = []
    lower_bounds: list[float] = []
    constraint_upper_bounds: list[float] = []

    def add_constraint(
        coefficients: list[tuple[int, float]], lower: float, upper: float
    ) -> None:
        constraint_rows.append(coefficients)
        lower_bounds.append(lower)
        constraint_upper_bounds.append(upper)

    add_constraint([(squad_offset + i, 1) for i in range(count)], 15, 15)
    for position_id, required in POSITION_LIMITS.items():
        add_constraint(
            [
                (squad_offset + i, 1)
                for i, player in enumerate(candidates)
                if player.element_type == position_id
            ],
            required,
            required,
        )
    for team_id in sorted({player.team for player in candidates}):
        add_constraint(
            [
                (squad_offset + i, 1)
                for i, player in enumerate(candidates)
                if player.team == team_id
            ],
            0,
            3,
        )
        add_constraint(
            [
                (captain_offset + i, 1)
                for i, player in enumerate(candidates)
                if player.team == team_id
            ]
            + [
                (vice_offset + i, 1)
                for i, player in enumerate(candidates)
                if player.team == team_id
            ],
            0,
            1,
        )
    add_constraint(
        [
            (squad_offset + i, float(player.now_cost))
            for i, player in enumerate(candidates)
        ],
        0,
        budget_tenths,
    )

    add_constraint([(lineup_offset + i, 1) for i in range(count)], 11, 11)
    for index in range(count):
        add_constraint(
            [(lineup_offset + index, 1), (squad_offset + index, -1)],
            -np.inf,
            0,
        )
        add_constraint(
            [(captain_offset + index, 1), (lineup_offset + index, -1)],
            -np.inf,
            0,
        )
        add_constraint(
            [(vice_offset + index, 1), (lineup_offset + index, -1)],
            -np.inf,
            0,
        )
        add_constraint(
            [(captain_offset + index, 1), (vice_offset + index, 1)],
            -np.inf,
            1,
        )

    lineup_position_bounds = {1: (1, 1), 2: (3, 5), 3: (2, 5), 4: (1, 3)}
    for position_id, (minimum, maximum) in lineup_position_bounds.items():
        add_constraint(
            [
                (lineup_offset + i, 1)
                for i, player in enumerate(candidates)
                if player.element_type == position_id
            ],
            minimum,
            maximum,
        )
    add_constraint([(captain_offset + i, 1) for i in range(count)], 1, 1)
    add_constraint([(vice_offset + i, 1) for i in range(count)], 1, 1)

    matrix_data: list[float] = []
    matrix_rows: list[int] = []
    matrix_columns: list[int] = []
    for row_index, coefficients in enumerate(constraint_rows):
        for column_index, value in coefficients:
            matrix_rows.append(row_index)
            matrix_columns.append(column_index)
            matrix_data.append(value)

    matrix = coo_matrix(
        (matrix_data, (matrix_rows, matrix_columns)),
        shape=(len(constraint_rows), variable_count),
    ).tocsr()
    constraints = LinearConstraint(
        matrix,
        np.asarray(lower_bounds),
        np.asarray(constraint_upper_bounds),
    )
    result = milp(
        objective,
        integrality=np.ones(variable_count),
        bounds=Bounds(np.zeros(variable_count), upper_bounds),
        constraints=constraints,
        options={"time_limit": time_limit_seconds, "mip_rel_gap": 0.001},
    )
    if not result.success or result.x is None:
        raise RuntimeError(f"Squad optimizer failed: {result.message}")

    selected_indexes = [i for i in range(count) if result.x[squad_offset + i] > 0.5]
    starter_indexes = {i for i in range(count) if result.x[lineup_offset + i] > 0.5}
    captain_index = next(i for i in range(count) if result.x[captain_offset + i] > 0.5)
    vice_index = next(i for i in range(count) if result.x[vice_offset + i] > 0.5)

    bench_indexes = sorted(
        (i for i in selected_indexes if i not in starter_indexes),
        key=lambda i: (
            candidates[i].element_type == 1,
            -_ranking_next(projection_by_id[candidates[i].id]),
        ),
    )
    bench_order_by_index = {index: order + 1 for order, index in enumerate(bench_indexes)}
    picks = [
        _player_payload(
            candidates[index],
            projection_by_id[candidates[index].id],
            starter=index in starter_indexes,
            captain=index == captain_index,
            vice_captain=index == vice_index,
            bench_order=bench_order_by_index.get(index),
        )
        for index in selected_indexes
    ]
    picks.sort(
        key=lambda item: (
            not item["starter"],
            item["position_id"],
            item["bench_order"] or 0,
            -item["xp_next"],
        )
    )
    starters = [item for item in picks if item["starter"]]
    validation = validate_squad(
        [item["player_id"] for item in picks], candidates, budget_tenths=budget_tenths
    )

    return {
        "optimizer_version": OPTIMIZER_VERSION,
        "objective_mode": objective_mode,
        "solver": "SciPy HiGHS MILP",
        "status": "optimal" if result.status == 0 else "feasible",
        "budget": budget_tenths / 10,
        "cost": validation["total_cost"],
        "money_left": validation["remaining_budget"],
        "formation": "-".join(
            str(sum(item["position_id"] == position_id for item in starters))
            for position_id in (2, 3, 4)
        ),
        "xp_starting_xi": round(sum(item["xp_next"] for item in starters), 2),
        "xp_with_captain": round(
            sum(item["xp_next"] for item in starters)
            + projection_by_id[candidates[captain_index].id]["xp_next"],
            2,
        ),
        "xp_squad_horizon": round(sum(item["xp_horizon"] for item in picks), 2),
        "ranking_score_starting_xi": round(
            sum(float(item["ranking_score_next"]) for item in starters), 2
        ),
        "ranking_score_squad_horizon": round(
            sum(float(item["ranking_score_horizon"]) for item in picks), 2
        ),
        "captain_id": candidates[captain_index].id,
        "vice_captain_id": candidates[vice_index].id,
        "picks": picks,
        "validation": validation,
    }


def select_best_lineup(
    player_ids: Iterable[int],
    players: list[Player],
    projections: list[dict[str, Any]],
) -> dict[str, Any]:
    ids = list(player_ids)
    validation = validate_squad(ids, players, budget_tenths=100_000)
    fatal_violations = [
        violation
        for violation in validation["violations"]
        if "above the" not in violation
    ]
    if fatal_violations:
        return {"valid": False, "violations": fatal_violations, "picks": []}

    player_by_id = {player.id: player for player in players}
    projection_by_id = _projection_map(projections)
    selected = [player_by_id[player_id] for player_id in ids]
    best_starters: list[Player] | None = None
    best_score = -1.0

    for defenders, midfielders, forwards in VALID_FORMATIONS:
        requirements = {1: 1, 2: defenders, 3: midfielders, 4: forwards}
        starters: list[Player] = []
        feasible = True
        for position_id, required in requirements.items():
            pool = sorted(
                (player for player in selected if player.element_type == position_id),
                key=lambda player: _ranking_next(projection_by_id[player.id]),
                reverse=True,
            )
            if len(pool) < required:
                feasible = False
                break
            starters.extend(pool[:required])
        score = sum(_ranking_next(projection_by_id[player.id]) for player in starters)
        if feasible and score > best_score:
            best_score = score
            best_starters = starters

    if best_starters is None:
        return {"valid": False, "violations": ["No legal starting formation."], "picks": []}

    captain_pool = [
        player
        for player in best_starters
        if projection_by_id[player.id].get("captain_eligible", True)
    ]
    if len(captain_pool) < 2:
        captain_pool = best_starters
    captain_order = sorted(
        captain_pool,
        key=lambda player: _captain_score(projection_by_id[player.id]),
        reverse=True,
    )
    captain_id = captain_order[0].id
    vice_id = captain_order[1].id
    starter_ids = {player.id for player in best_starters}
    bench = sorted(
        (player for player in selected if player.id not in starter_ids),
        key=lambda player: (
            player.element_type == 1,
            -_ranking_next(projection_by_id[player.id]),
        ),
    )
    bench_order = {player.id: index + 1 for index, player in enumerate(bench)}
    picks = [
        _player_payload(
            player,
            projection_by_id[player.id],
            starter=player.id in starter_ids,
            captain=player.id == captain_id,
            vice_captain=player.id == vice_id,
            bench_order=bench_order.get(player.id),
        )
        for player in selected
    ]
    starters_payload = [item for item in picks if item["starter"]]
    return {
        "valid": True,
        "formation": "-".join(
            str(sum(item["position_id"] == position_id for item in starters_payload))
            for position_id in (2, 3, 4)
        ),
        "captain_id": captain_id,
        "vice_captain_id": vice_id,
        "ranking_score_starting_xi": round(best_score, 2),
        "xp_with_captain": round(
            sum(float(item["xp_next"]) for item in starters_payload)
            + float(projection_by_id[captain_id]["xp_next"]),
            2,
        ),
        "picks": picks,
    }


def recommend_transfers(
    player_ids: Iterable[int],
    players: list[Player],
    projections: list[dict[str, Any]],
    *,
    bank_tenths: int = 0,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Rank affordable one-player swaps using current prices as an approximation."""

    selected_ids = set(player_ids)
    player_by_id = {player.id: player for player in players}
    selected = [player_by_id[player_id] for player_id in selected_ids if player_id in player_by_id]
    projection_by_id = _projection_map(projections)
    team_counts = Counter(player.team for player in selected)
    suggestions: list[dict[str, Any]] = []

    for outgoing in selected:
        outgoing_projection = projection_by_id.get(outgoing.id)
        if outgoing_projection is None:
            continue
        for incoming in players:
            incoming_projection = projection_by_id.get(incoming.id)
            if (
                incoming.id in selected_ids
                or incoming.element_type != outgoing.element_type
                or incoming_projection is None
                or float(incoming_projection["availability"]) < 0.5
                or incoming.now_cost > outgoing.now_cost + bank_tenths
            ):
                continue
            incoming_team_count = team_counts[incoming.team]
            if incoming.team != outgoing.team and incoming_team_count >= 3:
                continue

            next_gain = float(incoming_projection["xp_next"]) - float(
                outgoing_projection["xp_next"]
            )
            horizon_gain = float(incoming_projection["xp_horizon"]) - float(
                outgoing_projection["xp_horizon"]
            )
            score = next_gain + 0.35 * horizon_gain
            if score <= 0:
                continue
            suggestions.append(
                {
                    "out_player_id": outgoing.id,
                    "out_name": outgoing.web_name,
                    "in_player_id": incoming.id,
                    "in_name": incoming.web_name,
                    "position": POSITION_NAMES[outgoing.element_type],
                    "cost_change": round((incoming.now_cost - outgoing.now_cost) / 10, 1),
                    "xp_next_gain": round(next_gain, 2),
                    "xp_horizon_gain": round(horizon_gain, 2),
                    "score": round(score, 2),
                    "price_note": "Uses current prices; actual selling value may differ.",
                }
            )

    suggestions.sort(key=lambda item: item["score"], reverse=True)
    return suggestions[:limit]
