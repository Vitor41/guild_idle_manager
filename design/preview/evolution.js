document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-dialog]");
  if (!trigger) return;
  const dialog = document.getElementById(trigger.dataset.dialog);
  if (dialog instanceof HTMLDialogElement) dialog.showModal();
});

document.querySelectorAll(".preview-dialog").forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
});
