document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-evolution-dialog]");
  if (trigger) {
    const dialog = document.getElementById(trigger.dataset.evolutionDialog);
    if (dialog instanceof HTMLDialogElement) dialog.showModal();
    return;
  }
  const close = event.target.closest("[data-evolution-dialog-close]");
  if (close) close.closest("dialog")?.close();
});

document.querySelectorAll(".evolution-dialog").forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
});

document.querySelectorAll("dialog[data-regional-rebellion-auto-open]").forEach((dialog) => {
  if (dialog instanceof HTMLDialogElement) window.GIMStartupModalQueue?.enqueue(dialog, 2);
});

document.querySelectorAll(".evolution-page img").forEach((image) => {
  const fallback = () => {
    image.hidden = true;
    image.closest(".evolution-hero, .evolution-vigil-card, .evolution-gathering__art, .evolution-future-card, .evolution-reward")?.classList.add("has-art-fallback");
  };
  image.addEventListener("error", fallback, { once: true });
  if (image.complete && image.naturalWidth === 0) fallback();
});

function updateVigilCountdowns() {
  document.querySelectorAll("[data-evolution-countdown]").forEach((element) => {
    const deadline = Date.parse(element.dataset.evolutionCountdown);
    const seconds = Math.max(0, Math.floor((deadline - Date.now()) / 1000));
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainder = seconds % 60;
    element.textContent = `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
  });
}
updateVigilCountdowns();
window.setInterval(updateVigilCountdowns, 1000);
