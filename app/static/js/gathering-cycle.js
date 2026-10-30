(() => {
  const initializedCycles = new WeakSet();

  window.initializeGatheringCycles = () => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.querySelectorAll("[data-gathering-cycle]").forEach((cycle) => {
      if (initializedCycles.has(cycle)) return;
      initializedCycles.add(cycle);

      const progress = cycle.querySelector("progress");
      const remainingLabel = cycle.querySelector("[data-gathering-remaining]");
      if (!progress || !remainingLabel) return;
      let elapsed = Number(cycle.dataset.progressSeconds || 0);

      if (reducedMotion) {
        remainingLabel.textContent = String(60 - elapsed);
        return;
      }

      const timer = window.setInterval(() => {
        if (!cycle.isConnected) {
          window.clearInterval(timer);
          return;
        }
        if (document.hidden) return;
        elapsed = (elapsed + 1) % 60;
        progress.value = elapsed;
        remainingLabel.textContent = String(60 - elapsed);
      }, 1000);
    });
  };

  document.addEventListener("DOMContentLoaded", window.initializeGatheringCycles);
})();
