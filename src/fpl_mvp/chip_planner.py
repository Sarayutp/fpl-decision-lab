from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from .models import Player
from .optimizer import (
    POSITION_NAMES,
    optimize_initial_squad,
    select_best_lineup,
    validate_squad,
)


CHIP_PLANNER_VERSION = "chip-planner-1.0"
CHIP_RULES_VERSION = "fpl-2026-27-two-sets"
RULES_CHECKED_AT = "2026-08-30"
CHIP_NAMES = ("bench_boost", "triple_captain", "free_hit", "wildcard")
CHIP_ALIASES = {
    "bboost": "bench_boost",
    "bench_boost": "bench_boost",
    "3xc": "triple_captain",
    "triple_captain": "triple_captain",
    "freehit": "free_hit",
    "free_hit": "free_hit",
    "wildcard": "wildcard",
}
RULE_SOURCES = [
    {
        "title": "What's happening with FPL chips in 2026/27?",
        "url": "https://www.premierleague.com/en/news/4679879/whats-happening-with-fpl-chips-in-202627",
        "publisher": "Premier League",
    },
    {
        "title": "FPL 2026/27 FAQ",
        "url": "https://www.premierleague.com/en/news/4661030",
        "publisher": "Premier League",
    },
]


def _normalise_chip(value: object) -> str | None:
    if value is None:
        return None
    return CHIP_ALIASES.get(str(value).strip().lower())


def _period(gameweek: int) -> int:
    return 1 if gameweek <= 19 else 2


def _gameweek_projection(
    projection: dict[str, Any], gameweek: int, visible_gameweeks: list[int]
) -> dict[str, Any]:
    rows = {
        int(row.get("gameweek")): row
        for row in projection.get("gameweeks", [])
        if row.get("gameweek") is not None
    }
    row = rows.get(gameweek, {})
    remaining_rows = [
        rows[item]
        for item in visible_gameweeks
        if item >= gameweek and item in rows
    ]
    expected = float(row.get("expected_points", row.get("xp", 0.0)))
    ranking = float(row.get("ranking_score", expected))
    expected_minutes = float(
        row.get("expected_minutes", projection.get("expected_minutes", 0.0))
    )
    start_probability = float(row.get("start_probability", projection.get("start_probability", 0.0)))
    fixture_count = int(row.get("fixture_count", len(row.get("opponents", []))))
    interval = row.get("interval", {"lower": 0.0, "upper": 0.0})
    expected_horizon = sum(
        float(item.get("expected_points", item.get("xp", 0.0)))
        for item in remaining_rows
    )
    ranking_horizon = sum(
        float(item.get("ranking_score", item.get("expected_points", 0.0)))
        for item in remaining_rows
    )
    captain_score = expected * (0.70 + 0.30 * start_probability)
    captain_score += 0.06 * float(interval.get("upper", expected))
    original_rows = projection.get("gameweeks", [])
    if original_rows and original_rows[0].get("gameweek") == gameweek:
        captain_score = float(projection.get("captain_score", captain_score))
    flags = [flag for flag in projection.get("data_quality_flags", []) if flag not in {"blank_gameweek", "double_gameweek"}]
    if fixture_count == 0:
        flags.append("blank_gameweek")
    elif fixture_count > 1:
        flags.append("double_gameweek")
    return {
        **projection,
        "expected_points_next": round(expected, 2),
        "expected_points_horizon": round(expected_horizon, 2),
        "xp_next": round(expected, 2),
        "xp_horizon": round(expected_horizon, 2),
        "ranking_score_next": round(ranking, 2),
        "ranking_score_horizon": round(ranking_horizon, 2),
        "captain_score": round(max(0.0, captain_score), 2),
        "captain_eligible": bool(
            expected > 0
            and expected_minutes >= 60
            and start_probability >= 0.65
            and float(projection.get("availability", 0.0)) >= 0.75
        ),
        "expected_minutes": round(expected_minutes, 1),
        "start_probability": start_probability,
        "fixture_count": fixture_count,
        "opponents": row.get("opponents", []),
        "data_quality_flags": flags,
        "expected_points_range": interval,
        "clean_sheet_probability_next": row.get("model_components", {}).get(
            "clean_sheet_probability"
        ),
    }


