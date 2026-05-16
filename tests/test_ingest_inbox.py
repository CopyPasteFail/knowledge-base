from __future__ import annotations

from pathlib import Path

import pytest

from tools import ingest_inbox
from tools import process_html


def configure_tmp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    inbox = tmp_path / "inbox"
    docs = tmp_path / "docs"
    assets = tmp_path / "assets"
    output_assets = docs / "assets"

    (inbox / "ai").mkdir(parents=True)
    (inbox / "devops-interview-prep").mkdir(parents=True)
    docs.mkdir()
    assets.mkdir()

    for section in ["ai", "devops-interview-prep"]:
        (inbox / section / ".gitkeep").write_text("", encoding="utf-8")

    (assets / "style.css").write_text("body {}", encoding="utf-8")
    (assets / "site.js").write_text("console.log('ok')", encoding="utf-8")
    (assets / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
    (assets / "site.webmanifest").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(ingest_inbox, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ingest_inbox, "INBOX_DIR", inbox)
    monkeypatch.setattr(ingest_inbox, "DOCS_DIR", docs)
    monkeypatch.setattr(process_html, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(process_html, "OUTPUT_DIR", docs)
    monkeypatch.setattr(process_html, "SOURCE_ASSETS_DIR", assets)
    monkeypatch.setattr(process_html, "OUTPUT_ASSETS_DIR", output_assets)

    return inbox, docs, assets


def test_plan_ingest_overwrites_same_slug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inbox, docs, _assets = configure_tmp_repo(tmp_path, monkeypatch)
    existing = docs / "ai" / "execution-tools.html"
    existing.parent.mkdir(parents=True)
    existing.write_text(
        """<!doctype html>
<html><head><title>Old Execution Tools · DevBrain</title></head>
<body><p class="article-meta">Source: Execution Tools.html</p></body></html>
""",
        encoding="utf-8",
    )

    source = inbox / "ai" / "Execution Tools.html"
    source.write_text("<h1>Execution Tools</h1><p>Updated content.</p>", encoding="utf-8")

    ingest_inbox.validate_inbox_files([source])
    planned = ingest_inbox.plan_ingest([source])

    assert len(planned) == 1
    assert planned[0].action == "overwrite"
    assert planned[0].output_relpath == "ai/execution-tools.html"


def test_validate_inbox_rejects_batch_slug_collision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inbox, _docs, _assets = configure_tmp_repo(tmp_path, monkeypatch)
    first = inbox / "ai" / "Execution Tools.html"
    second = inbox / "ai" / "Execution_Tools.html"
    first.write_text("<h1>Execution Tools</h1>", encoding="utf-8")
    second.write_text("<h1>Execution Tools Copy</h1>", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        ingest_inbox.validate_inbox_files([first, second])

    assert "collides" in str(excinfo.value)
    assert "docs/ai/execution-tools.html" in str(excinfo.value)


def test_generate_writes_previewable_article_and_indexes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inbox, docs, _assets = configure_tmp_repo(tmp_path, monkeypatch)
    source = inbox / "ai" / "Execution Tools.html"
    source.write_text(
        """<!doctype html>
<html>
<head><title>Execution Tools</title></head>
<body><en-note><h1>Execution Tools</h1><h2>Runtime choices</h2><p>Use vLLM.</p></en-note></body>
</html>
""",
        encoding="utf-8",
    )

    planned = ingest_inbox.plan_ingest([source])
    written = ingest_inbox.generate(planned)

    article = docs / "ai" / "execution-tools.html"
    assert article in written
    assert article.exists()
    article_html = article.read_text(encoding="utf-8")
    assert "Execution Tools" in article_html
    assert "Runtime choices" in article_html
    assert "<en-note" not in article_html
    assert (docs / "ai" / "index.html").exists()
    assert (docs / "index.html").exists()
