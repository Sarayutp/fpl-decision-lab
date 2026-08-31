from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fpl_mvp.models import Player
from fpl_mvp.risk_layer import apply_risk_layer, load_risk_evidence


NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def player(**updates: object) -> Player:
    values: dict[str, object] = {
        "id": 10,
        "first_name": "Risk",
        "second_name": "Player",
        "web_name": "Risky",
        "team": 1,
        "element_type": 3,
        "now_cost": 70,
        "status": "a",
        "minutes": 180,
        "starts": 2,
    }
    values.update(updates)
    return Player.model_validate(values)


def projection() -> dict:
    return {
        "player_id": 10,
        "expected_points_next": 6.0,
        "expected_points_horizon": 20.0,
        "xp_next": 6.0,
        "xp_horizon": 20.0,
        "ranking_score_next": 5.8,
        "ranking_score_horizon": 19.0,
        "captain_score": 6.2,
        "captain_eligible": True,
        "value_score": 2.71,
        "expected_minutes": 80.0,
        "expected_minutes_range": {"lower": 65.0, "upper": 90.0},
        "start_probability": 0.9,
        "projection_confidence": "medium",
        "confidence_score": 0.65,
        "expected_points_range": {"lower": 3.0, "upper": 9.0},
        "availability": 1.0,
        "risk": "low",
        "data_quality_flags": [],
        "feature_contributions": {},
        "model_inputs": {"projected_points_per_90": 6.5},
        "gameweeks": [
            {
                "gameweek": 3,
                "expected_points": 6.0,
                "xp": 6.0,
                "ranking_score": 5.8,
                "expected_minutes": 80.0,
                "start_probability": 0.9,
                "interval": {"lower": 3.0, "upper": 9.0},
                "fixture_count": 1,
                "model_components": {"average_fixture_factor": 1.0},
            },
            {
                "gameweek": 4,
                "expected_points": 4.0,
                "xp": 4.0,
                "ranking_score": 3.8,
                "expected_minutes": 80.0,
                "start_probability": 0.9,
                "interval": {"lower": 1.0, "upper": 7.0},
                "fixture_count": 1,
                "model_components": {"average_fixture_factor": 1.0},
            },
        ],
    }


def evidence(**updates: object) -> dict:
    values: dict[str, object] = {
        "id": "club-press-1",
        "player_id": 10,
        "category": "injury",
        "claim_type": "fact",
        "source_tier": "official_club",
        "source_label": "Club press conference",
        "source_url": "https://club.example/news/team-news",
        "summary": "Manager says the player is limited to the bench.",
        "published_at": (NOW - timedelta(hours=2)).isoformat(),
        "effective_gameweek": 3,
        "expires_gameweek": 3,
        "adjustment": {
            "expected_minutes_override": 30,
            "start_probability_override": 0.25,
        },
    }
    values.update(updates)
    return values


def test_fpl_status_is_fact_with_source_and_observation_time() -> None:
    risky = player(
        status="d",
        chance_of_playing_next_round=75,
        news="Knock - 75% chance of playing",
        news_added=NOW - timedelta(days=2),
    )

    _, layer = apply_risk_layer(
        [risky],
        [projection()],
        generated_at=NOW,
        target_gameweek=3,
        fpl_observed_at=NOW - timedelta(minutes=5),
    )

    item = layer["evidence"][0]
    assert item["claim_type"] == "fact"
    assert item["source_url"].startswith("https://fantasy.premierleague.com/")
    assert item["freshness"] == "fresh"
    assert item["content_age_hours"] == 48.0


def test_official_fresh_evidence_changes_minutes_and_is_auditable() -> None:
    adjusted, layer = apply_risk_layer(
        [player()],
        [projection()],
        generated_at=NOW,
        target_gameweek=3,
        curated_payload={"evidence": [evidence()]},
        curated_source_status="loaded",
    )

    result = adjusted[0]
    assert result["expected_minutes"] == 30
    assert result["start_probability"] == 0.25
    assert result["gameweeks"][0]["start_probability"] == 0.25
    assert result["gameweeks"][1]["start_probability"] == 0.9
    assert result["expected_points_next"] == 2.25
    assert result["risk"] == "high"
    assert result["risk_context"]["applied_evidence_id"] == "club-press-1"
    assert layer["adjusted_player_count"] == 1
    assert layer["source_hierarchy"][0] == "official club statement"
    assert layer["adjustments"][0]["before"]["expected_minutes"] == 80.0
    assert layer["adjustments"][0]["after"]["expected_minutes"] == 30.0


def test_predicted_lineup_is_inference_and_has_bounded_impact() -> None:
    predicted = evidence(
        source_tier="predicted_lineup",
        claim_type="fact",
        category="lineup",
        adjustment={
            "expected_minutes_override": 0,
            "start_probability_override": 0,
        },
    )

    adjusted, layer = apply_risk_layer(
        [player()],
        [projection()],
        generated_at=NOW,
        target_gameweek=3,
        curated_payload={"evidence": [predicted]},
        curated_source_status="loaded",
    )

    assert layer["evidence"][-1]["claim_type"] == "inference"
    assert adjusted[0]["expected_minutes"] == 65
    assert adjusted[0]["start_probability"] == 0.75
    assert adjusted[0]["projection_confidence"] == "low"


def test_stale_or_expired_evidence_never_adjusts_projection() -> None:
    stale = evidence(published_at=(NOW - timedelta(hours=25)).isoformat())
    expired = evidence(id="old-gw", expires_gameweek=2)

    adjusted, layer = apply_risk_layer(
        [player()],
        [projection()],
        generated_at=NOW,
        target_gameweek=3,
        curated_payload={"evidence": [stale, expired]},
        curated_source_status="loaded",
    )

    assert adjusted[0]["expected_minutes"] == 80
    assert layer["adjusted_player_count"] == 0
    assert layer["stale_curated_count"] == 1
    assert layer["expired_curated_count"] == 1


def test_override_without_expiry_is_rejected() -> None:
    invalid = evidence(expires_gameweek=None)

    _, layer = apply_risk_layer(
        [player()],
        [projection()],
        generated_at=NOW,
        target_gameweek=3,
        curated_payload={"evidence": [invalid]},
        curated_source_status="loaded",
    )

    assert layer["invalid_curated_count"] == 1
    assert "expires_gameweek is required" in layer["validation_errors"][0]["errors"]


def test_missing_or_invalid_evidence_file_uses_safe_fallback(tmp_path) -> None:
    payload, status, warnings = load_risk_evidence(tmp_path / "missing.json")
    assert payload is None
    assert status == "not_configured"
    assert warnings

    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    _, broken_status, broken_warnings = load_risk_evidence(broken)
    assert broken_status == "invalid"
    assert broken_warnings
