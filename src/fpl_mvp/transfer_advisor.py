from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from .models import Player
from .optimizer import POSITION_NAMES, validate_squad


TRANSFER_ADVISOR_VERSION = "transfer-advisor-1.0"
HORIZONS = (1, 3, 5)
HIT_COST = 4
MAX_FREE_TRANSFERS = 5
MIN_HIT_EXPECTED_MINUTES = 65.0
MIN_HIT_START_PROBABILITY = 0.70


def _projection_map(
    projections: Iterable[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    return {int(item["player_id"]): item for item in projections}


def _expected_points(projection: dict[str, Any], horizon: int) -> float:
    gameweeks = projection.get("gameweeks", [])
    if gameweeks:
        return round(
            sum(
                float(item.get("expected_points", item.get("xp", 0)))
                for item in gameweeks[:horizon]
            ),
            4,
        )
    if horizon == 1:
        return float(
            projection.get("expected_points_next", projection.get("xp_next", 0))
        )
    horizon_total = float(
        projection.get(
            "expected_points_horizon", projection.get("xp_horizon", 0)
        )
    )
    return round(horizon_total * horizon / 5, 4)


def _confidence_rank(value: str | None) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(str(value), 0)


def _scenario_confidence(projections: Iterable[dict[str, Any]]) -> str:
    values = [str(item.get("projection_confidence", "unavailable")) for item in projections]
    if not values or any(value not in {"high", "medium", "low"} for value in values):
        return "unavailable"
    return min(values, key=_confidence_rank)


def _move_payload(
    outgoing: Player,
    incoming: Player,
    outgoing_projection: dict[str, Any],
    incoming_projection: dict[str, Any],
) -> dict[str, Any]:
    gains: dict[str, float] = {}
    downside: dict[str, float] = {}
    for horizon in HORIZONS:
        incoming_points = _expected_points(incoming_projection, horizon)
        outgoing_points = _expected_points(outgoing_projection, horizon)
        gains[str(horizon)] = round(incoming_points - outgoing_points, 2)
        # A transparent sensitivity case: incoming scores 20% below projection
        # while the outgoing player scores 10% above projection.
        downside[str(horizon)] = round(
            incoming_points * 0.80 - outgoing_points * 1.10, 2
        )
    score = gains["3"] + 0.35 * gains["5"] + 0.20 * gains["1"]
    return {
        "out_player_id": outgoing.id,
        "out_name": outgoing.web_name,
        "out_team_id": outgoing.team,
        "out_current_price": outgoing.now_cost / 10,
        "in_player_id": incoming.id,
        "in_name": incoming.web_name,
        "in_team_id": incoming.team,
        "in_price": incoming.now_cost / 10,
        "position_id": outgoing.element_type,
        "position": POSITION_NAMES[outgoing.element_type],
        "gains": gains,
        "downside_gains": downside,
        "score": round(score, 3),
        "incoming_expected_minutes": incoming_projection.get("expected_minutes"),
        "incoming_start_probability": incoming_projection.get("start_probability"),
        "incoming_confidence": incoming_projection.get("projection_confidence"),
        "incoming_risk": incoming_projection.get("risk"),
    }


def build_candidate_moves(
    player_ids: Iterable[int],
    players: list[Player],
    projections: list[dict[str, Any]],
    *,
    per_out_limit: int = 14,
) -> list[dict[str, Any]]:
    """Build a compact price-independent shortlist for the static dashboard."""

    selected_ids = {int(player_id) for player_id in player_ids}
    player_by_id = {player.id: player for player in players}
    projection_by_id = _projection_map(projections)
    selected = [player_by_id[player_id] for player_id in selected_ids if player_id in player_by_id]
    moves: list[dict[str, Any]] = []

    for outgoing in selected:
        outgoing_projection = projection_by_id.get(outgoing.id)
        if outgoing_projection is None:
            continue
        candidates: list[dict[str, Any]] = []
        for incoming in players:
            incoming_projection = projection_by_id.get(incoming.id)
            if (
                incoming.id in selected_ids
                or incoming.element_type != outgoing.element_type
                or incoming_projection is None
                or not incoming.can_select
                or not incoming.can_transact
                or float(incoming_projection.get("availability", 0)) < 0.5
            ):
                continue
            move = _move_payload(
                outgoing, incoming, outgoing_projection, incoming_projection
            )
            if move["gains"]["3"] <= 0 and move["gains"]["5"] <= 0:
                continue
            candidates.append(move)

        by_score = sorted(candidates, key=lambda item: item["score"], reverse=True)
        # Preserve a few cheap enablers because a double/triple move can be better
        # than either component considered alone.
        cheap_enablers = sorted(
            candidates,
            key=lambda item: (item["in_price"], -item["gains"]["5"]),
        )[:4]
        chosen: dict[int, dict[str, Any]] = {
            int(item["in_player_id"]): item
            for item in [*by_score[:per_out_limit], *cheap_enablers]
        }
        moves.extend(chosen.values())

    return sorted(
        moves,
        key=lambda item: (
            -float(item["score"]),
            int(item["out_player_id"]),
            int(item["in_player_id"]),
        ),
    )


def build_transfer_advisor(
    player_ids: Iterable[int],
    players: list[Player],
    projections: list[dict[str, Any]],
    *,
    bank_tenths: int | None,
) -> dict[str, Any]:
    ids = [int(player_id) for player_id in player_ids]
    candidate_moves = build_candidate_moves(ids, players, projections)
    return {
        "version": TRANSFER_ADVISOR_VERSION,
        "status": "needs_user_input",
        "mode": "regular_transfers",
        "required_inputs": ["free_transfers", "selling_prices"],
        "inputs": {
            "free_transfers": None,
            "free_transfers_min": 1,
            "free_transfers_max": MAX_FREE_TRANSFERS,
            "bank": bank_tenths / 10 if bank_tenths is not None else None,
            "bank_source": "FPL last deadline" if bank_tenths is not None else "user",
            "selling_price_player_ids": ids,
            "selling_price_source": "user",
        },
        "rules": {
            "hit_cost_per_transfer": HIT_COST,
            "max_free_transfers": MAX_FREE_TRANSFERS,
            "horizons": list(HORIZONS),
            "hit_min_expected_minutes": MIN_HIT_EXPECTED_MINUTES,
            "hit_min_start_probability": MIN_HIT_START_PROBABILITY,
            "official_rules_url": "https://www.premierleague.com/en/news/2174907",
        },
        "candidate_moves": candidate_moves,
        "candidate_count": len(candidate_moves),
        "price_certainty": "unconfirmed",
        "wildcard_separate": True,
        "limitations": [
            "Public FPL data does not expose exact selling prices for the current squad.",
            "Free Transfers may be affected by pending moves or chips and require user confirmation.",
            "Current prices are used only to shortlist moves, never to certify affordability.",
        ],
    }


def evaluate_transfer_scenario(
    *,
    transfers: list[tuple[int, int]],
    player_ids: Iterable[int],
    players: list[Player],
    projections: list[dict[str, Any]],
    bank_tenths: int,
    free_transfers: int,
    selling_prices_tenths: dict[int, int] | None = None,
) -> dict[str, Any]:
    """Evaluate one explicit scenario with legal, price and hit guardrails."""

    ids = [int(player_id) for player_id in player_ids]
    owned_ids = set(ids)
    player_by_id = {player.id: player for player in players}
    projection_by_id = _projection_map(projections)
    selling_prices = selling_prices_tenths or {}
    violations: list[str] = []
    outgoing_ids = [int(outgoing) for outgoing, _ in transfers]
    incoming_ids = [int(incoming) for _, incoming in transfers]

    if not 1 <= free_transfers <= MAX_FREE_TRANSFERS:
        violations.append("Free Transfers must be between 1 and 5.")
    if len(outgoing_ids) != len(set(outgoing_ids)):
        violations.append("A player cannot be sold more than once.")
    if len(incoming_ids) != len(set(incoming_ids)):
        violations.append("A player cannot be bought more than once.")
    if any(player_id not in owned_ids for player_id in outgoing_ids):
        violations.append("Every outgoing player must be in the current squad.")
    if any(player_id in owned_ids for player_id in incoming_ids):
        violations.append("An incoming player is already in the current squad.")
    if any(player_id not in player_by_id for player_id in [*outgoing_ids, *incoming_ids]):
        violations.append("Scenario contains an unknown player ID.")

    resolved: list[tuple[Player, Player]] = []
    if not violations:
        for outgoing_id, incoming_id in transfers:
            outgoing = player_by_id[outgoing_id]
            incoming = player_by_id[incoming_id]
            if outgoing.element_type != incoming.element_type:
                violations.append("Each swap must keep the same position.")
            if not incoming.can_select or not incoming.can_transact:
                violations.append(f"{incoming.web_name} cannot currently be transferred in.")
            if incoming_id not in projection_by_id or outgoing_id not in projection_by_id:
                violations.append("Scenario is missing a player projection.")
            resolved.append((outgoing, incoming))

    resulting_ids = [player_id for player_id in ids if player_id not in outgoing_ids]
    resulting_ids.extend(incoming_ids)
    squad_validation = validate_squad(
        resulting_ids, players, budget_tenths=100_000
    )
    violations.extend(squad_validation["violations"])

    missing_selling_prices = [
        player_id for player_id in outgoing_ids if player_id not in selling_prices
    ]
    sale_total = sum(
        selling_prices.get(player.id, player.now_cost) for player, _ in resolved
    )
    purchase_total = sum(incoming.now_cost for _, incoming in resolved)
    bank_after = bank_tenths + sale_total - purchase_total
    if bank_after < 0:
        violations.append(
            f"Scenario is over budget by {abs(bank_after) / 10:.1f}m."
        )

    gross_gains: dict[str, float] = {}
    downside_gains: dict[str, float] = {}
    for horizon in HORIZONS:
        incoming_points = sum(
            _expected_points(projection_by_id[incoming.id], horizon)
            for _, incoming in resolved
        )
        outgoing_points = sum(
            _expected_points(projection_by_id[outgoing.id], horizon)
            for outgoing, _ in resolved
        )
        gross_gains[str(horizon)] = round(incoming_points - outgoing_points, 2)
        downside_gains[str(horizon)] = round(
            incoming_points * 0.80 - outgoing_points * 1.10, 2
        )

    transfer_count = len(transfers)
    hit_cost = max(0, transfer_count - free_transfers) * HIT_COST
    net_gains = {
        horizon: round(value - hit_cost, 2)
        for horizon, value in gross_gains.items()
    }
    downside_net_gains = {
        horizon: round(value - hit_cost, 2)
        for horizon, value in downside_gains.items()
    }
    roll_next_free_transfers = min(MAX_FREE_TRANSFERS, free_transfers + 1)
    next_free_transfers = min(
        MAX_FREE_TRANSFERS, max(0, free_transfers - transfer_count) + 1
    )
    incoming_projections = [projection_by_id[incoming.id] for _, incoming in resolved]
    expected_minutes = [
        float(item.get("expected_minutes") or 0) for item in incoming_projections
    ]
    start_probabilities = [
        float(item.get("start_probability") or 0) for item in incoming_projections
    ]
    confidence = _scenario_confidence(incoming_projections)
    certified = not missing_selling_prices and not violations

    if transfer_count == 0:
        recommendation = "Roll"
    elif violations:
        recommendation = "Unavailable"
    elif missing_selling_prices:
        recommendation = "Needs input"
    elif hit_cost:
        robust_hit = (
            downside_net_gains["5"] > 0
            and min(expected_minutes, default=0) >= MIN_HIT_EXPECTED_MINUTES
            and min(start_probabilities, default=0) >= MIN_HIT_START_PROBABILITY
            and confidence in {"high", "medium"}
        )
        recommendation = "Do" if robust_hit else (
            "Consider" if net_gains["5"] > 0 else "Roll"
        )
    else:
        robust_free_move = (
            net_gains["3"] >= 2
            and downside_net_gains["3"] >= 0
            and min(expected_minutes, default=0) >= 60
            and confidence in {"high", "medium"}
        )
        recommendation = "Do" if robust_free_move else (
            "Consider" if net_gains["5"] > 0 else "Roll"
        )

    return {
        "version": TRANSFER_ADVISOR_VERSION,
        "transfer_count": transfer_count,
        "transfers": [
            {
                "out_player_id": outgoing.id,
                "out_name": outgoing.web_name,
                "in_player_id": incoming.id,
                "in_name": incoming.web_name,
                "position": POSITION_NAMES[outgoing.element_type],
            }
            for outgoing, incoming in resolved
        ],
        "valid": not violations,
        "certified_affordable": certified,
        "price_status": "confirmed" if not missing_selling_prices else "unconfirmed",
        "missing_selling_price_player_ids": missing_selling_prices,
        "violations": violations,
        "bank_before": bank_tenths / 10,
        "bank_after": round(bank_after / 10, 1),
        "gross_gains": gross_gains,
        "hit_cost": hit_cost,
        "net_gains": net_gains,
        "downside_net_gains": downside_net_gains,
        "free_transfers_before": free_transfers,
        "free_transfers_next_deadline": next_free_transfers,
        "free_transfer_opportunity_cost": (
            roll_next_free_transfers - next_free_transfers
        ),
        "incoming_min_expected_minutes": min(expected_minutes, default=None),
        "incoming_min_start_probability": min(start_probabilities, default=None),
        "confidence": confidence,
        "recommendation": recommendation,
    }
