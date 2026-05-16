from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import webbrowser
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import process_html


INBOX_DIR = REPO_ROOT / "inbox"
DOCS_DIR = REPO_ROOT / "docs"


@dataclass(frozen=True)
class PlannedIngest:
    source_path: Path
    section: str
    output_name: str
    output_path: Path
    output_relpath: str
    title: str
    action: str


def run_git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_command(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_output(args: list[str]) -> str:
    return run_git(args).stdout.strip()


def current_branch() -> str:
    return git_output(["branch", "--show-current"])


def ensure_repo_state(allow_dirty: bool) -> None:
    if not (REPO_ROOT / ".git").exists():
        raise SystemExit("This script must be run from a clone of the knowledge-base repository.")

    branch = current_branch()
    if not branch:
        raise SystemExit("Git is in detached HEAD state. Check out a branch before ingesting files.")

    status = git_output(["status", "--porcelain"])
    if status and not allow_dirty:
        raise SystemExit(
            "Working tree has existing changes. Commit/stash them first, or rerun with --allow-dirty.\n"
            + status
        )

    run_git(["fetch", "origin", branch], check=False)
    local_sha = git_output(["rev-parse", "HEAD"])
    remote = run_git(["rev-parse", f"origin/{branch}"], check=False)
    if remote.returncode == 0 and remote.stdout.strip() and remote.stdout.strip() != local_sha:
        raise SystemExit(
            f"Local {branch} is not aligned with origin/{branch}. Pull/rebase before ingesting."
        )


def known_sections() -> list[str]:
    if not INBOX_DIR.exists():
        return []
    return sorted(path.name for path in INBOX_DIR.iterdir() if path.is_dir())


def scan_inbox() -> list[Path]:
    if not INBOX_DIR.exists():
        return []
    return sorted(path for path in INBOX_DIR.rglob("*.html") if path.is_file())


def validate_inbox_files(files: list[Path]) -> None:
    sections = set(known_sections())
    if not sections:
        raise SystemExit("No inbox section folders found. Expected folders like inbox/ai/.gitkeep.")

    errors: list[str] = []
    seen_targets: dict[str, Path] = {}
    for file_path in files:
        rel = file_path.relative_to(INBOX_DIR)
        if len(rel.parts) < 2:
            errors.append(f"{rel}: HTML files must be inside a section folder, for example inbox/ai/Note.html")
            continue

        section = rel.parts[0]
        if section not in sections:
            errors.append(f"{rel}: unknown section folder {section!r}")
            continue

        try:
            html_text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            errors.append(f"{rel}: could not read file: {exc}")
            continue

        output_name = process_html.slugify_filename(file_path.name)
        target = f"{section}/{output_name}"
        if target in seen_targets:
            errors.append(
                f"{rel}: collides with {seen_targets[target].relative_to(INBOX_DIR)}; both resolve to docs/{target}"
            )
        else:
            seen_targets[target] = file_path

        title = process_html.extract_title(html_text, output_name)
        if not title.strip():
            errors.append(f"{rel}: could not determine a title")

    if errors:
        raise SystemExit("Inbox validation failed:\n" + "\n".join(f"- {error}" for error in errors))


def source_name_from_article(html_text: str, fallback: str) -> str:
    match = process_html.re.search(
        r'<p\b[^>]*class\s*=\s*["\'][^"\']*\barticle-meta\b[^"\']*["\'][^>]*>\s*Source:\s*(.*?)\s*</p>',
        html_text,
        flags=process_html.re.IGNORECASE | process_html.re.DOTALL,
    )
    if not match:
        return fallback
    source = process_html.clean_text(match.group(1))
    return source or fallback


def existing_entries() -> dict[str, process_html.ArticleEntry]:
    entries: dict[str, process_html.ArticleEntry] = {}
    if not DOCS_DIR.exists():
        return entries

    for path in sorted(DOCS_DIR.rglob("*.html")):
        rel = path.relative_to(DOCS_DIR).as_posix()
        if rel == "index.html" or rel.endswith("/index.html") or rel.startswith("assets/"):
            continue
        if len(path.relative_to(DOCS_DIR).parts) < 2:
            continue

        html_text = path.read_text(encoding="utf-8", errors="ignore")
        section = path.parent.relative_to(DOCS_DIR).as_posix()
        title = process_html.extract_title(html_text, path.name).removesuffix(" · DevBrain").strip()
        entries[rel] = {
            "source_path": path,
            "source_name": source_name_from_article(html_text, path.name),
            "output_path": path,
            "output_name": path.name,
            "output_relpath": rel,
            "title": title,
            "section": section,
        }

    return entries


def plan_ingest(files: list[Path]) -> list[PlannedIngest]:
    existing = existing_entries()
    planned: list[PlannedIngest] = []

    for source_path in files:
        rel = source_path.relative_to(INBOX_DIR)
        section = rel.parts[0]
        output_name = process_html.slugify_filename(source_path.name)
        output_path = DOCS_DIR / section / output_name
        output_relpath = output_path.relative_to(DOCS_DIR).as_posix()
        html_text = source_path.read_text(encoding="utf-8", errors="ignore")
        title = process_html.extract_title(html_text, output_name)
        action = "overwrite" if output_relpath in existing else "create"
        planned.append(
            PlannedIngest(
                source_path=source_path,
                section=section,
                output_name=output_name,
                output_path=output_path,
                output_relpath=output_relpath,
                title=title,
                action=action,
            )
        )

    return planned


def grouped_entries_with_plan(planned: list[PlannedIngest]) -> dict[str, list[process_html.ArticleEntry]]:
    entries = existing_entries()
    for item in planned:
        entries[item.output_relpath] = {
            "source_path": item.source_path,
            "source_name": item.source_path.name,
            "output_path": item.output_path,
            "output_name": item.output_name,
            "output_relpath": item.output_relpath,
            "title": item.title,
            "section": item.section,
        }

    grouped: dict[str, list[process_html.ArticleEntry]] = defaultdict(list)
    for entry in entries.values():
        grouped[entry["section"]].append(entry)
    return grouped


def nav_placeholder(path: Path) -> str:
    rel = path.relative_to(DOCS_DIR)
    parts = rel.parts
    if len(parts) < 2:
        prefix = ""
        current_section = ""
        current_output = ""
    else:
        prefix = "../"
        current_section = parts[0]
        current_output = "" if parts[-1] == "index.html" else parts[-1]

    return (
        '<aside class="docs-sidebar" aria-label="Documentation navigation" '
        'data-docs-nav '
        f'data-nav-prefix="{process_html.html.escape(prefix, quote=True)}" '
        f'data-current-section="{process_html.html.escape(current_section, quote=True)}" '
        f'data-current-output="{process_html.html.escape(current_output, quote=True)}"></aside>'
    )


def replace_embedded_nav(path: Path) -> None:
    html_text = path.read_text(encoding="utf-8", errors="ignore")
    pattern = process_html.re.compile(
        r'<aside\b[^>]*class=["\'][^"\']*\bdocs-sidebar\b[^"\']*["\'][^>]*>.*?</aside>',
        flags=process_html.re.IGNORECASE | process_html.re.DOTALL,
    )
    updated = pattern.sub(nav_placeholder(path), html_text, count=1)
    if updated != html_text:
        path.write_text(updated, encoding="utf-8", newline="\n")


def write_shared_data(grouped: dict[str, list[process_html.ArticleEntry]]) -> Path:
    assets_dir = DOCS_DIR / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    sections = []
    for section_slug in sorted(grouped.keys()):
        entries = sorted(grouped[section_slug], key=lambda item: item["title"].lower())
        sections.append(
            {
                "slug": section_slug,
                "title": process_html.humanize_slug(section_slug),
                "items": [
                    {
                        "title": entry["title"],
                        "href": entry["output_relpath"],
                        "output": entry["output_name"],
                    }
                    for entry in entries
                ],
            }
        )

    payload = json.dumps({"sections": sections}, ensure_ascii=False, indent=2)
    output = assets_dir / "navigation-data.js"
    output.write_text(f"window.DEVBRAIN_NAVIGATION = {payload};\n", encoding="utf-8", newline="\n")
    return output


def generate(planned: list[PlannedIngest]) -> list[Path]:
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8", newline="\n")
    process_html.copy_assets_directory()

    grouped = grouped_entries_with_plan(planned)
    all_entries = process_html.flatten_entries(grouped)
    by_relpath = {entry["output_relpath"]: entry for entry in all_entries}

    written: list[Path] = []
    for item in planned:
        entry = by_relpath[item.output_relpath]
        entry["output_path"].parent.mkdir(parents=True, exist_ok=True)
        entry["output_path"].write_text(
            process_html.render_article_page(entry, grouped, all_entries),
            encoding="utf-8",
            newline="\n",
        )
        replace_embedded_nav(entry["output_path"])
        written.append(entry["output_path"])

    affected_sections = sorted({item.section for item in planned})
    for section in affected_sections:
        process_html.generate_section_index(section, grouped[section], grouped)
        section_index = DOCS_DIR / section / "index.html"
        replace_embedded_nav(section_index)
        written.append(section_index)

    process_html.generate_root_index(grouped)
    written.append(DOCS_DIR / "index.html")
    written.append(write_shared_data(grouped))
    return written


def print_plan(planned: list[PlannedIngest]) -> None:
    print("Planned inbox ingest:\n")
    for item in planned:
        rel_source = item.source_path.relative_to(REPO_ROOT).as_posix()
        rel_output = item.output_path.relative_to(REPO_ROOT).as_posix()
        print(f"[{item.section}] {item.action}")
        print(f"  source: {rel_source}")
        print(f"  output: {rel_output}")
        print(f"  title:  {item.title}")
        print()


def open_previews(planned: list[PlannedIngest], skip_open: bool) -> None:
    print("Local previews:")
    for item in planned:
        url = item.output_path.resolve().as_uri()
        print(f"  {url}")
        if not skip_open:
            webbrowser.open(url)
    print()


def confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    answer = input(f"{prompt} [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def commit_and_push(message: str, no_push: bool) -> str | None:
    run_git(["add", "docs", "assets"])

    cached = run_git(["diff", "--cached", "--quiet"], check=False)
    if cached.returncode == 0:
        print("No generated changes to commit.")
        return None

    run_git(["commit", "-m", message])
    commit_sha = git_output(["rev-parse", "HEAD"])

    if no_push:
        print(f"Committed {commit_sha}; not pushing because --no-push was used.")
        return commit_sha

    branch = current_branch()
    run_git(["push", "origin", branch])
    print(f"Pushed {commit_sha} to origin/{branch}.")
    return commit_sha


def wait_for_workflow(commit_sha: str, skip_workflow_check: bool) -> bool:
    if skip_workflow_check:
        print("Skipping workflow check.")
        return True

    if shutil.which("gh") is None:
        print("GitHub CLI not found. Leaving inbox files in place because workflow status could not be verified.")
        return False

    branch = current_branch()
    print("Waiting for GitHub workflow result...")
    for _ in range(60):
        result = run_command(
            [
                "gh",
                "run",
                "list",
                "--branch",
                branch,
                "--commit",
                commit_sha,
                "--limit",
                "1",
                "--json",
                "status,conclusion,url,headSha",
            ],
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            runs = json.loads(result.stdout)
            if runs:
                run = runs[0]
                status = run.get("status")
                conclusion = run.get("conclusion")
                url = run.get("url")
                if status == "completed":
                    print(f"Workflow completed: {conclusion or 'unknown'}")
                    if url:
                        print(url)
                    return conclusion == "success"
                print(f"Workflow status: {status}")
        time.sleep(10)

    print("Timed out waiting for workflow result. Leaving inbox files in place.")
    return False


def cleanup_inbox(files: list[Path]) -> None:
    for file_path in files:
        try:
            file_path.unlink()
            print(f"Deleted {file_path.relative_to(REPO_ROOT).as_posix()}")
        except FileNotFoundError:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest local Evernote HTML exports from inbox/ into docs/.")
    parser.add_argument("--yes", action="store_true", help="Approve without prompting.")
    parser.add_argument("--skip-open", action="store_true", help="Print preview links without opening the browser.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow pre-existing working tree changes.")
    parser.add_argument("--no-push", action="store_true", help="Commit locally but do not push.")
    parser.add_argument("--skip-workflow-check", action="store_true", help="Delete inbox files after push without verifying CI.")
    parser.add_argument(
        "--message",
        default="Ingest knowledge base updates",
        help="Commit message to use for generated docs changes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_repo_state(args.allow_dirty)

    files = scan_inbox()
    if not files:
        print("No inbox HTML files found.")
        return 0

    validate_inbox_files(files)
    planned = plan_ingest(files)
    print_plan(planned)

    generate(planned)
    open_previews(planned, args.skip_open)

    action = "commit locally" if args.no_push else "commit and push"
    if not confirm(f"Approve generated output and {action}?", args.yes):
        print("Not approved. Generated files and inbox files were left in place for review or manual cleanup.")
        return 1

    commit_sha = commit_and_push(args.message, args.no_push)
    if commit_sha is None:
        if confirm("No generated changes were found. Delete inbox files anyway?", args.yes):
            cleanup_inbox(files)
        return 0

    if args.no_push:
        print("Leaving inbox files in place because changes were not pushed.")
        return 0

    if wait_for_workflow(commit_sha, args.skip_workflow_check):
        cleanup_inbox(files)
        return 0

    print("Workflow was not verified as successful. Inbox files were left in place for recovery.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
