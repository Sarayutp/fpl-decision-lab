"""Serve anonymized, time-rebased Phase 6 browser regression states."""
from __future__ import annotations

import argparse
import base64
import gzip
import json
from datetime import UTC, datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
FIXTURE = ROOT / "tests/fixtures/owned-team-gw3.json.gz.b64"
QA_NOW = datetime.now(UTC).replace(microsecond=0)


def snapshot(state: str) -> dict:
    payload = base64.b64decode("".join(FIXTURE.read_text().split()))
    data = json.loads(gzip.decompress(payload))
    now = QA_NOW
    previous = data["generated_at"]
    generated = now.isoformat()
    text = json.dumps(data).replace(previous, generated)
    data = json.loads(text)
    source_time = now - timedelta(hours=49) if state == "stale" else now
    data["generated_at"] = generated
    data["identity"]["verified_at"] = generated
    data["data_quality"].update(oldest_source_at=source_time.isoformat(), newest_source_at=generated,
                                assessed_at=generated, age_hours=49 if state == "stale" else 0,
                                is_stale=state == "stale", status="stale" if state == "stale" else "fresh")
    data["game"]["next_gameweek"]["deadline_time"] = (now + timedelta(days=7)).isoformat()
    data["gameweek_decision"]["target_gameweek"]["deadline_time"] = data["game"]["next_gameweek"]["deadline_time"]
    if state == "deadline":
        data["game"]["next_gameweek"]["deadline_time"] = (now - timedelta(minutes=2)).isoformat()
        data["gameweek_decision"]["target_gameweek"]["deadline_time"] = data["game"]["next_gameweek"]["deadline_time"]
    if state == "incompatible": data["schema_version"] = 999
    if state == "empty":
        data["team"].update(picks=[], source_status="local_required")
        decision = data["gameweek_decision"]
        decision["status"] = "unavailable"
        decision["starting_xi"].update(status="unavailable", squad=[], players=[])
        decision["captaincy"].update(captain=None, vice_captain=None)
        decision["bench"].update(players=[], outfield_order=[], goalkeeper=None)
        data["analysis"]["recommendations"]["chip_planner"]["status"] = "unavailable"
    return data


def briefing(data: dict, state: str) -> bytes:
    team = 999_999 if state == "mismatch" else data["manager"]["team_id"]
    return (f"# FPL Decision Briefing\n\n- สร้างเมื่อ: {data['generated_at']}\n"
            f"- เป้าหมาย: {data['game']['next_gameweek']['name']}\n- Team ID: {team}\n").encode()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(DIST), **kwargs)
    def do_GET(self) -> None:  # noqa: N802 - stdlib hook
        parsed = urlparse(self.path)
        state = parse_qs(parsed.query).get("qaState", ["ready"])[0]
        if parsed.path in {"/qa.html", "/qa.js", "/qa.css"}:
            path = ROOT / "tests/browser" / parsed.path.removeprefix("/")
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", {".html":"text/html; charset=utf-8", ".js":"text/javascript; charset=utf-8", ".css":"text/css"}[path.suffix])
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if parsed.path == "/data/latest.json":
            if state == "error": return self.send_error(503, "QA snapshot unavailable")
            body = json.dumps(snapshot(state), ensure_ascii=False, separators=(",", ":")).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            if state == "offline": self.send_header("X-FPL-Cache", "offline")
            self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if parsed.path == "/data/briefing.md":
            if state == "partial": return self.send_error(503, "QA briefing unavailable")
            data = snapshot(state)
            body = briefing(data, state)
            self.send_response(200); self.send_header("Content-Type", "text/markdown; charset=utf-8")
            if state == "offline": self.send_header("X-FPL-Cache", "offline")
            self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        self.path = parsed.path
        super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--port", type=int, default=8011); args = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__": main()
