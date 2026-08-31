from __future__ import annotations

from typing import Any, Iterable


DECISION_VERSION = "gameweek-decision-5.0"


def _reason(kind: str, text: str) -> dict[str, str]:
    return {"kind": kind, "text": text}


def _projection_map(
    projections: Iterable[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    return {int(item["player_id"]): item for item in projections}


def _opponent(projection: dict[str, Any] | None) -> str:
    gameweeks = projection.get("gameweeks", []) if projection else []
    if not gameweeks:
        return "ไม่ทราบคู่แข่ง"
    opponents = gameweeks[0].get("opponents", [])
    return " + ".join(opponents) if opponents else "Blank Gameweek"


def _decision_player(
    pick: dict[str, Any], projection_by_id: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    player_id = int(pick["player_id"])
    projection = projection_by_id.get(player_id, {})
    return {
        **pick,
        "opponent": _opponent(projection),
        "availability": projection.get("availability"),
    }


def _confidence(
    players: Iterable[dict[str, Any]], data_quality: dict[str, Any]
) -> str:
    if data_quality.get("is_stale"):
        return "low"
    risks = {str(player.get("risk", "unavailable")) for player in players}
    if risks & {"high", "unavailable"}:
        return "low"
    projection_confidence = {
        str(player.get("projection_confidence"))
        for player in players
        if player.get("projection_confidence")
    }
    if "low" in projection_confidence:
        return "low"
    if projection_confidence and projection_confidence == {"high"}:
        return "high"
    return "medium"


def _unavailable_section(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "headline": "ยังแนะนำไม่ได้",
        "confidence": "unavailable",
        "reasons": [_reason("limitation", reason)],
    }


def build_gameweek_decision(
    *,
    team_id: int,
    target_gameweek: dict[str, Any] | None,
    generated_at: str,
    identity_verified: bool,
    data_quality: dict[str, Any],
    published_gameweek: int | None,
    team_source_status: str,
    current_squad: dict[str, Any] | None,
    transfer_suggestions: list[dict[str, Any]],
    projections: list[dict[str, Any]],
    transfer_advisor: dict[str, Any] | None = None,
    chip_planner: dict[str, Any] | None = None,
    risk_layer: dict[str, Any] | None = None,
    model_version: str = "unknown",
) -> dict[str, Any]:
    """Build one decision-first contract from the manager's owned squad."""

    base = {
        "version": DECISION_VERSION,
        "team_id": team_id,
        "target_gameweek": target_gameweek,
        "generated_at": generated_at,
        "source": {
            "squad": team_source_status,
            "published_gameweek": published_gameweek,
            "kind": "fact",
            "pending_changes_included": False,
            "model_version": model_version,
            "transfer_advisor_version": (
                transfer_advisor.get("version") if transfer_advisor else None
            ),
            "risk_layer_version": risk_layer.get("version") if risk_layer else None,
            "risk_layer_status": risk_layer.get("status") if risk_layer else None,
            "chip_planner_version": (
                chip_planner.get("version") if chip_planner else None
            ),
        },
        "freshness": data_quality,
    }
    unavailable_reason: str | None = None
    if not identity_verified:
        unavailable_reason = "Team ID ยังไม่ผ่านการยืนยัน"
    elif target_gameweek is None:
        unavailable_reason = "ไม่มี Gameweek ถัดไป"
    elif current_squad is None:
        unavailable_reason = "ยังไม่มีทีม 15 คนที่ FPL เปิดเป็นสาธารณะ"
    elif not current_squad.get("valid"):
        violations = current_squad.get("violations", [])
        unavailable_reason = "; ".join(violations) or "ทีมปัจจุบันไม่ผ่านกฎ FPL"

    if unavailable_reason:
        unavailable = _unavailable_section(unavailable_reason)
        return {
            **base,
            "status": "unavailable",
            "confidence": "unavailable",
            "summary": {
                "headline": "ยังสร้างแผน Gameweek ไม่ได้",
                "detail": unavailable_reason,
            },
            "transfer": unavailable,
            "starting_xi": unavailable,
            "captaincy": unavailable,
            "bench": unavailable,
            "chip": unavailable,
            "alternatives": [],
            "warnings": [unavailable_reason],
        }

    projection_by_id = _projection_map(projections)
    squad = [
        _decision_player(pick, projection_by_id)
        for pick in current_squad.get("picks", [])
    ]
    starters = sorted(
        (player for player in squad if player.get("starter")),
        key=lambda player: (int(player["position_id"]), -float(player["xp_next"])),
    )
    bench_players = sorted(
        (player for player in squad if not player.get("starter")),
        key=lambda player: int(player.get("bench_order") or 99),
    )
    captain = next((player for player in starters if player.get("captain")), None)
    vice = next((player for player in starters if player.get("vice_captain")), None)
    captain_alternative = vice
    lineup_confidence = _confidence(starters, data_quality)
    bench_confidence = _confidence(bench_players, data_quality)
    warnings = [
        "ทีมจาก public API คือทีมที่ประกาศล่าสุด ไม่รวมการแก้ทีมที่ยังไม่ผ่าน deadline",
        "ข่าวสโมสรและ predicted lineup จะมีผลต่อคำแนะนำเมื่อมีหลักฐานที่ยังไม่หมดอายุใน Risk Layer",
    ]
    if risk_layer:
        warnings.extend(str(item) for item in risk_layer.get("warnings", []))
    if any(
        "early_season" in player.get("data_quality_flags", []) for player in squad
    ):
        warnings.append(
            "ข้อมูลยังอยู่ช่วงต้นฤดูกาล โมเดลจึง shrink เข้าหา price/role prior และลด confidence"
        )
    if data_quality.get("is_stale"):
        warnings.insert(0, "ข้อมูลเกิน 24 ชั่วโมง ต้อง refresh ก่อนยืนยันแผน")

    transfer: dict[str, Any]
    if transfer_advisor and transfer_advisor.get("status") == "needs_user_input":
        default_bank = transfer_advisor.get("inputs", {}).get("bank")
        transfer = {
            "status": "needs_user_input",
            "action": "configure",
            "label": "กรอกข้อมูล",
            "headline": "ตั้งค่า Transfer Advisor",
            "confidence": "unavailable",
            "hit_recommended": False,
            "requires_confirmation": [
                "free_transfers",
                "selling_prices",
                "latest_news",
            ],
            "advisor_version": transfer_advisor.get("version"),
            "candidate_count": transfer_advisor.get("candidate_count", 0),
            "reasons": [
                _reason(
                    "fact",
                    (
                        f"FPL เปิดเผยเงินในธนาคารล่าสุด {float(default_bank):.1f}m"
                        if default_bank is not None
                        else "FPL ไม่มีข้อมูลเงินในธนาคารที่ใช้ยืนยันได้"
                    ),
                ),
                _reason(
                    "limitation",
                    "ต้องกรอก Free Transfer และราคาขายจริงก่อนรับรองว่าแผนทำได้",
                ),
            ],
            "alternative": {
                "action": "roll",
                "headline": "เก็บ Free Transfer",
                "reason": "ทางเลือกตั้งต้นจนกว่าข้อมูลราคาและ FT จะครบ",
            },
        }
    else:
        top_transfer = transfer_suggestions[0] if transfer_suggestions else None
        if top_transfer and float(top_transfer.get("xp_next_gain", 0)) >= 2:
            transfer = {
                "status": "consider",
                "action": "consider",
                "label": "พิจารณา",
                "headline": f"{top_transfer['out_name']} → {top_transfer['in_name']}",
                "confidence": "low",
                "out_player_id": top_transfer["out_player_id"],
                "out_name": top_transfer["out_name"],
                "in_player_id": top_transfer["in_player_id"],
                "in_name": top_transfer["in_name"],
                "position": top_transfer["position"],
                "estimated_cost_change": top_transfer["cost_change"],
                "xp_next_gain": top_transfer["xp_next_gain"],
                "xp_horizon_gain": top_transfer["xp_horizon_gain"],
                "hit_recommended": False,
                "requires_confirmation": [
                    "free_transfers",
                    "selling_price",
                    "latest_news",
                ],
                "reasons": [
                    _reason(
                        "estimate",
                        f"โมเดลให้ expected points เพิ่ม {top_transfer['xp_next_gain']:.2f} ใน GW ถัดไป "
                        f"และ {top_transfer['xp_horizon_gain']:.2f} ในช่วงโมเดล",
                    ),
                    _reason(
                        "limitation",
                        "ยังไม่ทราบราคาขายจริงและจำนวน Free Transfer จึงไม่ยืนยันให้ทำทันที",
                    ),
                ],
                "alternative": {
                    "action": "roll",
                    "headline": "เก็บ Free Transfer",
                    "reason": "ทางเลือกปลอดภัยหากงบหรือข่าวไม่ผ่านการยืนยัน",
                },
            }
        else:
            transfer = {
                "status": "ready",
                "action": "roll",
                "label": "เก็บ FT",
                "headline": "เก็บ Free Transfer",
                "confidence": "medium",
                "hit_recommended": False,
                "requires_confirmation": ["latest_news"],
                "reasons": [
                    _reason("estimate", "ยังไม่มี one-transfer upgrade ที่ผ่านเกณฑ์"),
                    _reason("fact", "ระบบไม่เสนอการติดลบโดยไม่มี downside case"),
                ],
                "alternative": None,
            }

    starting_xi = {
        "status": "ready",
        "headline": f"จัด {current_squad['formation']}",
        "confidence": lineup_confidence,
        "formation": current_squad["formation"],
        "xp_starting_xi_with_captain": current_squad["xp_with_captain"],
        "players": starters,
        "squad": squad,
        "reasons": [
            _reason(
                "fact",
                f"เลือกจากผู้เล่น 15 คนที่ FPL เปิดเผยหลัง GW{published_gameweek}",
            ),
            _reason(
                "estimate",
                "เลือก formation ด้วย ranking score ที่รวม expected points และความมั่นใจ",
            ),
            _reason(
                "fact",
                f"Risk Layer ปรับนาทีของผู้เล่น {int((risk_layer or {}).get('adjusted_player_count', 0))} คนจากหลักฐานที่ยังใช้ได้",
            ),
        ],
    }

    captaincy = {
        "status": "ready" if captain and vice else "unavailable",
        "headline": f"{captain['name']} (C)" if captain else "ยังแนะนำไม่ได้",
        "confidence": _confidence(
            [player for player in (captain, vice) if player], data_quality
        ),
        "captain": captain,
        "vice_captain": vice,
        "alternative": (
            {
                "captain": captain_alternative,
                "vice_captain": captain,
                "label": "ทางเลือกปลอดภัย",
            }
            if captain and captain_alternative
            else None
        ),
        "reasons": [
            _reason(
                "estimate",
                (
                    f"{captain['name']} มี expected points {captain['xp_next']:.2f} "
                    f"ช่วง {captain.get('expected_points_range', {}).get('lower', 0):.2f}–"
                    f"{captain.get('expected_points_range', {}).get('upper', 0):.2f} "
                    f"และคาดนาที {captain.get('expected_minutes', 0):.0f}"
                )
                if captain
                else "ไม่มีข้อมูลกัปตัน",
            ),
            _reason("limitation", "ต้องยืนยันข่าวและโอกาสลงก่อน deadline"),
        ],
    }

    outfield_bench = [
        player for player in bench_players if int(player["position_id"]) != 1
    ]
    goalkeeper_bench = next(
        (player for player in bench_players if int(player["position_id"]) == 1), None
    )
    bench = {
        "status": "ready",
        "headline": " → ".join(player["name"] for player in outfield_bench),
        "confidence": bench_confidence,
        "players": bench_players,
        "outfield_order": outfield_bench,
        "goalkeeper": goalkeeper_bench,
        "xp_total": round(sum(float(player["xp_next"]) for player in bench_players), 2),
        "reasons": [
            _reason("estimate", "เรียงตัวสำรองสนามตาม ranking score ถัดไป"),
            _reason("fact", "ผู้รักษาประตูสำรองแสดงแยกจากลำดับผู้เล่นสนาม"),
        ],
    }

    planner_recommendation = (chip_planner or {}).get("recommendation", {})
    planner_chips = (chip_planner or {}).get("chips", {})
    if (chip_planner or {}).get("status") == "ready" and planner_recommendation:
        selected_chip = planner_recommendation.get("chip")
        selected_evaluation = planner_chips.get(selected_chip, {}) if selected_chip else {}
        chip = {
            "status": "ready",
            "action": planner_recommendation.get("action", "save"),
            "chip": selected_chip,
            "label": planner_recommendation.get("label", "เก็บชิป"),
            "headline": planner_recommendation.get(
                "headline", "ยังไม่ใช้ชิปใน Gameweek นี้"
            ),
            "confidence": planner_recommendation.get("confidence", "low"),
            "bench_boost_xp": bench["xp_total"],
            "estimated_gain": planner_recommendation.get("gain", 0.0),
            "opportunity_cost": planner_recommendation.get(
                "opportunity_cost", 0.0
            ),
            "best_visible_gameweek": selected_evaluation.get(
                "best_visible_gameweek"
            ),
            "reasons": planner_recommendation.get("reasons", []),
            "alternative": {
                "chip": None,
                "label": "เก็บชิป",
                "condition": "เลือกแผนสำรองหากข่าวหรือโอกาสลงเปลี่ยนก่อน deadline",
            }
            if selected_chip
            else None,
        }
    else:
        chip = {
            "status": "unavailable",
            "action": "save",
            "chip": None,
            "label": "เก็บชิป",
            "headline": "ยังประเมินชิปไม่ได้",
            "confidence": "unavailable",
            "bench_boost_xp": bench["xp_total"],
            "estimated_gain": 0.0,
            "opportunity_cost": 0.0,
            "reasons": [
                _reason(
                    "limitation",
                    "Multi-GW Chip Planner ไม่มีทีมจริงหรือ projection ที่ใช้ได้",
                )
            ],
            "alternative": None,
        }

    if data_quality.get("is_stale") or (risk_layer or {}).get("status") == "degraded":
        chip.update(status="review_required", action="save", chip=None, label="รอตรวจข้อมูล", headline="ยังไม่ใช้ชิปจนกว่าจะตรวจข้อมูลใหม่", estimated_gain=0.0)
        chip["reasons"] = [_reason("limitation", "ข้อมูลเก่าหรือ Risk Layer ต้องตรวจสอบ จึงพักคำแนะนำใช้ชิป")]

    alternatives = []
    if vice and captain:
        alternatives.append(
            {
                "type": "safe",
                "label": "แผนปลอดภัย",
                "transfer": "roll",
                "captain_id": vice["player_id"],
                "captain_name": vice["name"],
                "detail": "เก็บ FT และสลับรองกัปตันขึ้นเป็นกัปตันหากข่าวตัวเลือกหลักไม่ชัด",
            }
        )
    alternatives.append(
        {
            "type": "model",
            "label": "แผนเน้นเพดาน",
            "transfer": transfer["action"],
            "captain_id": captain["player_id"] if captain else None,
            "captain_name": captain["name"] if captain else None,
            "detail": "ใช้ XI, captain และ bench ตาม ranking score สูงสุด โดยยืนยันข่าวก่อน deadline",
        }
    )

    status = (
        "review_required"
        if data_quality.get("is_stale") or (risk_layer or {}).get("status") == "degraded"
        else "ready"
    )
    overall_confidence = (
        "low" if status == "review_required" else _confidence(starters, data_quality)
    )
    return {
        **base,
        "status": status,
        "confidence": overall_confidence,
        "summary": {
            "headline": f"แผน {target_gameweek['name']} พร้อม Risk Check",
            "detail": "ใช้ทีมจริงที่ประกาศล่าสุด พร้อมแยกข่าวข้อเท็จจริงออกจาก predicted lineup",
        },
        "transfer": transfer,
        "starting_xi": starting_xi,
        "captaincy": captaincy,
        "bench": bench,
        "chip": chip,
        "alternatives": alternatives,
        "warnings": warnings,
    }
