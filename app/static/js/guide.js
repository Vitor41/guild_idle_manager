(() => {
  const utils = window.GuideUtils;
  if (!utils) return;
  const root = document.querySelector(".game-guide");
  if (!root) return;

  const searchForm = root.querySelector("[data-guide-search-form]");
  const searchInput = searchForm?.querySelector("#guide-search-query");
  const searchStatus = root.querySelector("[data-guide-search-status]");
  let activeMark = null;
  const clearSearchMark = () => {
    if (!activeMark) return;
    const parent = activeMark.parentNode;
    if (parent) {
      parent.replaceChild(document.createTextNode(activeMark.textContent || ""), activeMark);
      parent.normalize();
    }
    activeMark = null;
  };
  const isSearchControl = (node) => Boolean(node.parentElement?.closest(
    ".guide-search, .guide-catalog-controls, [data-guide-catalog-status], [data-guide-catalog-error], [data-guide-catalog-empty]"
  ));
  searchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    clearSearchMark();
    const term = (searchInput?.value || "").trim();
    if (!term) {
      searchStatus.textContent = "Digite um termo para pesquisar no Guia.";
      searchInput?.focus();
      return;
    }
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let found = null;
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!node.nodeValue?.trim() || isSearchControl(node)) continue;
      if (node.parentElement?.closest("script, style, [hidden], [aria-hidden='true']")) continue;
      const match = utils.findNormalizedMatch(node.nodeValue, term);
      if (match) { found = { node, ...match }; break; }
    }
    if (!found) {
      searchStatus.textContent = `Nenhum resultado para ${term}.`;
      return;
    }
    const range = document.createRange();
    range.setStart(found.node, found.index);
    range.setEnd(found.node, found.index + found.length);
    const mark = document.createElement("mark");
    mark.className = "guide-search-result";
    mark.tabIndex = -1;
    range.surroundContents(mark);
    activeMark = mark;
    searchStatus.textContent = `Resultado encontrado para ${term}.`;
    mark.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
    mark.focus({ preventScroll: true });
  });

  const catalogRoot = root.querySelector("#equipamentos-materiais");
  const rowsNode = catalogRoot?.querySelector("[data-guide-catalog-rows]");
  const statusNode = catalogRoot?.querySelector("[data-guide-catalog-status]");
  const errorNode = catalogRoot?.querySelector("[data-guide-catalog-error]");
  const emptyNode = catalogRoot?.querySelector("[data-guide-catalog-empty]");
  const tableWrap = catalogRoot?.querySelector("[data-guide-catalog-wrap]");
  const filters = {
    name: catalogRoot?.querySelector("[data-filter-name]"),
    type: catalogRoot?.querySelector("[data-filter-type]"),
    family: catalogRoot?.querySelector("[data-filter-family]"),
    band: catalogRoot?.querySelector("[data-filter-band]"),
    tier: catalogRoot?.querySelector("[data-filter-tier]"),
    source: catalogRoot?.querySelector("[data-filter-source]"),
  };
  const filterLabels = {
    mission: "Missões", dungeon_or_boss: "Masmorras e Chefes", docks_possible_offer: "Docas",
    gathering: "Coleta", salvage: "Desmontagem", workshop: "Oficina", crafting: "Ferreiro",
    none: "Sem fonte disponível",
  };
  const familyLabels = {
    wood: "Madeira", ore: "Minério", leather: "Couro", essence: "Essência", gem: "Gemas",
    herb: "Ervas", relic: "Relíquias", cloth: "Tecido", meat: "Carne", supply_kit: "Suprimentos",
  };
  const setOptions = (select, values, labelMap = {}) => {
    if (!select) return;
    for (const value of values) {
      const option = document.createElement("option");
      option.value = String(value);
      option.textContent = labelMap[value] || String(value);
      select.append(option);
    }
  };
  const sourceAnchor = (source) => ({
    mission: "guide-source-missions", dungeon_or_boss: source.label === "Chefes" ? "guide-source-bosses" : "guide-source-dungeons",
    docks_possible_offer: "guide-source-docks", gathering: "guide-source-gathering", salvage: "guide-source-salvage",
    workshop_output: "guide-source-special", crafting_output: "guide-source-special",
  })[source.type] || "guide-source-special";
  let sourceObserver = null;
  const bindSourceIndex = () => {
    const nav = catalogRoot?.querySelector(".guide-source-index");
    if (!nav) return;
    if (sourceObserver) sourceObserver.disconnect();
    const links = Array.from(nav.querySelectorAll("a[href^='#']"));
    const targets = [];
    for (const link of links) {
      const target = document.getElementById(link.hash.slice(1));
      link.hidden = !target;
      link.removeAttribute("aria-current");
      if (target) targets.push(target);
    }
    if (!("IntersectionObserver" in window) || !targets.length) return;
    sourceObserver = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (!visible) return;
      links.forEach((link) => {
        if (link.hash === `#${visible.target.id}`) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      });
    }, { rootMargin: "-18% 0px -65% 0px" });
    targets.forEach((target) => sourceObserver.observe(target));
  };
  let catalogItems = [];
  let apiSources = [];
  const renderCatalog = () => {
    if (!rowsNode) return;
    rowsNode.replaceChildren();
    const visibleItems = new Set();
    const anchorAdded = new Set();
    const groupedRows = new Map();
    const selectedFilters = Object.fromEntries(Object.entries(filters).map(([key, control]) => [key, control?.value || "all"]));
    const visibleRows = utils.filterCatalog(catalogItems, selectedFilters);
    for (const { item, sources: matchingSources } of visibleRows) {
      visibleItems.add(item.id);
      const slot = item.equipment_slot ? ` · ${item.equipment_slot}` : "";
      const itemLabel = `${item.name} · ${item.item_type_label}${slot} · ${item.rarity} · Tier ${item.tier} · ${item.level_band}`;
      for (const source of matchingSources) {
        const groupKey = `${source.filter_key || "none"}\u0000${source.label}\u0000${source.name || ""}`;
        if (!groupedRows.has(groupKey)) groupedRows.set(groupKey, { source, entries: [] });
        groupedRows.get(groupKey).entries.push({ item, itemLabel, source });
      }
    }
    const groups = Array.from(groupedRows.values()).sort((left, right) =>
      left.source.label.localeCompare(right.source.label, "pt-BR") ||
      (left.source.name || "").localeCompare(right.source.name || "", "pt-BR"));
    for (const group of groups) {
      const anchorId = sourceAnchor(group.source);
      const headingRow = document.createElement("tr");
      headingRow.className = "guide-catalog-group";
      if (!anchorAdded.has(anchorId)) { headingRow.id = anchorId; anchorAdded.add(anchorId); }
      const heading = document.createElement("th");
      heading.scope = "rowgroup";
      heading.colSpan = 5;
      heading.textContent = group.source.name ? `${group.source.label} · ${group.source.name}` : group.source.label;
      headingRow.append(heading);
      rowsNode.append(headingRow);
      for (const { item, itemLabel, source } of group.entries) {
        const row = document.createElement("tr");
        row.dataset.guideCatalogRow = "";
        row.dataset.guideItemId = String(item.id);
        row.dataset.guideItemName = item.name.toLocaleLowerCase("pt-BR");
        row.dataset.guideItemType = item.item_type;
        row.dataset.guideFamily = item.family;
        row.dataset.guideTier = String(item.tier);
        row.dataset.guideBand = item.level_band;
        row.dataset.guideSource = source.filter_key || "none";
        const sourceCell = document.createElement("td");
        sourceCell.dataset.label = "Fonte/atividade";
        const sourceName = document.createElement("strong");
        sourceName.textContent = source.label;
        sourceCell.append(sourceName);
        if (source.name) {
          const detail = document.createElement("small");
          detail.textContent = source.name;
          sourceCell.append(document.createElement("br"), detail);
        }
        const itemCell = document.createElement("td");
        itemCell.dataset.label = "Item";
        if (item.icon) {
          const icon = document.createElement("img");
          icon.src = item.icon;
          icon.alt = "";
          icon.width = 44;
          icon.height = 44;
          icon.loading = "lazy";
          itemCell.append(icon);
        }
        const itemName = document.createElement("strong");
        itemName.textContent = itemLabel;
        itemCell.append(itemName);
        const reqCell = document.createElement("td"); reqCell.dataset.label = "Requisito";
        reqCell.textContent = source.price ? `${source.requirement}; preço unitário registrado: ${source.price} ouro` : source.requirement;
        const chanceCell = document.createElement("td"); chanceCell.dataset.label = "Chance"; chanceCell.textContent = source.chance;
        const quantityCell = document.createElement("td"); quantityCell.dataset.label = "Quantidade"; quantityCell.textContent = source.quantity;
        row.append(sourceCell, itemCell, reqCell, chanceCell, quantityCell);
        rowsNode.append(row);
      }
    }
    if (statusNode) {
      const active = Object.entries(filters).filter(([, control]) => control && control.value && control.value !== "all").length;
      statusNode.textContent = `${visibleItems.size} item(ns) · ${active} filtro(s) ativo(s).`;
    }
    if (emptyNode) emptyNode.hidden = visibleItems.size > 0;
    if (tableWrap) tableWrap.hidden = visibleItems.size === 0;
    bindSourceIndex();
  };
  const loadCatalog = async () => {
    if (!catalogRoot) return;
    errorNode.hidden = true;
    tableWrap.hidden = true;
    statusNode.textContent = "Carregando catálogo…";
    try {
      const response = await fetch("/guide/catalog.json", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!Array.isArray(data.items)) throw new Error("Resposta de catálogo inválida");
      catalogItems = data.items;
      apiSources = data.filters?.sources || [];
      setOptions(filters.family, data.filters?.families || [], familyLabels);
      setOptions(filters.band, (data.filters?.level_bands || []).sort((a, b) => Number(a.split("-")[0]) - Number(b.split("-")[0])));
      setOptions(filters.tier, data.filters?.tiers || []);
      setOptions(filters.source, apiSources, filterLabels);
      if (emptyNode) emptyNode.hidden = true;
      renderCatalog();
    } catch (_error) {
      statusNode.textContent = "";
      errorNode.hidden = false;
    }
  };
  Object.values(filters).forEach((control) => {
    control?.addEventListener("input", renderCatalog);
    control?.addEventListener("change", renderCatalog);
  });
  catalogRoot?.querySelectorAll("[data-clear-guide-filters]").forEach((button) => button.addEventListener("click", () => {
    Object.values(filters).forEach((control) => { if (control) control.value = control.tagName === "SELECT" ? "all" : ""; });
    renderCatalog();
  }));
  catalogRoot?.querySelector("[data-guide-catalog-retry]")?.addEventListener("click", loadCatalog);
  loadCatalog();

  const exportButton = root.querySelector("[data-guide-export]");
  const exportStatus = root.querySelector("[data-guide-export-status]");
  const exportFeedback = root.querySelector("[data-guide-export-feedback]");
  const exportProgress = root.querySelector("[data-guide-export-progress]");
  exportButton?.addEventListener("click", async () => {
    if (exportButton.disabled) return;
    exportButton.disabled = true;
    exportButton.setAttribute("aria-busy", "true");
    exportButton.textContent = "Preparando Guia…";
    exportFeedback.hidden = false;
    exportProgress.hidden = false;
    exportStatus.setAttribute("role", "status");
    exportStatus.textContent = "Preparando o arquivo Markdown do Guia…";
    try {
      const response = await fetch("/guide/export.md", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok || !(response.headers.get("content-type") || "").includes("text/markdown")) {
        throw new Error(response.ok ? "O servidor não retornou um arquivo Markdown." : `Falha ${response.status} ao preparar o arquivo.`);
      }
      const blob = await response.blob();
      if (!blob.size) throw new Error("O servidor retornou um arquivo vazio.");
      const disposition = response.headers.get("content-disposition") || "";
      const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
      const quotedName = disposition.match(/filename="?([^";]+)"?/i)?.[1];
      const suggestedName = encodedName ? decodeURIComponent(encodedName) : (quotedName || "guia-guild-idle-manager.md");
      const fileName = suggestedName.split(/[\\/]/).pop() || "guia-guild-idle-manager.md";
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = fileName;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      exportStatus.textContent = `Guia gerado e enviado ao navegador: ${fileName}. Confira a pasta de downloads definida no navegador.`;
      exportButton.textContent = "Baixar Guia em Markdown";
    } catch (error) {
      exportStatus.setAttribute("role", "alert");
      exportStatus.textContent = `${error.message || "Não foi possível preparar o Guia."} Tente novamente.`;
      exportButton.textContent = "Tentar novamente";
    } finally {
      exportProgress.hidden = true;
      exportButton.removeAttribute("aria-busy");
      exportButton.disabled = false;
    }
  });
})();
