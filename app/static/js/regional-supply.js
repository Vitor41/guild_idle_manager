document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("form[data-supply-quote-url]").forEach((form) => {
    const supply = form.querySelector('input[name="supply"]');
    const summary = form.querySelector(".supply-preparation small");
    if (!supply || !summary) return;

    let requestVersion = 0;
    let quoteState = "pending";
    const refreshQuote = async () => {
      const version = ++requestVersion;
      quoteState = "pending";
      const selected = form.querySelectorAll('input[name="mercenary_ids"]:checked').length;
      if (!selected) {
        quoteState = "unavailable";
        supply.checked = false;
        supply.disabled = true;
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
          return;
        }
        quoteState = "available";
        supply.disabled = false;
        summary.textContent = `Chance ${quote.base_final_chance}% → ${quote.final_chance}% (+${quote.chance_bonus_pp} p.p.) · ${quote.cost_gold} ouro · retorno incremental esperado ${quote.incremental_ev_gold} ouro.`;
      } catch (_error) {
        if (version !== requestVersion) return;
        quoteState = "unavailable";
        supply.disabled = !supply.checked;
        summary.textContent = `Não foi possível consultar a disponibilidade. Tente novamente.${supply.checked ? " Desmarque o suprimento para iniciar sem ele." : ""}`;
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

    supply.addEventListener("change", () => {
      if (quoteState === "unavailable" && !supply.checked) supply.disabled = true;
    });

    form.querySelectorAll('input[name="mercenary_ids"]').forEach((input) => {
      input.addEventListener("change", refreshQuote);
    });
    form.querySelectorAll('select[name="run_multiplier"]').forEach((input) => {
      input.addEventListener("change", refreshQuote);
    });
    refreshQuote();
  });
});
