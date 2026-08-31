from __future__ import annotations

from fpl_mvp.briefing import build_briefing_markdown


def test_briefing_is_compact_and_ready_for_chatgpt() -> None:
    snapshot = {
        "generated_at": "2026-08-16T12:00:00+00:00",
        "identity": {
            "requested_team_id": 5_105_794,
            "snapshot_team_id": 5_105_794,
            "verified": True,
            "team_name": "Sarayut FC",
            "manager_name": "Sarayut P",
            "season": "2026-27",
        },
        "data_quality": {
            "status": "fresh",
            "oldest_source_at": "2026-08-16T11:55:00+00:00",
        },
        "game": {
            "next_gameweek": {
                "name": "Gameweek 1",
                "deadline_time": "2026-08-21T17:30:00+00:00",
            }
        },
        "manager": {
            "team_id": 5_105_794,
            "overall_points": None,
            "overall_rank": None,
        },
        "catalog": {"players": [], "teams": []},
        "gameweek_decision": {
            "status": "ready",
            "confidence": "medium",
            "source": {"squad": "published", "published_gameweek": 1},
            "transfer": {
                "label": "เก็บ FT",
                "headline": "เก็บ Free Transfer",
                "confidence": "medium",
                "hit_recommended": False,
                "reasons": [{"kind": "fact", "text": "ไม่เสนอการติดลบ"}],
            },
            "starting_xi": {
                "formation": "3-4-3",
                "xp_starting_xi_with_captain": 55.0,
                "players": [
                    {
                        "player_id": 1,
                        "name": "Captain",
                        "position": "MID",
                        "position_id": 3,
                        "captain": True,
                        "vice_captain": False,
                        "opponent": "ARS (H)",
                        "xp_next": 8.0,
                        "risk": "low",
                    }
                ],
                "reasons": [{"kind": "estimate", "text": "จัด XI ตาม xP"}],
            },
            "captaincy": {
                "captain": {"name": "Captain", "xp_next": 8.0, "opponent": "ARS (H)"},
                "vice_captain": {"name": "Vice", "xp_next": 7.0, "opponent": "CHE (A)"},
                "confidence": "medium",
                "reasons": [],
            },
            "bench": {
                "players": [],
                "xp_total": 4.0,
                "reasons": [],
            },
            "chip": {
                "label": "เก็บชิป",
                "headline": "ยังไม่ใช้ชิป",
                "bench_boost_xp": 4.0,
                "confidence": "low",
                "reasons": [{"kind": "limitation", "text": "ต้องเทียบหลาย GW"}],
            },
            "alternatives": [
                {"label": "แผนปลอดภัย", "detail": "เก็บ FT และตรวจข่าว"}
            ],
        },
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

    assert "Team ID: 5105794" in briefing
    assert "ชื่อทีม: Sarayut FC" in briefing
    assert "ยืนยันตัวตนทีม: ผ่าน" in briefing
    assert "สถานะความสด: fresh" in briefing
    assert "### 1) Transfer" in briefing
    assert "คำตอบ: เก็บ FT" in briefing
    assert "Captain: Captain" in briefing
    assert "คำตอบ: เก็บชิป" in briefing
    assert "ข้อเท็จจริงจากข้อมูล" in briefing
    assert "ทีมเริ่มต้นที่ optimizer เสนอ" not in briefing
    assert "Gameweek 1" in briefing
    assert "ค้นเว็บ" in briefing
    assert "ไม่ต้องใช้ OpenAI API key" in briefing
    assert len(briefing) < 10_000