def _projection_sets(
    projections: list[dict[str, Any]], visible_gameweeks: list[int]
) -> dict[int, list[dict[str, Any]]]:
    return {
        gameweek: [
            _gameweek_projection(projection, gameweek, visible_gameweeks)
            for projection in projections
        ]
        for gameweek in visible_gameweeks
    }


def _lineup_week(
    gameweek: int,
    squad_ids: list[int],
    players: list[Player],
    projections: list[dict[str, Any]],
) -> dict[str, Any]:
    lineup = select_best_lineup(squad_ids, players, projections)
    if not lineup.get("valid"):
        return {
            "gameweek": gameweek,
            "status": "unavailable",
            "violations": lineup.get("violations", []),
        }
    picks = lineup.get("picks", [])
    projections_by_id = {item["player_id"]: item for item in projections}
    for pick in picks:
        item = projections_by_id[pick["player_id"]]
        pick["fixture_count"] = item.get("fixture_count", 0)
        pick["availability"] = item.get("availability", 0)
        pick["opponents"] = item.get("opponents", [])
        pick["expected_minutes_per_fixture"] = round(float(pick.get("expected_minutes") or 0) / max(1, pick["fixture_count"]), 1)
    starters = [item for item in picks if item.get("starter")]
    bench = sorted(
        (item for item in picks if not item.get("starter")),
        key=lambda item: int(item.get("bench_order") or 99),
    )
    captain = next((item for item in starters if item.get("captain")), None)
    vice = next((item for item in starters if item.get("vice_captain")), None)
    bench_xp = round(sum(float(item.get("xp_next", 0.0)) for item in bench), 2)
    captain_xp = round(float((captain or {}).get("xp_next", 0.0)), 2)
    return {
        "gameweek": gameweek,
        "status": "ready",
        "formation": lineup.get("formation"),
        "base_xp_with_captain": lineup.get("xp_with_captain", 0.0),
        "starting_xi_xp": round(
            sum(float(item.get("xp_next", 0.0)) for item in starters), 2
        ),
        "bench_boost_gain": bench_xp,
        "triple_captain_gain": captain_xp,
        "captain": captain,
        "vice_captain": vice,
        "bench": bench,
        "picks": picks,
        "all_15_legal": len(picks) == 15 and len(starters) == 11 and len(bench) == 4,
        "all_15_have_fixture": all(
            "blank_gameweek" not in item.get("data_quality_flags", []) for item in picks
        ),
        "all_15_likely_available": all(
            float(item.get("start_probability") or 0.0) >= 0.65
            and float(item.get("availability") or 0.0) >= 0.5
            and float(item.get("expected_minutes") or 0.0) > 0
            for item in picks
        ),
    }


def _chip_state(
    *,
    target_gameweek: int,
    chip_history: Iterable[dict[str, Any]],
    active_chip: str | None,
) -> dict[str, Any]:
    current_period = _period(target_gameweek)
    uses: dict[str, list[int]] = {name: [] for name in CHIP_NAMES}
    for item in chip_history:
        chip = _normalise_chip(item.get("name"))
        event = item.get("event")
        if chip and event is not None:
            uses[chip].append(int(event))
    active = _normalise_chip(active_chip)
    state: dict[str, Any] = {}
    for chip in CHIP_NAMES:
        used_in_period = sorted(
            event for event in uses[chip] if _period(event) == current_period
        )
        blocked_reasons: list[str] = []
        if used_in_period:
            blocked_reasons.append(
                f"ใช้ {chip.replace('_', ' ')} ชุดครึ่งฤดูกาลนี้แล้วใน GW{used_in_period[-1]}"
            )
        if chip in {"free_hit", "wildcard"} and target_gameweek == 1:
            blocked_reasons.append("ชิปนี้ใช้ไม่ได้ใน GW1")
        if chip == "free_hit" and target_gameweek - 1 in uses[chip]:
            blocked_reasons.append("Free Hit ใช้สอง Gameweek ติดต่อกันไม่ได้")
        if active and active != chip:
            blocked_reasons.append(
                f"มี {active.replace('_', ' ')} รอใช้งานอยู่ และใช้ได้เพียงหนึ่งชิปต่อ Gameweek"
            )
        state[chip] = {
            "available": not blocked_reasons,
            "period": current_period,
            "used_events": sorted(uses[chip]),
            "used_in_current_period": used_in_period,
            "pending_for_target": active == chip,
            "blocked_reasons": blocked_reasons,
            "source": "FPL public manager history",
        }
    return state


