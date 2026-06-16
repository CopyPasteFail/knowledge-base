from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import shutil

import pytest

from tools import process_html


@pytest.fixture()
def isolated_site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    source_dir = tmp_path / "raw-html"
    output_dir = tmp_path / "docs"
    assets_dir = tmp_path / "assets"
    output_assets_dir = output_dir / "assets"

    (source_dir / "ai").mkdir(parents=True)
    (source_dir / "devops-interview-prep").mkdir(parents=True)
    assets_dir.mkdir()

    (assets_dir / "style.css").write_text("body {}", encoding="utf-8")
    (assets_dir / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
    (assets_dir / "site.webmanifest").write_text("{}", encoding="utf-8")
    (assets_dir / "site.js").write_text("console.log('ok')", encoding="utf-8")

    share_host = "share.evernote." + "com"
    (source_dir / "ai" / "Execution Tools.html").write_text(
        f"""<!doctype html>
<html>
<head><title>Execution Tools</title></head>
<body>
<en-note class="peso">
<icons><svg aria-hidden="true"><symbol id="sprite"></symbol></svg></icons>
<h1>Execution Tools</h1>
<h2>Runtime choices</h2>
<p>Use <code>vLLM</code> for serving.</p>
<p>
  <a href="evernote:///view/123/s1/guid/context-rot/">Context Rot</a>
  <a href="https://{share_host}/note/abc123">AI Safety</a>
  <a href="https://github.com/gepa-ai/gepa">GEPA on GitHub</a>
  <a href="https://gepa-ai.github.io/gepa/guides/quickstart/">GEPA quickstart</a>
</p>
<h2></h2>
<h3>Operational notes</h3>
<pre><code>python app.py</code></pre>
</en-note>
</body>
</html>
""",
        encoding="utf-8",
    )
    (source_dir / "devops-interview-prep" / "DevOps Screening Cheat-sheet.html").write_text(
        "<h1>DevOps Screening Cheat-sheet</h1><p>Questions and notes.</p>",
        encoding="utf-8",
    )

    monkeypatch.setattr(process_html, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(process_html, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(process_html, "SOURCE_ASSETS_DIR", assets_dir)
    monkeypatch.setattr(process_html, "OUTPUT_ASSETS_DIR", output_assets_dir)

    yield output_dir

    shutil.rmtree(tmp_path, ignore_errors=True)


def test_generator_preserves_static_urls_and_adds_devbrain_shell(
    isolated_site: Path,
):
    process_html.main()

    assert (isolated_site / "ai" / "execution-tools.html").exists()
    assert (isolated_site / "devops-interview-prep" / "devops-screening-cheat-sheet.html").exists()

    article = (isolated_site / "ai" / "execution-tools.html").read_text(encoding="utf-8")
    assert 'class="devbrain-header"' in article
    assert 'class="docs-layout"' in article
    assert '<div class="desktop-docs-nav">' in article
    assert '<details class="mobile-docs-nav">' in article
    assert '<summary class="mobile-docs-summary">' in article
    assert 'href="../assets/style.css"' in article
    assert 'src="../assets/site.js"' in article
    assert "devbrain-theme" in article
    assert "data-theme-toggle" in article
    assert ">API<" not in article
    assert ">Changelog<" not in article
    assert ">Community<" not in article
    assert ">GitHub<" not in article
    assert 'href="execution-tools.html" class="tree-link is-active"' in article
    assert 'href="#runtime-choices"' in article
    assert "Operational notes" in article
    assert "evernote:///" not in article
    assert "Context Rot" not in article
    assert ("share.evernote." + "com") not in article
    assert "AI Safety" not in article
    assert 'href="https://github.com/gepa-ai/gepa"' in article
    assert 'href="https://gepa-ai.github.io/gepa/guides/quickstart/"' in article
    assert "<h2></h2>" in article
    assert "<en-note" not in article
    assert "<icons>" not in article


def test_sanitize_evernote_links_removes_share_links_with_quoted_and_unquoted_hrefs() -> None:
    share_host = "share.evernote." + "com"
    html_text = f"""
<p>
  <a href="https://{share_host}/note/double">Double quoted</a>
  <a href='https://{share_host}/note/single'>Single quoted</a>
  <a href=https://{share_host}/note/unquoted>Unquoted</a>
  <a href="https://github.com/gepa-ai/gepa">GEPA on GitHub</a>
</p>
"""

    sanitized = process_html.sanitize_evernote_links(html_text)

    assert share_host not in sanitized
    assert "Double quoted" not in sanitized
    assert "Single quoted" not in sanitized
    assert "Unquoted" not in sanitized
    assert 'href="https://github.com/gepa-ai/gepa"' in sanitized


def test_generator_removes_empty_hierarchical_sections(isolated_site: Path) -> None:
    source = isolated_site.parent / "raw-html" / "ai" / "Private Links Only.html"
    share_host = "share.evernote." + "com"
    source.write_text(
        f"""<!doctype html>
<html>
<head><title>Private Links Only</title></head>
<body>
<en-note class="peso">
<h1>Private Links Only</h1>
<h1>Reference Bucket</h1>
<h2>Related notes</h2>
<ul role="list">
  <li><div><div class="para"><a href="https://{share_host}/note/abc123">Private note</a></div></div></li>
</ul>
<h1>Useful stuff</h1>
<h2>External links</h2>
<ul role="list">
  <li><a href="https://example.com/">Example</a></li>
</ul>
</en-note>
</body>
</html>
""",
        encoding="utf-8",
    )

    process_html.main()

    article = (isolated_site / "ai" / "private-links-only.html").read_text(encoding="utf-8")
    assert "Reference Bucket" not in article
    assert "Related notes" not in article
    assert "Private note" not in article
    assert share_host not in article
    assert 'href="#reference-bucket"' not in article
    assert 'href="#related-notes"' not in article
    assert "Useful stuff" in article
    assert "External links" in article
    assert 'href="https://example.com/"' in article


def test_homepage_contains_lightweight_search_index_and_deterministic_sections(
    isolated_site: Path,
):
    process_html.main()

    homepage = (isolated_site / "index.html").read_text(encoding="utf-8")
    assert "DevBrain" in homepage
    assert "devbrain-theme" in homepage
    assert ">API<" not in homepage
    assert ">Changelog<" not in homepage
    assert ">Community<" not in homepage
    assert ">GitHub<" not in homepage
    assert 'data-search-input' in homepage
    assert 'data-search-item data-title="Execution Tools"' in homepage
    assert 'href="ai/execution-tools.html"' in homepage
    assert 'href="devops-interview-prep/devops-screening-cheat-sheet.html"' in homepage
    assert "Recent updates" not in homepage
    assert "Quick links" not in homepage
