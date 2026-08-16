from __future__ import annotations

from datetime import UTC, datetime

from fpl_mvp.api import FPLNotFound
from fpl_mvp.models import BootstrapStatic, Entry, EntryHistory, Fixture, PicksResponse
from fpl_mvp.pipeline import build_snapshot, latest_published_gameweek


BEFORE_DEADLINE = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
AFTER_DEADLINE = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)


def bootstrap() -> BootstrapStatic:
    return BootstrapStatic.model_validate(
        {
            "events": [
                {
                    "id": 1,
                    "name": "Gameweek 1",
                    "deadline_time": "2026-08-21T17:30:00Z",
                },
                {
                    "id": 2,
                    "name": "Gameweek 2",
                    "deadline_time": "2026-08-29T10:00:00Z",
                },
            ],
            "teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS"}],
            "element_types": [
                {
                    "id": 1,
                    "singular_name": "Goalkeeper",
                    "singular_name_short": "GKP",
                    "squad_select": 2,
                    "squad_min_play": 1,
                    "squad_max_play": 1,
                }
            ],
            "elements": [
                {
                    "id": 1,
                    "first_name": "Test",
                    "second_name": "Keeper",
                    "web_name": "Keeper",
                    "team": 1,
                    "element_type": 1,
                    "now_cost": 50,
                    "status": "a",
                }
            ],
        }
    )


class FakeClient:
    base_url = "https://fantasy.premierleague.com/api/"
    fetch_records: list = []

    def __init__(self) -> None:
        self.picks_called = False

    def get_bootstrap(self) -> BootstrapStatic:
        return bootstrap()

    def get_fixtures(self) -> list[Fixture]:
        return [
            Fixture.model_validate(
                {
                    "id": 1,
                    "event": 1,
                    "kickoff_time": "2026-08-21T19:00:00Z",
                    "team_h": 1,
                    "team_a": 2,
                }
            )
        ]

    def get_entry(self, team_id: int) -> Entry:
        return Entry.model_validate({"id": team_id, "started_event": 1})

    def get_entry_history(self, team_id: int) -> EntryHistory:
        return EntryHistory()

    def get_transfers(self, team_id: int) -> list[dict]:
        return []

    def get_picks(self, team_id: int, gameweek: int):
        self.picks_called = True
        raise AssertionError("Picks must not be requested before the first deadline")


class PublishedPicksClient(FakeClient):
    def get_picks(self, team_id: int, gameweek: int) -> PicksResponse:
        self.picks_called = True
        return PicksResponse.model_validate(
            {
                "active_chip": None,
                "entry_history": {"event": gameweek, "points": 61},
                "picks": [
                    {
                        "element": 1,
                        "position": 1,
                        "multiplier": 2,
                        "is_captain": True,
                        "is_vice_captain": False,
                    }
                ],
            }
        )


class UnpublishedPicksClient(FakeClient):
    def get_picks(self, team_id: int, gameweek: int) -> PicksResponse:
        self.picks_called = True
        raise FPLNotFound("not public yet")


def test_published_gameweek_respects_deadline() -> None:
    data = bootstrap()
    assert latest_published_gameweek(data, BEFORE_DEADLINE) is None
    assert latest_published_gameweek(data, AFTER_DEADLINE) == 1


def test_snapshot_before_gw1_does_not_request_private_picks() -> None:
    client = FakeClient()
    snapshot = build_snapshot(client, team_id=3_647_781, now=BEFORE_DEADLINE)

    assert client.picks_called is False
    assert snapshot["manager"]["team_id"] == 3_647_781
    assert snapshot["team"]["picks"] is None
    assert snapshot["game"]["next_gameweek"]["id"] == 1
    assert snapshot["catalog"]["players"][0]["price"] == 5.0
    assert "No public picks" in snapshot["diagnostics"]["warnings"][0]


def test_snapshot_after_deadline_includes_public_picks() -> None:
    client = PublishedPicksClient()
    snapshot = build_snapshot(client, team_id=3_647_781, now=AFTER_DEADLINE)

    assert client.picks_called is True
    assert snapshot["team"]["published_gameweek"] == 1
    assert snapshot["team"]["picks"][0]["element"] == 1
    assert snapshot["team"]["picks"][0]["is_captain"] is True
    assert not any(
        "not public yet" in warning
        for warning in snapshot["diagnostics"]["warnings"]
    )


def test_snapshot_survives_publication_delay_after_deadline() -> None:
    client = UnpublishedPicksClient()
    snapshot = build_snapshot(client, team_id=3_647_781, now=AFTER_DEADLINE)

    assert client.picks_called is True
    assert snapshot["team"]["picks"] is None
    assert "not public yet" in snapshot["diagnostics"]["warnings"][0]
