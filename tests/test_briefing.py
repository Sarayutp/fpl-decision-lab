from __future__ import annotations

from fpl_mvp.briefing import build_briefing_markdown


def test_briefing_is_compact_and_ready_for_chatgpt() -> None:
    snapshot = {
        "generated_at": "2026-08-16T12:00:00+00:00",
        "game": {
            "next_gameweek": {
                "name": "Gameweek 1",
                "deadline_time": "2026-08-21T17:30:00+00:00",
            }
        },
        "manager": {
            "team_id": 3_647_781,
            "overall_points": None,
            "overall_rank": None,
        },
        "catalog": {"players": [], "teams": []},
        "analysis": {
            "model": {"version": "test", "horizon": 5},
            "projections": [],
            "recommendations": {
                "initial_squad": {
                    "formation": "3-4-3",
                    "cost": 99.5,
                    "money_left": 0.5,
                    "xp_with_captain": 55.0,
                    "picks": [],
                }
            },
        },
        "diagnostics": {"warnings": []},
    }

    briefing = build_briefing_markdown(snapshot)

    assert "Team ID: 3647781" in briefing
    assert "Gameweek 1" in briefing
    assert "ค้นเว็บ" in briefing
    assert "ไม่ต้องใช้ OpenAI API key" in briefing
    assert len(briefing) < 10_000
