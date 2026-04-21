from __future__ import annotations

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
STYLESHEET_HREF = "assets/style.css"


def slugify_filename(filename: str) -> str:
    """
    Make filenames readable and URL-friendly.

    Rules:
    - lowercase
    - keep letters and digits
    - convert spaces/underscores to hyphens
    - keep existing hyphens
    - remove punctuation and other non-standard characters
    - collapse repeated hyphens
    - trim leading/trailing hyphens
    """
    stem = Path(filename).stem

    # Normalize unicode to ASCII where possible
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


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def inject_stylesheet(html_text: str) -> str:
    if STYLESHEET_HREF in html_text:
        return html_text

    stylesheet_tag = f'    <link rel="stylesheet" href="{STYLESHEET_HREF}">'

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


def write_output_file(source_path: Path, output_name: str) -> dict:
    original_html = source_path.read_text(encoding="utf-8", errors="ignore")
    processed_html = inject_stylesheet(original_html)
    processed_html = ensure_marker(processed_html)

    output_path = OUTPUT_DIR / output_name
    output_path.write_text(processed_html, encoding="utf-8")

    title = extract_title(processed_html, output_name)

    return {
        "source_name": source_path.name,
        "output_name": output_name,
        "title": title,
    }


def remove_stale_generated_files(expected_names: set[str]) -> None:
    for path in OUTPUT_DIR.glob("*.html"):
        if path.name == "index.html":
            continue

        if path.name in expected_names:
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if GENERATED_MARKER in content:
            path.unlink()


def generate_index(entries: list[dict]) -> None:
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

    index_html = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AI Tools</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
{GENERATED_MARKER}
    <main>
      <h1>AI Tools</h1>
      <p class="intro">Published notes generated automatically from the files in <code>raw-html/</code></p>

      <ul class="index-list">
{list_html}
      </ul>
    </main>
</body>
</html>
"""
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")


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
        [path for path in SOURCE_DIR.glob("*.html") if path.is_file()],
        key=lambda p: p.name.lower(),
    )

    used_names: set[str] = set()
    entries: list[dict] = []

    for source_path in source_files:
        normalized_name = slugify_filename(source_path.name)
        output_name = unique_output_name(normalized_name, used_names)
        entry = write_output_file(source_path, output_name)
        entries.append(entry)

    expected_names = {entry["output_name"] for entry in entries}
    remove_stale_generated_files(expected_names)
    generate_index(entries)

    print("Generated site files:")
    for entry in entries:
        print(f"  {entry['source_name']} -> docs/{entry['output_name']}")
    print("  docs/index.html")
    print("  docs/.nojekyll")


if __name__ == "__main__":
    main()