def _optimized_squad_for_week(
    players: list[Player],
    projections: list[dict[str, Any]],
    *,
    budget_tenths: int,
    single_gameweek: bool = False,
) -> dict[str, Any] | None:
    try:
        result = optimize_initial_squad(
            players,
            projections,
            budget_tenths=budget_tenths,
            time_limit_seconds=5.0,
            objective_mode="single_gameweek" if single_gameweek else "balanced",
        )
    except (RuntimeError, ValueError):
        return None
    return result if result.get("validation", {}).get("valid") else None


def _chip_evaluations(
    *,
    weekly: list[dict[str, Any]],
    chip_state: dict[str, Any],
    optimized: dict[int, dict[str, Any] | None],
    free_hit_optimized: dict[int, dict[str, Any] | None],
    projection_sets: dict[int, list[dict[str, Any]]],
    players: list[Player],
    current_squad_ids: list[int],
) -> dict[str, dict[str, Any]]:
    ready_weeks = [item for item in weekly if item.get("status") == "ready"]
    current = ready_weeks[0] if ready_weeks else {}
    current_picks = current.get("picks", [])
    confidence_ready = bool(current_picks) and (
        sum(
            item.get("projection_confidence") in {"medium", "high"}
            for item in current_picks
        )
        / len(current_picks)
        >= 0.7
    )
    by_gameweek = {int(item["gameweek"]): item for item in ready_weeks}

    gains: dict[str, dict[int, float]] = {
        "bench_boost": {
            int(item["gameweek"]): float(item["bench_boost_gain"])
            for item in ready_weeks
        },
        "triple_captain": {
            int(item["gameweek"]): float(item["triple_captain_gain"])
            for item in ready_weeks
        },
        "free_hit": {},
        "wildcard": {},
    }
    optimized_ids: dict[int, list[int]] = {}
    for gameweek, result in free_hit_optimized.items():
        owned = by_gameweek.get(gameweek)
        if result and owned:
            gains["free_hit"][gameweek] = round(
                float(result.get("xp_with_captain", 0.0))
                - float(owned.get("base_xp_with_captain", 0.0)),
                2,
            )
    optimized_ids = {
        gameweek: [int(item["player_id"]) for item in result.get("picks", [])]
        for gameweek, result in optimized.items() if result
    }

    visible_gameweeks = sorted(by_gameweek)
    for gameweek in visible_gameweeks:
        ids = optimized_ids.get(gameweek)
        if not ids:
            continue
        owned_total = 0.0
        optimized_total = 0.0
        for future_gameweek in visible_gameweeks:
            if future_gameweek < gameweek:
                continue
            owned_week = by_gameweek.get(future_gameweek, {})
            optimized_week = _lineup_week(
                future_gameweek,
                ids,
                players,
                projection_sets[future_gameweek],
            )
            owned_total += float(owned_week.get("base_xp_with_captain", 0.0))
            optimized_total += float(
                optimized_week.get("base_xp_with_captain", 0.0)
            )
        gains["wildcard"][gameweek] = round(optimized_total - owned_total, 2)

    evaluations: dict[str, dict[str, Any]] = {}
    for chip in CHIP_NAMES:
        state = chip_state[chip]
        chip_gains = {
            gameweek: gain for gameweek, gain in gains[chip].items()
            if _period(gameweek) == state["period"]
            and not (chip in {"free_hit", "wildcard"} and gameweek == 1)
        }
        current_gameweek = int(current.get("gameweek", 0)) if current else 0
        current_gain = float(chip_gains.get(current_gameweek, 0.0))
        best_gameweek = (
            max(chip_gains, key=lambda gameweek: chip_gains[gameweek])
            if chip_gains
            else None
        )
        best_gain = float(chip_gains.get(best_gameweek, 0.0)) if best_gameweek else 0.0
        opportunity_cost = max(0.0, best_gain - current_gain)
        reasons: list[dict[str, str]] = []
        if not state["available"]:
            action = "unavailable"
            reasons.extend(
                {"kind": "rule", "text": reason}
                for reason in state["blocked_reasons"]
            )
        else:
            action = "save"
            reasons.append(
                {
                    "kind": "estimate",
                    "text": f"กำไรคาดการณ์ GW ปัจจุบัน {current_gain:.2f} แต้ม; ดีสุดที่มองเห็น GW{best_gameweek} {best_gain:.2f} แต้ม",
                }
            )
            reasons.append(
                {
                    "kind": "opportunity_cost",
                    "text": f"ค่าเสียโอกาสในช่วงที่มองเห็น {opportunity_cost:.2f} แต้ม",
                }
            )
            close_to_best = current_gain >= best_gain - 0.75
            if chip == "triple_captain":
                captain = current.get("captain") or {}
                robust_minutes = (
                    float(captain.get("expected_minutes_per_fixture") or 0.0) >= 75
                    and float(captain.get("start_probability") or 0.0) >= 0.85
                )
                if current_gain >= 7.0 and close_to_best and robust_minutes:
                    action = "use_now"
                reasons.append(
                    {
                        "kind": "risk",
                        "text": f"กัปตัน {captain.get('name', 'ไม่ทราบ')} เพดานช่วงคะแนน {float((captain.get('expected_points_range') or {}).get('upper', 0)):.2f}, {captain.get('fixture_count', 0)} นัด, คาดนาที {float(captain.get('expected_minutes') or 0):.0f}, ตัวจริง {float(captain.get('start_probability') or 0) * 100:.0f}% — ต้องยืนยันข่าวก่อน deadline",
                    }
                )
            elif chip == "bench_boost":
                if (
                    current_gain >= 16.0
                    and close_to_best
                    and bool(current.get("all_15_have_fixture"))
                    and bool(current.get("all_15_likely_available"))
                ):
                    action = "use_now"
                reasons.append(
                    {
                        "kind": "risk",
                        "text": "ต้องมีทีมถูกกฎ 15 คนและสำรองพร้อมลงทั้ง 4 คน; gain คือคะแนนม้านั่ง ยังไม่หักแต้มที่อาจได้ผ่าน autosub ปกติ",
                    }
                )
            elif chip == "free_hit":
                if current_gain >= 8.0 and close_to_best and confidence_ready:
                    action = "use_now"
                reasons.append(
                    {
                        "kind": "risk",
                        "text": "กำไรเป็นค่าประมาณจากราคาปัจจุบัน; ต้องมี projection ระดับ medium/high อย่างน้อย 70% และยืนยันราคาขายจริง",
                    }
                )
            else:
                if current_gain >= 18.0 and close_to_best and confidence_ready:
                    action = "use_now"
                reasons.append(
                    {
                        "kind": "risk",
                        "text": "Wildcard เปลี่ยนถาวร; gain เทียบทีมเดิมไม่ย้ายตัว ไม่ได้หักกำไรที่ทำได้ด้วย FT ปกติ ต้องมี confidence medium/high ≥70% และยืนยันราคาขาย/ข่าว",
                    }
                )
        scenario = (free_hit_optimized if chip == "free_hit" else optimized).get(current_gameweek) if chip in {"free_hit", "wildcard"} else None
        evaluations[chip] = {
            "chip": chip,
            "available": state["available"],
            "action": action,
            "current_gain": round(current_gain, 2),
            "best_visible_gameweek": best_gameweek,
            "best_visible_gain": round(best_gain, 2),
            "opportunity_cost": round(opportunity_cost, 2),
            "confidence": "low",
            "confidence_gate_passed": confidence_ready,
            "comparison_period": state["period"],
            "gain_basis": "remaining_horizon_vs_unchanged_squad" if chip == "wildcard" else "one_gameweek_increment",
            "scenario_status": "unavailable" if chip in {"free_hit", "wildcard"} and scenario is None else "ready",
            "scenario": {
                "squad_ids": [item["player_id"] for item in scenario["picks"]],
                "picks": scenario["picks"],
                "cost": scenario["cost"],
                "budget": scenario["budget"],
                "validation": scenario["validation"],
                "objective_mode": scenario["objective_mode"],
                "permanent": chip == "wildcard",
                "restores_squad_ids": current_squad_ids if chip == "free_hit" else None,
                "requires_selling_price_confirmation": True,
            } if scenario else None,
            "used_events": state["used_events"],
            "reasons": reasons,
            "weekly_gains": [
                {"gameweek": gameweek, "gain": round(value, 2)}
                for gameweek, value in sorted(chip_gains.items())
            ],
        }

    use_now = [item for item in evaluations.values() if item["action"] == "use_now"]
    if len(use_now) > 1:
        chosen = max(
            use_now,
            key=lambda item: (
                float(item["current_gain"]) - float(item["opportunity_cost"]),
                float(item["current_gain"]),
            ),
        )
        for item in use_now:
            if item is chosen:
                continue
            item["action"] = "save"
            item["reasons"].append(
                {
                    "kind": "rule",
                    "text": f"เก็บไว้เพราะระบบเลือก {chosen['chip'].replace('_', ' ')} เป็นชิปเดียวของ Gameweek นี้",
                }
            )
    return evaluations


