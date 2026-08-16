from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Sequence

from .config import Settings
from .pipeline import run_pipeline
from .site import build_site


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fpl-refresh",
        description="Fetch public FPL data and build a validated Dashboard snapshot.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="refresh",
        choices=["refresh", "build-site", "all"],
        help="refresh data, build the static site, or run both (default: refresh)",
    )
    parser.add_argument("--team-id", type=int, help="Public FPL team ID")
    parser.add_argument("--base-url", help="FPL API base URL")
    parser.add_argument("--cache-dir", type=Path, help="JSON cache directory")
    parser.add_argument("--output", type=Path, help="Snapshot output path")
    parser.add_argument("--briefing-output", type=Path, help="AI briefing output path")
    parser.add_argument("--dashboard-dir", type=Path, help="Dashboard source directory")
    parser.add_argument("--site-output", type=Path, help="Built static site directory")
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore fresh cache and request every endpoint again",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env().with_overrides(
        team_id=args.team_id,
        base_url=args.base_url,
        cache_dir=args.cache_dir,
        output_path=args.output,
        briefing_path=args.briefing_output,
        dashboard_dir=args.dashboard_dir,
        site_output_dir=args.site_output,
    )
    if args.command in {"refresh", "all"}:
        snapshot = run_pipeline(settings, force_refresh=args.force_refresh)
        game = snapshot["game"]
        diagnostics = snapshot["diagnostics"]
        next_event = game["next_gameweek"]
        next_label = (
            f"{next_event['name']} at {next_event['deadline_time']}"
            if next_event
            else "season complete"
        )
        print(f"Wrote {settings.output_path} and {settings.briefing_path}")
        print(
            f"Validated {game['player_count']} players, {game['team_count']} teams, "
            f"and {game['fixture_count']} fixtures."
        )
        sources = Counter(fetch["source"] for fetch in diagnostics["fetches"])
        if sources:
            source_summary = ", ".join(
                f"{source}={count}" for source, count in sorted(sources.items())
            )
            print(f"Data sources: {source_summary}")
        print(f"Next deadline: {next_label}")
        if diagnostics["warnings"]:
            print("Warnings:")
            for warning in diagnostics["warnings"]:
                print(f"- {warning}")

    if args.command in {"build-site", "all"}:
        build_info = build_site(
            dashboard_dir=settings.dashboard_dir,
            data_path=settings.output_path,
            briefing_path=settings.briefing_path,
            output_dir=settings.site_output_dir,
        )
        print(
            f"Built {settings.site_output_dir} with {build_info['player_count']} players "
            f"(data {build_info['data_generated_at']})."
        )
    return 0
