from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any


def _player_lookup(snapshot: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {player["id"]: player for player in snapshot["catalog"]["players"]}


def build_briefing_markdown(snapshot: dict[str, Any]) -> str:
    """Build a compact, upload/paste-ready briefing for ChatGPT Plus."""

    game = snapshot["game"]
    manager = snapshot["manager"]
    analysis = snapshot.get("analysis", {})
    recommendations = analysis.get("recommendations", {})
    initial_squad = recommendations.get("initial_squad", {})
    projections = analysis.get("projections", [])
    players = _player_lookup(snapshot)
    team_names = {
        team["id"]: team["short_name"] for team in snapshot["catalog"]["teams"]
    }

    next_gameweek = game.get("next_gameweek") or {}
    deadline = next_gameweek.get("deadline_time", "ไม่มี deadline ถัดไป")
    gameweek_name = next_gameweek.get("name", "ไม่ทราบ Gameweek")

    top_candidates = sorted(
        projections, key=lambda item: item["xp_next"], reverse=True
    )[:12]
    candidate_lines = []
    for item in top_candidates:
        player = players.get(item["player_id"], {})
        candidate_lines.append(
            f"- {player.get('web_name', item['player_id'])} "
            f"({team_names.get(player.get('team_id'), '?')}, "
            f"{player.get('position', player.get('position_id', '?'))}) — "
            f"xP ถัดไป {item['xp_next']:.2f}, "
            f"xP {analysis.get('model', {}).get('horizon', 5)} GW "
            f"{item['xp_horizon']:.2f}, risk={item['risk']}"
        )

    squad_lines: list[str] = []
    for pick in initial_squad.get("picks", []):
        role = "ตัวจริง" if pick["starter"] else f"สำรอง {pick['bench_order']}"
        badges = []
        if pick["captain"]:
            badges.append("C")
        if pick["vice_captain"]:
            badges.append("VC")
        badge_text = f" [{' / '.join(badges)}]" if badges else ""
        squad_lines.append(
            f"- {pick['position']} {pick['name']}{badge_text} — {role}, "
            f"ราคา {pick['price']:.1f}, xP {pick['xp_next']:.2f}"
        )

    warning_lines = [
        f"- {warning}" for warning in snapshot["diagnostics"].get("warnings", [])
    ] or ["- ไม่มีคำเตือนจาก data pipeline"]

    return "\n".join(
        [
            "# FPL Decision Briefing",
            "",
            "> ใช้ไฟล์นี้กับ ChatGPT Plus ได้โดยอัปโหลดหรือคัดลอกทั้งหมด "
            "ระบบนี้ไม่ต้องใช้ OpenAI API key",
            "",
            "## คำสั่งสำหรับ ChatGPT",
            "",
            "คุณคือผู้ช่วยวิเคราะห์ Fantasy Premier League ของผม "
            "ให้ใช้ข้อมูลเชิงตัวเลขด้านล่างเป็นฐาน แล้วค้นเว็บเพื่อยืนยันข่าวบาดเจ็บ "
            "การแถลงข่าว โอกาสลงตัวจริง และการเลื่อนโปรแกรมล่าสุดก่อนเสนอคำตอบ "
            "แยกข้อเท็จจริงออกจากข้อสันนิษฐานอย่างชัดเจน อย่าแนะนำการติดลบ "
            "4 แต้มเว้นแต่คาดว่าคุ้มจริงในระยะที่ระบุ สรุปเป็น: (1) transfers "
            "(2) starting XI (3) captain/vice (4) bench order (5) ความเสี่ยง "
            "และทางเลือกสำรอง หากข้อมูลนี้เก่าเกิน 24 ชั่วโมงให้เตือนผมก่อน",
            "",
            "## สถานะข้อมูล",
            "",
            f"- สร้างเมื่อ: {snapshot['generated_at']}",
            f"- เป้าหมาย: {gameweek_name}",
            f"- Deadline: {deadline}",
            f"- Team ID: {manager['team_id']}",
            f"- คะแนนรวม: {manager.get('overall_points')}",
            f"- อันดับรวม: {manager.get('overall_rank')}",
            f"- โมเดล: {analysis.get('model', {}).get('version', 'ไม่มี')}",
            "",
            "## ทีมเริ่มต้นที่ optimizer เสนอ",
            "",
            f"- Formation: {initial_squad.get('formation', '-')}",
            f"- Cost: {initial_squad.get('cost', 0):.1f}",
            f"- เงินเหลือ: {initial_squad.get('money_left', 0):.1f}",
            f"- xP XI รวมกัปตัน: {initial_squad.get('xp_with_captain', 0):.2f}",
            *squad_lines,
            "",
            "## ตัวเลือก xP สูงสำหรับ Gameweek ถัดไป",
            "",
            *candidate_lines,
            "",
            "## คำเตือนจากระบบ",
            "",
            *warning_lines,
            "",
            "## ข้อจำกัด",
            "",
            "- xP เป็นคะแนนจัดลำดับ ไม่ใช่การรับประกันผลลัพธ์",
            "- ระบบยังไม่รู้ราคาขายจริงของผู้เล่นแต่ละคนจากบัญชีส่วนตัว",
            "- ข่าวด่วนและ predicted lineup ต้องยืนยันจากเว็บใกล้ deadline",
            "",
        ]
    )


def write_briefing(content: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output_path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
