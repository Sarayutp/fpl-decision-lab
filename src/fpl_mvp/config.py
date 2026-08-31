from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path


DEFAULT_BASE_URL = "https://fantasy.premierleague.com/api/"
DEFAULT_TEAM_ID = 5_105_794


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings with free, public FPL endpoints as defaults."""

    base_url: str = DEFAULT_BASE_URL
    team_id: int = DEFAULT_TEAM_ID
    cache_dir: Path = Path("data/cache")
    output_path: Path = Path("data/latest.json")
    briefing_path: Path = Path("data/briefing.md")
    risk_evidence_path: Path = Path("data/risk-evidence.json")
    dashboard_dir: Path = Path("dashboard")
    site_output_dir: Path = Path("dist")
    timeout_seconds: float = 20.0
    retries: int = 3
    cache_ttl_seconds: int = 1_800

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            base_url=os.getenv("FPL_BASE_URL", DEFAULT_BASE_URL),
            team_id=int(os.getenv("FPL_TEAM_ID", str(DEFAULT_TEAM_ID))),
            cache_dir=Path(os.getenv("FPL_CACHE_DIR", "data/cache")),
            output_path=Path(os.getenv("FPL_OUTPUT_PATH", "data/latest.json")),
            briefing_path=Path(os.getenv("FPL_BRIEFING_PATH", "data/briefing.md")),
            risk_evidence_path=Path(
                os.getenv("FPL_RISK_EVIDENCE_PATH", "data/risk-evidence.json")
            ),
            dashboard_dir=Path(os.getenv("FPL_DASHBOARD_DIR", "dashboard")),
            site_output_dir=Path(os.getenv("FPL_SITE_OUTPUT_DIR", "dist")),
            timeout_seconds=float(os.getenv("FPL_TIMEOUT_SECONDS", "20")),
            retries=int(os.getenv("FPL_RETRIES", "3")),
            cache_ttl_seconds=int(os.getenv("FPL_CACHE_TTL_SECONDS", "1800")),
        )

    def with_overrides(self, **changes: object) -> "Settings":
        return replace(self, **{key: value for key, value in changes.items() if value is not None})
