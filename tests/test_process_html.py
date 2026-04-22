from __future__ import annotations

import shutil

import pytest

from tools import process_html


@pytest.fixture()
def isolated_site(tmp_path, monkeypatch):
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

    (source_dir / "ai" / "Execution Tools.html").write_text(
        """<!doctype html>
<html>
<head><title>Execution Tools</title></head>
<body>
<en-note class="peso">
<icons><svg aria-hidden="true"><symbol id="sprite"></symbol></svg></icons>
<h1>Execution Tools</h1>
<h2>Runtime choices</h2>
<p>Use <code>vLLM</code> for serving.</p>
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


def test_generator_preserves_static_urls_and_adds_devbrain_shell(isolated_site):
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
    assert 'href="execution-tools.html" class="tree-link is-active"' in article
    assert 'href="#runtime-choices"' in article
    assert "Operational notes" in article
    assert "<h2></h2>" in article
    assert "<en-note" not in article
    assert "<icons>" not in article


def test_homepage_contains_lightweight_search_index_and_deterministic_sections(isolated_site):
    process_html.main()

    homepage = (isolated_site / "index.html").read_text(encoding="utf-8")
    assert "DevBrain" in homepage
    assert 'data-search-input' in homepage
    assert 'data-search-item data-title="Execution Tools"' in homepage
    assert 'href="ai/execution-tools.html"' in homepage
    assert 'href="devops-interview-prep/devops-screening-cheat-sheet.html"' in homepage
    assert "Recent updates" in homepage
