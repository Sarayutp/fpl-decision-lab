from __future__ import annotations

import argparse
from pathlib import Path

from fpl_mvp.api import FPLClient
from fpl_mvp.backtest import rolling_backtest, write_backtest_report
from fpl_mvp.config import Settings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a rolling, no-lookahead xP v2 backtest on public player history."
    )
    parser.add_argument("--player-limit", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("data/model-backtest.json"))
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()

    with FPLClient(
        base_url=settings.base_url,
        cache_dir=settings.cache_dir,
        timeout_seconds=settings.timeout_seconds,
        retries=settings.retries,
        cache_ttl_seconds=settings.cache_ttl_seconds,
        force_refresh=args.force_refresh,
    ) as client:
        bootstrap = client.get_bootstrap()
        players = sorted(
            bootstrap.elements,
            key=lambda player: float(player.selected_by_percent or 0),
            reverse=True,
        )[: max(1, args.player_limit)]
        histories = {
            player.id: client.get_player_summary(player.id).history for player in players
        }

    report = rolling_backtest(players, histories)
    report["selection"] = {
        "method": "highest current ownership",
        "requested_player_limit": args.player_limit,
        "player_count": len(players),
    }
    write_backtest_report(report, args.output)
    print(
        f"Wrote {args.output}: {report['status']} / "
        f"{report['sample_count']} samples / {len(report['evaluated_gameweeks'])} Gameweeks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