def _remaining_xp(
    projection: dict[str, Any], planned_gameweek: int
) -> float:
    return sum(
        float(row.get("expected_points", row.get("xp", 0.0)))
        for row in projection.get("gameweeks", [])
        if int(row.get("gameweek", 0)) >= planned_gameweek
    )


def _best_path(
    *,
    current_squad_ids: list[int],
    players: list[Player],
    projections: list[dict[str, Any]],
    visible_gameweeks: list[int],
    bank_tenths: int,
    excluded_first_move: tuple[int, int] | None = None,
) -> dict[str, Any]:
    player_by_id = {player.id: player for player in players}
    projection_by_id = {
        int(projection["player_id"]): projection for projection in projections
    }
    squad = list(current_squad_ids)
    bank = bank_tenths
    initial_capacity = sum(player_by_id[item].now_cost for item in squad) + bank
    moves: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    weekly: list[dict[str, Any]] = []
    sets = _projection_sets(projections, visible_gameweeks)
    free_transfers = 1
    excluded_incoming = excluded_first_move[1] if excluded_first_move else None

    def lineup_total(ids: list[int], start: int) -> float:
        return sum(float(select_best_lineup(ids, players, sets[gw]).get("xp_with_captain", 0)) for gw in visible_gameweeks if gw >= start)

    baseline_total = lineup_total(squad, visible_gameweeks[0])
    for planned_gameweek in visible_gameweeks:
        selected = set(squad)
        team_counts = Counter(player_by_id[item].team for item in squad)
        best: tuple[float, Player, Player] | None = None
        candidates: list[tuple[float, Player, Player]] = []
        for outgoing_id in squad if len(moves) < 2 else []:
            outgoing = player_by_id[outgoing_id]
            if not outgoing.can_transact:
                continue
            outgoing_projection = projection_by_id.get(outgoing_id)
            if not outgoing_projection:
                continue
            outgoing_remaining = _remaining_xp(
                outgoing_projection, planned_gameweek
            )
            for incoming in players:
                if (
                    incoming.id in selected
                    or incoming.element_type != outgoing.element_type
                    or incoming.now_cost > outgoing.now_cost + bank
                    or not incoming.can_select
                    or not incoming.can_transact
                    or incoming.status in {"u", "n"}
                    or incoming.id == excluded_incoming
                ):
                    continue
                if (
                    incoming.team != outgoing.team
                    and team_counts[incoming.team] >= 3
                ):
                    continue
                incoming_projection = projection_by_id.get(incoming.id)
                if (
                    not incoming_projection
                    or float(incoming_projection.get("availability", 0.0)) < 0.5
                ):
                    continue
                gain = _remaining_xp(incoming_projection, planned_gameweek)
                gain -= outgoing_remaining
                if gain <= 0.25:
                    continue
                candidate = (gain, outgoing, incoming)
                candidates.append(candidate)
        before_total = lineup_total(squad, planned_gameweek)
        for _, outgoing, incoming in sorted(candidates, key=lambda item: item[0], reverse=True)[:30]:
            trial = [incoming.id if item == outgoing.id else item for item in squad]
            gain = lineup_total(trial, planned_gameweek) - before_total
            if gain > 0.75 and (best is None or gain > best[0]):
                best = (gain, outgoing, incoming)
        if best is not None:
            gain, outgoing, incoming = best
            bank += outgoing.now_cost - incoming.now_cost
            squad[squad.index(outgoing.id)] = incoming.id
            moves.append({
                "gameweek": planned_gameweek,
                "out_player_id": outgoing.id, "out_name": outgoing.web_name,
                "in_player_id": incoming.id, "in_name": incoming.web_name,
                "position": POSITION_NAMES[outgoing.element_type],
                "price_change": round((incoming.now_cost - outgoing.now_cost) / 10, 1),
                "estimated_horizon_gain": round(gain, 2),
                "bank_after": round(bank / 10, 1),
            })
        validation = validate_squad(squad, players, budget_tenths=initial_capacity)
        transfer_count = 1 if best is not None else 0
        week = select_best_lineup(squad, players, sets[planned_gameweek])
        weekly.append({
            "gameweek": planned_gameweek, "squad_ids": list(squad),
            "action": "transfer" if best else "roll",
            "formation": week.get("formation"),
            "captain_id": week.get("captain_id"),
            "base_xp_with_captain": week.get("xp_with_captain", 0),
        })
        checkpoint = {
            "gameweek": planned_gameweek,
            "bank": round(bank / 10, 1),
            "squad_cost_current_prices": round(
                sum(player_by_id[item].now_cost for item in squad) / 10, 1
            ),
            "budget_capacity_current_prices": round(initial_capacity / 10, 1),
            "legal": bool(validation["valid"] and bank >= 0),
            "violations": validation["violations"],
            "free_transfers_before": free_transfers,
            "free_transfers_next": min(5, free_transfers - transfer_count + 1),
            "hit_cost": 0,
        }
        checkpoints.append(checkpoint)
        free_transfers = checkpoint["free_transfers_next"]
    return {
        "status": "needs_confirmation" if moves else "roll",
        "moves": moves,
        "estimated_horizon_gain": round(sum(float(item["base_xp_with_captain"]) for item in weekly) - baseline_total, 2),
        "gain_basis": "legal_XI_plus_captain_vs_roll",
        "baseline_roll_xp": round(baseline_total, 2),
        "weekly": weekly,
        "budget_checkpoints": checkpoints,
        "valid": all(item["legal"] for item in checkpoints),
        "resulting_squad_ids": squad,
        "price_basis": "current FPL prices, not manager-specific selling prices",
        "certified_affordable": False,
        "starting_free_transfers_assumed": 1,
        "requires_confirmation": ["free_transfers", "selling_prices", "latest_news"],
        "excluded_incoming_player_id": excluded_incoming,
    }


