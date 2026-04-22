from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TypedDict
import html
import re
import shutil
import unicodedata


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "raw-html"
OUTPUT_DIR = REPO_ROOT / "docs"
SOURCE_ASSETS_DIR = REPO_ROOT / "assets"
OUTPUT_ASSETS_DIR = OUTPUT_DIR / "assets"

GENERATED_MARKER = "<!-- generated-by: tools/process_html.py -->"


class TocItem(TypedDict):
    level: str
    title: str
    id: str


class ArticleEntry(TypedDict):
    source_path: Path
    source_name: str
    output_path: Path
    output_name: str
    output_relpath: str
    title: str
    section: str


def slugify_filename(filename: str) -> str:
    stem = Path(filename).stem

    stem = unicodedata.normalize("NFKD", stem)
    stem = stem.encode("ascii", "ignore").decode("ascii")

    stem = stem.lower()
    stem = stem.replace("_", "-")
    stem = re.sub(r"\s+", "-", stem)
    stem = re.sub(r"[^a-z0-9-]+", "", stem)
    stem = re.sub(r"-{2,}", "-", stem)
    stem = stem.strip("-")

    if not stem:
        stem = "page"

    return f"{stem}.html"


def slugify_segment(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = text.replace("_", "-")
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^a-z0-9-]+", "", text)
    text = re.sub(r"-{2,}", "-", text)
    text = text.strip("-")
    return text or "section"


