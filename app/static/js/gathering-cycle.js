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
        if (document.hidden) return;
        update((elapsed + 1) % 60);
      }, 1000);
    });
  };

  const page = document.querySelector("[data-gathering-status-url]");
  if (!page) return;
  let requestInFlight = false;
  const refreshGatheringStatus = async () => {
    if (requestInFlight || document.visibilityState !== "visible") return;
    requestInFlight = true;
    try {
      const response = await fetch(page.dataset.gatheringStatusUrl, {
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) return;
      const state = await response.json();
      const warehouseLabel = page.querySelector("[data-gathering-warehouse-label]");
      const warehouseProgress = page.querySelector("[data-gathering-warehouse-progress]");
      if (warehouseLabel) {
        warehouseLabel.textContent = `${Number(state.warehouse.used).toLocaleString("pt-BR")} / ${Number(state.warehouse.capacity).toLocaleString("pt-BR")}`;
      }
      if (warehouseProgress) {
        warehouseProgress.max = state.warehouse.capacity;
        warehouseProgress.value = Math.min(state.warehouse.used, state.warehouse.capacity);
      }
      page.querySelectorAll("[data-gathering-family-count]").forEach((counter) => {
        counter.textContent = String(state.inventory_by_family[counter.dataset.gatheringFamilyCount] || 0);
      });
      page.querySelectorAll("[data-gathering-cycle]").forEach((cycle) => {
        const family = cycle.dataset.gatheringFamily;
        const assignment = state.assignments[family];
        if (!assignment) {
          window.location.reload();
          return;
        }
        const status = cycle.closest("[data-gathering-card]")?.querySelector("[data-gathering-status]");
        if (assignment.capacity_paused) {
          cycle.hidden = true;
          if (status) status.textContent = `Pausada · Armazém cheio · ${assignment.worker}`;
        } else {
          cycle.hidden = false;
          if (status) status.textContent = `Em produção · ${assignment.worker}`;
          cycleUpdaters.get(cycle)?.(assignment.progress_seconds);
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