def build_chip_planner(
    *,
    current_squad_ids: Iterable[int],
    players: list[Player],
    projections: list[dict[str, Any]],
    target_gameweek: int,
    chip_history: Iterable[dict[str, Any]],
    active_chip: str | None = None,
    bank_tenths: int | None = None,
    budget_tenths: int | None = None,
    generated_at: str,
    season: str = "2026-27",
) -> dict[str, Any]:
    """Build a read-only 3–6 GW chip and transfer-path decision contract."""

    squad_ids = [int(item) for item in current_squad_ids]
    projection_gameweeks = sorted(
        {
            int(row["gameweek"])
            for projection in projections
            for row in projection.get("gameweeks", [])
            if row.get("gameweek") is not None
            and int(row["gameweek"]) >= target_gameweek
            and int(row["gameweek"]) <= 38
        }
    )[:6]
    rules = {
        "version": CHIP_RULES_VERSION,
        "checked_at": RULES_CHECKED_AT,
        "season": "2026/27",
        "sets_per_season": 2,
        "first_set_gameweeks": [1, 19],
        "second_set_gameweeks": [20, 38],
        "one_chip_per_gameweek": True,
        "first_set_carries_over": False,
        "free_hit_consecutive_allowed": False,
        "wildcard_and_free_hit_available_gameweek_1": False,
        "sources": RULE_SOURCES,
    }
    validation = validate_squad(squad_ids, players, budget_tenths=100_000)
    missing_projections = set(squad_ids) - {int(item["player_id"]) for item in projections}
    limitations = list(validation["violations"])
    if season not in {"2026-27", "2026/27"}:
        limitations.append("ยังไม่ได้ยืนยันกติกาชิปสำหรับฤดูกาลนี้")
    if missing_projections:
        limitations.append("ผู้เล่นในทีมจริงมี projection ไม่ครบ")
    if not projection_gameweeks or projection_gameweeks[0] != target_gameweek:
        limitations.append("ไม่มี projection ของ Gameweek เป้าหมาย")
    if limitations:
        return {
            "version": CHIP_PLANNER_VERSION,
            "status": "unavailable",
            "generated_at": generated_at,
            "rules": rules,
            "horizon": {"gameweeks": projection_gameweeks, "count": len(projection_gameweeks)},
            "limitations": limitations,
        }

    projection_sets = _projection_sets(projections, projection_gameweeks)
    weekly = [
        _lineup_week(
            gameweek, squad_ids, players, projection_sets[gameweek]
        )
        for gameweek in projection_gameweeks
    ]
    state = _chip_state(
        target_gameweek=target_gameweek,
        chip_history=chip_history,
        active_chip=active_chip,
    )
    player_by_id = {player.id: player for player in players}
    current_cost = sum(player_by_id[item].now_cost for item in squad_ids)
    safe_bank = max(0, int(bank_tenths or 0))
    optimization_budget = min(current_cost, int(budget_tenths)) + safe_bank if budget_tenths and budget_tenths > 0 else current_cost + safe_bank
    optimized = {
        gameweek: _optimized_squad_for_week(
            players,
            projection_sets[gameweek],
            budget_tenths=optimization_budget,
        )
        for gameweek in projection_gameweeks
    }
    free_hit_optimized = {
        gameweek: _optimized_squad_for_week(
            players, projection_sets[gameweek], budget_tenths=optimization_budget,
            single_gameweek=True,
        )
        for gameweek in projection_gameweeks
    }
    chips = _chip_evaluations(
        weekly=weekly,
        chip_state=state,
        optimized=optimized,
        free_hit_optimized=free_hit_optimized,
        projection_sets=projection_sets,
        players=players,
        current_squad_ids=squad_ids,
    )
    use_now = next(
        (item for item in chips.values() if item["action"] == "use_now"), None
    )
    recommendation = (
        {
            "action": "use_now",
            "chip": use_now["chip"],
            "label": f"ใช้ {use_now['chip'].replace('_', ' ').title()}",
            "headline": f"ใช้ใน GW{target_gameweek} ตามเงื่อนไขก่อน deadline",
            "confidence": use_now["confidence"],
            "gain": use_now["current_gain"],
            "opportunity_cost": use_now["opportunity_cost"],
            "reasons": use_now["reasons"],
        }
        if use_now
        else {
            "action": "save",
            "chip": None,
            "label": "เก็บชิป",
            "headline": "ยังไม่ใช้ชิปใน Gameweek นี้",
            "confidence": "low",
            "gain": 0.0,
            "opportunity_cost": 0.0,
            "reasons": [
                {
                    "kind": "estimate",
                    "text": "ยังไม่มีชิปที่ผ่านทั้งเกณฑ์ผลตอบแทน ความพร้อม และค่าเสียโอกาส",
                }
            ],
        }
    )
    main_path = _best_path(
        current_squad_ids=squad_ids,
        players=players,
        projections=projections,
        visible_gameweeks=projection_gameweeks,
        bank_tenths=safe_bank,
    )
    first_move = (
        (
            int(main_path["moves"][0]["out_player_id"]),
            int(main_path["moves"][0]["in_player_id"]),
        )
        if main_path["moves"]
        else None
    )
    alternative_path = _best_path(
        current_squad_ids=squad_ids,
        players=players,
        projections=projections,
        visible_gameweeks=projection_gameweeks,
        bank_tenths=safe_bank,
        excluded_first_move=first_move,
    )
    return {
        "version": CHIP_PLANNER_VERSION,
        "status": "ready",
        "generated_at": generated_at,
        "target_gameweek": target_gameweek,
        "horizon": {
            "gameweeks": projection_gameweeks,
            "count": len(projection_gameweeks),
            "visibility_warning": f"เปรียบเทียบเฉพาะ GW{projection_gameweeks[0]}–GW{projection_gameweeks[-1]} ยังไม่เห็นโอกาสหลังช่วงโมเดล",
        },
        "rules": rules,
        "chip_state": state,
        "weekly": weekly,
        "chips": chips,
        "recommendation": recommendation,
        "transfer_paths": {
            "main": main_path,
            "alternative": alternative_path,
            "regular_transfers_only": True,
        },
        "assumptions": {
            "selling_prices": "ใช้ราคาปัจจุบันเป็นค่าประมาณ",
            "free_transfers": "จำลองเริ่มต้น 1 FT และได้เพิ่ม 1 FT ต่อ GW; ยังต้องยืนยัน FT และราคาขายจริง",
            "future_news": "นาทีและโอกาสตัวจริงมาจาก Risk Layer ณ เวลาสร้าง snapshot",
            "wildcard_free_hit_budget": round(optimization_budget / 10, 1),
        },
        "safety": {
            "read_only": True,
            "applies_transfers": False,
            "activates_chips": False,
            "one_chip_recommendation": sum(
                item["action"] == "use_now" for item in chips.values()
            )
            <= 1,
        },
    }
