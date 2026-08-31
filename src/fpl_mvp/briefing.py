from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any


def _pick_line(player: dict[str, Any], *, role: str) -> str:
    badges = []
    if player.get("captain"):
        badges.append("C")
    if player.get("vice_captain"):
        badges.append("VC")
    badge = f" [{' / '.join(badges)}]" if badges else ""
    interval = player.get("expected_points_range") or {}
    flags = ",".join(player.get("data_quality_flags", [])) or "none"
    return (
        f"- {player.get('position', '?')} {player.get('name', '?')}{badge} — {role}, "
        f"คู่แข่ง {player.get('opponent', 'ไม่ทราบ')}, "
        f"xPts {float(player.get('xp_next', 0)):.2f} "
        f"(ช่วง {float(interval.get('lower', 0)):.2f}–{float(interval.get('upper', 0)):.2f}), "
        f"นาที {float(player.get('expected_minutes') or 0):.0f}, "
        f"start {float(player.get('start_probability') or 0) * 100:.0f}%, "
        f"confidence={player.get('projection_confidence', 'ไม่ทราบ')}, "
        f"risk={player.get('risk', 'ไม่ทราบ')}, flags={flags}"
    )


def _reason_groups(decision: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    groups: dict[str, list[str]] = {"fact": [], "estimate": [], "limitation": []}
    for section_name in ("transfer", "starting_xi", "captaincy", "bench", "chip"):
        for reason in decision.get(section_name, {}).get("reasons", []):
            kind = reason.get("kind", "limitation")
            if kind not in groups:
                kind = "limitation"
            text = str(reason.get("text", "")).strip()
            if text and text not in groups[kind]:
                groups[kind].append(text)
    return groups["fact"], groups["estimate"], groups["limitation"]


def build_briefing_markdown(snapshot: dict[str, Any]) -> str:
    """Build a compact, upload/paste-ready briefing for ChatGPT Plus."""

    game = snapshot["game"]
    manager = snapshot["manager"]
    identity = snapshot.get("identity", {})
    data_quality = snapshot.get("data_quality", {})
    analysis = snapshot.get("analysis", {})
    model = analysis.get("model", {})
    model_quality = model.get("quality") or {}
    transfer_advisor = (
        analysis.get("recommendations", {}).get("transfer_advisor", {})
    )
    chip_planner = analysis.get("recommendations", {}).get("chip_planner", {})
    risk_layer = analysis.get("risk_layer", {})
    decision = snapshot.get("gameweek_decision", {})

    next_gameweek = game.get("next_gameweek") or {}
    deadline = next_gameweek.get("deadline_time", "ไม่มี deadline ถัดไป")
    gameweek_name = next_gameweek.get("name", "ไม่ทราบ Gameweek")

    transfer = decision.get("transfer", {})
    starting_xi = decision.get("starting_xi", {})
    captaincy = decision.get("captaincy", {})
    bench = decision.get("bench", {})
    chip = decision.get("chip", {})
    xi_lines = [
        _pick_line(player, role="ตัวจริง")
        for player in starting_xi.get("players", [])
    ] or ["- ยังแนะนำไม่ได้"]
    bench_lines = [
        _pick_line(
            player,
            role=(
                "ผู้รักษาประตูสำรอง"
                if int(player.get("position_id", 0)) == 1
                else f"สำรองลำดับ {player.get('bench_order', '?')}"
            ),
        )
        for player in bench.get("players", [])
    ] or ["- ยังแนะนำไม่ได้"]
    captain = captaincy.get("captain") or {}
    vice = captaincy.get("vice_captain") or {}
    fact_reasons, estimate_reasons, limitation_reasons = _reason_groups(decision)
    alternative_lines = [
        f"- {item.get('label', item.get('type', 'ทางเลือก'))}: {item.get('detail', '-')}"
        for item in decision.get("alternatives", [])
    ] or ["- ไม่มีทางเลือกสำรองจากข้อมูลชุดนี้"]

    warning_lines = [
        f"- {warning}" for warning in snapshot["diagnostics"].get("warnings", [])
    ] or ["- ไม่มีคำเตือนจาก data pipeline"]
    owned_ids = {
        int(player.get("player_id", 0))
        for player in starting_xi.get("squad", [])
    }
    relevant_evidence = [
        item
        for item in risk_layer.get("evidence", [])
        if int(item.get("player_id", 0)) in owned_ids and item.get("active")
    ]
    risk_evidence_lines = [
        (
            f"- [{item.get('claim_type', 'inference')}] {item.get('player_name', '?')} — "
            f"{item.get('category', 'availability')}: {item.get('summary', '-')} | "
            f"{item.get('source_label', 'ไม่ทราบแหล่ง')} | "
            f"เผยแพร่ {item.get('published_at', 'ไม่ทราบเวลา')} | "
            f"สถานะ {item.get('freshness', 'unknown')} | {item.get('source_url', '-')}"
        )
        for item in relevant_evidence[:20]
    ] or ["- ไม่มี evidence ที่ active สำหรับผู้เล่น 15 คน; ใช้ FPL status และช่วงความไม่แน่นอน"]
    risk_adjustment_lines = [
        (
            f"- {item.get('player_name', '?')}: นาที "
            f"{float(item.get('before', {}).get('expected_minutes') or 0):.0f} → "
            f"{float(item.get('after', {}).get('expected_minutes') or 0):.0f}, "
            f"xPts {float(item.get('before', {}).get('expected_points_next') or 0):.2f} → "
            f"{float(item.get('after', {}).get('expected_points_next') or 0):.2f} "
            f"จาก {item.get('evidence_id', '-') }"
        )
        for item in risk_layer.get("adjustments", [])
        if int(item.get("player_id", 0)) in owned_ids
    ] or ["- ไม่มีการปรับนาทีจาก curated evidence ใน snapshot นี้"]
    chip_labels = {
        "bench_boost": "Bench Boost",
        "triple_captain": "Triple Captain",
        "free_hit": "Free Hit",
        "wildcard": "Wildcard",
    }
    chip_plan_lines = []
    for chip_name, evaluation in chip_planner.get("chips", {}).items():
        used = ", ".join(f"GW{item}" for item in evaluation.get("used_events", []))
        chip_plan_lines.append(
            f"- {chip_labels.get(chip_name, chip_name)}: {evaluation.get('action', 'unavailable')} | "
            f"กำไร GW ปัจจุบัน {float(evaluation.get('current_gain', 0)):.2f} | "
            f"ดีที่สุดที่มองเห็น GW{evaluation.get('best_visible_gameweek', '-')} "
            f"{float(evaluation.get('best_visible_gain', 0)):.2f} | "
            f"ค่าเสียโอกาส {float(evaluation.get('opportunity_cost', 0)):.2f}"
            + (f" | เคยใช้ {used}" if used else "")
        )
    if not chip_plan_lines:
        chip_plan_lines = ["- Chip Planner ยังไม่มีข้อมูล"]
    transfer_path_lines = []
    for path_name, path in chip_planner.get("transfer_paths", {}).items():
        if path_name not in {"main", "alternative"}:
            continue
        moves = path.get("moves", []) if isinstance(path, dict) else []
        detail = "; ".join(
            f"GW{move.get('gameweek')} {move.get('out_name')} → {move.get('in_name')} "
            f"(bank {float(move.get('bank_after', 0)):.1f}m)"
            for move in moves
        ) or "Roll / ไม่มี move ที่ผ่านเกณฑ์"
        transfer_path_lines.append(
            f"- {'แผนหลัก' if path_name == 'main' else 'แผนสำรอง'}: {detail}; "
            f"กำไรช่วงโมเดล {float(path.get('estimated_horizon_gain', 0)):.2f}; "
            f"ผ่านงบ/กฎ={'ใช่' if path.get('valid') else 'ไม่'}"
        )

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
            f"- สถานะความสด: {data_quality.get('status', 'ไม่ทราบ')}",
            f"- ข้อมูลต้นทางเก่าสุด: {data_quality.get('oldest_source_at', 'ไม่ทราบ')}",
            f"- เป้าหมาย: {gameweek_name}",
            f"- Deadline: {deadline}",
            f"- Team ID: {manager['team_id']}",
            f"- ชื่อทีม: {identity.get('team_name') or manager.get('team_name') or 'ไม่ทราบ'}",
            f"- ผู้จัดการ: {identity.get('manager_name') or manager.get('manager_name') or 'ไม่ทราบ'}",
            f"- ยืนยันตัวตนทีม: {'ผ่าน' if identity.get('verified') else 'ไม่ผ่าน/ไม่มีข้อมูล'}",
            f"- ฤดูกาล: {identity.get('season') or game.get('season') or 'ไม่ทราบ'}",
            f"- คะแนนรวม: {manager.get('overall_points')}",
            f"- อันดับรวม: {manager.get('overall_rank')}",
            f"- โมเดล: {analysis.get('model', {}).get('version', 'ไม่มี')}",
            f"- Model guardrails: {model_quality.get('status', 'ไม่ทราบ')}",
            f"- นิยาม expected points: {model.get('score_definitions', {}).get('expected_points', 'ไม่มี')}",
            f"- นิยาม ranking score: {model.get('score_definitions', {}).get('ranking_score', 'ไม่มี')}",
            f"- Transfer Advisor: {transfer_advisor.get('version', 'ไม่มี')} / "
            f"{transfer_advisor.get('status', 'ไม่ทราบ')}",
            f"- Risk Layer: {risk_layer.get('version', 'ไม่มี')} / "
            f"{risk_layer.get('status', 'ไม่ทราบ')}",
            f"- Chip Planner: {chip_planner.get('version', 'ไม่มี')} / "
            f"{chip_planner.get('status', 'ไม่ทราบ')}",
            f"- ข่าวหมดอายุหลัง: {risk_layer.get('stale_after_hours', 24)} ชั่วโมง",
            "",
            "## News, Minutes & Risk",
            "",
            f"- Evidence ทั้งหมด: {risk_layer.get('evidence_count', 0)}",
            f"- Curated evidence ที่ active: {risk_layer.get('active_curated_count', 0)}",
            f"- ข่าวเก่า: {risk_layer.get('stale_curated_count', 0)}; "
            f"ไม่ผ่าน validation: {risk_layer.get('invalid_curated_count', 0)}",
            f"- ผู้เล่นที่ถูกปรับนาที: {risk_layer.get('adjusted_player_count', 0)}",
            "- Predicted lineup ถูกจัดเป็นข้อสันนิษฐานและไม่ใช้แทนข่าวทางการ",
            "",
            "### Evidence ที่เกี่ยวกับทีมจริง",
            "",
            *risk_evidence_lines,
            "",
            "### ผลกระทบต่อโมเดล",
            "",
            *risk_adjustment_lines,
            "",
            "## คำแนะนำประจำ Gameweek",
            "",
            f"- สถานะแผน: {decision.get('status', 'unavailable')}",
            f"- ความมั่นใจรวม: {decision.get('confidence', 'unavailable')}",
            f"- แหล่งทีม: {decision.get('source', {}).get('squad', 'ไม่ทราบ')} "
            f"หลัง GW{decision.get('source', {}).get('published_gameweek', '-')}",
            "",
            "### 1) Transfer",
            "",
            f"- คำตอบ: {transfer.get('label', 'ยังแนะนำไม่ได้')} — "
            f"{transfer.get('headline', 'ยังแนะนำไม่ได้')}",
            f"- ความมั่นใจ: {transfer.get('confidence', 'unavailable')}",
            f"- แนะนำการติดลบ: {'ใช่' if transfer.get('hit_recommended') else 'ไม่'}",
            f"- ข้อมูลที่ยังต้องกรอก: {', '.join(transfer_advisor.get('required_inputs', [])) or 'ไม่มี'}",
            f"- เงินในธนาคารจาก FPL ล่าสุด: {transfer_advisor.get('inputs', {}).get('bank', 'ไม่ทราบ')}m",
            f"- Candidate shortlist: {transfer_advisor.get('candidate_count', 0)} moves",
            *(
                [
                    f"- Expected points เพิ่มโดยประมาณ: GW ถัดไป {float(transfer['xp_next_gain']):.2f}, "
                    f"ช่วงโมเดล {float(transfer['xp_horizon_gain']):.2f}",
                    f"- ราคาต่างโดยประมาณ: {float(transfer['estimated_cost_change']):+.1f}m",
                ]
                if "xp_next_gain" in transfer
                else []
            ),
            "",
            "### 2) Starting XI",
            "",
            f"- Formation: {starting_xi.get('formation', '-')}",
            f"- Expected points XI รวมกัปตัน: {float(starting_xi.get('xp_starting_xi_with_captain', 0)):.2f}",
            *xi_lines,
            "",
            "### 3) Captain / Vice",
            "",
            f"- Captain: {captain.get('name', 'ยังแนะนำไม่ได้')} — "
            f"xPts {float(captain.get('xp_next', 0)):.2f}, "
            f"นาที {float(captain.get('expected_minutes') or 0):.0f}, "
            f"confidence={captain.get('projection_confidence', 'ไม่ทราบ')}, "
            f"{captain.get('opponent', '-')}",
            f"- Vice: {vice.get('name', 'ยังแนะนำไม่ได้')} — "
            f"xPts {float(vice.get('xp_next', 0)):.2f}, "
            f"นาที {float(vice.get('expected_minutes') or 0):.0f}, "
            f"confidence={vice.get('projection_confidence', 'ไม่ทราบ')}, "
            f"{vice.get('opponent', '-')}",
            f"- ความมั่นใจ: {captaincy.get('confidence', 'unavailable')}",
            "",
            "### 4) Bench Order",
            "",
            *bench_lines,
            f"- Expected points ม้านั่งรวม: {float(bench.get('xp_total', 0)):.2f}",
            "",
            "### 5) Chip",
            "",
            f"- คำตอบ: {chip.get('label', 'ยังแนะนำไม่ได้')} — "
            f"{chip.get('headline', 'ยังแนะนำไม่ได้')}",
            f"- Bench Boost expected points ปัจจุบัน: {float(chip.get('bench_boost_xp', 0)):.2f}",
            f"- กำไรชิปที่แนะนำ: {float(chip.get('estimated_gain', 0)):.2f}",
            f"- ค่าเสียโอกาสที่มองเห็น: {float(chip.get('opportunity_cost', 0)):.2f}",
            f"- ความมั่นใจ: {chip.get('confidence', 'unavailable')}",
            "",
            "## Multi-GW & Chip Planner",
            "",
            f"- ช่วงที่มองเห็น: {', '.join(f'GW{item}' for item in chip_planner.get('horizon', {}).get('gameweeks', [])) or 'ไม่มี'}",
            f"- กติกา: {chip_planner.get('rules', {}).get('sets_per_season', '-')} ชุดต่อฤดูกาล; "
            f"1 ชิปต่อ GW={'ใช่' if chip_planner.get('rules', {}).get('one_chip_per_gameweek') else 'ไม่'}",
            f"- คำเตือนช่วงโมเดล: {chip_planner.get('horizon', {}).get('visibility_warning', '-')}",
            *chip_plan_lines,
            "",
            "### Transfer path 3–6 GW",
            "",
            *transfer_path_lines,
            "- งบใช้ราคาปัจจุบันเป็นค่าประมาณ ต้องยืนยันราคาขายจริงและ FT ใน Transfer Advisor ก่อนทำจริง",
            "",
            "## ทางเลือกสำรอง",
            "",
            *alternative_lines,
            "",
            "## ข้อเท็จจริงจากข้อมูล",
            "",
            *([f"- {reason}" for reason in fact_reasons] or ["- ไม่มีข้อเท็จจริงเพิ่มเติม"]),
            "",
            "## ค่าประมาณจากโมเดล",
            "",
            *([f"- {reason}" for reason in estimate_reasons] or ["- ไม่มีค่าประมาณเพิ่มเติม"]),
            "",
            "## ข้อจำกัดและสิ่งที่ต้องยืนยัน",
            "",
            *([f"- {reason}" for reason in limitation_reasons] or ["- ไม่มีข้อจำกัดเพิ่มเติม"]),
            "",
            "## คำเตือนจากระบบ",
            "",
            *warning_lines,
            "",
            "## ข้อจำกัด",
            "",
            "- expected points คือคะแนน FPL ที่คาด ไม่ใช่การรับประกันผลลัพธ์",
            "- ranking score ใช้จัดอันดับและอาจไม่เท่ากับ expected points",
            "- ช่วงคะแนนเป็น decision range ที่ยังไม่ผ่าน statistical calibration เต็มฤดูกาล",
            "- ระบบยังไม่รู้ราคาขายจริงของผู้เล่นแต่ละคนจากบัญชีส่วนตัว",
            "- Free Transfer และราคาขายที่กรอกใน Browser จะถูกต่อท้าย briefing ตอนกดคัดลอก",
            "- Current price ใช้สร้าง shortlist เท่านั้น ไม่ใช้รับรองว่า transfer อยู่ในงบ",
            "- ข่าวด่วนและ predicted lineup ต้องยืนยันจากเว็บใกล้ deadline",
            "- ข่าวที่เก่ากว่า 24 ชั่วโมงหรือหมดอายุจะไม่ถูกใช้ปรับ expected minutes",
            "- ทีมจาก public API คือทีมที่ประกาศล่าสุด ไม่ใช่การเปลี่ยนแปลงที่ยังไม่ผ่าน deadline",
            "",
            "## แหล่งที่มาของข้อมูล",
            "",
            "- ตัวตนทีมและทีมที่ประกาศล่าสุด: FPL Public API (ข้อเท็จจริง)",
            "- ทีมใน Squad Lab: Browser localStorage (ผู้ใช้กรอกและไม่รวมอยู่ในไฟล์นี้)",
            "- expected points, ranking score และคำแนะนำ: FPL Decision Lab model (ค่าประมาณ)",
            "- availability: FPL Public API; ข่าวสโมสร/นาที/lineup: Risk Layer พร้อม source snapshot",
            "- กติกา FT และ -4: Premier League FPL transfer rules (ข้อเท็จจริง)",
            "- กติกาชิป 2026/27: Premier League FPL chip rules และ FAQ (ข้อเท็จจริง)",
            *[f"- [{source.get('title', 'Chip rules')}]({source.get('url', '')})" for source in chip_planner.get("rules", {}).get("sources", [])],
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
