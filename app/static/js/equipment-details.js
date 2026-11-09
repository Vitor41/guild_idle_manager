(() => {
  const triggers = document.querySelectorAll("[data-equipment-details-trigger]");
  if (!triggers.length) return;

  const closePanel = (trigger, panel, { restoreFocus = false } = {}) => {
    trigger.setAttribute("aria-expanded", "false");
    panel.hidden = true;
    panel.classList.remove("is-open", "is-pinned");
    panel.style.removeProperty("left");
    panel.style.removeProperty("top");
    panel.style.removeProperty("max-height");
    if (restoreFocus) {
      trigger.dataset.suppressDetailsFocus = "true";
      trigger.focus();
      delete trigger.dataset.suppressDetailsFocus;
    }
  };

  const positionPanel = (trigger, panel) => {
    if (window.matchMedia("(max-width: 760px)").matches) return;
    const rect = trigger.getBoundingClientRect();
    const margin = 12;
    const width = Math.min(360, window.innerWidth - margin * 2);
    const estimatedHeight = Math.min(panel.scrollHeight || 300, window.innerHeight - margin * 2);
    const rightSpace = window.innerWidth - rect.right;
    const left = rightSpace >= width + margin
      ? rect.right + margin
      : Math.max(margin, rect.left - width - margin);
    const top = Math.max(margin, Math.min(rect.top, window.innerHeight - estimatedHeight - margin));
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
    panel.style.maxHeight = `${window.innerHeight - margin * 2}px`;
  };

  for (const trigger of triggers) {
    const slot = trigger.closest(".equipment-slot");
    const panel = slot?.querySelector("[data-equipment-details]");
    if (!slot || !panel) continue;

    let pinned = false;
    let closeTimer = 0;
    const openPanel = () => {
      window.clearTimeout(closeTimer);
      panel.hidden = false;
      panel.classList.add("is-open");
      panel.classList.toggle("is-pinned", pinned);
      trigger.setAttribute("aria-expanded", "true");
      positionPanel(trigger, panel);
    };
    const scheduleClose = () => {
      window.clearTimeout(closeTimer);
      closeTimer = window.setTimeout(() => {
        if (pinned || trigger.matches(":hover") || panel.matches(":hover") || trigger.contains(document.activeElement) || panel.contains(document.activeElement)) return;
        closePanel(trigger, panel);
      }, 160);
    };

    trigger.addEventListener("pointerenter", (event) => {
      if (event.pointerType === "mouse") openPanel();
    });
    trigger.addEventListener("pointerleave", (event) => {
      if (event.pointerType === "mouse") scheduleClose();
    });
    trigger.addEventListener("focus", () => {
      if (trigger.dataset.suppressDetailsFocus !== "true") openPanel();
    });
    trigger.addEventListener("blur", scheduleClose);
    trigger.addEventListener("click", () => {
      pinned = !pinned;
      if (pinned) openPanel();
      else if (!trigger.matches(":hover") && !panel.matches(":hover")) closePanel(trigger, panel);
      else panel.classList.remove("is-pinned");
    });
    panel.addEventListener("pointerenter", (event) => {
      if (event.pointerType === "mouse") window.clearTimeout(closeTimer);
    });
    panel.addEventListener("pointerleave", (event) => {
      if (event.pointerType === "mouse") scheduleClose();
    });
    panel.addEventListener("focusin", () => window.clearTimeout(closeTimer));
    panel.addEventListener("focusout", scheduleClose);
    panel.querySelector("[data-equipment-details-close]")?.addEventListener("click", () => {
      pinned = false;
      closePanel(trigger, panel, { restoreFocus: true });
    });
    trigger.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !panel.hidden) {
        event.preventDefault();
        pinned = false;
        closePanel(trigger, panel, { restoreFocus: true });
      }
    });
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        pinned = false;
        closePanel(trigger, panel, { restoreFocus: true });
      }
    });
    window.addEventListener("resize", () => { if (!panel.hidden) positionPanel(trigger, panel); });
    window.addEventListener("scroll", () => { if (!panel.hidden) positionPanel(trigger, panel); }, true);
  }
})();
