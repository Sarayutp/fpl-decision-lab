from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from scipy.stats import spearmanr

from .forecast import neutral_expected_points, position_price_prior
from .models import Player


BACKTEST_VERSION = "rolling-backtest-1.0"


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _aggregate_history(rows: list[dict[str, Any]]) -> dict[str, float]:
    minutes = sum(_number(row.get("minutes")) for row in rows)
    starts = sum(_number(row.get("starts")) for row in rows)
    total_points = sum(_number(row.get("total_points")) for row in rows)
    xgi_numerator = sum(
        _number(row.get("expected_goal_involvements")) for row in rows
    )
    xgi_per_90 = xgi_numerator / minutes * 90 if minutes else 0.0
    return {
        "minutes": minutes,
        "starts": starts,
        "total_points": total_points,
        "xgi_per_90": xgi_per_90,
    }


def _metric_rows(
    players: list[Player],
    histories: dict[int, list[dict[str, Any]]],
    *,
    minimum_training_gameweeks: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for player in players:
        history = sorted(
            histories.get(player.id, []), key=lambda item: int(item.get("round", 0))
        )
        target_gameweeks = sorted(
            {int(item.get("round", 0)) for item in history if item.get("round")}
        )
        for target_gameweek in target_gameweeks:
            training = [
                item for item in history if int(item.get("round", 0)) < target_gameweek
            ]
            training_gameweeks = sorted(
                {int(item.get("round", 0)) for item in training}
            )
            if len(training_gameweeks) < minimum_training_gameweeks:
                continue
            actual_rows = [
                item for item in history if int(item.get("round", 0)) == target_gameweek
            ]
            if not actual_rows:
                continue

            observed = _aggregate_history(training)
            value = int(_number(training[-1].get("value"), player.now_cost))
            as_of_player = player.model_copy(
                update={
                    "now_cost": value,
                    "total_points": int(observed["total_points"]),
                    "minutes": int(observed["minutes"]),
                    "starts": int(observed["starts"]),
                    "ep_next": None,
                    "status": "a",
                    "chance_of_playing_next_round": None,
                    "expected_goal_involvements_per_90": observed["xgi_per_90"],
                    "penalties_order": None,
                    "direct_freekicks_order": None,
                    "corners_and_indirect_freekicks_order": None,
                }
            )
            v2 = neutral_expected_points(as_of_player, len(training))
            prior = position_price_prior(as_of_player)
            prior_prediction = prior["points_per_90"] * prior["minutes"] / 90
            recent_by_gameweek: dict[int, float] = defaultdict(float)
            for item in training:
                recent_by_gameweek[int(item["round"])] += _number(
                    item.get("total_points")
                )
            recent_values = [
                recent_by_gameweek[event] for event in training_gameweeks[-3:]
            ]
            rows.append(
                {
                    "player_id": player.id,
                    "target_gameweek": target_gameweek,
                    "trained_through_gameweek": max(training_gameweeks),
                    "training_gameweeks": training_gameweeks,
                    "actual_points": round(
                        sum(_number(item.get("total_points")) for item in actual_rows), 4
                    ),
                    "v2": v2["expected_points"],
                    "price_role_prior": round(prior_prediction, 4),
                    "recent_points": round(mean(recent_values), 4),
                    "expected_minutes": v2["expected_minutes"],
                    "current_season_weight": v2["current_season_weight"],
                }
            )
    return rows


def _mae(rows: list[dict[str, Any]], key: str) -> float:
    return round(mean(abs(row[key] - row["actual_points"]) for row in rows), 4)


def _rank_correlation(rows: list[dict[str, Any]], key: str) -> float:
    if len(rows) < 2:
        return 0.0
    predicted = [row[key] for row in rows]
    actual = [row["actual_points"] for row in rows]
    if len(set(predicted)) < 2 or len(set(actual)) < 2:
        return 0.0
    correlation = spearmanr(
        predicted,
        actual,
    ).statistic
    return round(float(correlation), 4) if correlation == correlation else 0.0


def _top_k_hit_rate(rows: list[dict[str, Any]], key: str, top_k: int) -> float:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["target_gameweek"])].append(row)
    rates = []
    for gameweek_rows in grouped.values():
        k = min(top_k, len(gameweek_rows))
        predicted = {
            row["player_id"]
            for row in sorted(gameweek_rows, key=lambda item: item[key], reverse=True)[:k]
        }
        actual = {
            row["player_id"]
            for row in sorted(
                gameweek_rows, key=lambda item: item["actual_points"], reverse=True
            )[:k]
        }
        rates.append(len(predicted & actual) / max(1, k))
    return round(mean(rates), 4) if rates else 0.0


def rolling_backtest(
    players: list[Player],
    histories: dict[int, list[dict[str, Any]]],
    *,
    minimum_training_gameweeks: int = 1,
    minimum_evaluation_gameweeks: int = 3,
    top_k: int = 10,
) -> dict[str, Any]:
    """Evaluate v2 with expanding windows and strict pre-target features."""

    rows = _metric_rows(
        players,
        histories,
        minimum_training_gameweeks=minimum_training_gameweeks,
    )
    evaluated_gameweeks = sorted({row["target_gameweek"] for row in rows})
    if not rows:
        return {
            "version": BACKTEST_VERSION,
            "status": "insufficient_history",
            "sample_count": 0,
            "evaluated_gameweeks": [],
            "leakage_guard": "training round must be lower than target round",
            "metrics": {},
        }

    metrics = {}
    for key in ("v2", "price_role_prior", "recent_points"):
        metrics[key] = {
            "mae": _mae(rows, key),
            "rank_correlation": _rank_correlation(rows, key),
            "top_k_hit_rate": _top_k_hit_rate(rows, key, top_k),
        }
    v2_wins = sum(
        (
            metrics["v2"]["mae"] < metrics[baseline]["mae"]
            and metrics["v2"]["rank_correlation"]
            > metrics[baseline]["rank_correlation"]
        )
        for baseline in ("price_role_prior", "recent_points")
    )
    ready = len(evaluated_gameweeks) >= minimum_evaluation_gameweeks
    leakage_violations = sum(
        int(row["trained_through_gameweek"] >= row["target_gameweek"])
        for row in rows
    )
    return {
        "version": BACKTEST_VERSION,
        "status": "ready" if ready else "insufficient_history",
        "sample_count": len(rows),
        "player_count": len({row["player_id"] for row in rows}),
        "evaluated_gameweeks": evaluated_gameweeks,
        "minimum_evaluation_gameweeks": minimum_evaluation_gameweeks,
        "leakage_guard": "Every training round is strictly lower than its target round.",
        "leakage_violations": leakage_violations,
        "metrics": metrics,
        "v2_beats_both_baselines_on_mae_and_rank": v2_wins == 2,
        "limitations": [
            "Historical FPL ep_next is not available from element-summary and is not backfilled.",
            "Results are not decision-ready until the minimum number of evaluation Gameweeks is met.",
        ],
        "prediction_audit": [
            {
                "player_id": row["player_id"],
                "target_gameweek": row["target_gameweek"],
                "trained_through_gameweek": row["trained_through_gameweek"],
                "actual_points": row["actual_points"],
                "v2": row["v2"],
                "price_role_prior": row["price_role_prior"],
                "recent_points": row["recent_points"],
            }
            for row in rows[:100]
        ],
    }


def write_backtest_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output_path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
