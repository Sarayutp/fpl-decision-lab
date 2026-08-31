from __future__ import annotations

import base64
import gzip
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from fpl_mvp.site import build_site

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("smoke_site", ROOT / "scripts/smoke_site.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def fixture_build(tmp_path, stamp="2026-08-31T00:00:00+00:00"):
    data = json.loads(gzip.decompress(base64.b64decode((ROOT / "tests/fixtures/owned-team-gw3.json.gz.b64").read_text())))
    data["generated_at"] = stamp
    data_path = tmp_path / "latest.json"; data_path.write_text(json.dumps(data))
    briefing = tmp_path / "briefing.md"
    briefing.write_text(f"- Team ID: 990001\n- เป้าหมาย: Gameweek 3\n- สร้างเมื่อ: {stamp}\n")
    info = build_site(dashboard_dir=ROOT / "dashboard", data_path=data_path, briefing_path=briefing, output_dir=tmp_path / "site")
    return info


def test_local_release_smoke_and_artifact_rollback(tmp_path):
    original = fixture_build(tmp_path)
    archive = tmp_path / "saved-release"
    shutil.copytree(tmp_path / "site", archive)
    newer = fixture_build(tmp_path, "2026-08-31T02:00:00+00:00")
    assert newer["build_id"] != original["build_id"]
    assert smoke.check_site(str(tmp_path / "site"), newer["build_id"])["status"] == "passed"
    # Rehearse restoration in isolated test directories; never touch a working deployment.
    restored = tmp_path / "restored"
    shutil.copytree(archive, restored)
    assert smoke.check_site(str(restored), original["build_id"])["status"] == "passed"
    assert json.loads((restored / "data/latest.json").read_text())["generated_at"] == original["data_generated_at"]


def test_smoke_rejects_a_mixed_or_modified_release(tmp_path):
    fixture_build(tmp_path)
    (tmp_path / "site/assets/app.js").write_text("broken")
    with pytest.raises(ValueError, match="hash mismatch"):
        smoke.check_site(str(tmp_path / "site"))


@pytest.mark.parametrize("module", ["scenario-compare", "decision-card"])
def test_smoke_covers_new_linked_assets_but_accepts_legacy_manifests(tmp_path, module):
    fixture_build(tmp_path)
    site = tmp_path / "site"
    info_path = site / "build-info.json"
    info = json.loads(info_path.read_text())
    del info["asset_sha256"][f"assets/{module}.js"]
    info_path.write_text(json.dumps(info))
    with pytest.raises(ValueError, match="Referenced assets"):
        smoke.check_site(str(site))
    # Legacy Phase 6 HTML did not reference the comparison module. Keep its 9-file contract valid.
    import hashlib
    import re
    index = re.sub(r'\s*<script src="\./assets/(?:scenario-compare|decision-card)\.js[^\"]*" defer></script>', "", (site / "index.html").read_text())
    for name in ("scenario-compare", "decision-card"):
        info["asset_sha256"].pop(f"assets/{name}.js", None)
    index = re.sub(r'\s*<a href="\./guide.html">[^<]+</a>', "", index)
    for name in ("guide.html", "guide.md", "assets/guide.css", "assets/guide.js"):
        info["asset_sha256"].pop(name)
    (site / "index.html").write_text(index)
    info["asset_sha256"]["index.html"] = hashlib.sha256(index.encode()).hexdigest()
    info_path.write_text(json.dumps(info))
    assert smoke.check_site(str(site))["assets_checked"] == 9


@pytest.mark.parametrize("missing", ["guide.html", "guide.md", "assets/guide.css", "assets/guide.js"])
def test_smoke_requires_the_linked_guide_and_download(tmp_path, missing):
    fixture_build(tmp_path)
    path = tmp_path / "site/build-info.json"
    info = json.loads(path.read_text())
    del info["asset_sha256"][missing]
    path.write_text(json.dumps(info))
    with pytest.raises(ValueError, match="Guide files"):
        smoke.check_site(str(tmp_path / "site"))


def test_build_rejects_same_team_same_gw_but_old_briefing(tmp_path):
    fixture_build(tmp_path)
    (tmp_path / "briefing.md").write_text("- Team ID: 990001\n- เป้าหมาย: Gameweek 3\n- สร้างเมื่อ: 2000-01-01\n")
    with pytest.raises(ValueError, match="timestamp"):
        build_site(dashboard_dir=ROOT / "dashboard", data_path=tmp_path / "latest.json", briefing_path=tmp_path / "briefing.md", output_dir=tmp_path / "site")


def test_frontend_release_matches_package_metadata():
    from fpl_mvp.release import RELEASE_VERSION
    assert f'APP_RELEASE = "{RELEASE_VERSION}"' in (ROOT / "dashboard/assets/runtime.js").read_text()


def test_restore_requires_a_successful_main_deployment():
    restore_spec = importlib.util.spec_from_file_location("verify_restore", ROOT / "scripts/verify_restore.py")
    restore = importlib.util.module_from_spec(restore_spec); restore_spec.loader.exec_module(restore)
    valid = {"conclusion":"success", "head_branch":"main", "path":".github/workflows/deploy-pages.yml", "event":"push", "head_repository":{"full_name":"owner/repo"}}
    restore.validate_run(valid, "owner/repo")
    for field, value in [("conclusion","failure"),("head_branch","feature"),("path",".github/workflows/ci.yml"),("event","pull_request"),("head_repository",{"full_name":"fork/repo"})]:
        with pytest.raises(ValueError): restore.validate_run({**valid, field:value}, "owner/repo")
