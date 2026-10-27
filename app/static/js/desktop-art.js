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

  function normalizeKey(value) {
    return String(value || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
  }

  const classAliases = {
    guerreiro: "warrior",
    arqueiro: "archer",
    ladino: "rogue",
    mago: "mage",
    clerigo: "cleric",
    aprendiz: "apprentice",
    patrulheiro: "ranger",
    cacador: "ranger",
    pistoleiro: "shooter",
    sacerdote: "high_priest",
  };

  function installEntityIcon(element, key, spriteUrl) {
    const url = spriteUrl(key);
    if (!url || element.querySelector(".desktop-entity-art")) return;
    element.replaceChildren(makeImage(url, "desktop-entity-art"));
    element.dataset.desktopArtApplied = key;
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
      const iconMaps = manifest.icon_maps || {};

      for (const element of document.querySelectorAll("[data-desktop-class]")) {
        const code = normalizeKey(element.dataset.desktopClass);
        const canonical = classAliases[code] || code;
        const key = iconMaps.classes?.[canonical] || `class-${canonical}`;
        if (manifest.sprites?.[key]) installEntityIcon(element, key, spriteUrl);
      }

      for (const element of document.querySelectorAll("[data-desktop-building]")) {
        const code = normalizeKey(element.dataset.desktopBuilding);
        const key = iconMaps.buildings?.[code] || `building-${code}`;
        if (manifest.sprites?.[key]) installEntityIcon(element, key, spriteUrl);
      }

      for (const element of document.querySelectorAll("[data-desktop-item-group], [data-desktop-item-slot], [data-desktop-item-family]")) {
        const group = normalizeKey(element.dataset.desktopItemGroup);
        const family = normalizeKey(element.dataset.desktopItemFamily);
        const slot = normalizeKey(element.dataset.desktopItemSlot);
        const candidates = [
          iconMaps.item_icon_groups?.[group],
          iconMaps.material_families?.[family],
          iconMaps.equipment_slots?.[slot],
        ];
        const key = candidates.find((candidate) => candidate && manifest.sprites?.[candidate]);
        if (key) installEntityIcon(element, key, spriteUrl);
      }

      for (const element of document.querySelectorAll("[data-desktop-resource]")) {
        const resource = normalizeKey(element.dataset.desktopResource);
        const key = iconMaps.resources?.[resource]
          || (resource === "crystal" ? iconMaps.resources?.crystals : null)
          || iconMaps.item_icon_groups?.[resource];
        const url = key && spriteUrl(key);
        if (url && !element.querySelector(".desktop-resource-art")) {
          element.prepend(makeImage(url, "desktop-resource-art"));
        }
      }

      for (const element of document.querySelectorAll(".status-badge")) {
        const status = [...element.classList].find((className) => className.startsWith("status-"))?.slice(7);
        const key = iconMaps.statuses?.[normalizeKey(status)];
        const url = key && spriteUrl(key);
        if (url && !element.querySelector(".desktop-status-art")) {
          element.prepend(makeImage(url, "desktop-status-art"));
        }
      }

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
        : document.querySelector("main.game-shell .dashboard > .topbar, main.game-shell .dashboard > .desktop-operations-intro");
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
