from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Protocol

from .api import FPLClient, FPLNotFound
from .briefing import build_briefing_markdown, write_briefing
from .chip_planner import CHIP_PLANNER_VERSION, build_chip_planner
from .config import Settings
from .decision import build_gameweek_decision
from .forecast import DEFAULT_HORIZON, model_metadata, project_players, upcoming_gameweeks
from .models import BootstrapStatic, Entry, EntryHistory, Fixture, PicksResponse
from .optimizer import optimize_initial_squad, recommend_transfers, select_best_lineup
from .risk_layer import (
    RISK_LAYER_VERSION,
    apply_risk_layer,
    load_risk_evidence,
)
from .transfer_advisor import TRANSFER_ADVISOR_VERSION, build_transfer_advisor
from .release import RELEASE_VERSION


SCHEMA_VERSION = 2
STALE_AFTER_HOURS = 24


class TeamIdentityMismatch(ValueError):
    """The requested team and the FPL entry response do not describe one account."""


class PipelineClient(Protocol):
    base_url: str
    fetch_records: list[Any]

    def get_bootstrap(self) -> BootstrapStatic: ...

    def get_fixtures(self) -> list[Fixture]: ...

    def get_entry(self, team_id: int) -> Entry: ...

    def get_entry_history(self, team_id: int) -> EntryHistory: ...

    def get_transfers(self, team_id: int) -> list[dict[str, Any]]: ...

    def get_picks(self, team_id: int, gameweek: int) -> PicksResponse: ...


def latest_published_gameweek(bootstrap: BootstrapStatic, now: datetime) -> int | None:
    published = [event.id for event in bootstrap.events if event.deadline_time <= now]
    return max(published, default=None)


def next_gameweek(bootstrap: BootstrapStatic, now: datetime) -> dict[str, Any] | None:
    upcoming = sorted(
        (event for event in bootstrap.events if event.deadline_time > now),
        key=lambda event: event.deadline_time,
    )
    if not upcoming:
        return None
    event = upcoming[0]
    return {
        "id": event.id,
        "name": event.name,
        "deadline_time": event.deadline_time.isoformat(),
    }


def season_key(bootstrap: BootstrapStatic) -> str:
    """Return a stable season namespace derived from the first deadline."""

    if not bootstrap.events:
        return "unknown"
    first_deadline = min(event.deadline_time for event in bootstrap.events)
    start_year = first_deadline.year
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _manager_name(entry: Entry) -> str | None:
    parts = [entry.player_first_name, entry.player_last_name]
    name = " ".join(part.strip() for part in parts if part and part.strip())
    return name or None


def _parse_fetch_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return timestamp.replace(tzinfo=UTC) if timestamp.tzinfo is None else timestamp


def _data_quality(
    fetches: list[dict[str, Any]], generated_at: datetime
) -> dict[str, Any]:
    timestamps: list[datetime] = []
    for record in fetches:
        fetched_at = record.get("fetched_at") if isinstance(record, dict) else None
        if not fetched_at:
            continue
        timestamp = _parse_fetch_timestamp(fetched_at)
        if timestamp is None:
            continue
        timestamps.append(timestamp)

    oldest_source = min(timestamps, default=generated_at)
    newest_source = max(timestamps, default=generated_at)
    age_hours = max(0.0, (generated_at - oldest_source).total_seconds() / 3_600)
    uses_stale_cache = any(
        isinstance(record, dict) and record.get("source") == "stale-cache"
        for record in fetches
    )
    is_stale = age_hours > STALE_AFTER_HOURS
    return {
        "status": "stale" if is_stale else "fresh",
        "is_stale": is_stale,
        "uses_stale_cache": uses_stale_cache,
        "stale_after_hours": STALE_AFTER_HOURS,
        "age_hours": round(age_hours, 2),
        "oldest_source_at": oldest_source.isoformat(),
        "newest_source_at": newest_source.isoformat(),
        "assessed_at": generated_at.isoformat(),
    }


