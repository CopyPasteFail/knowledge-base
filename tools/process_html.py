from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import html
import re
import shutil
import unicodedata


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "raw-html"
OUTPUT_DIR = REPO_ROOT / "docs"
SOURCE_STYLE = REPO_ROOT / "assets" / "style.css"
OUTPUT_ASSETS_DIR = OUTPUT_DIR / "assets"
OUTPUT_STYLE = OUTPUT_ASSETS_DIR / "style.css"

GENERATED_MARKER = "<!-- generated-by: tools/process_html.py -->"


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
    """
    Remove Evernote-generated TOC blocks.

    Only runs on Evernote exports.
    Primary signal is data-testid="tableofcontents".
    """
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


def cleanup_dangling_toc_wrappers(html_text: str) -> str:
    html_text = re.sub(
        r"(</h1>)\s*</div>\s*(<h1\b)",
        r"\1 \2",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return html_text


def ensure_relative_stylesheet(html_text: str, depth: int) -> str:
    href = "../" * depth + "assets/style.css"
    if href in html_text:
        return html_text

    stylesheet_tag = f'    <link rel="stylesheet" href="{href}">'

    head_match = re.search(r"<head[^>]*>", html_text, flags=re.IGNORECASE)
    if head_match:
        insert_at = head_match.end()
        return html_text[:insert_at] + "\n" + stylesheet_tag + html_text[insert_at:]

    html_match = re.search(r"<html[^>]*>", html_text, flags=re.IGNORECASE)
    if html_match:
        insert_at = html_match.end()
        head_block = f"\n<head>\n{stylesheet_tag}\n</head>"
        return html_text[:insert_at] + head_block + html_text[insert_at:]

    return f"<head>\n{stylesheet_tag}\n</head>\n{html_text}"


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


def write_output_file(source_path: Path, output_path: Path, depth: int) -> dict:
    original_html = source_path.read_text(encoding="utf-8", errors="ignore")
    processed_html = strip_embedded_styling(original_html)
    processed_html = strip_evernote_checklists(processed_html)
    processed_html = strip_evernote_heading_controls(processed_html)
    processed_html = strip_evernote_generated_toc(processed_html)
    processed_html = cleanup_dangling_toc_wrappers(processed_html)
    processed_html = ensure_relative_stylesheet(processed_html, depth)
    processed_html = ensure_marker(processed_html)
    processed_html = remove_empty_wrappers(processed_html)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(processed_html, encoding="utf-8")

    title = extract_title(processed_html, output_path.name)

    return {
        "source_name": source_path.name,
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


def generate_section_index(section_slug: str, entries: list[dict]) -> None:
    section_dir = OUTPUT_DIR / section_slug

    items = []
    for entry in sorted(entries, key=lambda item: item["title"].lower()):
        title = html.escape(entry["title"])
        href = html.escape(entry["output_name"])
        source_name = html.escape(entry["source_name"])

        items.append(
            f"""        <li>
          <a href="{href}">{title}</a>
          <div class="meta">Source file: {source_name}</div>
        </li>"""
        )

    list_html = "\n".join(items) if items else "        <li>No HTML files found</li>"
    section_title = html.escape(humanize_slug(section_slug))

    page = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{section_title}</title>
    <link rel="stylesheet" href="../assets/style.css">
</head>
<body>
{GENERATED_MARKER}
    <main>
      <p><a href="../">← Back to Knowledge Base</a></p>
      <h1>{section_title}</h1>

      <ul class="index-list">
{list_html}
      </ul>
    </main>
</body>
</html>
"""
    section_dir.mkdir(parents=True, exist_ok=True)
    (section_dir / "index.html").write_text(page, encoding="utf-8")


def generate_root_index(grouped_entries: dict[str, list[dict]]) -> None:
    sections_html = []

    for section_slug in sorted(grouped_entries.keys()):
        section_title = html.escape(humanize_slug(section_slug))
        section_href = html.escape(f"{section_slug}/")
        section_items = []

        for entry in sorted(grouped_entries[section_slug], key=lambda item: item["title"].lower()):
            title = html.escape(entry["title"])
            href = html.escape(f"{section_slug}/{entry['output_name']}")
            section_items.append(f'          <li><a href="{href}">{title}</a></li>')

        sections_html.append(
            f"""      <section class="kb-section">
        <h2><a href="{section_href}">{section_title}</a></h2>
        <ul>
{chr(10).join(section_items)}
        </ul>
      </section>"""
        )

    sections_block = "\n".join(sections_html) if sections_html else "      <p>No sections found</p>"

    page = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Knowledge Base</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
{GENERATED_MARKER}
    <main>
      <h1>Knowledge Base</h1>
      <p class="intro">Public notes generated automatically from the files in <code>raw-html/</code></p>

{sections_block}
    </main>
</body>
</html>
"""
    (OUTPUT_DIR / "index.html").write_text(page, encoding="utf-8")


def main() -> None:
    SOURCE_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / ".nojekyll").write_text("", encoding="utf-8")
    OUTPUT_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    if SOURCE_STYLE.exists():
        shutil.copy2(SOURCE_STYLE, OUTPUT_STYLE)
    else:
        raise FileNotFoundError(f"Missing stylesheet: {SOURCE_STYLE}")

    source_files = sorted(
        [path for path in SOURCE_DIR.rglob("*.html") if path.is_file()],
        key=lambda p: p.as_posix().lower(),
    )

    section_name_usage: dict[str, set[str]] = defaultdict(set)
    grouped_entries: dict[str, list[dict]] = defaultdict(list)

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
        entry = write_output_file(source_path, output_path, depth=1)
        grouped_entries[section_slug].append(entry)

    expected_paths = {
        "index.html",
        ".nojekyll",
        "assets/style.css",
    }

    for section_slug, section_entries in grouped_entries.items():
        expected_paths.add(f"{section_slug}/index.html")
        for entry in section_entries:
            expected_paths.add(entry["output_relpath"])

    remove_stale_generated_files(expected_paths)

    for section_slug, section_entries in grouped_entries.items():
        generate_section_index(section_slug, section_entries)

    generate_root_index(grouped_entries)

    print("Generated site files:")
    print("  docs/index.html")
    print("  docs/.nojekyll")
    for section_slug in sorted(grouped_entries.keys()):
        print(f"  docs/{section_slug}/index.html")
        for entry in sorted(grouped_entries[section_slug], key=lambda item: item["title"].lower()):
            print(f"  docs/{entry['output_relpath']}")


if __name__ == "__main__":
    main()
