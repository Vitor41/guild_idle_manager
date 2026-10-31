(() => {
  const balance = document.querySelector("[data-offline-stamina-value]");
  if (!balance) return;

  const available = document.querySelector("[data-offline-stamina-available]");
  const nextRecharge = document.querySelector("[data-offline-stamina-next]");
  const formatBalance = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}min`;
  };

  const refresh = async () => {
    if (document.hidden) return;
    try {
      const response = await fetch("/desktop/api/stamina-status", { credentials: "same-origin" });
      const status = await response.json();
      if (!response.ok || !status.available) throw new Error("stamina unavailable");

      const cap = Math.max(0, Number(status.cap_seconds) || 28800);
      const seconds = Math.max(0, Math.min(cap, Number(status.stamina_seconds) || 0));
      const label = formatBalance(seconds);
      balance.textContent = `Estamina ${label} / 8h`;
      if (available) available.textContent = label;
      if (nextRecharge) {
        const atCap = seconds >= cap;
        nextRecharge.hidden = atCap;
        if (!atCap) {
          const remaining = Math.max(0, Number(status.seconds_until_recharge) || 0);
          nextRecharge.textContent = `Próxima recarga de 2h em ${Math.ceil(remaining / 60)} min online.`;
        }
      }
    } catch (_error) {
      balance.textContent = "Saldo temporariamente indisponível";
      if (available) available.textContent = "temporariamente indisponível";
      if (nextRecharge) nextRecharge.hidden = true;
    }
  };

  refresh();
  window.setInterval(refresh, 15000);
  document.addEventListener("visibilitychange", refresh);
})();
