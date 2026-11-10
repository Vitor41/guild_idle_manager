(() => {
  const initializedTriggers = new WeakSet();

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

  const positionVisiblePanels = () => {
    document.querySelectorAll("[data-equipment-details-trigger][aria-expanded='true']").forEach((trigger) => {
      const panel = trigger.closest(".equipment-slot")?.querySelector("[data-equipment-details]");
      if (panel && !panel.hidden) positionPanel(trigger, panel);
    });
  };
  window.addEventListener("resize", positionVisiblePanels);
  window.addEventListener("scroll", positionVisiblePanels, true);

  const initializeEquipmentDetails = (root = document) => {
    const triggers = root.querySelectorAll?.("[data-equipment-details-trigger]") ?? [];
    for (const trigger of triggers) {
      if (initializedTriggers.has(trigger)) continue;
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
      initializedTriggers.add(trigger);
    }
  }

  const initializeEquipmentSwap = (root = document) => {
    root.querySelectorAll("[data-equipment-swap]").forEach((form) => {
      const itemSelect = form.querySelector("[data-equipment-swap-item]");
      const replacementField = form.querySelector("[data-equipment-replacement-field]");
      const replacementSelect = form.querySelector("[data-equipment-swap-replacement]");
      if (!itemSelect || !replacementField || !replacementSelect) return;

      const updateReplacementOptions = () => {
        const selectedItem = itemSelect.selectedOptions[0];
        let candidateIds = [];
        try {
          candidateIds = JSON.parse(selectedItem?.dataset.replacementCandidateIds || "[]");
        } catch (_error) {
          candidateIds = [];
        }
        const required = selectedItem?.dataset.replacementRequired === "true";
        replacementField.hidden = !required;
        replacementSelect.required = required;

        Array.from(replacementSelect.options).slice(1).forEach((option) => {
          const allowed = required && candidateIds.includes(Number(option.value));
          option.hidden = !allowed;
          option.disabled = !allowed;
        });
        if (!candidateIds.includes(Number(replacementSelect.value))) {
          replacementSelect.value = "";
        }
      };

      itemSelect.addEventListener("change", updateReplacementOptions);
      updateReplacementOptions();
    });
  };

  window.initializeEquipmentDetails = initializeEquipmentDetails;
  initializeEquipmentDetails(document);
  window.initializeEquipmentSwap = initializeEquipmentSwap;
  initializeEquipmentSwap(document);
})();
