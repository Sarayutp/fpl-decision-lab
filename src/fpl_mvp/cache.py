from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class CacheEntry:
    endpoint: str
    fetched_at: datetime
    data: Any


class JsonCache:
    """Small file cache with atomic writes and stale-read support."""

    def __init__(
        self,
        directory: Path,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.directory = directory
        self._now = now or (lambda: datetime.now(UTC))

    def _path_for(self, endpoint: str) -> Path:
        digest = hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:12]
        label = endpoint.strip("/").replace("/", "__") or "root"
        label = "".join(char if char.isalnum() or char in "-_" else "_" for char in label)
        return self.directory / f"{label[:80]}-{digest}.json"

    def read(self, endpoint: str) -> CacheEntry | None:
        path = self._path_for(endpoint)
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(payload["fetched_at"])
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=UTC)
            return CacheEntry(
                endpoint=payload["endpoint"],
                fetched_at=fetched_at,
                data=payload["data"],
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def read_fresh(self, endpoint: str, ttl_seconds: int) -> CacheEntry | None:
        entry = self.read(endpoint)
        if entry is None:
            return None
        age_seconds = (self._now() - entry.fetched_at).total_seconds()
        return entry if age_seconds <= ttl_seconds else None

    def write(
        self,
        endpoint: str,
        data: Any,
        *,
        fetched_at: datetime | None = None,
    ) -> CacheEntry:
        timestamp = fetched_at or self._now()
        entry = CacheEntry(endpoint=endpoint, fetched_at=timestamp, data=data)
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self._path_for(endpoint)
        payload = {
            "endpoint": endpoint,
            "fetched_at": timestamp.isoformat(),
            "data": data,
        }

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=self.directory,
            text=True,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, destination)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

        return entry

