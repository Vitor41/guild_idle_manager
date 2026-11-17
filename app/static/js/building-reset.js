(() => {
  const dialog = document.querySelector("[data-building-reset-dialog]");
  if (!dialog) return;

  if (dialog.open && typeof dialog.showModal === "function") {
    dialog.close();
    dialog.showModal();
  }
  const cancel = dialog.querySelector("[data-reset-cancel]");
  if (cancel) cancel.focus({ preventScroll: true });

  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    window.location.assign("/buildings");
  });

  const form = dialog.querySelector("[data-building-reset-form]");
  const button = form?.querySelector("[data-reset-submit]");
  const status = form?.querySelector("[data-reset-status]");
  if (!form || !button) return;

  form.addEventListener("submit", () => {
    form.setAttribute("aria-busy", "true");
    button.disabled = true;
    button.textContent = "Resetando…";
    if (status) status.textContent = "Aguarde enquanto o reset é salvo.";
  });
})();
