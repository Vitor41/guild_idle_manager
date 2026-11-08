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
      if (filters.tier && filters.tier !== "all" && Number(item.tier) !== Number(filters.tier)) continue;
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

  const api = Object.freeze({ findNormalizedMatch, filterCatalog, normalize });
  global.GuideUtils = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
