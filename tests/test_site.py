from __future__ import annotations

import json

from fpl_mvp.site import REQUIRED_DASHBOARD_FILES, build_site


def test_build_site_copies_dashboard_and_data_atomically(tmp_path) -> None:
    dashboard = tmp_path / "dashboard"
    for relative_path in REQUIRED_DASHBOARD_FILES:
        path = dashboard / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative_path, encoding="utf-8")
    data = tmp_path / "latest.json"
    data.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-08-16T12:00:00+00:00",
                "game": {"player_count": 587},
            }
        ),
        encoding="utf-8",
    )
    briefing = tmp_path / "briefing.md"
    briefing.write_text("# Briefing\n", encoding="utf-8")
    output = tmp_path / "dist"

    info = build_site(
        dashboard_dir=dashboard,
        data_path=data,
        briefing_path=briefing,
        output_dir=output,
    )

    assert info["player_count"] == 587
    assert (output / "data/latest.json").is_file()
    assert (output / "data/briefing.md").is_file()
    assert (output / ".nojekyll").is_file()
    assert not (tmp_path / ".dist.previous").exists()
