(() => {
  function updateProgress(root = document) {
    root.querySelectorAll("[data-workshop-progress]").forEach((bar) => {
      const start = Date.parse(bar.dataset.startsAt || "");
      const end = Date.parse(bar.dataset.endsAt || "");
      const span = Math.max(1, end - start);
      const percent = Math.max(0, Math.min(100, ((Date.now() - start) / span) * 100));
      bar.value = percent;
      bar.textContent = `${Math.floor(percent)}%`;
    });
  }

  function parseWorkshopQuantity(input) {
    const raw = input.value;
    if (raw === "" || !Number.isFinite(Number(raw))) return null;
    const quantity = Number(raw);
    const minimum = Number(input.min || 0);
    const maximum = input.max === "" ? Number.POSITIVE_INFINITY : Number(input.max);
    const step = Number(input.step || 1);
    if (!Number.isInteger(quantity) || quantity < minimum || quantity > maximum || !Number.isFinite(step) || step <= 0) return null;
    const offset = quantity - minimum;
    if (Math.abs(offset / step - Math.round(offset / step)) > 1e-9) return null;
    return quantity;
  }

  function updateEstimate(form) {
    const input = form.querySelector("#workshop-quantity");
    const estimate = form.querySelector("[data-workshop-estimate]");
    if (!input || !estimate) return;
    const submit = form.querySelector("[data-workshop-submit]");
    const quantity = parseWorkshopQuantity(input);
    if (submit && submit.dataset.workshopServerDisabled === undefined) {
      submit.dataset.workshopServerDisabled = String(submit.disabled);
    }
    if (submit) submit.disabled = submit.dataset.workshopServerDisabled === "true" || quantity === null;
    if (quantity === null) {
      estimate.textContent = "Informe uma quantidade válida para estimar custo e prazo.";
      return;
    }
    const meatPerKit = Number(estimate.dataset.meatPerKit);
    const herbsPerKit = Number(estimate.dataset.herbsPerKit);
    const seconds = quantity * Number(estimate.dataset.secondsPerKit);
    estimate.textContent = `Custo: ${quantity * meatPerKit} Carnes + ${quantity * herbsPerKit} Ervas · Tempo estimado: ${seconds} segundo(s).`;
  }

  function initialize(root = document) {
    root.querySelectorAll(".workshop-batch-form").forEach((form) => {
      if (form.dataset.workshopControlsInitialized === "true") return;
      const input = form.querySelector("#workshop-quantity");
      const estimate = form.querySelector("[data-workshop-estimate]");
      if (!input || !estimate) return;
      form.dataset.workshopControlsInitialized = "true";
      form.querySelector("[data-workshop-max]")?.addEventListener("click", () => {
        input.value = input.max;
        input.dispatchEvent(new Event("input", { bubbles: true }));
      });
      input.addEventListener("input", () => updateEstimate(form));
      updateEstimate(form);
    });

    updateProgress(root);
    if (!window.workshopSupplyProgressTimer) {
      window.workshopSupplyProgressTimer = window.setInterval(() => updateProgress(document), 1000);
    }
  }

  window.initializeWorkshopSupplyControls = initialize;
  initialize(document);
})();
