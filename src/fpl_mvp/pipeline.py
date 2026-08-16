from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Protocol

from .api import FPLClient, FPLNotFound
from .briefing import build_briefing_markdown, write_briefing
from .config import Settings
from .forecast import DEFAULT_HORIZON, model_metadata, project_players, upcoming_gameweeks
from .models import BootstrapStatic, Entry, EntryHistory, Fixture, PicksResponse
from .optimizer import optimize_initial_squad, recommend_transfers, select_best_lineup


SCHEMA_VERSION = 1


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
) -> dict[str, Any]:
    generated_at = now or datetime.now(UTC)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)

    bootstrap = client.get_bootstrap()
    fixtures = client.get_fixtures()
    entry = client.get_entry(team_id)
    history = client.get_entry_history(team_id)
    transfers = client.get_transfers(team_id)

    warnings: list[str] = []
    published_gameweek = latest_published_gameweek(bootstrap, generated_at)
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

    projections = project_players(
        bootstrap,
        fixtures,
        now=generated_at,
        horizon=DEFAULT_HORIZON,
    )
    target_gameweeks = upcoming_gameweeks(
        bootstrap, generated_at, horizon=DEFAULT_HORIZON
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
        projections, key=lambda item: item["xp_next"], reverse=True
    ):
        player = player_by_id[projection["player_id"]]
        if projection["availability"] < 0.5 or projection["xp_next"] <= 0:
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
            }
            for item in pool
        ]

    current_squad_analysis: dict[str, Any] | None = None
    transfer_suggestions: list[dict[str, Any]] = []
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

    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "source": {
            "name": "Fantasy Premier League",
            "base_url": client.base_url,
            "read_only": True,
        },
        "game": {
            "gameweek_count": len(bootstrap.events),
            "player_count": len(bootstrap.elements),
            "team_count": len(bootstrap.teams),
            "fixture_count": len(fixtures),
            "next_gameweek": next_gameweek(bootstrap, generated_at),
            "latest_published_gameweek": published_gameweek,
        },
        "manager": {
            "team_id": entry.id,
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
        "analysis": {
            "model": model_metadata(DEFAULT_HORIZON, target_gameweeks),
            "projections": projections,
            "recommendations": {
                "initial_squad": initial_squad,
                "captain_candidates": captain_candidates,
                "value_candidates": value_candidates,
                "current_squad": current_squad_analysis,
                "transfer_suggestions": transfer_suggestions,
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
    with FPLClient(
        base_url=settings.base_url,
        cache_dir=settings.cache_dir,
        timeout_seconds=settings.timeout_seconds,
        retries=settings.retries,
        cache_ttl_seconds=settings.cache_ttl_seconds,
        force_refresh=force_refresh,
    ) as client:
        snapshot = build_snapshot(client, team_id=settings.team_id)
    write_snapshot(snapshot, settings.output_path)
    write_briefing(build_briefing_markdown(snapshot), settings.briefing_path)
    return snapshot
