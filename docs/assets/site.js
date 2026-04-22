(function () {
  const root = document.documentElement;
  const storedTheme = window.localStorage.getItem("devbrain-theme");

  if (storedTheme === "light" || storedTheme === "dark") {
    root.dataset.theme = storedTheme;
  }

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextTheme = root.dataset.theme === "light" ? "dark" : "light";
      root.dataset.theme = nextTheme;
      window.localStorage.setItem("devbrain-theme", nextTheme);
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