def _normalise_players(bootstrap: BootstrapStatic) -> list[dict[str, Any]]:
    position_names = {
        position.id: position.singular_name_short
        for position in bootstrap.element_types
    }
    return [
        {
            "id": player.id,
            "first_name": player.first_name,
            "second_name": player.second_name,
            "web_name": player.web_name,
            "team_id": player.team,
            "position_id": player.element_type,
            "position": position_names.get(player.element_type),
            "price": player.now_cost / 10,
            "now_cost": player.now_cost,
            "status": player.status,
            "news": player.news,
            "news_added": player.news_added.isoformat() if player.news_added else None,
            "chance_of_playing_next_round": player.chance_of_playing_next_round,
            "selected_by_percent": player.selected_by_percent,
            "form": player.form,
            "total_points": player.total_points,
            "event_points": player.event_points,
            "minutes": player.minutes,
            "starts": player.starts,
            "points_per_game": player.points_per_game,
            "ep_next": player.ep_next,
            "can_select": player.can_select,
            "can_transact": player.can_transact,
            "goals_scored": player.goals_scored,
            "assists": player.assists,
            "clean_sheets": player.clean_sheets,
            "bonus": player.bonus,
            "expected_goals_per_90": player.expected_goals_per_90,
            "expected_assists_per_90": player.expected_assists_per_90,
            "expected_goal_involvements_per_90": (
                player.expected_goal_involvements_per_90
            ),
            "expected_goals_conceded_per_90": (
                player.expected_goals_conceded_per_90
            ),
            "defensive_contribution_per_90": (
                player.defensive_contribution_per_90
            ),
            "saves_per_90": player.saves_per_90,
            "transfers_in_event": player.transfers_in_event,
            "transfers_out_event": player.transfers_out_event,
            "cost_change_event": player.cost_change_event,
            "penalties_order": player.penalties_order,
        }
        for player in bootstrap.elements
    ]


def _normalise_fixtures(fixtures: list[Fixture]) -> list[dict[str, Any]]:
    return [
        {
            "id": fixture.id,
            "gameweek": fixture.event,
            "kickoff_time": fixture.kickoff_time.isoformat() if fixture.kickoff_time else None,
            "home_team_id": fixture.team_h,
            "away_team_id": fixture.team_a,
            "home_score": fixture.team_h_score,
            "away_score": fixture.team_a_score,
            "home_difficulty": fixture.team_h_difficulty,
            "away_difficulty": fixture.team_a_difficulty,
            "finished": fixture.finished,
            "started": fixture.started,
        }
        for fixture in fixtures
    ]


