from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal

import httpx

from .cache import JsonCache
from .models import (
    BootstrapStatic,
    Entry,
    EntryHistory,
    Fixture,
    PicksResponse,
    PlayerSummary,
)


class FPLError(RuntimeError):
    """Base error for the FPL data source."""


class FPLNotFound(FPLError):
    """The requested public FPL resource is not available."""


class FPLUnavailable(FPLError):
    """The network failed and no stale cache was available."""


@dataclass(frozen=True, slots=True)
class FetchRecord:
    endpoint: str
    source: Literal["network", "cache", "stale-cache"]
    fetched_at: str
    duration_ms: int
    warning: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class FPLClient:
    """Read-only client for endpoints used by fantasy.premierleague.com."""

    def __init__(
        self,
        *,
        base_url: str,
        cache_dir: Path,
        timeout_seconds: float = 20.0,
        retries: int = 3,
        cache_ttl_seconds: int = 1_800,
        force_refresh: bool = False,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.retries = max(1, retries)
        self.cache_ttl_seconds = max(0, cache_ttl_seconds)
        self.force_refresh = force_refresh
        self._now = now or (lambda: datetime.now(UTC))
        self._sleep = sleep
        self.cache = JsonCache(cache_dir, now=self._now)
        self.fetch_records: list[FetchRecord] = []
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout_seconds,
            follow_redirects=True,
            transport=transport,
            headers={"User-Agent": "fpl-decision-assistant/0.1 (+personal-use)"},
        )

    def __enter__(self) -> "FPLClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _record(
        self,
        *,
        endpoint: str,
        source: Literal["network", "cache", "stale-cache"],
        fetched_at: datetime,
        duration_ms: int,
        warning: str | None = None,
    ) -> None:
        self.fetch_records.append(
            FetchRecord(
                endpoint=endpoint,
                source=source,
                fetched_at=fetched_at.isoformat(),
                duration_ms=duration_ms,
                warning=warning,
            )
        )

    def get_json(self, endpoint: str, *, ttl_seconds: int | None = None) -> Any:
        endpoint = endpoint.lstrip("/")
        ttl = self.cache_ttl_seconds if ttl_seconds is None else max(0, ttl_seconds)

        if not self.force_refresh:
            cached = self.cache.read_fresh(endpoint, ttl)
            if cached is not None:
                self._record(
                    endpoint=endpoint,
                    source="cache",
                    fetched_at=cached.fetched_at,
                    duration_ms=0,
                )
                return cached.data

        stale = self.cache.read(endpoint)
        started = time.monotonic()
        final_error: Exception | None = None

        for attempt in range(self.retries):
            try:
                response = self._client.get(endpoint)
                if response.status_code == httpx.codes.NOT_FOUND:
                    raise FPLNotFound(f"FPL resource is not available: {endpoint}")
                response.raise_for_status()
                data = response.json()
                fetched_at = self._now()
                self.cache.write(endpoint, data, fetched_at=fetched_at)
                self._record(
                    endpoint=endpoint,
                    source="network",
                    fetched_at=fetched_at,
                    duration_ms=round((time.monotonic() - started) * 1_000),
                )
                return data
            except FPLNotFound:
                raise
            except (httpx.HTTPError, ValueError) as error:
                final_error = error
                if attempt + 1 < self.retries:
                    self._sleep(0.5 * (2**attempt))

        if stale is not None:
            warning = f"Network refresh failed; using stale cache: {final_error}"
            self._record(
                endpoint=endpoint,
                source="stale-cache",
                fetched_at=stale.fetched_at,
                duration_ms=round((time.monotonic() - started) * 1_000),
                warning=warning,
            )
            return stale.data

        raise FPLUnavailable(f"Unable to fetch {endpoint}: {final_error}") from final_error

    def get_bootstrap(self) -> BootstrapStatic:
        return BootstrapStatic.model_validate(self.get_json("bootstrap-static/"))

    def get_fixtures(self) -> list[Fixture]:
        payload = self.get_json("fixtures/")
        return [Fixture.model_validate(item) for item in payload]

    def get_entry(self, team_id: int) -> Entry:
        return Entry.model_validate(self.get_json(f"entry/{team_id}/", ttl_seconds=300))

    def get_entry_history(self, team_id: int) -> EntryHistory:
        return EntryHistory.model_validate(
            self.get_json(f"entry/{team_id}/history/", ttl_seconds=300)
        )

    def get_transfers(self, team_id: int) -> list[dict[str, Any]]:
        payload = self.get_json(f"entry/{team_id}/transfers/", ttl_seconds=300)
        if not isinstance(payload, list):
            raise FPLError("FPL transfers response must be a list")
        return payload

    def get_picks(self, team_id: int, gameweek: int) -> PicksResponse:
        return PicksResponse.model_validate(
            self.get_json(f"entry/{team_id}/event/{gameweek}/picks/", ttl_seconds=300)
        )

    def get_player_summary(self, player_id: int) -> PlayerSummary:
        return PlayerSummary.model_validate(
            self.get_json(f"element-summary/{player_id}/", ttl_seconds=900)
        )

