(function () {
  const root = document.documentElement;

  function preferredTheme() {
    try {
      const storedTheme = window.localStorage.getItem("devbrain-theme");
      if (storedTheme === "light" || storedTheme === "dark") {
        return storedTheme;
      }
    } catch {
      // Ignore storage access errors and fall back to system preference.
    }

    return window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }

  function setTheme(theme, persist) {
    root.dataset.theme = theme;
    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) {
      themeColor.setAttribute("content", theme === "light" ? "#f6f8fb" : "#0b1326");
    }

    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const nextTheme = theme === "light" ? "dark" : "light";
      button.textContent = nextTheme === "light" ? "Light" : "Dark";
      button.setAttribute("aria-label", `Switch to ${nextTheme} theme`);
      button.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    });

    if (persist) {
      try {
        window.localStorage.setItem("devbrain-theme", theme);
      } catch {
        // Theme still changes for the current page if persistence is unavailable.
      }
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function normalizeEvernoteRichLinks() {
    document.querySelectorAll('[data-testid="default-richlink-viewer"]').forEach((card) => {
      const href = card.getAttribute("data-href") || card.querySelector("a[href]")?.getAttribute("href") || "";
      const label = card.querySelector(".Hseq7")?.textContent?.trim() || href || card.textContent.trim();

      if (!href || !label) {
        return;
      }

      const link = document.createElement("a");
      link.href = href;
      link.textContent = label;
      link.rel = "noopener noreferrer";
      card.replaceWith(link);
    });
  }

  function renderDocsNav() {
    const navData = window.DEVBRAIN_NAVIGATION;
    if (!navData || !Array.isArray(navData.sections)) {
      return;
    }

    document.querySelectorAll("[data-docs-nav]").forEach((container) => {
      const prefix = container.dataset.navPrefix || "";
      const currentSection = container.dataset.currentSection || "";
      const currentOutput = container.dataset.currentOutput || "";

      const sectionsHtml = navData.sections.map((section) => {
        const itemsHtml = section.items.map((item) => {
          const isActive = section.slug === currentSection && item.output === currentOutput;
          const href = section.slug === currentSection ? item.output : `${prefix}${item.href}`;
          const className = isActive ? "tree-link is-active" : "tree-link";
          return `          <li><a href="${escapeHtml(href)}" class="${className}">${escapeHtml(item.title)}</a></li>`;
        }).join("\n");

        return `        <section class="tree-section">
          <h2>${escapeHtml(section.title)}</h2>
          <ul>
${itemsHtml}
          </ul>
        </section>`;
      }).join("\n");

      container.innerHTML = `
        <div class="desktop-docs-nav">
          <div class="sidebar-kicker">Documentation</div>
${sectionsHtml}
        </div>
        <details class="mobile-docs-nav">
          <summary class="mobile-docs-summary">Documentation</summary>
          <div class="mobile-docs-content">
${sectionsHtml}
          </div>
        </details>`;
    });
  }

  function loadDocsNav() {
    if (!document.querySelector("[data-docs-nav]")) {
      return;
    }

    if (window.DEVBRAIN_NAVIGATION) {
      renderDocsNav();
      return;
    }

    const currentScript = document.currentScript;
    const src = currentScript && currentScript.getAttribute("src");
    const navSrc = src ? src.replace(/site\.js(?:\?.*)?$/, "navigation-data.js") : "assets/navigation-data.js";
    const script = document.createElement("script");
    script.src = navSrc;
    script.onload = renderDocsNav;
    script.onerror = () => {
      console.warn("DevBrain navigation data was not found.");
    };
    document.head.appendChild(script);
  }

  setTheme(root.dataset.theme === "light" || root.dataset.theme === "dark" ? root.dataset.theme : preferredTheme(), false);
  normalizeEvernoteRichLinks();
  loadDocsNav();

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextTheme = root.dataset.theme === "light" ? "dark" : "light";
      setTheme(nextTheme, true);
    });
  });

  document.querySelectorAll("[data-search-input]").forEach((input) => {
    const scope = input.closest("main") || document;
    const items = Array.from(scope.querySelectorAll("[data-search-item]"));

    if (!items.length) {
      return;
    }

    input.addEventListener("input", () => {
      const query = input.value.trim().toLowerCase();

      items.forEach((item) => {
        const haystack = [
          item.dataset.title || "",
          item.dataset.section || "",
          item.textContent || "",
        ].join(" ").toLowerCase();

        item.hidden = query.length > 0 && !haystack.includes(query);
      });
    });
  });

  document.querySelectorAll("pre").forEach((block) => {
    if (!block.querySelector("code") || block.querySelector(".copy-code")) {
      return;
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy-code";
    button.textContent = "Copy";
    block.appendChild(button);

    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(block.querySelector("code").innerText);
        button.textContent = "Copied";
        window.setTimeout(() => {
          button.textContent = "Copy";
        }, 1400);
      } catch {
        button.textContent = "Select";
      }
    });
  });

  const tocLinks = Array.from(document.querySelectorAll(".toc-panel a[href^='#']"));
  if (!tocLinks.length || !("IntersectionObserver" in window)) {
    return;
  }

  const headings = tocLinks
    .map((link) => document.getElementById(decodeURIComponent(link.hash.slice(1))))
    .filter(Boolean);

  const byId = new Map(tocLinks.map((link) => [decodeURIComponent(link.hash.slice(1)), link]));

  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];

      if (!visible) {
        return;
      }

      tocLinks.forEach((link) => link.classList.remove("is-active"));
      const active = byId.get(visible.target.id);
      if (active) {
        active.classList.add("is-active");
      }
    },
    { rootMargin: "-80px 0px -70% 0px", threshold: 0.01 },
  );

  headings.forEach((heading) => observer.observe(heading));
})();
