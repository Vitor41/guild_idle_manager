(() => {
  const body = document.body;
  if (body.dataset.appMode !== "desktop") return;

  const navigationArt = new Map([
    ["/dashboard", "guild-sigil"],
    ["/tavern", "building-tavern"],
    ["/mercenaries", "class-warrior"],
    ["/professions", "building-training_ground"],
    ["/missions", "expedition-map"],
    ["/dungeons", "dungeon-gate"],
    ["/inventory", "item-chest"],
    ["/blacksmith", "building-blacksmith"],
    ["/market", "building-market"],
    ["/docks", "building-docks"],
    ["/buildings", "building-warehouse"],
    ["/class-change", "class-apprentice"],
    ["/guild/progress", "resource-xp"],
    ["/classes", "class-warrior"],
    ["/tiers", "status-ready"],
    ["/codex", "item-book"],
    ["/guide", "item-quest-scroll"],
    ["/admin", "status-warning"],
  ]);

  const routeArt = [
    { path: "/desktop/campaigns", sprite: "guild-sigil", illustration: "guild_hall" },
    { path: "/dashboard", sprite: "guild-sigil", illustration: "guild_hall" },
    { path: "/tavern", sprite: "building-tavern", illustration: "tavern" },
    { path: "/dungeons", sprite: "dungeon-gate", illustration: "dungeon" },
    { path: "/mercenaries", sprite: "class-warrior" },
    { path: "/professions", sprite: "building-training_ground" },
    { path: "/missions", sprite: "expedition-map" },
    { path: "/inventory", sprite: "item-chest" },
    { path: "/blacksmith", sprite: "building-blacksmith" },
    { path: "/market", sprite: "building-market" },
    { path: "/docks", sprite: "building-docks" },
    { path: "/buildings", sprite: "building-warehouse" },
    { path: "/class-change", sprite: "class-apprentice" },
    { path: "/guild/progress", sprite: "resource-xp" },
    { path: "/classes", sprite: "class-warrior" },
    { path: "/tiers", sprite: "status-ready" },
    { path: "/codex", sprite: "item-book" },
    { path: "/guide", sprite: "item-quest-scroll" },
    { path: "/admin", sprite: "status-warning" },
  ];

  function routeMatches(route, path) {
    return route === path || (route !== "/dashboard" && path.startsWith(`${route}/`));
  }

  function makeImage(url, className) {
    const image = document.createElement("img");
    image.src = url;
    image.className = className;
    image.alt = "";
    image.setAttribute("aria-hidden", "true");
    image.decoding = "async";
    return image;
  }

  async function applyDesktopArt() {
    try {
      const response = await fetch("/static/assets/desktop/manifest.json", { cache: "no-store" });
      if (!response.ok) return;
      const manifest = await response.json();
      const base = new URL(manifest.base, window.location.origin);
      const spriteUrl = (key) => {
        const entry = manifest.sprites?.[key];
        const path = entry?.paths?.["64"] || entry?.paths?.["128"];
        return path ? new URL(path, base).href : null;
      };
      const illustrationUrl = (key) => {
        const path = manifest.assets?.[key]?.path;
        return path ? new URL(path, base).href : null;
      };

      const route = body.dataset.route || window.location.pathname;
      for (const [href, key] of navigationArt) {
        const link = [...document.querySelectorAll(".sidebar-nav a")].find((anchor) => anchor.getAttribute("href") === href);
        if (!link) continue;
        if (routeMatches(href, route)) link.setAttribute("aria-current", "page");
        const icon = link.querySelector(".nav-icon");
        const url = spriteUrl(key);
        if (icon && url) icon.replaceChildren(makeImage(url, "desktop-nav-art"));
      }

      const currentArt = routeArt.find((entry) => routeMatches(entry.path, route));
      if (!currentArt) return;
      const title = document.querySelector("main.game-shell h1, main.desktop-shell h1");
      const iconUrl = spriteUrl(currentArt.sprite);
      if (title && iconUrl && !title.querySelector(".desktop-title-art")) {
        title.prepend(makeImage(iconUrl, "desktop-title-art"));
      }

      const brand = document.querySelector(".brand-sigil, .seal");
      const crestUrl = spriteUrl("guild-sigil");
      if (brand && crestUrl && !brand.querySelector("img")) brand.replaceChildren(makeImage(crestUrl, "desktop-brand-art"));

      const crest = document.querySelector(".crest-placeholder");
      if (crest && crestUrl && !crest.querySelector("img")) crest.replaceChildren(makeImage(crestUrl, "desktop-crest-art"));

      const campaignMarks = document.querySelectorAll(".campaign-mark");
      const campaignMarkUrl = spriteUrl("guild-sigil");
      for (const mark of campaignMarks) {
        if (campaignMarkUrl && !mark.querySelector("img")) {
          const initial = document.createElement("span");
          initial.className = "campaign-mark-initial";
          initial.textContent = mark.textContent.trim();
          mark.replaceChildren(makeImage(campaignMarkUrl, "desktop-campaign-art"), initial);
        }
      }

      const illustration = currentArt.illustration && illustrationUrl(currentArt.illustration);
      const header = route === "/desktop/campaigns"
        ? document.querySelector(".masthead")
        : document.querySelector("main.game-shell .dashboard > .topbar");
      if (header && illustration && !header.querySelector(".desktop-page-illustration")) {
        header.classList.add("desktop-page-hero");
        header.append(makeImage(illustration, "desktop-page-illustration"));
      }
    } catch (_error) {
      // Art is decorative; a missing manifest must leave all existing navigation usable.
    }
  }

  applyDesktopArt();
})();
