"""Read-only release smoke check for a local artifact or an HTTP(S) Pages URL."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen


REQUIRED = {"index.html", "assets/app.js", "assets/runtime.js", "assets/decision-log.js", "assets/styles.css", "sw.js", "manifest.webmanifest", "data/latest.json", "data/briefing.md"}


def check_site(target: str, expected_build: str | None = None) -> dict:
    remote = target.startswith(("https://", "http://"))
    base = target.rstrip("/") + "/"

    def read(relative: str) -> bytes:
        if relative.startswith("/") or ".." in Path(relative).parts or ":" in relative:
            raise ValueError("Unsafe artifact path")
        if remote:
            request = Request(urljoin(base, relative), headers={"Cache-Control": "no-cache"})
            with urlopen(request, timeout=20) as response:
                return response.read()
        return (Path(target) / relative).read_bytes()

    info = json.loads(read("build-info.json"))
    if expected_build and info.get("build_id") != expected_build:
        raise ValueError("Published build does not match the expected artifact")
    hashes = info.get("asset_sha256", {})
    if not REQUIRED.issubset(hashes):
        raise ValueError("Incomplete release manifest")
    payloads = {}
    for relative, digest in hashes.items():
        body = read(relative)
        if hashlib.sha256(body).hexdigest() != digest:
            raise ValueError(f"Release hash mismatch: {relative}")
        payloads[relative] = body
    snapshot = json.loads(payloads["data/latest.json"])
    if snapshot.get("schema_version") != 2 or info.get("schema_version") != 2:
        raise ValueError("Unsupported schema")
    if snapshot["generated_at"] != info["data_generated_at"]:
        raise ValueError("Snapshot timestamp mismatch")
    identity = snapshot["identity"]
    if not identity.get("verified") or identity["snapshot_team_id"] != info["team_id"] or snapshot["manager"]["team_id"] != info["team_id"]:
        raise ValueError("Team identity mismatch")
    briefing = payloads["data/briefing.md"].decode()
    for pattern, expected in [(r"^- Team ID: (.+)$", str(info["team_id"])), (r"^- สร้างเมื่อ: (.+)$", snapshot["generated_at"])]:
        match = re.search(pattern, briefing, re.MULTILINE)
        if not match or match.group(1).strip() != expected:
            raise ValueError("Briefing belongs to another snapshot")
    runtime = payloads["assets/runtime.js"].decode()
    if f'APP_RELEASE = "{info["release_version"]}"' not in runtime:
        raise ValueError("Frontend release version mismatch")
    if info["build_id"] not in payloads["sw.js"].decode():
        raise ValueError("Service-worker build mismatch")
    index = payloads["index.html"].decode()
    # New assets must be covered, while archived Phase 6 releases remain restorable.
    linked_assets = set(re.findall(r'(?:src|href)="\./(assets/[^"?]+)(?:\?[^\"]*)?"', index))
    if not linked_assets.issubset(hashes):
        raise ValueError("Referenced assets missing from release manifest")
    for anchor in ["this-gameweek", "transfer-advisor", "chip-planner", "decision-log", "players", "system", "runtime-state"]:
        if f'id="{anchor}"' not in index:
            raise ValueError(f"Missing page section: {anchor}")
    return {"status": "passed", "build_id": info["build_id"], "release": info["release_version"], "team_id": info["team_id"], "assets_checked": len(hashes), "data_generated_at": info["data_generated_at"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="dist directory or Pages base URL")
    parser.add_argument("--expected-build")
    args = parser.parse_args()
    print(json.dumps(check_site(args.target, args.expected_build), indent=2))


if __name__ == "__main__":
    main()
