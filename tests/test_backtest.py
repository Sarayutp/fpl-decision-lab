from __future__ import annotations

from fpl_mvp.backtest import rolling_backtest
from fpl_mvp.models import Player


def player(player_id: int, price: int = 75) -> Player:
    return Player.model_validate(
        {
            "id": player_id,
            "first_name": "Backtest",
            "second_name": str(player_id),
            "web_name": f"P{player_id}",
            "team": 1,
            "element_type": 3,
            "now_cost": price,
            "status": "a",
        }
    )


def history(points: list[int], minutes: list[int]) -> list[dict]:
    return [
        {
            "round": index + 1,
            "total_points": score,
            "minutes": played,
            "starts": int(played >= 60),
            "value": 75,
            "expected_goal_involvements": 0.3 if played else 0.0,
        }
        for index, (score, played) in enumerate(zip(points, minutes, strict=True))
    ]


def test_rolling_backtest_uses_only_pre_target_gameweeks() -> None:
    players = [player(1), player(2)]
    histories = {
        1: history([6, 2, 8, 4], [90, 90, 90, 90]),
        2: history([2, 5, 1, 7], [70, 80, 30, 90]),
    }

    report = rolling_backtest(
        players,
        histories,
        minimum_evaluation_gameweeks=3,
        top_k=1,
    )

    assert report["status"] == "ready"
    assert report["leakage_violations"] == 0
    assert report["evaluated_gameweeks"] == [2, 3, 4]
    assert all(
        row["trained_through_gameweek"] < row["target_gameweek"]
        for row in report["prediction_audit"]
    )
    assert set(report["metrics"]) == {"v2", "price_role_prior", "recent_points"}


def test_future_result_does_not_change_an_earlier_prediction() -> None:
    players = [player(1)]
    base = {1: history([6, 2, 8], [90, 90, 90])}
    changed = {1: history([6, 2, 30], [90, 90, 90])}

    base_report = rolling_backtest(players, base, minimum_evaluation_gameweeks=1)
    changed_report = rolling_backtest(
        players, changed, minimum_evaluation_gameweeks=1
    )
    base_gw2 = next(
        row for row in base_report["prediction_audit"] if row["target_gameweek"] == 2
    )
    changed_gw2 = next(
        row
        for row in changed_report["prediction_audit"]
        if row["target_gameweek"] == 2
    )

    assert base_gw2["v2"] == changed_gw2["v2"]
    assert base_gw2["actual_points"] == changed_gw2["actual_points"]
