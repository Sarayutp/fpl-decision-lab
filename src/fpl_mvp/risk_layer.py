from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from .models import Player


RISK_LAYER_VERSION = "risk-layer-1.0"
NEWS_STALE_AFTER_HOURS = 24
OFFICIAL_INJURY_URL = "https://www.premierleague.com/en/latest-player-injuries/"
FPL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"

ALLOWED_CATEGORIES = {
    "injury",
    "rotation",
    "suspension",
    "travel",
    "lineup",
    "availability",
    "unavailable",
}
ALLOWED_SOURCE_TIERS = {
    "official_club",
    "official_competition",
    "predicted_lineup",
    "user_override",
}
SOURCE_PRECEDENCE = {
    "official_club": 4,
    "official_competition": 3,
    "user_override": 2,
    "predicted_lineup": 1,
}
STATUS_LABELS = {
    "a": "Available",
    "d": "Doubtful",
    "i": "Injured",
    "s": "Suspended",
    "u": "Unavailable",
    "n": "Not available for selection",
}


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _timestamp(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _age_hours(now: datetime, timestamp: datetime | None) -> float | None:
    if timestamp is None:
        return None
    return round(max(0.0, (now - timestamp).total_seconds() / 3_600), 2)


def _valid_url(value: object) -> bool:
    parsed = urlparse(str(value or ""))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def load_risk_evidence(path: Path) -> tuple[dict[str, Any] | None, str, list[str]]:
    """Load optional curated evidence without making it a pipeline dependency."""

    if not path.exists():
        return None, "not_configured", [
            "Curated club news is not configured; using current FPL status and model uncertainty."
        ]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return None, "invalid", [
            f"Curated risk evidence could not be loaded ({error}); using FPL status fallback."
        ]
    if not isinstance(payload, dict) or not isinstance(payload.get("evidence", []), list):
        return None, "invalid", [
            "Curated risk evidence has an invalid shape; using FPL status fallback."
        ]
    return payload, "loaded", []


def _fpl_category(player: Player) -> str:
    if player.status == "s":
        return "suspension"
    if player.status in {"i", "d"}:
        return "injury"
    if player.status in {"u", "n"}:
        return "unavailable"
    return "availability"


def _fpl_evidence(
    players: Iterable[Player],
    *,
    generated_at: datetime,
    observed_at: datetime,
    target_gameweek: int | None,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    observed_age = _age_hours(generated_at, observed_at)
    source_fresh = observed_age is not None and observed_age <= NEWS_STALE_AFTER_HOURS
    for player in players:
        if (
            player.status == "a"
            and player.chance_of_playing_next_round is None
            and not player.news
        ):
            continue
        published_at = player.news_added or observed_at
        content_age = _age_hours(generated_at, published_at)
        summary = player.news.strip() or (
            f"FPL status: {STATUS_LABELS.get(player.status, player.status)}"
        )
        evidence.append(
            {
                "id": f"fpl-{player.id}-{published_at.isoformat()}",
                "player_id": player.id,
                "player_name": player.web_name,
                "category": _fpl_category(player),
                "claim_type": "fact",
                "source_tier": "official_competition",
                "source_label": "FPL Public API",
                "source_url": FPL_BOOTSTRAP_URL,
                "summary": summary,
                "published_at": published_at.isoformat(),
                "observed_at": observed_at.isoformat(),
                "age_hours": observed_age,
                "content_age_hours": content_age,
                "freshness": "fresh" if source_fresh else "stale",
                "effective_gameweek": target_gameweek,
                "expires_gameweek": target_gameweek,
                "active": True,
                "applied_in_base_model": True,
                "adjustment": {
                    "availability_factor": (
                        player.chance_of_playing_next_round / 100
                        if player.chance_of_playing_next_round is not None
                        else {"a": 1.0, "d": 0.75, "i": 0.10, "s": 0.05}.get(
                            player.status, 0.0
                        )
                    )
                },
                "validation_errors": [],
            }
        )
    return evidence


def _normalise_curated_evidence(
    raw: object,
    *,
    index: int,
    player_by_id: dict[int, Player],
    generated_at: datetime,
    target_gameweek: int | None,
) -> dict[str, Any]:
    item = raw if isinstance(raw, dict) else {}
    errors: list[str] = []
    player_id = int(_number(item.get("player_id"), -1))
    player = player_by_id.get(player_id)
    if player is None:
        errors.append("unknown player_id")

    category = str(item.get("category") or "availability")
    if category not in ALLOWED_CATEGORIES:
        errors.append("invalid category")

    source_tier = str(item.get("source_tier") or "user_override")
    if source_tier not in ALLOWED_SOURCE_TIERS:
        errors.append("invalid source_tier")

    claim_type = str(item.get("claim_type") or "inference")
    if source_tier in {"predicted_lineup", "user_override"}:
        claim_type = "inference"
    elif claim_type not in {"fact", "inference"}:
        errors.append("claim_type must be fact or inference")

    summary = str(item.get("summary") or "").strip()
    if not summary:
        errors.append("summary is required")

    source_url = str(item.get("source_url") or "").strip()
    if not _valid_url(source_url):
        errors.append("source_url must be an http(s) URL")

    published_at = _timestamp(item.get("published_at"))
    if published_at is None:
        errors.append("published_at is required")
    elif published_at > generated_at:
        errors.append("published_at cannot be in the future")

    effective_gameweek = int(
        _number(item.get("effective_gameweek"), target_gameweek or -1)
    )
    expires_gameweek = int(_number(item.get("expires_gameweek"), -1))
    if expires_gameweek < 1:
        errors.append("expires_gameweek is required")
    if effective_gameweek > expires_gameweek > 0:
        errors.append("expires_gameweek precedes effective_gameweek")

    expires_at = _timestamp(item.get("expires_at"))
    age = _age_hours(generated_at, published_at)
    stale = age is None or age > NEWS_STALE_AFTER_HOURS
    expired = bool(
        (target_gameweek is not None and expires_gameweek > 0 and target_gameweek > expires_gameweek)
        or (expires_at is not None and generated_at > expires_at)
    )
    not_yet_effective = bool(
        target_gameweek is not None and effective_gameweek > target_gameweek
    )

    adjustment_raw = item.get("adjustment")
    adjustment = adjustment_raw if isinstance(adjustment_raw, dict) else {}
    cleaned_adjustment: dict[str, float] = {}
    limits = {
        "expected_minutes_override": (0.0, 90.0),
        "expected_minutes_cap": (0.0, 90.0),
        "expected_minutes_delta": (-90.0, 90.0),
        "start_probability_override": (0.0, 1.0),
        "start_probability_cap": (0.0, 1.0),
        "start_probability_delta": (-1.0, 1.0),
    }
    for key, (minimum, maximum) in limits.items():
        if adjustment.get(key) is None:
            continue
        try:
            value = float(adjustment[key])
        except (TypeError, ValueError):
            errors.append(f"{key} must be numeric")
            continue
        if not minimum <= value <= maximum:
            errors.append(f"{key} is outside its allowed range")
            continue
        cleaned_adjustment[key] = value

    evidence_id = str(item.get("id") or f"curated-{index + 1}-{player_id}")
    return {
        "id": evidence_id,
        "player_id": player_id,
        "player_name": player.web_name if player else f"Player {player_id}",
        "category": category,
        "claim_type": claim_type,
        "source_tier": source_tier,
        "source_label": str(item.get("source_label") or source_tier.replace("_", " ").title()),
        "source_url": source_url,
        "summary": summary,
        "reason": str(item.get("reason") or "").strip() or None,
        "published_at": published_at.isoformat() if published_at else None,
        "observed_at": generated_at.isoformat(),
        "age_hours": age,
        "content_age_hours": age,
        "freshness": "stale" if stale else "fresh",
        "effective_gameweek": effective_gameweek,
        "expires_gameweek": expires_gameweek if expires_gameweek > 0 else None,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "active": not errors and not stale and not expired and not not_yet_effective,
        "expired": expired,
        "not_yet_effective": not_yet_effective,
        "applied_in_base_model": False,
        "adjustment": cleaned_adjustment,
        "validation_errors": errors,
    }


def _adjust_projection(
    projection: dict[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    adjusted = deepcopy(projection)
    baseline_minutes = _number(projection.get("expected_minutes"))
    baseline_start = _number(projection.get("start_probability"))
    adjustment = evidence.get("adjustment", {})

    minutes = baseline_minutes
    if "expected_minutes_override" in adjustment:
        minutes = _number(adjustment["expected_minutes_override"])
    if "expected_minutes_cap" in adjustment:
        minutes = min(minutes, _number(adjustment["expected_minutes_cap"]))
    minutes += _number(adjustment.get("expected_minutes_delta"))

    start = baseline_start
    if "start_probability_override" in adjustment:
        start = _number(adjustment["start_probability_override"])
    if "start_probability_cap" in adjustment:
        start = min(start, _number(adjustment["start_probability_cap"]))
    start += _number(adjustment.get("start_probability_delta"))

    minutes = _clamp(minutes, 0.0, 90.0)
    start = _clamp(start, 0.0, 1.0)
    if evidence.get("source_tier") == "predicted_lineup":
        minutes = _clamp(minutes, max(0.0, baseline_minutes - 15), min(90.0, baseline_minutes + 10))
        start = _clamp(start, max(0.0, baseline_start - 0.15), min(1.0, baseline_start + 0.10))

    minutes_factor = (
        minutes / baseline_minutes
        if baseline_minutes > 0
        else (1.0 if minutes == 0 else 0.0)
    )
    gameweeks = adjusted.get("gameweeks", [])
    if gameweeks:
        row = gameweeks[0]
        baseline_points = _number(row.get("expected_points", row.get("xp")))
        baseline_row_minutes = _number(row.get("expected_minutes"))
        if baseline_minutes > 0:
            expected_points = baseline_points * minutes_factor
            expected_row_minutes = baseline_row_minutes * minutes_factor
        else:
            rate = _number(projection.get("model_inputs", {}).get("projected_points_per_90"))
            fixture_factor = _number(
                row.get("model_components", {}).get("average_fixture_factor"), 1.0
            )
            fixture_weight = 1.0 + 0.9 * max(0, int(row.get("fixture_count", 1)) - 1)
            expected_points = rate * minutes / 90 * fixture_factor * fixture_weight
            expected_row_minutes = minutes * fixture_weight
        expected_points = round(max(0.0, expected_points), 2)
        row["expected_points"] = expected_points
        row["xp"] = expected_points
        row["expected_minutes"] = round(expected_row_minutes, 1)
        row["start_probability"] = round(start, 2)
        confidence_score = _number(adjusted.get("confidence_score"), 0.1)
        interval = row.get("interval", {"lower": 0.0, "upper": expected_points})
        interval_factor = expected_points / baseline_points if baseline_points > 0 else 1.0
        row["interval"] = {
            "lower": round(max(0.0, _number(interval.get("lower")) * interval_factor), 2),
            "upper": round(max(expected_points, _number(interval.get("upper")) * interval_factor), 2),
        }
        row["ranking_score"] = round(
            expected_points * (0.82 + 0.18 * confidence_score)
            + 0.04 * row["interval"]["upper"],
            2,
        )
        row.setdefault("model_components", {})["risk_layer"] = {
            "evidence_id": evidence["id"],
            "baseline_expected_points": round(baseline_points, 2),
            "adjusted_expected_points": expected_points,
        }

    expected_next = _number(gameweeks[0].get("expected_points")) if gameweeks else 0.0
    ranking_next = _number(gameweeks[0].get("ranking_score")) if gameweeks else 0.0
    expected_horizon = round(sum(_number(row.get("expected_points")) for row in gameweeks), 2)
    ranking_horizon = round(sum(_number(row.get("ranking_score")) for row in gameweeks), 2)
    previous_value = _number(projection.get("value_score"))
    previous_ranking_horizon = _number(projection.get("ranking_score_horizon"))
    implied_price = previous_ranking_horizon / previous_value if previous_value > 0 else 0.0

    adjusted.update(
        {
            "expected_minutes": round(minutes, 2),
            "start_probability": round(start, 2),
            "expected_points_next": expected_next,
            "xp_next": expected_next,
            "expected_points_horizon": expected_horizon,
            "xp_horizon": expected_horizon,
            "ranking_score_next": ranking_next,
            "ranking_score_horizon": ranking_horizon,
            "value_score": round(ranking_horizon / implied_price, 2) if implied_price else previous_value,
            "expected_points_range": gameweeks[0].get("interval") if gameweeks else {"lower": 0.0, "upper": 0.0},
            "captain_score": round(_number(projection.get("captain_score")) * minutes_factor, 2),
            "captain_eligible": bool(
                minutes >= 60 and start >= 0.65 and expected_next > 0
            ),
        }
    )
    adjusted["expected_minutes_range"] = {
        "lower": round(max(0.0, minutes - 12), 1),
        "upper": round(min(90.0, minutes + 12), 1),
    }
    if evidence.get("claim_type") == "inference":
        adjusted["projection_confidence"] = "low"
        adjusted["confidence_score"] = min(_number(adjusted.get("confidence_score"), 0.1), 0.49)
    if evidence.get("category") in {"injury", "suspension", "unavailable"} and minutes < 45:
        adjusted["risk"] = "high"
    elif evidence.get("category") in {"rotation", "travel", "lineup"}:
        adjusted["risk"] = "medium" if adjusted.get("risk") == "low" else adjusted.get("risk")
    flags = list(adjusted.get("data_quality_flags", []))
    for flag in ("risk_layer_adjusted", f"risk_{evidence.get('category', 'availability')}"):
        if flag not in flags:
            flags.append(flag)
    adjusted["data_quality_flags"] = flags
    adjusted["feature_contributions"] = {
        **adjusted.get("feature_contributions", {}),
        "risk_layer_minutes_delta": round(minutes - baseline_minutes, 2),
    }
    adjusted["risk_context"] = {
        "applied_evidence_id": evidence["id"],
        "claim_type": evidence["claim_type"],
        "source_tier": evidence["source_tier"],
        "baseline_expected_minutes": round(baseline_minutes, 2),
        "adjusted_expected_minutes": round(minutes, 2),
        "baseline_start_probability": round(baseline_start, 2),
        "adjusted_start_probability": round(start, 2),
        "adjusted_at": evidence["observed_at"],
    }
    return adjusted


def apply_risk_layer(
    players: list[Player],
    projections: list[dict[str, Any]],
    *,
    generated_at: datetime,
    target_gameweek: int | None,
    fpl_observed_at: datetime | None = None,
    curated_payload: dict[str, Any] | None = None,
    curated_source_status: str = "not_configured",
    loader_warnings: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply fresh, source-ranked evidence and return a complete audit contract."""

    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)
    observed_at = fpl_observed_at or generated_at
    player_by_id = {player.id: player for player in players}
    all_evidence = _fpl_evidence(
        players,
        generated_at=generated_at,
        observed_at=observed_at,
        target_gameweek=target_gameweek,
    )
    curated_rows = (curated_payload or {}).get("evidence", [])
    curated = [
        _normalise_curated_evidence(
            row,
            index=index,
            player_by_id=player_by_id,
            generated_at=generated_at,
            target_gameweek=target_gameweek,
        )
        for index, row in enumerate(curated_rows)
    ]
    all_evidence.extend(curated)

    adjusted = [deepcopy(item) for item in projections]
    projection_index = {int(item["player_id"]): index for index, item in enumerate(adjusted)}
    applied: list[dict[str, Any]] = []
    for player_id in sorted(player_by_id):
        candidates = [
            item
            for item in curated
            if item["player_id"] == player_id
            and item["active"]
            and item.get("adjustment")
        ]
        candidates.sort(
            key=lambda item: (
                SOURCE_PRECEDENCE.get(str(item.get("source_tier")), 0),
                str(item.get("published_at") or ""),
            ),
            reverse=True,
        )
        if not candidates or player_id not in projection_index:
            continue
        chosen = candidates[0]
        index = projection_index[player_id]
        adjusted[index] = _adjust_projection(adjusted[index], chosen)
        chosen["applied"] = True
        applied.append(
            {
                "player_id": player_id,
                "player_name": chosen["player_name"],
                "evidence_id": chosen["id"],
                "source_tier": chosen["source_tier"],
                "claim_type": chosen["claim_type"],
                "category": chosen["category"],
                "before": {
                    "expected_minutes": projections[index].get("expected_minutes"),
                    "start_probability": projections[index].get("start_probability"),
                    "expected_points_next": projections[index].get("expected_points_next"),
                },
                "after": {
                    "expected_minutes": adjusted[index].get("expected_minutes"),
                    "start_probability": adjusted[index].get("start_probability"),
                    "expected_points_next": adjusted[index].get("expected_points_next"),
                },
            }
        )

    validation_errors = [
        {"evidence_id": item["id"], "errors": item["validation_errors"]}
        for item in curated
        if item["validation_errors"]
    ]
    stale_count = sum(1 for item in curated if item["freshness"] == "stale")
    expired_count = sum(1 for item in curated if item.get("expired"))
    warnings = list(loader_warnings or [])
    if validation_errors:
        warnings.append(
            f"Ignored {len(validation_errors)} invalid curated evidence item(s)."
        )
    if stale_count:
        warnings.append(
            f"Ignored {stale_count} curated news item(s) older than {NEWS_STALE_AFTER_HOURS} hours."
        )
    if curated_source_status == "loaded" and not curated:
        warnings.append(
            "No curated club press or midweek evidence is active; FPL status remains the fallback."
        )
    fpl_age = _age_hours(generated_at, observed_at)
    fpl_stale = fpl_age is None or fpl_age > NEWS_STALE_AFTER_HOURS
    if fpl_stale:
        warnings.insert(0, "FPL availability source is older than 24 hours.")

    status = "degraded" if fpl_stale or curated_source_status == "invalid" else "ready"
    return adjusted, {
        "version": RISK_LAYER_VERSION,
        "status": status,
        "generated_at": generated_at.isoformat(),
        "target_gameweek": target_gameweek,
        "stale_after_hours": NEWS_STALE_AFTER_HOURS,
        "source_hierarchy": [
            "official club statement",
            "FPL or official competition status",
            "manual user override",
            "predicted lineup (inference only)",
        ],
        "rules": {
            "every_item_requires_source_and_timestamp": True,
            "predicted_lineups_are_inference": True,
            "stale_evidence_can_adjust_projection": False,
            "manual_override_requires_expiry_gameweek": True,
        },
        "official_reference_urls": {
            "fpl_availability": FPL_BOOTSTRAP_URL,
            "premier_league_injuries": OFFICIAL_INJURY_URL,
        },
        "source_snapshot": [
            {
                "source": "FPL Public API",
                "url": FPL_BOOTSTRAP_URL,
                "status": "stale" if fpl_stale else "available",
                "observed_at": observed_at.isoformat(),
                "age_hours": fpl_age,
                "kind": "fact",
            },
            {
                "source": "Curated official/secondary evidence",
                "status": curated_source_status,
                "observed_at": generated_at.isoformat(),
                "kind": "mixed",
            },
        ],
        "evidence": all_evidence,
        "evidence_count": len(all_evidence),
        "active_curated_count": sum(1 for item in curated if item["active"]),
        "stale_curated_count": stale_count,
        "expired_curated_count": expired_count,
        "invalid_curated_count": len(validation_errors),
        "adjusted_player_count": len(applied),
        "adjustments": applied,
        "validation_errors": validation_errors,
        "warnings": warnings,
        "fallback": "Use fresh FPL status plus model minutes uncertainty when curated news is unavailable.",
    }
