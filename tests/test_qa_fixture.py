from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path


def test_owned_team_fixture_is_anonymized_and_useful() -> None:
    path = Path(__file__).parent / "fixtures/owned-team-gw3.json.gz.b64"
    raw = gzip.decompress(base64.b64decode("".join(path.read_text().split()))).decode()
    data = json.loads(raw)
    assert "5105794" not in raw and "Sarayut" not in raw
    assert data["identity"]["team_name"] == "QA United"
    assert data["identity"]["manager_name"] == "QA Manager"
    assert data["identity"]["snapshot_team_id"] == 990001
    assert len(data["team"]["picks"]) == 15
    assert len(data["gameweek_decision"]["starting_xi"]["squad"]) == 15
    assert 3 <= data["analysis"]["recommendations"]["chip_planner"]["horizon"]["count"] <= 6
    assert not any(key.lower() in {"password", "cookie", "token", "secret", "session"} for key in _keys(data))


def _keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _keys(child)
    elif isinstance(value, list):
        for child in value: yield from _keys(child)