def build_snapshot(
    client: PipelineClient,
    *,
    team_id: int,
    now: datetime | None = None,
    risk_evidence: dict[str, Any] | None = None,
    risk_evidence_status: str = "not_configured",
    risk_evidence_warnings: list[str] | None = None,
) -> dict[str, Any]:
    generated_at = now or datetime.now(UTC)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)

    bootstrap = client.get_bootstrap()
    fixtures = client.get_fixtures()
    entry = client.get_entry(team_id)
    if entry.id != team_id:
        raise TeamIdentityMismatch(
            f"Requested Team ID {team_id}, but FPL returned Team ID {entry.id}. "
            "Recommendations were not generated."
        )
    history = client.get_entry_history(team_id)
    transfers = client.get_transfers(team_id)

    warnings: list[str] = []
    published_gameweek = latest_published_gameweek(bootstrap, generated_at)
    target_gameweek = next_gameweek(bootstrap, generated_at)
    picks: PicksResponse | None = None

    if published_gameweek is None:
        warnings.append(
            "No public picks are available before the first Gameweek deadline; "
            "the initial squad must be entered locally in the Dashboard."
        )
    elif published_gameweek >= entry.started_event:
        try:
            picks = client.get_picks(team_id, published_gameweek)
        except FPLNotFound:
            warnings.append(
                f"Picks for Gameweek {published_gameweek} are not public yet; "
                "the last locally saved squad should be used."
            )

    fetches = [
        record.as_dict() if hasattr(record, "as_dict") else record
        for record in client.fetch_records
    ]
    warnings.extend(
        record["warning"]
        for record in fetches
        if isinstance(record, dict) and record.get("warning")
    )
    data_quality = _data_quality(fetches, generated_at)
    if data_quality["is_stale"]:
        warnings.insert(
            0,
            f"Core data is {data_quality['age_hours']:.1f} hours old; "
            "verify it before using any recommendation.",
        )

    projections = project_players(
        bootstrap,
        fixtures,
        now=generated_at,
        horizon=DEFAULT_HORIZON,
    )
    bootstrap_fetch_at = next(
        (
            _parse_fetch_timestamp(record.get("fetched_at"))
            for record in fetches
            if isinstance(record, dict)
            and str(record.get("endpoint", "")).rstrip("/") == "bootstrap-static"
        ),
        None,
    )
    target_gameweek_id = target_gameweek["id"] if target_gameweek else None
    projections, risk_layer = apply_risk_layer(
        bootstrap.elements,
        projections,
        generated_at=generated_at,
        target_gameweek=target_gameweek_id,
        fpl_observed_at=bootstrap_fetch_at,
        curated_payload=risk_evidence,
        curated_source_status=risk_evidence_status,
        loader_warnings=risk_evidence_warnings,
    )
    warnings.extend(risk_layer.get("warnings", []))
    target_gameweeks = upcoming_gameweeks(
        bootstrap, generated_at, horizon=DEFAULT_HORIZON
    )
    model = model_metadata(DEFAULT_HORIZON, target_gameweeks, projections)
    model["risk_layer_version"] = RISK_LAYER_VERSION
    if not model.get("quality", {}).get("guardrails_passed", False):
        warnings.append(
            "Projection quality guardrails require review; do not use model rankings "
            "until Diagnostics returns passed."
        )
    try:
        initial_squad = optimize_initial_squad(bootstrap.elements, projections)
    except (RuntimeError, ValueError) as error:
        warnings.append(f"Initial squad optimizer is unavailable: {error}")
        initial_squad = {
            "optimizer_version": "unavailable",
            "status": "unavailable",
            "reason": str(error),
            "picks": [],
        }
    player_by_id = {player.id: player for player in bootstrap.elements}
    captain_candidates = []
    for projection in sorted(
        projections, key=lambda item: item["captain_score"], reverse=True
    ):
        player = player_by_id[projection["player_id"]]
        if (
            projection["availability"] < 0.5
            or projection["xp_next"] <= 0
            or not projection.get("captain_eligible", False)
        ):
            continue
        captain_candidates.append(
            {
                "player_id": player.id,
                "name": player.web_name,
                "team_id": player.team,
                "position_id": player.element_type,
                "price": player.now_cost / 10,
                "xp_next": projection["xp_next"],
                "xp_horizon": projection["xp_horizon"],
                "ranking_score_next": projection["ranking_score_next"],
                "captain_score": projection["captain_score"],
                "expected_minutes": projection["expected_minutes"],
                "start_probability": projection["start_probability"],
                "projection_confidence": projection["projection_confidence"],
                "expected_points_range": projection["expected_points_range"],
                "data_quality_flags": projection["data_quality_flags"],
                "risk": projection["risk"],
            }
        )
        if len(captain_candidates) == 10:
            break

    value_candidates: dict[str, list[dict[str, Any]]] = {}
    for position_id, position_name in ((1, "GKP"), (2, "DEF"), (3, "MID"), (4, "FWD")):
        pool = sorted(
            (
                projection
                for projection in projections
                if player_by_id[projection["player_id"]].element_type == position_id
                and projection["availability"] >= 0.5
                and projection["xp_next"] > 0
            ),
            key=lambda item: (item["value_score"], item["xp_horizon"]),
            reverse=True,
        )[:8]
        value_candidates[position_name] = [
            {
                "player_id": item["player_id"],
                "name": player_by_id[item["player_id"]].web_name,
                "team_id": player_by_id[item["player_id"]].team,
                "price": player_by_id[item["player_id"]].now_cost / 10,
                "xp_next": item["xp_next"],
                "xp_horizon": item["xp_horizon"],
                "value_score": item["value_score"],
                "expected_minutes": item["expected_minutes"],
                "projection_confidence": item["projection_confidence"],
            }
            for item in pool
        ]

    current_squad_analysis: dict[str, Any] | None = None
    transfer_suggestions: list[dict[str, Any]] = []
    transfer_advisor: dict[str, Any] = {
        "version": TRANSFER_ADVISOR_VERSION,
        "status": "unavailable",
        "mode": "regular_transfers",
        "required_inputs": [],
        "candidate_moves": [],
        "candidate_count": 0,
        "wildcard_separate": True,
        "limitations": ["A published 15-player squad is required."],
    }
    chip_planner: dict[str, Any] = {
        "version": CHIP_PLANNER_VERSION,
        "status": "unavailable",
        "limitations": ["A published 15-player squad is required."],
    }
    if picks is not None:
        current_ids = [pick.element for pick in picks.picks]
        current_squad_analysis = select_best_lineup(
            current_ids, bootstrap.elements, projections
        )
        transfer_suggestions = recommend_transfers(
            current_ids,
            bootstrap.elements,
            projections,
            bank_tenths=entry.last_deadline_bank or 0,
        )
        transfer_advisor = build_transfer_advisor(
            current_ids,
            bootstrap.elements,
            projections,
            bank_tenths=entry.last_deadline_bank,
        )
        if target_gameweek_id is not None:
            chip_planner = build_chip_planner(
                current_squad_ids=current_ids,
                players=bootstrap.elements,
                projections=projections,
                target_gameweek=target_gameweek_id,
                chip_history=history.chips,
                active_chip=None,
                bank_tenths=entry.last_deadline_bank,
                budget_tenths=entry.last_deadline_value,
                generated_at=generated_at.isoformat(),
                season=season_key(bootstrap),
            )

    gameweek_decision = build_gameweek_decision(
        team_id=team_id,
        target_gameweek=target_gameweek,
        generated_at=generated_at.isoformat(),
        identity_verified=entry.id == team_id,
        data_quality=data_quality,
        published_gameweek=published_gameweek if picks is not None else None,
        team_source_status="published" if picks is not None else "local_required",
        current_squad=current_squad_analysis,
        transfer_suggestions=transfer_suggestions,
        transfer_advisor=transfer_advisor,
        chip_planner=chip_planner,
        projections=projections,
        model_version=model["version"],
        risk_layer=risk_layer,
    )

    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "release": {"version": RELEASE_VERSION},
        "generated_at": generated_at.isoformat(),
        "identity": {
            "requested_team_id": team_id,
            "snapshot_team_id": entry.id,
            "verified": entry.id == team_id,
            "team_name": entry.name,
            "manager_name": _manager_name(entry),
            "season": season_key(bootstrap),
            "target_gameweek_id": target_gameweek["id"] if target_gameweek else None,
            "verified_at": generated_at.isoformat(),
        },
        "data_quality": data_quality,
        "source": {
            "name": "Fantasy Premier League",
            "base_url": client.base_url,
            "read_only": True,
        },
        "game": {
            "season": season_key(bootstrap),
            "gameweek_count": len(bootstrap.events),
            "player_count": len(bootstrap.elements),
            "team_count": len(bootstrap.teams),
            "fixture_count": len(fixtures),
            "next_gameweek": target_gameweek,
            "latest_published_gameweek": published_gameweek,
        },
        "manager": {
            "team_id": entry.id,
            "team_name": entry.name,
            "manager_name": _manager_name(entry),
            "started_event": entry.started_event,
            "current_event": entry.current_event,
            "bank": entry.last_deadline_bank / 10 if entry.last_deadline_bank is not None else None,
            "squad_value": (
                entry.last_deadline_value / 10 if entry.last_deadline_value is not None else None
            ),
            "total_transfers": entry.last_deadline_total_transfers,
            "overall_points": entry.summary_overall_points,
            "overall_rank": entry.summary_overall_rank,
        },
        "team": {
            "published_gameweek": published_gameweek if picks is not None else None,
            "source_status": "published" if picks is not None else "local_required",
            "source_kind": (
                "fpl_public_picks" if picks is not None else "browser_local_squad_required"
            ),
            "active_chip": picks.active_chip if picks else None,
            "entry_history": picks.entry_history if picks else None,
            "picks": (
                [pick.model_dump(mode="json") for pick in picks.picks] if picks else None
            ),
        },
        "catalog": {
            "events": [
                {
                    "id": event.id,
                    "name": event.name,
                    "deadline_time": event.deadline_time.isoformat(),
                    "finished": event.finished,
                    "data_checked": event.data_checked,
                    "is_previous": event.is_previous,
                    "is_current": event.is_current,
                    "is_next": event.is_next,
                }
                for event in bootstrap.events
            ],
            "teams": [
                {
                    "id": team.id,
                    "name": team.name,
                    "short_name": team.short_name,
                    "code": team.code,
                    "strength": team.strength,
                    "strength_overall_home": team.strength_overall_home,
                    "strength_overall_away": team.strength_overall_away,
                    "strength_attack_home": team.strength_attack_home,
                    "strength_attack_away": team.strength_attack_away,
                    "strength_defence_home": team.strength_defence_home,
                    "strength_defence_away": team.strength_defence_away,
                }
                for team in bootstrap.teams
            ],
            "positions": [
                {
                    "id": position.id,
                    "name": position.singular_name,
                    "short_name": position.singular_name_short,
                    "squad_select": position.squad_select,
                    "min_play": position.squad_min_play,
                    "max_play": position.squad_max_play,
                }
                for position in bootstrap.element_types
            ],
            "players": _normalise_players(bootstrap),
            "fixtures": _normalise_fixtures(fixtures),
        },
        "history": history.model_dump(mode="json"),
        "transfers": transfers,
        "gameweek_decision": gameweek_decision,
        "provenance": {
            "identity": {
                "source": "FPL Public API",
                "endpoint": f"entry/{team_id}/",
                "kind": "fact",
            },
            "published_squad": {
                "source": "FPL Public API",
                "endpoint": (
                    f"entry/{team_id}/event/{published_gameweek}/picks/"
                    if picks is not None
                    else None
                ),
                "kind": "fact",
                "gameweek": published_gameweek if picks is not None else None,
            },
            "local_squad": {
                "source": "Browser localStorage",
                "kind": "user_input",
                "included_in_snapshot": False,
            },
            "analysis": {
                "source": "FPL Decision Lab model",
                "kind": "estimate",
                "version": model["version"],
            },
            "risk_evidence": {
                "source": "FPL Public API + curated evidence file",
                "kind": "fact_and_inference",
                "version": risk_layer["version"],
                "source_snapshot": risk_layer["source_snapshot"],
            },
            "chip_planner": {
                "source": "FPL public manager history + Decision Lab model",
                "kind": "fact_and_estimate",
                "version": chip_planner.get("version"),
                "rules_version": chip_planner.get("rules", {}).get("version"),
            },
        },
        "analysis": {
            "model": model,
            "risk_layer": risk_layer,
            "projections": projections,
            "recommendations": {
                "initial_squad": initial_squad,
                "captain_candidates": captain_candidates,
                "value_candidates": value_candidates,
                "current_squad": current_squad_analysis,
                "transfer_suggestions": transfer_suggestions,
                "transfer_advisor": transfer_advisor,
                "chip_planner": chip_planner,
                "transfer_price_note": (
                    "Public FPL data does not expose each manager's exact selling price; "
                    "transfer affordability uses current prices."
                ),
            },
        },
        "diagnostics": {
            "fetches": fetches,
            "warnings": warnings,
        },
    }
    return snapshot


def write_snapshot(snapshot: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(snapshot, handle, ensure_ascii=False, indent=2)
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


def run_pipeline(settings: Settings, *, force_refresh: bool = False) -> dict[str, Any]:
    risk_evidence, risk_status, risk_warnings = load_risk_evidence(
        settings.risk_evidence_path
    )
    with FPLClient(
        base_url=settings.base_url,
        cache_dir=settings.cache_dir,
        timeout_seconds=settings.timeout_seconds,
        retries=settings.retries,
        cache_ttl_seconds=settings.cache_ttl_seconds,
        force_refresh=force_refresh,
    ) as client:
        snapshot = build_snapshot(
            client,
            team_id=settings.team_id,
            risk_evidence=risk_evidence,
            risk_evidence_status=risk_status,
            risk_evidence_warnings=risk_warnings,
        )
    write_snapshot(snapshot, settings.output_path)
    write_briefing(build_briefing_markdown(snapshot), settings.briefing_path)
    return snapshot
