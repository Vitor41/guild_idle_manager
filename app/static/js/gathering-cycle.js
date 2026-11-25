(() => {
  const initializedCycles = new WeakSet();
  const cycleUpdaters = new WeakMap();

  window.initializeGatheringCycles = () => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.querySelectorAll("[data-gathering-cycle]").forEach((cycle) => {
      if (initializedCycles.has(cycle)) return;
      initializedCycles.add(cycle);

      const progress = cycle.querySelector("progress");
      const remainingLabel = cycle.querySelector("[data-gathering-remaining]");
      if (!progress || !remainingLabel) return;
      let elapsed = Number(cycle.dataset.progressSeconds || 0);
      const update = (value) => {
        elapsed = Math.max(0, Math.min(59, Number(value) || 0));
        cycle.dataset.progressSeconds = String(elapsed);
        progress.value = elapsed;
        remainingLabel.textContent = String(60 - elapsed);
      };
      cycleUpdaters.set(cycle, update);

      if (reducedMotion) {
        update(elapsed);
        return;
      }

      const timer = window.setInterval(() => {
        if (!cycle.isConnected) {
          window.clearInterval(timer);
          return;
        }
        if (document.hidden || cycle.hidden) return;
        update((elapsed + 1) % 60);
      }, 1000);
    });
  };

  let requestInFlight = false;
  const refreshGatheringStatus = async () => {
    if (requestInFlight || document.visibilityState !== "visible") return;
    const page = document.querySelector("[data-gathering-status-url]");
    if (!page) return;
    requestInFlight = true;
    try {
      const response = await fetch(page.dataset.gatheringStatusUrl, {
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) return;
      const state = await response.json();
      if (!page.isConnected || document.querySelector("[data-gathering-status-url]") !== page) return;
      const warehouseLabel = page.querySelector("[data-gathering-warehouse-label]");
      const warehouseProgress = page.querySelector("[data-gathering-warehouse-progress]");
      const capacityStateLabel = page.querySelector("[data-gathering-capacity-state]");
      const used = Number(state.warehouse?.used);
      const capacity = Number(state.warehouse?.capacity);
      if (Number.isFinite(used) && used >= 0 && Number.isFinite(capacity) && capacity > 0) {
        const displayedUsed = Math.min(used, capacity);
        if (warehouseLabel) {
          const nextLabel = `${used.toLocaleString("pt-BR")} / ${capacity.toLocaleString("pt-BR")}`;
          if (warehouseLabel.textContent !== nextLabel) warehouseLabel.textContent = nextLabel;
        }
        if (warehouseProgress) {
          warehouseProgress.max = capacity;
          warehouseProgress.value = displayedUsed;
          warehouseProgress.setAttribute?.("aria-label", `Armazém: ${used} de ${capacity}`);
        }
        if (capacityStateLabel) {
          const full = used >= capacity;
          if (capacityStateLabel.hidden === full) capacityStateLabel.hidden = !full;
        }
      }
      page.querySelectorAll("[data-gathering-family-count]").forEach((counter) => {
        counter.textContent = String(state.inventory_by_family[counter.dataset.gatheringFamilyCount] || 0);
      });
      page.querySelectorAll("[data-gathering-card]").forEach((card) => {
        if (card.dataset.gatheringAssigned !== "true") return;
        const family = card.dataset.gatheringCard;
        const assignment = state.assignments[family];
        if (!assignment) {
          window.location.reload();
          return;
        }
        const cycle = card.querySelector("[data-gathering-cycle]");
        const status = card.querySelector("[data-gathering-status]");
        const catalogWarning = card.querySelector("[data-gathering-catalog-warning]");
        const capacityHelp = card.querySelector("[data-gathering-capacity-help]");
        const targetLabel = card.querySelector("[data-gathering-target-label]");
        const targetValue = card.querySelector("[data-gathering-target-value]");
        if (targetLabel) {
          targetLabel.textContent = assignment.catalog_unavailable
            ? "Alvo salvo (indisponível):"
            : "Alvo desta designação:";
        }
        if (targetValue && assignment.target_item_name) {
          const rarityLabels = {
            common: "Comum", uncommon: "Incomum", rare: "Raro", epic: "Épico",
            legendary: "Lendário", mythic: "Mítico",
          };
          const rarity = rarityLabels[assignment.target_item_rarity] || assignment.target_item_rarity;
          targetValue.textContent = `${assignment.target_item_name} · ${rarity}`;
        }
        const setStatus = (className, text) => {
          if (!status) return;
          status.classList?.remove("evolution-status--active", "evolution-status--paused", "evolution-status--muted");
          status.classList?.add(className);
          if (status.textContent !== text) status.textContent = text;
        };
        if (catalogWarning) catalogWarning.hidden = !assignment.catalog_unavailable;
        if (assignment.catalog_unavailable) {
          if (cycle) cycle.hidden = true;
          if (capacityHelp) capacityHelp.hidden = true;
          cycleUpdaters.get(cycle)?.(assignment.progress_seconds);
          setStatus("evolution-status--muted", `Indisponível · catálogo · ${assignment.worker}`);
        } else if (assignment.capacity_paused) {
          if (cycle) cycle.hidden = true;
          if (capacityHelp) capacityHelp.hidden = false;
          cycleUpdaters.get(cycle)?.(assignment.progress_seconds);
          setStatus("evolution-status--paused", `Pausada · Armazém cheio · ${assignment.worker}`);
        } else {
          if (cycle) cycle.hidden = false;
          if (capacityHelp) capacityHelp.hidden = true;
          setStatus("evolution-status--active", `Em produção · ${assignment.worker}`);
          if (cycle) cycleUpdaters.get(cycle)?.(assignment.progress_seconds);
        }
      });
    } catch (_error) {
      // A falha de uma consulta não interrompe o contador local; a próxima consulta tenta novamente.
    } finally {
      requestInFlight = false;
    }
  };
  window.setInterval(refreshGatheringStatus, 15000);

  document.addEventListener("DOMContentLoaded", window.initializeGatheringCycles);
})();
