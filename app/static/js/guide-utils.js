(function (global) {
  "use strict";

  const normalize = (value) => String(value ?? "").toLocaleLowerCase("pt-BR").trim().replace(/\s+/gu, " ");

  function findNormalizedMatch(text, query) {
    const needle = normalize(query);
    if (!needle) return null;

    const source = String(text ?? "");
    let normalized = "";
    const starts = [];
    const ends = [];
    let pendingWhitespaceStart = null;

    for (let offset = 0; offset < source.length;) {
      const point = String.fromCodePoint(source.codePointAt(offset));
      const nextOffset = offset + point.length;
      if (/\s/u.test(point)) {
        if (normalized && pendingWhitespaceStart === null) pendingWhitespaceStart = offset;
      } else {
        if (pendingWhitespaceStart !== null) {
          normalized += " ";
          starts.push(pendingWhitespaceStart);
          ends.push(offset);
          pendingWhitespaceStart = null;
        }
        const lowered = point.toLocaleLowerCase("pt-BR");
        normalized += lowered;
        for (let index = 0; index < lowered.length; index += 1) {
          starts.push(offset);
          ends.push(nextOffset);
        }
      }
      offset = nextOffset;
    }

    const index = normalized.indexOf(needle);
    if (index < 0) return null;
    return { index: starts[index], length: ends[index + needle.length - 1] - starts[index] };
  }

  function filterCatalog(items, filters = {}) {
    const name = normalize(filters.name);
    const selectedSource = filters.source || "all";
    const results = [];
    for (const item of items || []) {
      if (name && !normalize(item.name).includes(name)) continue;
      if (filters.type && filters.type !== "all" && item.item_type !== filters.type) continue;
      if (filters.family && filters.family !== "all" && item.family !== filters.family) continue;
      if (filters.band && filters.band !== "all" && item.level_band !== filters.band) continue;
      const matchingSources = (item.sources || []).filter((source) => selectedSource === "all" || source.filter_key === selectedSource);
      if (item.sources?.length) {
        if (!matchingSources.length) continue;
        results.push({ item, sources: matchingSources });
      } else if (selectedSource === "all" || selectedSource === "none") {
        results.push({ item, sources: [{
          label: "Sem fonte disponível", name: "", requirement: "—", chance: "—", quantity: "—",
          type: "none", filter_key: "none",
        }] });
      }
    }
    return results;
  }

  function groupCatalogSources(visibleRows) {
    const grouped = new Map();
    for (const { item, sources } of visibleRows || []) {
      const slot = item.equipment_slot ? ` · ${item.equipment_slot}` : "";
      const itemLabel = `${item.name} · ${item.item_type_label}${slot}`;
      for (const source of sources || []) {
        const key = JSON.stringify([source.type, source.label]);
        if (!grouped.has(key)) grouped.set(key, { source, entries: [] });
        const entries = grouped.get(key).entries;
        const equivalent = entries.find((entry) => entry.item.name === item.name &&
          entry.item.item_type === item.item_type && entry.item.family === item.family &&
          entry.item.equipment_slot === item.equipment_slot);
        let entry = equivalent;
        if (equivalent) {
          if (!equivalent.rarities.includes(item.rarity)) equivalent.rarities.push(item.rarity);
        } else {
          entry = { item, itemLabel, source, rarities: [], variants: [], minimumGuildLevel: undefined };
          entries.push(entry);
        }
        if (!entry.rarities.includes(item.rarity)) entry.rarities.push(item.rarity);
        if (source.type === "gathering" && Number.isFinite(Number(source.minimum_guild_level))) {
          const minimumGuildLevel = Number(source.minimum_guild_level);
          entry.minimumGuildLevel = entry.minimumGuildLevel === undefined
            ? minimumGuildLevel : Math.min(entry.minimumGuildLevel, minimumGuildLevel);
        }
        const gathering = source.type === "gathering";
        const variantKey = JSON.stringify([source.name && source.name !== source.label ? source.name : "",
          source.recommendation || "", gathering ? "" : source.requirement || "",
          source.chance || "", source.quantity || "", source.price ?? "", source.condition || "",
          gathering ? null : source.minimum_guild_level ?? null]);
        let variant = entry.variants.find((row) => row.key === variantKey);
        if (!variant) {
          variant = { key: variantKey, source, rarities: [] };
          entry.variants.push(variant);
        }
        if (!variant.rarities.includes(item.rarity)) variant.rarities.push(item.rarity);
      }
    }
    return Array.from(grouped.values());
  }

  const api = Object.freeze({ findNormalizedMatch, filterCatalog, groupCatalogSources, normalize });
  global.GuideUtils = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
