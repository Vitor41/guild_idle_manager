document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-market-fill-max]");
  if (!button || button.disabled) return;
  const form = button.closest("form");
  const quantity = form?.querySelector("[data-market-quantity]");
  if (!quantity) return;
  quantity.value = String(Math.max(0, Number(button.dataset.max) || 0));
  quantity.dispatchEvent(new Event("input", { bubbles: true }));
  quantity.dispatchEvent(new Event("change", { bubbles: true }));
});
