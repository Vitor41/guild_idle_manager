document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".supply-preparation-progress").forEach((progressBox) => {
    const time = progressBox.querySelector("time[data-ends-at]");
    const bar = progressBox.querySelector("progress");
    const status = progressBox.querySelector("strong");
    const form = progressBox.closest("form");
    const startButton = form?.querySelector('button[type="submit"]:not([data-prepare-action])');
    const startedAt = Date.parse(time?.dataset.startsAt || "");
    const endsAt = Date.parse(time?.dataset.endsAt || "");
    if (!time || !bar || !status || !Number.isFinite(endsAt)) return;
    const updatePreparation = () => {
      const now = Date.now();
      const total = Number.isFinite(startedAt) ? Math.max(1, endsAt - startedAt) : 1;
      const remaining = Math.max(0, Math.ceil((endsAt - now) / 1000));
      const elapsed = Math.max(0, Math.min(total, now - (Number.isFinite(startedAt) ? startedAt : endsAt)));
      bar.value = Math.floor((elapsed / total) * 100);
      if (remaining === 0) {
        bar.value = 100;
        status.textContent = "Preparação concluída · pronta para iniciar";
        time.textContent = "Concluída";
        if (startButton) startButton.disabled = false;
        return false;
      }
      status.textContent = "Suprimento em preparo";
      const hours = Math.floor(remaining / 3600);
      const minutes = Math.floor((remaining % 3600) / 60);
      const seconds = remaining % 60;
      time.textContent = `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
      return true;
    };
    updatePreparation();
    const timer = window.setInterval(() => {
      if (!updatePreparation()) window.clearInterval(timer);
    }, 1000);
  });

  document.querySelectorAll("form[data-supply-quote-url]").forEach((form) => {
    const supply = form.querySelector('input[name="supply"]');
    const summary = form.querySelector(".supply-preparation small");
    if (!supply || !summary) return;

    let requestVersion = 0;
    let quoteState = "pending";
    form.addEventListener("click", (event) => {
      if (event.target.closest("[data-start-without-supply]")) supply.checked = false;
    });
    const prepareButton = form.querySelector("[data-prepare-action]");
    const syncPrepareButton = () => {
      if (prepareButton) prepareButton.disabled = !supply.checked || quoteState !== "available";
    };
    const refreshQuote = async () => {
      const version = ++requestVersion;
      quoteState = "pending";
      const selected = form.querySelectorAll('input[name="mercenary_ids"]:checked').length;
      if (!selected) {
        quoteState = "unavailable";
        supply.checked = false;
        supply.disabled = true;
        syncPrepareButton();
        summary.textContent = "Escolha uma equipe para consultar a chance final e o custo do suprimento.";
        return;
      }

      // Keep the checkbox enabled while quoting. If the player submits during
      // the request, FormData must still carry their current choice; the start
      // endpoint recalculates availability and cost from server state.
      supply.disabled = false;
      summary.textContent = "Calculando chance e custo para esta equipe…";
      try {
        const response = await fetch(form.dataset.supplyQuoteUrl, {
          method: "POST",
          body: new FormData(form),
          headers: { "X-Requested-With": "fetch" },
          credentials: "same-origin",
        });
        const quote = await response.json();
        if (version !== requestVersion) return;
        if (!response.ok || !quote.available) {
          quoteState = "unavailable";
          // Preserve an explicit selection so it is never silently omitted
          // from FormData. Leave a selected checkbox enabled so it can be
          // unchecked; an unchecked one stays disabled until a new quote.
          supply.disabled = !supply.checked;
          summary.textContent = `${quote.reason || "Suprimento indisponível para esta equipe."}${supply.checked ? " Desmarque o suprimento para iniciar sem ele." : ""}`;
          syncPrepareButton();
          return;
        }
        quoteState = "available";
        supply.disabled = false;
        summary.textContent = `Chance ${quote.base_final_chance}% → ${quote.final_chance}% (+${quote.chance_bonus_pp} p.p.) · ${quote.cost_gold} ouro · retorno incremental esperado ${quote.incremental_ev_gold} ouro.`;
        syncPrepareButton();
      } catch (_error) {
        if (version !== requestVersion) return;
        quoteState = "unavailable";
        supply.disabled = !supply.checked;
        summary.textContent = `Não foi possível consultar a disponibilidade. Tente novamente.${supply.checked ? " Desmarque o suprimento para iniciar sem ele." : ""}`;
        syncPrepareButton();
      }
    };

    form.addEventListener("submit", (event) => {
      // A server-side start always recalculates the quote. Only stop a submit
      // when the latest completed quote says a selected supply is unavailable.
      if (supply.checked && quoteState === "unavailable") {
        event.preventDefault();
        supply.focus();
      }
    });

    supply.addEventListener("change", syncPrepareButton);

    form.querySelectorAll('input[name="mercenary_ids"]').forEach((input) => {
      input.addEventListener("change", refreshQuote);
    });
    form.querySelectorAll('select[name="run_multiplier"]').forEach((input) => {
      input.addEventListener("change", refreshQuote);
    });
    refreshQuote();
  });
});