def humanize_slug(slug: str) -> str:
    return " ".join(word.capitalize() for word in slug.replace("-", " ").split())


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_title(html_text: str, fallback_filename: str) -> str:
    title_match = re.search(
        r"<title[^>]*>\s*(.*?)\s*</title>",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if title_match:
        title = clean_text(title_match.group(1))
        if title:
            return title

    h1_match = re.search(
        r"<h1[^>]*>\s*(.*?)\s*</h1>",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if h1_match:
        title = clean_text(h1_match.group(1))
        if title:
            return title

    stem = Path(fallback_filename).stem.replace("-", " ")
    return " ".join(word.capitalize() for word in stem.split())


def is_evernote_export(html_text: str) -> bool:
    markers = [
        'itemprop="application" content="Evernote"',
        "itemprop='application' content='Evernote'",
        "<en-note",
        "en-note.peso",
        "Evernote Corporation",
    ]
    return any(marker in html_text for marker in markers)


def remove_empty_wrappers(html_text: str) -> str:
    previous = None
    while previous != html_text:
        previous = html_text

        html_text = re.sub(
            r"<div>\s*</div>",
            "",
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        html_text = re.sub(
            r"<span[^>]*>\s*</span>",
            "",
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        html_text = re.sub(
            r"<p>\s*</p>",
            "",
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        html_text = re.sub(
            r"<div>\s*(?:<div>\s*</div>\s*|<span[^>]*>\s*</span>\s*)+</div>",
            "",
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )

    return html_text


def strip_embedded_styling(html_text: str) -> str:
    html_text = re.sub(
        r"<style\b[^>]*>.*?</style>",
        "",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    html_text = re.sub(
        r'<link\b[^>]*rel=["\']?stylesheet["\']?[^>]*>',
        "",
        html_text,
        flags=re.IGNORECASE,
    )

    html_text = re.sub(
        r'\sstyle\s*=\s*(".*?"|\'.*?\'|[^\s>]+)',
        "",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for attr in ["bgcolor", "text", "link", "vlink", "alink"]:
        html_text = re.sub(
            rf'\s{attr}\s*=\s*(".*?"|\'.*?\'|[^\s>]+)',
            "",
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )

    return html_text


def strip_evernote_checklists(html_text: str) -> str:
    html_text = re.sub(
        r"<en-todo\b[^>]*>\s*</en-todo>",
        "",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    html_text = re.sub(
        r"<en-todo\b[^>]*/>",
        "",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    html_text = re.sub(
        r"<input\b[^>]*type\s*=\s*['\"]checkbox['\"][^>]*>",
        "",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    html_text = re.sub(
        r'<div\b[^>]*class\s*=\s*["\'][^"\']*\blist-bullet-todo-container\b[^"\']*["\'][^>]*>\s*</div>',
        "",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    html_text = re.sub(
        r'<div\b([^>]*)class\s*=\s*["\'][^"\']*\blist-content\b[^"\']*["\']([^>]*)>',
        "<div>",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for attr in ["data-checked", "aria-checked", "contenteditable", "draggable", "tabindex"]:
        html_text = re.sub(
            rf'\s{attr}\s*=\s*(".*?"|\'.*?\'|[^\s>]+)',
            "",
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )

    def strip_classes(match: re.Match[str]) -> str:
        value = match.group(2)
        classes = [c for c in re.split(r"\s+", value.strip()) if c]
        classes = [
            c for c in classes
            if c not in {
                "list-bullet-todo-container",
                "list-bullet-todo",
                "list-content",
            }
        ]
        if classes:
            return f' class="{" ".join(classes)}"'
        return ""

    html_text = re.sub(
        r'(\sclass\s*=\s*["\'])([^"\']*)(["\'])',
        strip_classes,
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return remove_empty_wrappers(html_text)


def strip_evernote_heading_controls(html_text: str) -> str:
    if not is_evernote_export(html_text):
        return html_text

    control_class_names = {
        "Mx5dH",
        "Tuuvp",
        "E80MK",
        "i3yTS",
        "E6zaj",
    }

    def strip_classes(match: re.Match[str]) -> str:
        value = match.group(2)
        classes = [c for c in re.split(r"\s+", value.strip()) if c]
        classes = [c for c in classes if c not in control_class_names]
        if classes:
            return f' class="{" ".join(classes)}"'
        return ""

    html_text = re.sub(
        r'(\sclass\s*=\s*["\'])([^"\']*)(["\'])',
        strip_classes,
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return remove_empty_wrappers(html_text)


def strip_evernote_generated_toc(html_text: str) -> str:
    if not is_evernote_export(html_text):
        return html_text

    pattern = re.compile(
        r"""
        <
        (?P<tag>div|section|nav|aside)
        (?P<attrs>[^>]*data-testid\s*=\s*["']tableofcontents["'][^>]*)
        >
        (?P<body>.*?)
        </(?P=tag)>
        """,
        flags=re.IGNORECASE | re.DOTALL | re.VERBOSE,
    )

    previous = None
    while previous != html_text:
        previous = html_text
        html_text = pattern.sub("", html_text)

    return remove_empty_wrappers(html_text)


def strip_evernote_shell_artifacts(html_text: str) -> str:
    html_text = re.sub(
        r"<icons\b[^>]*>.*?</icons>",
        "",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    html_text = re.sub(
        r"<note-attributes\b[^>]*>.*?</note-attributes>",
        "",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    html_text = re.sub(
        r"<h1\b[^>]*class\s*=\s*['\"][^'\"]*\bnoteTitle\b[^'\"]*['\"][^>]*>.*?</h1>",
        "",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    html_text = re.sub(r"</?en-note\b[^>]*>", "", html_text, flags=re.IGNORECASE)
    return remove_empty_wrappers(html_text)


def cleanup_dangling_toc_wrappers(html_text: str) -> str:
    html_text = re.sub(
        r"(</h1>)\s*</div>\s*(<h1\b)",
        r"\1 \2",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return html_text


def build_head_assets(prefix: str) -> str:
    return "\n".join(
        [
            '    <meta name="color-scheme" content="dark light">',
            """    <script>
      (function () {
        try {
          var stored = window.localStorage.getItem("devbrain-theme");
          var theme = stored === "light" || stored === "dark"
            ? stored
            : (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
          document.documentElement.dataset.theme = theme;
        } catch (error) {
          document.documentElement.dataset.theme = "dark";
        }
      })();
    </script>""",
            f'    <link rel="stylesheet" href="{prefix}assets/style.css">',
            f'    <link rel="icon" href="{prefix}assets/favicon.svg" type="image/svg+xml">',
            f'    <link rel="manifest" href="{prefix}assets/site.webmanifest">',
            '    <meta name="theme-color" content="#0b1326">',
        ]
    )


def script_tag(prefix: str) -> str:
    return f'    <script src="{prefix}assets/site.js" defer></script>'


def ensure_head_assets(html_text: str, depth: int) -> str:
    prefix = "../" * depth

    required_markers = [
        f'{prefix}assets/style.css',
        f'{prefix}assets/favicon.svg',
        f'{prefix}assets/site.webmanifest',
    ]

    if all(marker in html_text for marker in required_markers):
        return html_text

    head_assets = build_head_assets(prefix)

    head_match = re.search(r"<head[^>]*>", html_text, flags=re.IGNORECASE)
    if head_match:
        insert_at = head_match.end()
        return html_text[:insert_at] + "\n" + head_assets + html_text[insert_at:]

    html_match = re.search(r"<html[^>]*>", html_text, flags=re.IGNORECASE)
    if html_match:
        insert_at = html_match.end()
        head_block = f"\n<head>\n{head_assets}\n</head>"
        return html_text[:insert_at] + head_block + html_text[insert_at:]

    return f"<head>\n{head_assets}\n</head>\n{html_text}"


def extract_body_content(html_text: str) -> str:
    body_match = re.search(
        r"<body\b[^>]*>(.*?)</body>",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if body_match:
        return body_match.group(1).strip()
    return html_text.strip()


def strip_duplicate_title_heading(content: str, title: str) -> str:
    pattern = re.compile(r"<h1\b[^>]*>\s*(.*?)\s*</h1>", flags=re.IGNORECASE | re.DOTALL)
    match = pattern.search(content)
    if not match:
        return content
    if clean_text(match.group(1)).lower() != title.lower():
        return content
    return content[: match.start()] + content[match.end() :]


def unique_slug(text: str, used: set[str]) -> str:
    base = slugify_segment(text)
    slug = base
    counter = 2
    while slug in used:
        slug = f"{base}-{counter}"
        counter += 1
    used.add(slug)
    return slug


def add_heading_ids_and_collect_toc(content: str) -> tuple[str, list[TocItem]]:
    toc: list[TocItem] = []
    used: set[str] = set()

    def replace_heading(match: re.Match[str]) -> str:
        level = match.group("level")
        attrs = match.group("attrs") or ""
        inner = match.group("inner")
        title = clean_text(inner)

        if not title or len(title) > 100:
            return match.group(0)

        existing_id = re.search(r'\sid\s*=\s*["\']([^"\']+)["\']', attrs, flags=re.IGNORECASE)
        slug = existing_id.group(1) if existing_id else unique_slug(title, used)
        if existing_id:
            used.add(slug)
        else:
            attrs = f'{attrs} id="{html.escape(slug, quote=True)}"'

        toc.append({"level": level, "title": title, "id": slug})
        return f"<h{level}{attrs}>{inner}</h{level}>"

    heading_pattern = re.compile(
        r"<h(?P<level>[2-3])(?P<attrs>[^>]*)>(?P<inner>.*?)</h(?P=level)>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    return heading_pattern.sub(replace_heading, content), toc


def render_header(prefix: str) -> str:
    return f"""    <header class="devbrain-header">
      <a class="brand" href="{prefix}index.html" aria-label="DevBrain home">
        <span class="brand-mark">DB</span>
        <span>DevBrain</span>
      </a>
      <div class="header-actions">
        <button class="icon-button theme-toggle" type="button" data-theme-toggle aria-label="Toggle theme">Theme</button>
      </div>
    </header>"""


def render_page(title: str, prefix: str, body_class: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title)} · DevBrain</title>
{build_head_assets(prefix)}
</head>
<body class="{body_class}">
{GENERATED_MARKER}
{render_header(prefix)}
{content}
{script_tag(prefix)}
</body>
</html>
"""


def flatten_entries(grouped_entries: dict[str, list[ArticleEntry]]) -> list[ArticleEntry]:
    entries: list[ArticleEntry] = []
    for section_slug in sorted(grouped_entries.keys()):
        entries.extend(sorted(grouped_entries[section_slug], key=lambda item: item["title"].lower()))
    return entries


def entry_href(entry: ArticleEntry, current_section: str | None, prefix: str) -> str:
    if current_section == entry["section"]:
        return html.escape(entry["output_name"])
    return html.escape(f"{prefix}{entry['output_relpath']}")


def render_article_tree(
    grouped_entries: dict[str, list[ArticleEntry]],
    current_section: str | None,
    current_output: str | None,
    prefix: str,
) -> str:
    sections: list[str] = []
    for section_slug in sorted(grouped_entries.keys()):
        section_title = html.escape(humanize_slug(section_slug))
        items: list[str] = []
        for entry in sorted(grouped_entries[section_slug], key=lambda item: item["title"].lower()):
            active = entry["section"] == current_section and entry["output_name"] == current_output
            class_name = "tree-link is-active" if active else "tree-link"
            items.append(
                f'          <li><a href="{entry_href(entry, current_section, prefix)}" class="{class_name}">{html.escape(entry["title"])}</a></li>'
            )
        sections.append(
            f"""        <section class="tree-section">
          <h2>{section_title}</h2>
          <ul>
{chr(10).join(items)}
          </ul>
        </section>"""
        )

    sections_html = chr(10).join(sections)

    return f"""      <aside class="docs-sidebar" aria-label="Documentation navigation">
        <div class="desktop-docs-nav">
          <div class="sidebar-kicker">Documentation</div>
{sections_html}
        </div>
        <details class="mobile-docs-nav">
          <summary class="mobile-docs-summary">Documentation</summary>
          <div class="mobile-docs-content">
{sections_html}
          </div>
        </details>
      </aside>"""


def render_toc(toc: list[TocItem]) -> str:
    if not toc:
        return """      <aside class="toc-panel" aria-label="On this page">
        <div class="toc-title">On this page</div>
        <p class="toc-empty">No section headings</p>
      </aside>"""

    links: list[str] = []
    for item in toc:
        title = html.escape(item["title"])
        href = html.escape(f'#{item["id"]}')
        links.append(f'          <li class="toc-level-{item["level"]}"><a href="{href}">{title}</a></li>')

    return f"""      <aside class="toc-panel" aria-label="On this page">
        <div class="toc-title">On this page</div>
        <ol>
{chr(10).join(links)}
        </ol>
      </aside>"""


def render_prev_next(all_entries: list[ArticleEntry], current_entry: ArticleEntry) -> str:
    index = all_entries.index(current_entry)
    previous_entry = all_entries[index - 1] if index > 0 else None
    next_entry = all_entries[index + 1] if index + 1 < len(all_entries) else None

    def item(label: str, entry: ArticleEntry | None, direction: str) -> str:
        if not entry:
            return f'<span class="pager-link is-disabled"><span>{label}</span><strong>{direction}</strong></span>'
        href = html.escape(f"../{entry['output_relpath']}")
        return f'<a class="pager-link" href="{href}"><span>{label}</span><strong>{html.escape(entry["title"])}</strong></a>'

    return f"""        <nav class="article-pager" aria-label="Article navigation">
          {item("Previous", previous_entry, "Start")}
          {item("Next", next_entry, "End")}
        </nav>"""


def render_article_page(
    entry: ArticleEntry,
    grouped_entries: dict[str, list[ArticleEntry]],
    all_entries: list[ArticleEntry],
) -> str:
    source_path = entry["source_path"]
    original_html = source_path.read_text(encoding="utf-8", errors="ignore")
    processed_html = strip_embedded_styling(original_html)
    processed_html = strip_evernote_checklists(processed_html)
    processed_html = strip_evernote_heading_controls(processed_html)
    processed_html = strip_evernote_generated_toc(processed_html)
    processed_html = strip_evernote_shell_artifacts(processed_html)
    processed_html = cleanup_dangling_toc_wrappers(processed_html)
    processed_html = remove_empty_wrappers(processed_html)

    title = entry["title"]
    content = extract_body_content(processed_html)
    content = strip_duplicate_title_heading(content, title)
    content, toc = add_heading_ids_and_collect_toc(content)

    section_title = humanize_slug(entry["section"])
    source_name = html.escape(entry["source_name"])
    article = f"""    <main class="docs-layout">
{render_article_tree(grouped_entries, entry["section"], entry["output_name"], "../")}
      <article class="article-shell">
        <nav class="breadcrumbs" aria-label="Breadcrumb">
          <a href="../index.html">Docs</a>
          <span>/</span>
          <a href="index.html">{html.escape(section_title)}</a>
        </nav>
        <header class="article-header">
          <p class="eyebrow">{html.escape(section_title)}</p>
          <h1>{html.escape(title)}</h1>
          <p class="article-meta">Source: {source_name}</p>
        </header>
        <div class="article-content">
{content}
        </div>
{render_prev_next(all_entries, entry)}
      </article>
{render_toc(toc)}
    </main>"""
    return render_page(title, "../", "article-page", article)


def ensure_marker(html_text: str) -> str:
    if GENERATED_MARKER in html_text:
        return html_text
    return GENERATED_MARKER + "\n" + html_text


def unique_output_name(target_name: str, used_names: set[str]) -> str:
    if target_name not in used_names:
        used_names.add(target_name)
        return target_name

    stem = Path(target_name).stem
    suffix = Path(target_name).suffix
    counter = 2

    while True:
        candidate = f"{stem}-{counter}{suffix}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        counter += 1


def copy_assets_directory() -> None:
    if not SOURCE_ASSETS_DIR.exists():
        raise FileNotFoundError(f"Missing assets directory: {SOURCE_ASSETS_DIR}")

    if OUTPUT_ASSETS_DIR.exists():
        shutil.rmtree(OUTPUT_ASSETS_DIR)

    shutil.copytree(SOURCE_ASSETS_DIR, OUTPUT_ASSETS_DIR)


def write_output_file(source_path: Path, output_path: Path, depth: int) -> ArticleEntry:
    original_html = source_path.read_text(encoding="utf-8", errors="ignore")
    processed_html = strip_embedded_styling(original_html)
    processed_html = strip_evernote_checklists(processed_html)
    processed_html = strip_evernote_heading_controls(processed_html)
    processed_html = strip_evernote_generated_toc(processed_html)
    processed_html = strip_evernote_shell_artifacts(processed_html)
    processed_html = cleanup_dangling_toc_wrappers(processed_html)
    processed_html = ensure_head_assets(processed_html, depth)
    processed_html = ensure_marker(processed_html)
    processed_html = remove_empty_wrappers(processed_html)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(processed_html, encoding="utf-8")

    title = extract_title(processed_html, output_path.name)

    return {
        "source_path": source_path,
        "source_name": source_path.name,
        "output_path": output_path,
        "output_name": output_path.name,
        "output_relpath": output_path.relative_to(OUTPUT_DIR).as_posix(),
        "title": title,
        "section": output_path.parent.relative_to(OUTPUT_DIR).as_posix(),
    }


def remove_stale_generated_files(expected_paths: set[str]) -> None:
    for path in OUTPUT_DIR.rglob("*.html"):
        rel = path.relative_to(OUTPUT_DIR).as_posix()
        if rel in expected_paths:
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if GENERATED_MARKER in content:
            path.unlink()


def generate_section_index(
    section_slug: str,
    entries: list[ArticleEntry],
    grouped_entries: dict[str, list[ArticleEntry]],
) -> None:
    section_dir = OUTPUT_DIR / section_slug

    items: list[str] = []
    for entry in sorted(entries, key=lambda item: item["title"].lower()):
        title = html.escape(entry["title"])
        href = html.escape(entry["output_name"])
        source_name = html.escape(entry["source_name"])

        items.append(
            f"""          <li class="doc-result" data-search-item data-title="{title}" data-section="{html.escape(humanize_slug(section_slug))}">
            <a href="{href}">{title}</a>
            <span>Source: {source_name}</span>
          </li>"""
        )

    list_html = "\n".join(items) if items else "          <li>No HTML files found</li>"
    section_title = html.escape(humanize_slug(section_slug))
    page_body = f"""    <main class="section-layout">
{render_article_tree(grouped_entries, section_slug, None, "../")}
      <section class="section-shell">
        <nav class="breadcrumbs" aria-label="Breadcrumb">
          <a href="../index.html">Docs</a>
          <span>/</span>
          <span>{section_title}</span>
        </nav>
        <header class="section-header">
          <p class="eyebrow">Category</p>
          <h1>{section_title}</h1>
          <p>Browse the notes in this collection.</p>
        </header>
        <label class="section-filter">
          <span>Filter this category</span>
          <input type="search" placeholder="Filter {section_title}..." data-search-input>
        </label>
        <ul class="index-list">
{list_html}
        </ul>
      </section>
    </main>"""
    page = render_page(section_title, "../", "section-page", page_body)
    section_dir.mkdir(parents=True, exist_ok=True)
    (section_dir / "index.html").write_text(page, encoding="utf-8")


def generate_root_index(grouped_entries: dict[str, list[ArticleEntry]]) -> None:
    sections_html: list[str] = []
    all_entries = flatten_entries(grouped_entries)

    for section_slug in sorted(grouped_entries.keys()):
        section_title = html.escape(humanize_slug(section_slug))
        section_href = html.escape(f"{section_slug}/")
        count = len(grouped_entries[section_slug])
        sample = sorted(grouped_entries[section_slug], key=lambda item: item["title"].lower())[0]["title"]

        sections_html.append(
            f"""          <a class="topic-card" href="{section_href}">
            <span class="topic-icon">{section_title[:2].upper()}</span>
            <strong>{section_title}</strong>
            <span>{count} {"article" if count == 1 else "articles"}</span>
            <small>Start with {html.escape(sample)}</small>
          </a>"""
        )

    search_items: list[str] = []
    for entry in all_entries:
        title = html.escape(entry["title"])
        section = html.escape(humanize_slug(entry["section"]))
        href = html.escape(entry["output_relpath"])
        search_items.append(
            f"""          <li class="doc-result" data-search-item data-title="{title}" data-section="{section}">
            <a href="{href}">{title}</a>
            <span>{section}</span>
          </li>"""
        )

    sections_block = "\n".join(sections_html) if sections_html else "          <p>No sections found</p>"
    search_block = "\n".join(search_items) if search_items else "          <li>No documents found</li>"

    page_body = f"""    <main class="home-shell">
      <section class="search-hero" aria-labelledby="home-title">
        <p class="eyebrow">Developer knowledge base</p>
        <h1 id="home-title">DevBrain</h1>
        <p class="intro">Search and browse notes from <code>docs/</code>.</p>
        <label class="global-search">
          <span>Search documentation</span>
          <input type="search" placeholder="Search notes, topics, and source files..." data-search-input autofocus>
        </label>
        <ul class="search-results" aria-label="Search results">
{search_block}
        </ul>
      </section>

      <section class="home-section" aria-labelledby="topics-title">
        <div class="section-title-row">
          <div>
            <p class="eyebrow">Browse</p>
            <h2 id="topics-title">Topics</h2>
          </div>
        </div>
        <div class="topic-grid">
{sections_block}
        </div>
      </section>
    </main>"""

    page = render_page("DevBrain Knowledge Base", "", "home-page", page_body)
    (OUTPUT_DIR / "index.html").write_text(page, encoding="utf-8")


def main() -> None:
    SOURCE_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / ".nojekyll").write_text("", encoding="utf-8")

    copy_assets_directory()

    source_files = sorted(
        [path for path in SOURCE_DIR.rglob("*.html") if path.is_file()],
        key=lambda p: p.as_posix().lower(),
    )

    section_name_usage: dict[str, set[str]] = defaultdict(set)
    grouped_entries: dict[str, list[ArticleEntry]] = defaultdict(list)

    for source_path in source_files:
        relative_source = source_path.relative_to(SOURCE_DIR)
        parts = relative_source.parts

        if len(parts) == 1:
            section_slug = "misc"
        else:
            section_slug = slugify_segment(parts[0])

        output_name = unique_output_name(
            slugify_filename(source_path.name),
            section_name_usage[section_slug],
        )

        output_path = OUTPUT_DIR / section_slug / output_name
        original_html = source_path.read_text(encoding="utf-8", errors="ignore")
        title = extract_title(original_html, output_name)
        entry: ArticleEntry = {
            "source_path": source_path,
            "source_name": source_path.name,
            "output_path": output_path,
            "output_name": output_name,
            "output_relpath": output_path.relative_to(OUTPUT_DIR).as_posix(),
            "title": title,
            "section": section_slug,
        }
        grouped_entries[section_slug].append(entry)

    all_entries = flatten_entries(grouped_entries)

    for entry in all_entries:
        entry["output_path"].parent.mkdir(parents=True, exist_ok=True)
        entry["output_path"].write_text(
            render_article_page(entry, grouped_entries, all_entries),
            encoding="utf-8",
        )

    expected_paths = {
        "index.html",
        ".nojekyll",
    }

    for asset_path in OUTPUT_ASSETS_DIR.rglob("*"):
        if asset_path.is_file():
            expected_paths.add(asset_path.relative_to(OUTPUT_DIR).as_posix())

    for section_slug, section_entries in grouped_entries.items():
        expected_paths.add(f"{section_slug}/index.html")
        for entry in section_entries:
            expected_paths.add(entry["output_relpath"])

    remove_stale_generated_files(expected_paths)

    for section_slug, section_entries in grouped_entries.items():
        generate_section_index(section_slug, section_entries, grouped_entries)

    generate_root_index(grouped_entries)

    print("Generated site files:")
    print("  docs/index.html")
    print("  docs/.nojekyll")

    for asset_path in sorted(OUTPUT_ASSETS_DIR.rglob("*")):
        if asset_path.is_file():
            print(f"  docs/{asset_path.relative_to(OUTPUT_DIR).as_posix()}")

    for section_slug in sorted(grouped_entries.keys()):
        print(f"  docs/{section_slug}/index.html")
        for entry in sorted(grouped_entries[section_slug], key=lambda item: item["title"].lower()):
            print(f"  docs/{entry['output_relpath']}")


if __name__ == "__main__":
    main()
