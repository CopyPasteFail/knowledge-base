# Knowledge Base

This repository publishes a personal technical knowledge base from sanitized Evernote HTML exports.

The generated public site lives under `docs/`. Raw Evernote exports are not committed to Git.

## Current ingestion model

The normal update flow is local and interactive:

```powershell
python tools\ingest_inbox.py
```

The script scans ignored local HTML files under `inbox/`, sanitizes them, generates public HTML under `docs/`, opens local previews in the browser, and asks for approval before committing or pushing anything.

## Inbox layout

Use the committed inbox section folders as local drop zones:

```text
inbox/
  ai/
    .gitkeep
  devops-interview-prep/
    .gitkeep
```

Put Evernote HTML exports into the matching section folder. Example:

```text
inbox/ai/Execution Tools.html
inbox/devops-interview-prep/Kafka Cheat Sheet.html
```

The actual HTML files under `inbox/**/*.html` are ignored by Git. The `.gitkeep` files are tracked only to preserve the folder structure.

## What the script does

`tools/ingest_inbox.py` performs the full upload flow:

1. scans all `inbox/**/*.html` files
2. validates that every file is inside a known section folder
3. validates that two files in the same run do not normalize to the same output path
4. sanitizes Evernote HTML using the existing cleanup/generation logic
5. writes or overwrites generated public pages under `docs/<section>/`
6. updates affected section index pages and `docs/index.html`
7. updates `docs/assets/navigation-data.js` for shared sidebar navigation
8. prints and opens local `file:///` preview links
9. asks for explicit approval
10. commits and optionally pushes generated public output
11. deletes local inbox HTML only after a successful pushed run and verified workflow

## Interactive approval prompt

After generating the local preview, the script asks one of these questions.

Normal mode:

```text
Approve generated output and commit and push? [y/n]
```

No-push mode:

```text
Approve generated output and commit locally? [y/n]
```

The prompt requires an explicit `y` or `n`. Pressing Enter without a choice does not silently approve or reject.

## What each answer means

### Type `n`

The script stops safely.

```text
Not approved. Generated files and inbox files were left in place for review or manual cleanup.
```

Meaning:

- nothing is committed
- nothing is pushed
- generated `docs/` changes stay in the working tree
- raw inbox HTML files stay in `inbox/`
- you can inspect, rerun, or clean up manually

Useful cleanup command after a rejected preview:

```powershell
git restore docs assets
Remove-Item -Force .\docs\assets\navigation-data.js -ErrorAction SilentlyContinue
```

If a new article file was generated, remove that too. Example:

```powershell
Remove-Item -Force .\docs\devops-interview-prep\aihpc-cluster-architecture-key-components.html -ErrorAction SilentlyContinue
```

### Type `y` in normal mode

The script commits and pushes the generated public files.

Meaning:

- generated `docs/` and `assets/` changes are committed
- the commit is pushed to the current branch
- the script waits for the GitHub workflow when GitHub CLI is available
- if the workflow is verified as successful, local inbox HTML files are deleted
- if the workflow fails or cannot be verified, inbox HTML files are kept for recovery

This is the normal publishing path.

### Type `y` with `--no-push`

Run:

```powershell
python tools\ingest_inbox.py --no-push
```

The script commits locally but does not push.

Meaning:

- generated files are committed locally
- no remote push happens
- inbox HTML files are kept
- no workflow check is performed
- this is useful for testing the generated commit safely

To undo a local no-push test commit:

```powershell
git reset --hard HEAD~1
```

## Same-name updates

The output path is based on the section and normalized filename.

```text
inbox/ai/Execution Tools.html
-> docs/ai/execution-tools.html
```

Uploading the same filename again overwrites the same generated page. The script does not create `-2.html` files for normal updates.

If two inbox files in the same run normalize to the same target path, the script fails clearly instead of guessing.

Example collision:

```text
inbox/ai/Execution Tools.html
inbox/ai/Execution_Tools.html
```

Both resolve to:

```text
docs/ai/execution-tools.html
```

## Validation workflow

GitHub Actions now validates the repository only. It does not generate files and does not push commits back to `main`.

The workflow checks that raw inbox HTML was not committed and runs the Python tests.

Run tests locally:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

## More details

See [`docs/INGESTION.md`](docs/INGESTION.md) for the full ingestion workflow, flags, and recovery rules.
