(() => {
  const dialogSelector = "[data-building-reset-dialog]";

  async function findResetReceipt(idempotencyKey) {
    const statusUrl = new URL("/buildings/reset/status", window.location.origin);
    statusUrl.searchParams.set("key", idempotencyKey);
    const response = await fetch(statusUrl.href, {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json", "X-Requested-With": "fetch" },
    });
    if (!response.ok) throw new Error("Não foi possível consultar o comprovante do reset.");
    const receipt = await response.json();
    if (!receipt.completed || !Number.isInteger(Number(receipt.reset_id)) || Number(receipt.reset_id) < 1) {
      return null;
    }
    return new URL(`/buildings?reset_id=${encodeURIComponent(receipt.reset_id)}`, window.location.origin).href;
  }

  function initializeDialog(dialog) {
    if (!dialog || dialog.dataset.resetInitialized === "true") return;
    dialog.dataset.resetInitialized = "true";

    if (typeof dialog.showModal === "function") {
      if (dialog.open) dialog.close();
      dialog.showModal();
    }
    const cancel = dialog.querySelector("[data-reset-cancel]");
    cancel?.focus({ preventScroll: true });

    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      window.location.assign("/buildings");
    });

    const form = dialog.querySelector("[data-building-reset-form]");
    const button = form?.querySelector("[data-reset-submit]");
    const status = form?.querySelector("[data-reset-status]");
    if (!form || !button) return;

    // The reset form owns its uncertain-response flow; skip main.js's generic POST handler.
    form.dataset.nativeSubmit = "true";
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (form.dataset.submitting === "true") return;

      form.dataset.submitting = "true";
      form.setAttribute("aria-busy", "true");
      button.disabled = true;
      button.textContent = "Resetando…";
      if (status) status.textContent = "Salvando o reset. Aguarde a confirmação.";

      const idempotencyKey = String(new FormData(form).get("idempotency_key") || "");
      try {
        const response = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          credentials: "same-origin",
          cache: "no-store",
          redirect: "follow",
        });
        if (response.redirected && response.url) {
          const destination = new URL(response.url, window.location.origin);
          if (destination.origin === window.location.origin) {
            window.location.assign(`${destination.pathname}${destination.search}${destination.hash}`);
            return;
          }
        }
      } catch {
        // A dropped response is reconciled below using the read-only receipt endpoint.
      }

      try {
        const receiptUrl = await findResetReceipt(idempotencyKey);
        if (receiptUrl) {
          window.location.assign(receiptUrl);
          return;
        }
      } catch {
        // Keep the same idempotency key so a safe retry cannot charge twice.
      }

      form.dataset.submitting = "false";
      form.removeAttribute("aria-busy");
      button.disabled = false;
      button.textContent = "Tentar novamente";
      if (status) {
        status.textContent = "Não foi possível confirmar se o reset foi salvo. Tente novamente; este mesmo pedido será reconhecido sem cobrar duas vezes.";
      }
    });
  }

  window.initializeBuildingResetDialogs = (root = document) => {
    if (root?.matches?.(dialogSelector)) {
      initializeDialog(root);
      return;
    }
    root?.querySelectorAll?.(dialogSelector).forEach(initializeDialog);
  };

  window.initializeBuildingResetDialogs(document);
})();
