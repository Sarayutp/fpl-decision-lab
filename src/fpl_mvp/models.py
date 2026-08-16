from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FPLModel(BaseModel):
    """Strict on fields we use, tolerant of new fields added by FPL."""

    model_config = ConfigDict(extra="allow", frozen=True)


class Gameweek(FPLModel):
    id: int
    name: str
    deadline_time: datetime
    finished: bool = False
    data_checked: bool = False
    is_previous: bool = False
    is_current: bool = False
    is_next: bool = False


class Team(FPLModel):
    id: int
    name: str
    short_name: str
    code: int | None = None
    strength: int | None = None


class ElementType(FPLModel):
    id: int
    singular_name: str
    singular_name_short: str
    squad_select: int
    squad_min_play: int
    squad_max_play: int


class Player(FPLModel):
    id: int
    first_name: str
    second_name: str
    web_name: str
    team: int
    element_type: int
    now_cost: int
    status: str
    news: str = ""
    news_added: datetime | None = None
    chance_of_playing_next_round: int | None = None
    chance_of_playing_this_round: int | None = None
    selected_by_percent: str = "0.0"
    form: str = "0.0"
    total_points: int = 0
    event_points: int = 0
    minutes: int = 0
    starts: int = 0
    points_per_game: str = "0.0"
    ep_next: str | None = None
    ep_this: str | None = None
    can_select: bool = True
    can_transact: bool = True
    goals_scored: int = 0
    assists: int = 0
    clean_sheets: int = 0
    bonus: int = 0
    bps: int = 0
    expected_goals_per_90: float = 0.0
    expected_assists_per_90: float = 0.0
    expected_goal_involvements_per_90: float = 0.0
    expected_goals_conceded_per_90: float = 0.0
    defensive_contribution_per_90: float = 0.0
    saves_per_90: float = 0.0
    transfers_in_event: int = 0
    transfers_out_event: int = 0
    cost_change_event: int = 0
    penalties_order: int | None = None
    direct_freekicks_order: int | None = None
    corners_and_indirect_freekicks_order: int | None = None


class BootstrapStatic(FPLModel):
    events: list[Gameweek]
    teams: list[Team]
    element_types: list[ElementType]
    elements: list[Player]


class Fixture(FPLModel):
    id: int
    event: int | None = None
    kickoff_time: datetime | None = None
    team_h: int
    team_a: int
    team_h_score: int | None = None
    team_a_score: int | None = None
    team_h_difficulty: int | None = None
    team_a_difficulty: int | None = None
    finished: bool = False
    started: bool | None = None


class Entry(FPLModel):
    id: int
    started_event: int
    current_event: int | None = None
    last_deadline_bank: int | None = None
    last_deadline_value: int | None = None
    last_deadline_total_transfers: int = 0
    summary_overall_points: int | None = None
    summary_overall_rank: int | None = None
    name: str | None = None


class EntryHistory(FPLModel):
    current: list[dict[str, Any]] = Field(default_factory=list)
    past: list[dict[str, Any]] = Field(default_factory=list)
    chips: list[dict[str, Any]] = Field(default_factory=list)


class Pick(FPLModel):
    element: int
    position: int
    multiplier: int
    is_captain: bool
    is_vice_captain: bool


class PicksResponse(FPLModel):
    active_chip: str | None = None
    automatic_subs: list[dict[str, Any]] = Field(default_factory=list)
    entry_history: dict[str, Any] = Field(default_factory=dict)
    picks: list[Pick]


class PlayerSummary(FPLModel):
    fixtures: list[dict[str, Any]] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)
    history_past: list[dict[str, Any]] = Field(default_factory=list)
