from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re

import pytest

from fpl_mvp.guide import render_guide
from fpl_mvp.release import RELEASE_VERSION

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = "<h1>{{guide_title}}</h1><nav>{{guide_toc}}</nav><article>{{guide_body}}</article>{{release}}"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a":
            self.hrefs.append(attrs.get("href", ""))


def test_guide_renders_all_chapters_and_resolves_every_local_link():
    html = render_guide((ROOT / "dashboard/guide.md").read_text(), (ROOT / "dashboard/guide.html").read_text())
    guide = Links(); guide.feed(html)
    dashboard = Links(); dashboard.feed((ROOT / "dashboard/index.html").read_text())
    assert len(guide.ids) == len(set(guide.ids))
    assert re.findall(r'<h2 id="(guide-\d+)"', html) == [f"guide-{n:02}" for n in range(1, 23)]
    assert RELEASE_VERSION in html
    assert "{{guide_" not in html
    assert '<th scope="col">' in html
    assert "<table class=\"guide-table\">" in html
    for href in guide.hrefs:
        if href.startswith("#"):
            assert href[1:] in guide.ids, href
        if href.startswith("./index.html#"):
            assert href.split("#")[1] in dashboard.ids, href


def test_guide_disables_raw_html_images_and_unsafe_links():
    html = render_guide('# <script>bad()</script>\n\n## 01. <b>Safe</b>\n\n<script>bad()</script>\n\n[bad](javascript:alert(1))\n\n![no image](https://example.com/x.png)\n', TEMPLATE)
    assert "<script>" not in html
    assert "<b>Safe</b>" not in html
    assert 'href="javascript:' not in html
    assert "<img" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.parametrize("markdown", ["No title", "# Title\n\nNo chapters", "# Title\n\n# Extra\n", "# Title\n\n## Start", "# Title\n\n## 02. Gap", "# Title\n\n## 01. First\n\n## 01. Duplicate"])
def test_guide_rejects_incomplete_or_ambiguous_structure(markdown):
    with pytest.raises(ValueError):
        render_guide(markdown, TEMPLATE)


def test_guide_requires_template_placeholders():
    with pytest.raises(ValueError, match="template marker"):
        render_guide("# Title\n\n## 01. Start", "<h1>empty</h1>")


def test_internal_dashboard_links_work_under_pages_subpaths():
    html = render_guide("# Title\n\n## 01. Start\n\n[Planner](https://sarayutp.github.io/fpl-decision-lab/#chip-planner)\n\n[Source](https://example.com/)", TEMPLATE)
    assert 'href="./index.html#chip-planner"' in html
    assert 'href="https://example.com/" rel="noreferrer"' in html
