# DevBrain Design Notes

## Source Of Truth

The knowledge base remains a fully static GitHub Pages site. Source content lives in `raw-html/`, and `tools/process_html.py` generates the published files in `docs/`.

The redesign intentionally avoids React, Tailwind, build tooling, client-side routing, and runtime content fetching.

## Stitch Direction

Stitch project: `projects/2339388166309452294`

Generated screens:

- Homepage: `1c84379ccc4446d1943f9b8b38a2ad76`
- Article layout: `57661b0c8e0344d8b8a2c6a592ffd693`

The implemented direction adapts Stitch's dark developer documentation style into a quieter static site system:

- Deep slate foundation: `#0b1326`
- Cyan primary accent: `#06b6d4`
- Inter/system sans typography
- 8px radius for panels and controls
- Subtle borders and active states
- Minimal glow and glass effects

## Page Templates

### Homepage

The homepage is search-first. It includes:

- A compact persistent header
- A prominent static filter input
- Deterministic search result list generated from all published articles
- Topic cards generated from content categories
- Quick-link chips chosen deterministically from short article titles
- Recent updates sorted by source file modification time

Search is a lightweight client-side filter over already-rendered links. It is not a full search engine.

### Category Pages

Category pages preserve existing URLs at `docs/<category>/index.html`.

They include:

- Global header
- Left documentation tree
- Breadcrumb
- Category filter
- Article list for the category

### Article Pages

Article URLs remain `docs/<category>/<article>.html`.

Each article is wrapped in a docs-style shell:

- Global header
- Left navigation tree for all generated content
- Breadcrumb and metadata
- Central article content from the original raw HTML
- Right table of contents generated from meaningful `h2` and `h3` headings
- Previous and next links based on deterministic sorted article order

The generator removes a duplicate first `h1` when it matches the article title, because the shell renders the title in a consistent article header.

## JavaScript Boundaries

`assets/site.js` is dependency-free and defensive. It only enhances already-usable static HTML:

- Theme toggle with `localStorage`
- Text filtering for homepage and category pages
- Copy buttons for code blocks
- Active table-of-contents highlighting with `IntersectionObserver`

If JavaScript fails or is disabled, links, navigation, article content, and generated TOCs remain usable.

## TOC Rules

The generated TOC includes only non-empty `h2` and `h3` headings with readable text under 100 characters. Empty headings and noisy generated markup are left out of the TOC.

## Preservation Decisions

- `raw-html/` remains unchanged.
- Existing section and article URL structure is preserved.
- Generated files in `docs/` remain rebuildable from the generator.
- Styling lives in `assets/style.css` and is copied into `docs/assets/`.
- Minimal behavior lives in `assets/site.js` and is copied into `docs/assets/`.
