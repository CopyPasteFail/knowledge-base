# Knowledge base ingestion

This site is updated from local Evernote HTML exports without committing the raw exports to Git.

## Folder layout

Use the committed inbox section folders as local drop zones:

```text
inbox/
  ai/
    .gitkeep
  devops-interview-prep/
    .gitkeep
```

Place Evernote HTML exports inside the matching section folder. For example:

```text
inbox/ai/Execution Tools.html
inbox/devops-interview-prep/Kafka Cheat Sheet.html
```

The `inbox/**/*.html` files are ignored by Git. Only `.gitkeep` files are tracked, so the folder structure stays in the repo without storing raw Evernote exports.

## Evernote exports with images

Evernote often exports a note as one HTML file plus a matching image folder:

```text
inbox/devops-interview-prep/DNS - Cheat-sheet.html
inbox/devops-interview-prep/DNS - Cheat-sheet files/
  dns-lookup-diagram.webp
  image.png
```

Keep the HTML file and its matching image folder together in the same inbox section folder.

During ingest, the script copies the image folder to the generated public section and renames it deterministically from the generated slug:

```text
inbox/devops-interview-prep/DNS - Cheat-sheet.html
inbox/devops-interview-prep/DNS - Cheat-sheet files/
-> docs/devops-interview-prep/dns-cheat-sheet.html
-> docs/devops-interview-prep/dns-cheat-sheet_files/
```

The script also rewrites Evernote image links, including Windows-style backslash paths, so links like this:

```html
<img src="DNS - Cheat-sheet files\dns-lookup-diagram.webp">
```

become:

```html
<img src="dns-cheat-sheet_files/dns-lookup-diagram.webp">
```

When you overwrite the same note later, the generated image folder is replaced so removed or renamed images do not leave stale public files behind.

During HTML cleanup, local Evernote app links such as `evernote:///view/...` and public Evernote share links are removed from public output, including their readable link text. If that leaves a heading section empty, the empty heading is removed according to heading hierarchy, and empty parent headings are removed as well. Normal external links, including other `https://` links, are preserved.

## Normal workflow

From the repository root:

```powershell
python tools\ingest_inbox.py
```

The script will:

1. scan all `inbox/**/*.html` files
2. validate section folders and filename collisions
3. sanitize Evernote HTML using the existing generator cleanup logic
4. copy matching Evernote image folders when present
5. write or overwrite generated public pages under `docs/<section>/`
6. update affected section indexes, `docs/index.html`, and `docs/assets/navigation-data.js`
7. print and open local `file:///` preview links
8. ask for approval before committing and pushing
9. wait for the GitHub workflow when the GitHub CLI is available
10. delete local inbox HTML files only after a successful push and verified workflow

## Updating an existing page

The output path is based on the section folder and normalized filename.

```text
inbox/ai/Execution Tools.html
-> docs/ai/execution-tools.html
```

Uploading the same filename again overwrites the same generated public page. The script does not create `-2.html` files for normal updates.

If two files in the same run normalize to the same output path, the script stops with a clear validation error instead of guessing.

## Preview behavior

The script opens generated HTML files directly in the browser using local `file:///` URLs. No local server is required.

Global documentation navigation is rendered from `docs/assets/navigation-data.js` by `assets/site.js`. That keeps local previews working without `fetch()` and avoids rewriting every article page when one document is added.

## Useful flags

```powershell
python tools\ingest_inbox.py --skip-open
```

Print preview links without opening the browser.

```powershell
python tools\ingest_inbox.py --no-push
```

Commit locally but do not push. Inbox files are kept so the run can be resumed.

```powershell
python tools\ingest_inbox.py --allow-dirty
```

Allow pre-existing working-tree changes. The default is strict because it is safer for recovery.

```powershell
python tools\ingest_inbox.py --skip-workflow-check
```

Delete inbox files after push without checking CI. Use only when GitHub CLI is unavailable and you have checked the result manually.

## Recovery rules

If you reject the preview, generated files and inbox files are left in place.

If commit or push fails, inbox files are left in place.

If the workflow cannot be verified as successful, inbox files are left in place.

If the run succeeds, the generated public files are committed and pushed, and the local raw inbox HTML files are deleted.

If you rerun with the same inbox files, the same output paths are regenerated. This makes the flow idempotent for normal updates.
