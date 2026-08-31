"""Build the help page from one reviewable Markdown source, without client data."""
from __future__ import annotations

from html import escape
from pathlib import Path
import re

from markdown_it import MarkdownIt

from .release import RELEASE_VERSION

PUBLIC_APP = "https://sarayutp.github.io/fpl-decision-lab/"


def render_guide(markdown: str, template: str) -> str:
    parser = MarkdownIt("commonmark", {"html": False}).enable("table").disable("image")
    tokens = parser.parse(markdown)
    if not tokens or tokens[0].type != "heading_open" or tokens[0].tag != "h1":
        raise ValueError("Guide must start with one H1 title")
    title = tokens[1].content
    tokens = tokens[3:]
    toc = []
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            if token.tag == "h1":
                raise ValueError("Guide must have exactly one H1")
            if token.tag == "h2":
                heading = tokens[index + 1].content
                number = re.match(r"(\d{2})\. ", heading)
                if not number or int(number[1]) != len(toc) + 1:
                    raise ValueError("Guide chapters must be numbered sequentially")
                anchor = f"guide-{number[1]}"
                token.attrSet("id", anchor)
                toc.append(f'<li><a href="#{anchor}">{escape(heading)}</a></li>')
        if token.type == "th_open":
            token.attrSet("scope", "col")
        if token.type == "table_open":
            token.attrSet("class", "guide-table")
        for child in token.children or []:
            if child.type == "link_open":
                href = child.attrGet("href") or ""
                if href.startswith(PUBLIC_APP):
                    child.attrSet("href", "./index.html" + href[len(PUBLIC_APP):])
                if href.startswith(("http://", "https://")):
                    child.attrSet("rel", "noreferrer")
    if not toc:
        raise ValueError("Guide needs chapters")
    replacements = {"{{guide_title}}": escape(title), "{{guide_body}}": parser.renderer.render(tokens, parser.options, {}),
                    "{{guide_toc}}": "\n".join(toc), "{{release}}": escape(RELEASE_VERSION)}
    for marker, value in replacements.items():
        if marker not in template:
            raise ValueError(f"Missing guide template marker: {marker}")
        template = template.replace(marker, value)
    return template


def build_guide(directory: Path) -> None:
    target = directory / "guide.html"
    target.write_text(render_guide((directory / "guide.md").read_text(encoding="utf-8"),
                                  target.read_text(encoding="utf-8")), encoding="utf-8")
