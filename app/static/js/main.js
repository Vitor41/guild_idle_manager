const startupModalQueue = (() => {
  const pending = [];
  let active = null;
  let sequence = 0;
  let batchDepth = 0;
  const advance = () => {
    if (batchDepth > 0 || active?.open) return;
    active = null;
    while (pending.length) {
      const next = pending.shift().dialog;
      if (!(next instanceof HTMLDialogElement) || next.open) continue;
      active = next;
      next.addEventListener("close", () => {
        if (active === next) active = null;
        advance();
      }, { once: true });
      next.showModal();
      return;
    }
  };
  return {
    beginBatch() {
      batchDepth += 1;
    },
    endBatch() {
      if (batchDepth > 0) batchDepth -= 1;
      if (batchDepth === 0) advance();
    },
    enqueue(dialog, priority, deadline = Number.POSITIVE_INFINITY) {
      if (!(dialog instanceof HTMLDialogElement) || dialog.open || pending.some((row) => row.dialog === dialog)) return;
      pending.push({ dialog, priority, deadline: Number.isFinite(deadline) ? deadline : Number.POSITIVE_INFINITY, sequence: sequence++ });
      pending.sort((left, right) => left.priority - right.priority || left.deadline - right.deadline || left.sequence - right.sequence);
      advance();
    },
    enqueueMany(entries) {
      this.beginBatch();
      try {
        for (const { dialog, priority, deadline } of entries) this.enqueue(dialog, priority, deadline);
      } finally {
        this.endBatch();
      }
    },
    remove(dialog) {
      const index = pending.findIndex((row) => row.dialog === dialog);
      if (index >= 0) pending.splice(index, 1);
      if (active === dialog && dialog.open) dialog.close();
    },
    isIdle() {
      return pending.length === 0 && !active?.open;
    },
  };
})();
window.GIMStartupModalQueue = startupModalQueue;

let navigationWorkStatusRequest = null;
let navigationWorkStatusController = null;
let regionalEventsRefreshRequest = null;

async function refreshRegionalEventsPageFromServer() {
  if (regionalEventsRefreshRequest) return regionalEventsRefreshRequest;
  const currentUrl = new URL(window.location.href);
  if (currentUrl.pathname !== "/regional/events") return false;
  const currentRoot = document.querySelector(".regional-events-page[data-regional-events]");
  if (!currentRoot) return false;

  const pendingRequest = fetch(`${currentUrl.pathname}${currentUrl.search}`, {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
    headers: { "Accept": "text/html", "X-Requested-With": "fetch" },
  }).then(async (response) => {
    if (!response.ok) return false;
    const responseUrl = response.url ? new URL(response.url, currentUrl) : currentUrl;
    if (responseUrl.origin !== currentUrl.origin || responseUrl.pathname !== currentUrl.pathname) return false;
    const parsedDocument = new DOMParser().parseFromString(await response.text(), "text/html");
    const incomingRoot = parsedDocument.querySelector(".regional-events-page[data-regional-events]");
    if (!incomingRoot || window.location.pathname !== currentUrl.pathname
        || document.querySelector(".regional-events-page[data-regional-events]") !== currentRoot) return false;

    const formState = captureGameFormState();
    const activeElement = document.activeElement;
    let focusState = null;
    if (activeElement && currentRoot.contains(activeElement)) {
      const form = activeElement.form || activeElement.closest?.("form");
      if (activeElement.id) {
        focusState = { id: activeElement.id };
      } else if (form && activeElement.name) {
        const matchingControls = Array.from(form.elements).filter(
          (control) => getControlStateKey(control) === getControlStateKey(activeElement),
        );
        focusState = {
          formKey: getFormStateKey(form),
          controlKey: getControlStateKey(activeElement),
          controlIndex: matchingControls.indexOf(activeElement),
          selectionStart: typeof activeElement.selectionStart === "number" ? activeElement.selectionStart : null,
          selectionEnd: typeof activeElement.selectionEnd === "number" ? activeElement.selectionEnd : null,
        };
      }
    }
    const openDetails = Array.from(currentRoot.querySelectorAll("details[open]")).map((details) => ({
      id: details.id,
      index: Array.from(currentRoot.querySelectorAll("details")).indexOf(details),
    }));
    const scrollPosition = window.scrollY;
    const replacement = document.importNode(incomingRoot, true);
    currentRoot.replaceWith(replacement);

    const replacementDetails = Array.from(replacement.querySelectorAll("details"));
    for (const detail of openDetails) {
      const target = (detail.id && replacement.querySelector(`#${detail.id}`)) || replacementDetails[detail.index];
      if (target) target.open = true;
    }
    restoreGameFormState(formState);
    window.GIMApplyDesktopArt?.(replacement);
    window.initializeRegionalSupply?.(replacement);
    updateGenericCountdowns();
    window.refreshRegionalEventAnchorOffset?.();

    let focusTarget = focusState?.id ? document.getElementById(focusState.id) : null;
    if (!focusTarget && focusState?.formKey) {
      const form = Array.from(replacement.querySelectorAll("form")).find(
        (candidate) => getFormStateKey(candidate) === focusState.formKey,
      );
      const matches = form
        ? Array.from(form.elements).filter((control) => getControlStateKey(control) === focusState.controlKey)
        : [];
      focusTarget = matches[focusState.controlIndex] || matches[0] || null;
    }
    focusTarget?.focus?.({ preventScroll: true });
    if (focusTarget && Number.isInteger(focusState?.selectionStart)
        && typeof focusTarget.setSelectionRange === "function") {
      focusTarget.setSelectionRange(focusState.selectionStart, focusState.selectionEnd);
    }
    window.scrollTo({ top: scrollPosition, behavior: "auto" });
    return true;
  }).catch(() => {
    // Keep the last rendered event state when the authoritative page request fails.
    return false;
  }).finally(() => {
    if (regionalEventsRefreshRequest === pendingRequest) regionalEventsRefreshRequest = null;
  });
  regionalEventsRefreshRequest = pendingRequest;
  return regionalEventsRefreshRequest;
}
window.refreshRegionalEventsPageFromServer = refreshRegionalEventsPageFromServer;

async function refreshNavigationWorkIndicators(force = false) {
  if (navigationWorkStatusRequest && !force) return navigationWorkStatusRequest;
  if (force) navigationWorkStatusController?.abort();
  const links = [...document.querySelectorAll("[data-nav-work-menu]")];
  if (!links.length) return;
  const controller = new AbortController();
  navigationWorkStatusController = controller;
  let refreshRegionalEvents = false;
  let regionalEventStatusTransition = null;
  const regionalEventsPageRoot = document.querySelector(".regional-events-page[data-regional-events]");
  const markUnavailable = (link) => {
    link.querySelector(".nav-work-indicator")?.remove();
    const indicator = document.createElement("span");
    indicator.className = "nav-work-indicator";
    indicator.dataset.state = "unknown";
    indicator.setAttribute("aria-hidden", "true");
    link.append(indicator);
    link.dataset.workState = "unknown";
    const label = `${link.dataset.navWorkLabel || "Atividade"}: status indisponível`;
    link.setAttribute("aria-label", label);
    link.title = label;
  };
  const pendingRequest = fetch("/api/navigation/work-status", {
    credentials: "same-origin",
    cache: "no-store",
    signal: controller.signal,
    headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
  }).then(async (response) => {
    if (!response.ok) {
      links.forEach(markUnavailable);
      return;
    }
    const payload = await response.json();
    for (const link of links) {
      const status = payload.menus?.[link.dataset.navWorkMenu];
      if (!status || !Number.isInteger(status.active) || status.active < 0
          || !Number.isInteger(status.ready) || status.ready < 0
          || typeof status.label !== "string" || !status.label.trim()
          || (link.dataset.navWorkMenu === "regional_events" && typeof status.review_token !== "string")) {
        markUnavailable(link);
        continue;
      }
      const active = status.active;
      const ready = status.ready;
      const previousActive = Number(link.dataset.workActive);
      const previousReady = Number(link.dataset.workReady);
      let previousReviewToken = link.dataset.workReviewToken;
      if (link.dataset.navWorkMenu === "regional_events" && regionalEventsPageRoot?.dataset.reviewToken) {
        previousReviewToken = regionalEventsPageRoot.dataset.reviewToken;
        link.dataset.workReviewToken = previousReviewToken;
      }
      const nextReviewToken = link.dataset.navWorkMenu === "regional_events"
        ? status.review_token
        : undefined;
      const reviewChanged = typeof nextReviewToken === "string"
        && previousReviewToken !== undefined
        && previousReviewToken !== nextReviewToken;
      if (link.dataset.navWorkMenu === "regional_events"
          && ((Number.isInteger(previousActive) && Number.isInteger(previousReady)
              && (previousActive !== active || previousReady !== ready))
            || reviewChanged)) {
        refreshRegionalEvents = true;
        regionalEventStatusTransition = {
          link, previousActive, previousReady, active, ready,
          previousReviewToken, nextReviewToken,
        };
      }
      link.dataset.workActive = String(active);
      link.dataset.workReady = String(ready);
      if (typeof nextReviewToken === "string") link.dataset.workReviewToken = nextReviewToken;
      link.querySelector(".nav-work-indicator")?.remove();
      if (!active && !ready) {
        link.removeAttribute("data-work-state");
        link.removeAttribute("aria-label");
        link.removeAttribute("title");
        continue;
      }
      const state = ready ? "ready" : "active";
      const inviteNote = link.querySelector(".regional-invite-badge") ? "; convite de rebelião pendente" : "";
      const indicator = document.createElement("span");
      indicator.className = "nav-work-indicator";
      indicator.dataset.state = state;
      indicator.setAttribute("aria-hidden", "true");
      link.append(indicator);
      link.dataset.workState = state;
      const accessibleLabel = `${status.label || link.dataset.navWorkLabel || "Atividade pendente"}${inviteNote}`;
      link.setAttribute("aria-label", accessibleLabel);
      link.title = accessibleLabel;
    }
    if (refreshRegionalEvents && window.location.pathname === "/regional/events") {
      const pageRefresh = window.refreshRegionalEventsPageFromServer?.();
      const restorePreviousCounts = () => {
        if (!regionalEventStatusTransition) return;
        const { link, previousActive, previousReady, active, ready, previousReviewToken, nextReviewToken } = regionalEventStatusTransition;
        if (link.dataset.workActive === String(active) && link.dataset.workReady === String(ready)) {
          link.dataset.workActive = String(previousActive);
          link.dataset.workReady = String(previousReady);
        }
        if (nextReviewToken !== undefined && link.dataset.workReviewToken === nextReviewToken) {
          if (previousReviewToken === undefined) delete link.dataset.workReviewToken;
          else link.dataset.workReviewToken = previousReviewToken;
        }
      };
      if (pageRefresh && typeof pageRefresh.then === "function") {
        void pageRefresh.then((updated) => {
          if (updated !== true) restorePreviousCounts();
        }).catch(restorePreviousCounts);
      } else {
        restorePreviousCounts();
      }
    }
  }).catch(() => {
    if (!controller.signal.aborted) links.forEach(markUnavailable);
  }).finally(() => {
    if (navigationWorkStatusRequest === pendingRequest) {
      navigationWorkStatusRequest = null;
      navigationWorkStatusController = null;
    }
  });
  navigationWorkStatusRequest = pendingRequest;
  return navigationWorkStatusRequest;
}
window.refreshNavigationWorkIndicators = refreshNavigationWorkIndicators;
refreshNavigationWorkIndicators();
window.setInterval(() => {
  if (!document.hidden) refreshNavigationWorkIndicators();
}, 20000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refreshNavigationWorkIndicators();
});

document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-bonus-dialog-open]");
  if (trigger) {
    const dialog = document.getElementById(trigger.dataset.bonusDialogOpen);
    if (dialog instanceof HTMLDialogElement) dialog.showModal();
    return;
  }
  if (event.target.matches(".bonus-details-dialog")) event.target.close();
});

function formatGenericRemaining(ms) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function updateGenericCountdowns() {
  document.querySelectorAll("[data-ends-at]").forEach((element) => {
    const raw = element.dataset.endsAt || "";
    const endsAt = Date.parse(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw) ? raw : `${raw}Z`);
    const remaining = endsAt - Date.now();
    if (!(element instanceof HTMLButtonElement)) {
      element.textContent = remaining <= 0 ? "Pronto" : formatGenericRemaining(remaining);
    }
    if (element instanceof HTMLButtonElement && remaining <= 0) {
      element.disabled = false;
    }
    const row = element.closest("tr");
    if (row && remaining <= 0) {
      row.querySelectorAll("button[disabled]").forEach((button) => {
        button.disabled = false;
      });
    }
  });
}

async function refreshResourceTotals() {
  if (!document.querySelector("[data-resource-total]")) return;
  try {
    const response = await fetch("/api/resources", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) return;
    const totals = await response.json();
    document.querySelectorAll("[data-resource-total]").forEach((element) => {
      const value = totals[element.dataset.resourceTotal];
      if (Number.isFinite(value)) element.textContent = new Intl.NumberFormat("pt-BR").format(value);
    });
  } catch (_error) {
    // Live totals are a convenience; the server-rendered balance remains visible.
  }
}

refreshResourceTotals();
window.setInterval(() => {
  if (document.visibilityState === "visible") refreshResourceTotals();
}, 15000);

window.parseUtcTimestamp = (value) => {
  const raw = value || "";
  return Date.parse(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw) ? raw : `${raw}Z`);
};

function initializeClassGuideIndex() {
  const nav = document.querySelector(".classes-page .classes-guide-index");
  if (!nav) return;
  const links = [...nav.querySelectorAll('a[href^="#"]')];
  const sections = links.map((link) => document.getElementById(decodeURIComponent(link.hash.slice(1)))).filter(Boolean);
  const revealLinkHorizontally = (link) => {
    const linkBounds = link.getBoundingClientRect();
    const navBounds = nav.getBoundingClientRect();
    const padding = 8;
    if (linkBounds.left < navBounds.left + padding) {
      nav.scrollTo({ left: nav.scrollLeft + linkBounds.left - navBounds.left - padding, behavior: "smooth" });
    } else if (linkBounds.right > navBounds.right - padding) {
      nav.scrollTo({ left: nav.scrollLeft + linkBounds.right - navBounds.right + padding, behavior: "smooth" });
    }
  };
  const setActive = (target) => {
    links.forEach((link) => {
      if (link.hash === `#${target.id}`) {
        link.setAttribute("aria-current", "location");
        revealLinkHorizontally(link);
      } else link.removeAttribute("aria-current");
    });
  };
  const observer = new IntersectionObserver((entries) => {
    const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (visible) setActive(visible.target);
  }, { rootMargin: "-120px 0px -65% 0px", threshold: [0, 0.2, 0.5] });
  sections.forEach((section) => observer.observe(section));
  nav.addEventListener("click", (event) => {
    const link = event.target.closest('a[href^="#"]');
    const target = link && document.getElementById(decodeURIComponent(link.hash.slice(1)));
    if (target) window.setTimeout(() => target.focus({ preventScroll: true }), 0);
  });
}

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const help = document.querySelector(".offline-action:hover .offline-help, .offline-action:focus-within .offline-help");
  if (!help) return;
  help.open = false;
  help.classList.add("escape-dismissed");
  help.querySelector("summary")?.blur();
});
document.querySelectorAll(".offline-help").forEach((help) => {
  help.addEventListener("toggle", () => { if (help.open) help.classList.remove("escape-dismissed"); });
  help.addEventListener("pointerleave", () => help.classList.remove("escape-dismissed"));
  help.addEventListener("focusin", () => help.classList.remove("escape-dismissed"));
});

const offlineDialog = document.querySelector("#offline-dialog[data-auto-open]");
if (offlineDialog) {
    offlineDialog.addEventListener("cancel", (event) => event.preventDefault());
    offlineDialog.querySelectorAll("[data-offline-close]").forEach((button) => {
      button.addEventListener("click", () => offlineDialog.close());
    });
    offlineDialog.querySelector("[data-offline-ack]")?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      const error = offlineDialog.querySelector(".offline-ack-error");
      button.disabled = true;
      error.hidden = true;
      try {
        const reportId = offlineDialog.dataset.reportId;
        if (offlineDialog.dataset.requiresAck === "True" && !reportId) {
          throw new Error("Não foi possível identificar o relatório salvo. Ele continuará pendente para recuperação.");
        }
        if (reportId) {
          const response = await fetch("/desktop/api/offline-report/acknowledge", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ report_id: reportId }),
          });
          if (!response.ok) throw new Error("Não foi possível confirmar o relatório. Tente novamente.");
        }
        offlineDialog.close();
      } catch (failure) {
        error.textContent = failure.message;
        error.hidden = false;
      } finally {
        button.disabled = false;
      }
    });
  startupModalQueue.enqueue(offlineDialog, 0);
}

const tutorialInvite = document.querySelector("#tutorial-invite[data-tutorial-invite]");
if (tutorialInvite) startupModalQueue.enqueue(tutorialInvite, 1);

document.addEventListener("click", (event) => {
  const closeButton = event.target.closest("[data-close-multi-select]");
  if (closeButton) {
    const dropdown = closeButton.closest(".multi-select-filter");
    if (dropdown) dropdown.open = false;
    return;
  }
  document.querySelectorAll(".multi-select-filter[open]").forEach((dropdown) => {
    if (!dropdown.contains(event.target)) dropdown.open = false;
  });
});

const formatMarketEstimate = (seconds) => {
  const safeSeconds = Math.max(0, Math.floor(seconds));
  if (safeSeconds < 60) return `${safeSeconds} s`;
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = safeSeconds % 60;
  if (minutes < 60) return remainder ? `${minutes} min ${remainder} s` : `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes ? `${hours} h ${remainingMinutes} min` : `${hours} h`;
};

function updateMarketEstimate(node) {
  const form = node.closest("form");
  const quantityInput = form?.querySelector("[data-market-quantity]");
  const quantity = quantityInput ? Number.parseInt(quantityInput.value, 10) : 1;
  if (!Number.isInteger(quantity) || quantity < 1) {
    node.textContent = "Informe a quantidade para estimar o prazo.";
    return;
  }
  const baseSeconds = Number.parseInt(node.dataset.durationBase || form?.dataset.durationBase || "30", 10);
  const reduction = Number.parseInt(node.dataset.timeReduction || form?.dataset.timeReduction || "0", 10);
  const baseTotal = Math.max(1, baseSeconds) * quantity;
  const finalSeconds = Math.max(5, Math.floor(baseTotal * (100 - Math.min(100, Math.max(0, reduction))) / 100));
  node.textContent = `Prazo estimado: ${formatMarketEstimate(finalSeconds)}.`;
}

function initializeMarketEstimates(root = document) {
  root.querySelectorAll("[data-market-estimate]").forEach((node) => updateMarketEstimate(node));
}

initializeMarketEstimates();
document.addEventListener("input", (event) => {
  if (!event.target.matches("[data-market-quantity]")) return;
  event.target.closest("form")?.querySelectorAll("[data-market-estimate]").forEach(updateMarketEstimate);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.querySelectorAll(".multi-select-filter[open]").forEach((dropdown) => { dropdown.open = false; });
  }
});

const sessionFrame = document.querySelector(".app-frame[data-session-started-at]");
if (sessionFrame) {
  const sessionStartedAt = Number(sessionFrame.dataset.sessionStartedAt) * 1000;
  const globalDuration = Number(sessionFrame.dataset.sessionGlobalSeconds || 18000) * 1000;
  const idleDuration = Number(sessionFrame.dataset.sessionIdleSeconds || 3600) * 1000;
  const heartbeatInterval = Math.min(5 * 60 * 1000, Math.max(60 * 1000, idleDuration / 4));
  let idleTimer = null;
  let lastHeartbeatAt = Date.now();

  const endSession = (reason) => window.location.assign(`/logout?reason=${reason}`);
  const scheduleIdleExpiration = () => {
    window.clearTimeout(idleTimer);
    idleTimer = window.setTimeout(() => endSession("idle"), idleDuration);
  };
  const registerActivity = () => {
    scheduleIdleExpiration();
    const now = Date.now();
    if (now - lastHeartbeatAt < heartbeatInterval) return;
    lastHeartbeatAt = now;
    fetch("/session/heartbeat", { method: "POST", credentials: "same-origin" }).then((response) => {
      if (response.status === 401) endSession("idle");
    }).catch(() => {});
  };

  ["pointerdown", "keydown", "scroll", "touchstart"].forEach((eventName) => {
    window.addEventListener(eventName, registerActivity, { passive: true });
  });
  scheduleIdleExpiration();
  const remainingGlobalTime = sessionStartedAt + globalDuration - Date.now();
  if (remainingGlobalTime <= 0) endSession("global");
  else window.setTimeout(() => endSession("global"), remainingGlobalTime);
}

updateGenericCountdowns();
setInterval(updateGenericCountdowns, 1000);
document.addEventListener("DOMContentLoaded", initializeClassGuideIndex);

function updateSalvagePreview(form) {
  const itemSelect = form.querySelector("[data-salvage-item]");
  const quantityInput = form.querySelector("[data-salvage-quantity]");
  if (!itemSelect || !quantityInput) return;
  const option = itemSelect.selectedOptions[0];
  const available = Math.max(1, Number(option?.dataset.available || 1));
  quantityInput.max = String(available);
  const quantity = Math.min(available, Math.max(1, Number(quantityInput.value || 1)));
  quantityInput.value = String(quantity);
  const unitCost = Number(form.dataset.unitCost || 0);
  const unitSeconds = Number(option?.dataset.unitSeconds || 0);
  const cost = form.querySelector("[data-salvage-cost]");
  const possibleReturn = form.querySelector("[data-salvage-return]");
  const duration = form.querySelector("[data-salvage-duration]");
  if (cost) cost.textContent = `${unitCost * quantity} ouro`;
  if (possibleReturn) possibleReturn.textContent = `${quantity}–${quantity * 3} materiais`;
  if (duration) duration.textContent = formatGenericRemaining(unitSeconds * quantity * 1000);
}

function initializeSalvagePreviews() {
  document.querySelectorAll("[data-salvage-form]").forEach(updateSalvagePreview);
}

document.addEventListener("input", (event) => {
  const form = event.target.closest?.("[data-salvage-form]");
  if (form) updateSalvagePreview(form);
});
document.addEventListener("change", (event) => {
  const form = event.target.closest?.("[data-salvage-form]");
  if (form) updateSalvagePreview(form);
});
initializeSalvagePreviews();

document.addEventListener("click", (event) => {
  const backButton = event.target.closest("[data-back-button]");
  if (!backButton) return;
  const referrer = document.referrer ? new URL(document.referrer) : null;
  const blockedPaths = new Set(["/login", "/register", "/logout"]);
  if (referrer && referrer.origin === window.location.origin && !blockedPaths.has(referrer.pathname)) {
    window.history.back();
    return;
  }
  window.location.assign("/dashboard");
});

const confirmationDialog = document.querySelector("#confirmation-dialog");

if (confirmationDialog) {
  const title = confirmationDialog.querySelector("#confirmation-title");
  const message = confirmationDialog.querySelector("#confirmation-message");
  const acceptButton = confirmationDialog.querySelector("[data-confirm-accept]");
  const cancelButtons = confirmationDialog.querySelectorAll("[data-confirm-cancel]");
  const sigil = confirmationDialog.querySelector(".confirmation-dialog__sigil");
  const skipCheckbox = confirmationDialog.querySelector("[data-confirm-skip]");
  let confirmationPreferences = {};
  try {
    confirmationPreferences = JSON.parse(document.querySelector(".app-frame")?.dataset.confirmationPreferences || "{}");
  } catch (error) {
    confirmationPreferences = {};
  }
  let pendingForm = null;
  let pendingSubmitter = null;
  const getConfirmationKey = (form) => form.dataset.confirmKey || new URL(form.action, window.location.origin).pathname.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "");

  function closeConfirmation() {
    confirmationDialog.close();
    pendingForm = null;
    pendingSubmitter = null;
  }

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.dataset.confirmMessage || form.dataset.confirmed === "true") {
      return;
    }

    const preferenceKey = getConfirmationKey(form);
    if (!form.dataset.confirmAlways && preferenceKey && confirmationPreferences[preferenceKey] === false) {
      form.dataset.confirmed = "true";
      return;
    }

    event.preventDefault();
    pendingForm = form;
    pendingSubmitter = event.submitter;
    const isDanger = form.dataset.confirmVariant === "danger";

    title.textContent = form.dataset.confirmTitle || "Confirmar ação?";
    message.textContent = form.dataset.confirmMessage;
    acceptButton.textContent = form.dataset.confirmAction || "Confirmar";
    acceptButton.classList.toggle("danger-button", isDanger);
    sigil.classList.toggle("is-danger", isDanger);
    if (skipCheckbox) skipCheckbox.checked = false;
    confirmationDialog.showModal();
    acceptButton.focus();
  });

  acceptButton.addEventListener("click", async () => {
    if (!pendingForm) {
      return;
    }

    const form = pendingForm;
    const submitter = pendingSubmitter;
    confirmationDialog.close();
    pendingForm = null;
    pendingSubmitter = null;
    const preferenceKey = getConfirmationKey(form);
    if (preferenceKey && skipCheckbox?.checked) {
      confirmationPreferences[preferenceKey] = false;
      await fetch("/session/confirmation-preferences", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ key: preferenceKey }),
      }).catch(() => {});
    }
    form.dataset.confirmed = "true";
    form.requestSubmit(submitter || undefined);
  });

  cancelButtons.forEach((button) => button.addEventListener("click", closeConfirmation));
  confirmationDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeConfirmation();
  });
  confirmationDialog.addEventListener("click", (event) => {
    if (event.target === confirmationDialog) {
      closeConfirmation();
    }
  });
}

function showActionToast(container) {
  const message = container.querySelector(".success-message, .error-message");
  if (!message) {
    return;
  }

  document.querySelectorAll(".action-toast").forEach((toast) => toast.remove());
  const toast = message.cloneNode(true);
  toast.classList.add("action-toast");
  document.body.appendChild(toast);
  window.setTimeout(() => toast.remove(), 5000);
}

window.reportGameplayClientFailure = (route, diagnosticId, phase = "client_request_failed") => {
  const target = new URL(route, window.location.origin);
  if (target.origin !== window.location.origin) return;
  const endpoint = ["click_received", "submit_started"].includes(phase)
    ? "/desktop/api/diagnostics/client-event"
    : "/desktop/api/diagnostics/client-error";
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 750);
  return fetch(endpoint, {
    method: "POST",
    credentials: "same-origin",
    signal: controller.signal,
    headers: {
      "Content-Type": "application/json",
      "X-GIM-Diagnostic-ID": diagnosticId,
    },
    body: JSON.stringify({ route: target.pathname, phase }),
  }).catch(() => {}).finally(() => window.clearTimeout(timeoutId));
};

function createGameplayDiagnosticId() {
  return window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getFormSubmitAction(form, submitter) {
  return submitter && submitter.hasAttribute("formaction")
    ? submitter.formAction
    : form.action;
}

function isGameplayDiagnosticPath(path) {
  return path === "/gathering/assign"
    || /^\/regional\/offers\/\d+\/(start|prepare|supply-quote)$/.test(path)
    || path === "/missions/start"
    || path === "/dungeons/start"
    || /^\/buildings\/\d+\/upgrade$/.test(path)
    || ["/tavern/hire-apprentice", "/tavern/hire-apprentices-bulk", "/tavern/refresh-special", "/tavern/hire-special"].includes(path);
}

document.addEventListener("click", (event) => {
  const submitter = event.target.closest('button[type="submit"], input[type="submit"], button:not([type])');
  const form = submitter?.form;
  if (!form || !form.closest(".game-shell") || (form.method || "get").toLowerCase() !== "post") return;
  const route = new URL(getFormSubmitAction(form, submitter), window.location.origin).pathname;
  if (!isGameplayDiagnosticPath(route)) return;
  const diagnosticId = createGameplayDiagnosticId();
  form.dataset.gimDiagnosticId = diagnosticId;
  window.reportGameplayClientFailure?.(route, diagnosticId, "click_received");
});

function getFormStateKey(form) {
  const actionPath = new URL(form.action, window.location.origin).pathname;
  const identity = Array.from(form.querySelectorAll('input[type="hidden"][name]'))
    .map((input) => `${input.name}=${input.value}`)
    .sort()
    .join("&");
  return `${actionPath}|${identity}`;
}

function getControlStateKey(control) {
  const valueIdentity = control instanceof HTMLInputElement && ["checkbox", "radio"].includes(control.type)
    ? `=${control.value}`
    : "";
  return `${control.tagName}:${control.name}${valueIdentity}`;
}

function captureGameFormState() {
  const state = new Map();
  document.querySelectorAll(".game-shell form").forEach((form) => {
    const formState = new Map();
    Array.from(form.elements).forEach((control) => {
      if (!(control instanceof HTMLInputElement || control instanceof HTMLSelectElement || control instanceof HTMLTextAreaElement)) return;
      if (!control.name || (control instanceof HTMLInputElement && ["hidden", "submit", "button"].includes(control.type))) return;
      formState.set(getControlStateKey(control), {
        value: control.value,
        checked: control instanceof HTMLInputElement ? control.checked : undefined,
      });
    });
    state.set(getFormStateKey(form), formState);
  });
  return state;
}

function restoreGameFormState(state) {
  document.querySelectorAll(".game-shell form").forEach((form) => {
    const formState = state.get(getFormStateKey(form));
    if (!formState) return;
    Array.from(form.elements).forEach((control) => {
      if (!(control instanceof HTMLInputElement || control instanceof HTMLSelectElement || control instanceof HTMLTextAreaElement)) return;
      const saved = formState.get(getControlStateKey(control));
      if (!saved || control.disabled) return;
      if (control instanceof HTMLInputElement && ["checkbox", "radio"].includes(control.type)) {
        control.checked = Boolean(saved.checked);
      } else if (!(control instanceof HTMLSelectElement) || Array.from(control.options).some((option) => option.value === saved.value)) {
        control.value = saved.value;
      }
    });
  });
}

function preservePageContext(responseUrl, previousUrl) {
  const target = new URL(responseUrl, window.location.origin);
  const previous = new URL(previousUrl, window.location.origin);
  if (target.pathname !== previous.pathname) return target;

  const merged = new URL(previous);
  ["message", "error", "result"].forEach((key) => merged.searchParams.delete(key));
  target.searchParams.forEach((value, key) => {
    merged.searchParams.delete(key);
    merged.searchParams.append(key, value);
  });
  merged.hash = target.hash || previous.hash;
  return merged;
}

function preserveRequestedNavigationFragment(responseUrl, requestedUrl) {
  const response = new URL(responseUrl, window.location.origin);
  const requested = new URL(requestedUrl, window.location.origin);
  if (response.origin === window.location.origin && requested.origin === response.origin && !response.hash) {
    response.hash = requested.hash;
  }
  return response.href;
}

let regionalEventTopbarObserver = null;
let regionalEventTopbarObserved = null;

function refreshRegionalEventAnchorOffset() {
  const topbar = document.querySelector(".game-topbar");
  const root = document.documentElement;
  let offset = 0;
  if (topbar) {
    const style = window.getComputedStyle(topbar);
    if (style.position === "sticky" || style.position === "fixed") {
      const top = Number.parseFloat(style.top);
      offset = Math.ceil(topbar.getBoundingClientRect().height + (Number.isFinite(top) ? Math.max(0, top) : 0));
    }
  }
  root.style.setProperty("--regional-event-sticky-topbar-height", `${offset}px`);

  if (regionalEventTopbarObserved !== topbar && regionalEventTopbarObserver) {
    if (regionalEventTopbarObserved) regionalEventTopbarObserver.unobserve(regionalEventTopbarObserved);
    regionalEventTopbarObserved = null;
  }
  if (topbar && regionalEventTopbarObserved !== topbar && typeof ResizeObserver === "function") {
    regionalEventTopbarObserver ||= new ResizeObserver(() => refreshRegionalEventAnchorOffset());
    regionalEventTopbarObserved = topbar;
    regionalEventTopbarObserver.observe(topbar);
  }
}

window.refreshRegionalEventAnchorOffset = refreshRegionalEventAnchorOffset;
window.addEventListener("resize", refreshRegionalEventAnchorOffset);
refreshRegionalEventAnchorOffset();

function syncCurrentSidebarPage(pathname) {
  const currentPath = pathname.startsWith("/regional/events")
    ? "/regional/events"
    : pathname.startsWith("/regional") ? "/regional" : pathname;
  for (const link of document.querySelectorAll(".sidebar-nav a[href]")) {
    const linkPath = new URL(link.href, window.location.origin).pathname;
    if (linkPath === currentPath) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

let guideAssetLoadPromise = null;
function initializeGameGuideForContent(parsedDocument, currentMain) {
  const guideRoot = currentMain.querySelector(".game-guide");
  if (!guideRoot) return;
  if (typeof window.initializeGameGuide === "function") {
    window.initializeGameGuide(guideRoot);
    return;
  }
  const showRecoverableError = () => {
    const catalog = guideRoot.querySelector("#equipamentos-materiais");
    const status = catalog?.querySelector("[data-guide-catalog-status]");
    const error = catalog?.querySelector("[data-guide-catalog-error]");
    if (!error) return;
    if (status) status.textContent = "";
    error.hidden = false;
    error.setAttribute("role", "alert");
    const message = error.querySelector("p");
    if (message) message.textContent = "Não foi possível iniciar os recursos do Guia. Saia e abra o Guia novamente para tentar.";
    const retry = error.querySelector("[data-guide-catalog-retry]");
    if (retry && retry.dataset.guideAssetRetryBound !== "true") {
      retry.dataset.guideAssetRetryBound = "true";
      retry.addEventListener("click", () => {
        if (document.querySelector(".game-guide") !== guideRoot) return;
        guideAssetLoadPromise = null;
        error.hidden = true;
        initializeGameGuideForContent(parsedDocument, currentMain);
      });
    }
  };
  const scriptSrcFor = (expectedPath) => {
    for (const script of parsedDocument.querySelectorAll("script[src]")) {
      const rawSrc = script.getAttribute("src");
      if (!rawSrc) continue;
      let candidate;
      try {
        candidate = new URL(rawSrc, window.location.origin);
      } catch {
        continue;
      }
      if ((candidate.protocol !== "http:" && candidate.protocol !== "https:")
          || candidate.origin !== window.location.origin
          || candidate.username || candidate.password
          || candidate.pathname !== expectedPath || candidate.hash) continue;
      return candidate.href;
    }
    return null;
  };
  const utilitySrc = scriptSrcFor("/static/js/guide-utils.js");
  const guideSrc = scriptSrcFor("/static/js/guide.js");
  if (!utilitySrc || !guideSrc) {
    showRecoverableError();
    return;
  }
  const loadScript = (src) => new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.addEventListener("load", resolve, { once: true });
    script.addEventListener("error", reject, { once: true });
    document.head.append(script);
  });
  guideAssetLoadPromise ||= loadScript(utilitySrc)
    .then(() => loadScript(guideSrc))
    .catch((error) => {
      guideAssetLoadPromise = null;
      throw error;
    });
  void guideAssetLoadPromise.then(() => {
    if (document.querySelector(".game-guide") === guideRoot) {
      window.initializeGameGuide?.(guideRoot);
    }
  }).catch((error) => {
    if (document.querySelector(".game-guide") === guideRoot) showRecoverableError();
    console.error("Não foi possível inicializar o Guia após a navegação.", error);
  });
}

function replaceGameContent(html, responseUrl, previousPath, scrollPosition, updateTopbar, formState, scrollToTop = false) {
  const parsedDocument = new DOMParser().parseFromString(html, "text/html");
  const nextUrl = new URL(responseUrl, window.location.origin);
  const incomingMain = parsedDocument.querySelector(".game-shell");
  const currentMain = document.querySelector(".game-shell");
  if (!incomingMain || !currentMain) {
    if (scrollToTop) window.scrollTo({ top: 0, behavior: "auto" });
    window.location.assign(responseUrl);
    return;
  }

  currentMain.innerHTML = incomingMain.innerHTML;
  initializeGameGuideForContent(parsedDocument, currentMain);
  window.initializeEquipmentDetails?.(currentMain);
  window.initializeBuildingResetDialogs?.(currentMain);
  initializeMarketEstimates(currentMain);
  syncRegionalEventNoticeDialogs(parsedDocument, Boolean(nextUrl.hash));
  window.initializeGatheringCycles?.();
  const incomingTopbar = parsedDocument.querySelector(".game-topbar");
  const currentTopbar = document.querySelector(".game-topbar");
  if (updateTopbar && incomingTopbar && currentTopbar) {
    currentTopbar.innerHTML = incomingTopbar.innerHTML;
  }
  window.refreshRegionalEventAnchorOffset?.();

  document.title = parsedDocument.title || document.title;
  document.body.dataset.route = nextUrl.pathname;
  syncCurrentSidebarPage(nextUrl.pathname);
  window.GIMApplyDesktopArt?.(currentMain);
  window.history.replaceState({}, "", `${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`);
  updateGenericCountdowns();
  initializeSalvagePreviews();
  restoreGameFormState(formState);
  window.initializeRegionalSupply?.(currentMain);
  window.initializeRegionalComparison?.(currentMain);
  showActionToast(currentMain);
  refreshNavigationWorkIndicators(true);

  const targetScroll = scrollToTop ? 0 : nextUrl.pathname === previousPath ? scrollPosition : 0;
  window.requestAnimationFrame(() => {
    let hashTarget = null;
    if (nextUrl.hash) {
      try {
        hashTarget = document.getElementById(decodeURIComponent(nextUrl.hash.slice(1)));
      } catch {
        hashTarget = null;
      }
    }
    if (hashTarget) {
      hashTarget.focus?.({ preventScroll: true });
      hashTarget.scrollIntoView({ block: "start", behavior: "auto" });
      return;
    }
    const maximumScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    window.scrollTo({ top: Math.min(targetScroll, maximumScroll), behavior: "auto" });
  });
}

function regionalNoticeMatches(current, replacement) {
  return current.dataset.eventId === replacement.dataset.eventId
    && current.dataset.eventDeadline === replacement.dataset.eventDeadline;
}
window.GIMRegionalNoticeMatches = regionalNoticeMatches;

function syncRegionalEventNoticeDialogs(parsedDocument, suppressAutoOpen = false) {
  const modalQueue = window.GIMStartupModalQueue;
  if (suppressAutoOpen) {
    for (const current of document.querySelectorAll("dialog[data-regional-event-notice]")) {
      current.dataset.regionalNoticeProgrammaticClose = "true";
      modalQueue?.remove(current);
      if (current.open) current.close();
      current.remove();
    }
    return;
  }
  modalQueue?.beginBatch?.();
  try {
    const incoming = [...parsedDocument.querySelectorAll("dialog[data-regional-event-notice]")];
    const incomingById = new Map(incoming.filter((dialog) => dialog.id).map((dialog) => [dialog.id, dialog]));
    for (const current of document.querySelectorAll("dialog[data-regional-event-notice]")) {
      const replacement = incomingById.get(current.id);
      if (replacement && regionalNoticeMatches(current, replacement)) continue;
      current.dataset.regionalNoticeProgrammaticClose = "true";
      modalQueue?.remove(current);
      if (current.open) current.close();
      current.remove();
    }
    for (const source of incoming) {
      if (source.id && document.getElementById(source.id)) continue;
      const dialog = document.importNode(source, true);
      document.body.append(dialog);
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
      });
      window.GIMEnqueueRegionalNotice?.(dialog);
    }
  } finally {
    modalQueue?.endBatch?.();
  }
}

let regionalComparisonInterval = null;
function initializeRegionalComparison(root = document) {
  if (regionalComparisonInterval !== null) {
    window.clearInterval(regionalComparisonInterval);
    regionalComparisonInterval = null;
  }
  const tableBody = root.querySelector?.("[data-regional-comparison]");
  if (!tableBody) return;
  const refresh = async () => {
    if (!tableBody.isConnected || document.visibilityState === "hidden") return;
    try {
      const response = await fetch(tableBody.dataset.refreshUrl, { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) return;
      const payload = await response.json();
      for (const row of tableBody.querySelectorAll("tr[data-guild-state-id]")) {
        const data = payload.guilds?.[row.dataset.guildStateId];
        if (!data) continue;
        const values = {
          wealth: data.wealth,
          roster: data.roster,
          tiers: Object.entries(data.tier_counts || {}).sort(([left], [right]) => left.localeCompare(right)).map(([tier, count]) => `${tier} ${count}`).join(" · ") || "—",
          contracts: data.results?.contracts ?? 0,
          dungeons: data.results?.dungeons ?? 0,
          bosses: data.results?.bosses ?? 0,
          "successes-failures": `${data.results?.successes ?? 0} · ${data.results?.failures ?? 0}`,
          "event-wins": data.event_wins ?? 0,
        };
        for (const [field, value] of Object.entries(values)) {
          const cell = row.querySelector(`[data-comparison-field="${field}"]`);
          if (cell) cell.textContent = String(value);
        }
      }
    } catch (_error) {
      // Keep the last successful comparison visible when a refresh is unavailable.
    }
  };
  refresh();
  regionalComparisonInterval = window.setInterval(() => {
    if (!tableBody.isConnected) return;
    refresh();
  }, 30000);
}
window.initializeRegionalComparison = initializeRegionalComparison;
initializeRegionalComparison();

document.addEventListener("click", async (event) => {
  if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
    const noticeLink = event.target.closest("[data-regional-notice-close]");
    if (noticeLink) {
      const dialog = noticeLink.closest("dialog[data-regional-event-notice]");
      if (dialog) dialog.dataset.regionalNoticeProgrammaticClose = "true";
      noticeLink.closest("dialog")?.close();
    }
  }
  const link = event.target.closest(".game-shell .filter-tabs a, .game-shell .pagination a, [data-async-navigation]");
  if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  const targetUrl = new URL(link.href, window.location.origin);
  if (targetUrl.origin !== window.location.origin) return;

  event.preventDefault();
  const previousPath = window.location.pathname;
  const scrollPosition = window.scrollY;
  const scrollToTop = link.hasAttribute("data-scroll-top");
  const formState = captureGameFormState();
  link.setAttribute("aria-busy", "true");
  try {
    const response = await fetch(targetUrl, {
      method: "GET",
      credentials: "same-origin",
      headers: { "Accept": "text/html", "X-Requested-With": "fetch" },
    });
    if (!response.ok) throw new Error("Falha ao atualizar a tela");
    replaceGameContent(
      await response.text(),
      preserveRequestedNavigationFragment(response.url || targetUrl.href, targetUrl.href),
      previousPath,
      scrollPosition,
      true,
      formState,
      scrollToTop,
    );
  } catch (error) {
    if (scrollToTop) window.scrollTo({ top: 0, behavior: "auto" });
    window.location.assign(targetUrl);
  }
});

window.addEventListener("pageshow", () => {
  if (!new Set(["/regional", "/regional/events"]).has(document.body.dataset.route) || window.location.hash) return;
  window.requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: "auto" }));
});

async function fetchTavernStateAfterUncertainAction(previousUrl) {
  try {
    const refreshed = await fetch(previousUrl, {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Accept": "text/html", "X-Requested-With": "fetch" },
    });
    if (!refreshed.ok) return null;
    return {
      html: await refreshed.text(),
      url: refreshed.url || previousUrl,
    };
  } catch (_refreshError) {
    return null;
  }
}

function lockTavernActionsUntilReload(form, submitter, previousUrl) {
  document.querySelectorAll("[data-tavern-candidate-price-mutation] button[type='submit']")
    .forEach((button) => { button.disabled = true; });
  if (submitter instanceof HTMLElement) {
    submitter.disabled = true;
    submitter.classList.remove("is-loading");
    submitter.textContent = "Aguardando atualização";
  }
  let status = form.querySelector("[data-apprentice-search-status]");
  if (!status) {
    status = document.createElement("p");
    status.dataset.apprenticeSearchStatus = "true";
    form.append(status);
  }
  status.setAttribute("role", "alert");
  status.setAttribute("aria-live", "assertive");
  const reloadLink = document.createElement("a");
  reloadLink.href = previousUrl;
  reloadLink.textContent = "Recarregar estado";
  reloadLink.className = "button-link secondary";
  status.replaceChildren(
    document.createTextNode("Não foi possível confirmar o resultado da busca. As ações de contratação e preço estão bloqueadas até sincronizar o candidato. "),
    reloadLink,
  );
}

document.addEventListener("submit", async (event) => {
  if (event.defaultPrevented) return;
  const form = event.target;
  const method = form instanceof HTMLFormElement ? form.method.toLowerCase() : "";
  if (
    !(form instanceof HTMLFormElement)
    || !["get", "post"].includes(method)
    || form.dataset.nativeSubmit === "true"
    || !form.closest(".game-shell")
  ) {
    return;
  }
  if (form.dataset.confirmMessage && form.dataset.confirmed !== "true") {
    return;
  }

  delete form.dataset.confirmed;
  event.preventDefault();
  const submitter = event.submitter;
  const formData = new FormData(form);
  if (submitter && submitter.name) {
    formData.append(submitter.name, submitter.value);
  }

  const previousUrl = window.location.href;
  const previousPath = window.location.pathname;
  const scrollPosition = window.scrollY;
  const formState = captureGameFormState();
  const originalSubmitterText = submitter instanceof HTMLElement ? submitter.textContent : null;
  const pendingLabel = submitter instanceof HTMLElement ? submitter.dataset.pendingLabel : "";
  const diagnosticId = form.dataset.gimDiagnosticId || createGameplayDiagnosticId();
  delete form.dataset.gimDiagnosticId;
  form.setAttribute("aria-busy", "true");
  if (submitter) {
    submitter.disabled = true;
    submitter.classList.add("is-loading");
    if (pendingLabel) submitter.textContent = pendingLabel;
  }
  const submitStatus = form.querySelector("[data-apprentice-search-status]");
  if (submitStatus) {
    submitStatus.textContent = "Buscando outro Aprendiz…";
  }
  try {
    if (method === "post") {
      window.reportGameplayClientFailure?.(getFormSubmitAction(form, submitter), diagnosticId, "submit_started");
    }
    const requestUrl = new URL(getFormSubmitAction(form, submitter), window.location.origin);
    const requestOptions = {
      method: method.toUpperCase(),
      credentials: "same-origin",
      headers: {
        "Accept": "text/html",
        "X-Requested-With": "fetch",
        "X-GIM-Diagnostic-ID": diagnosticId,
      },
    };
    if (method === "get") {
      requestUrl.search = new URLSearchParams(formData).toString();
    } else {
      requestOptions.body = new URLSearchParams(formData);
    }
    const response = await fetch(requestUrl, requestOptions);
    let html = await response.text();
    let responseUrl = response.url || window.location.href;
    const contextualUrl = method === "post"
      ? preservePageContext(responseUrl, previousUrl)
      : new URL(response.url, window.location.origin);
    if (contextualUrl.href !== responseUrl) {
      const contextualResponse = await fetch(contextualUrl, {
        method: "GET",
        credentials: "same-origin",
        headers: { "Accept": "text/html", "X-Requested-With": "fetch" },
      });
      if (contextualResponse.ok) {
        html = await contextualResponse.text();
        responseUrl = contextualResponse.url;
      }
    }
    replaceGameContent(html, responseUrl, previousPath, scrollPosition, response.ok, formState);
  } catch (error) {
    form.removeAttribute("aria-busy");
    const needsTavernRevalidation = form.dataset.revalidateOnError === "true";
    if (submitter && !needsTavernRevalidation) {
      submitter.disabled = false;
      submitter.classList.remove("is-loading");
      if (originalSubmitterText !== null) submitter.textContent = originalSubmitterText;
    }
    if (needsTavernRevalidation) {
      const refreshed = await fetchTavernStateAfterUncertainAction(previousUrl);
      if (refreshed) {
        replaceGameContent(
          refreshed.html,
          refreshed.url,
          previousPath,
          scrollPosition,
          true,
          formState,
        );
        const refreshedStatus = document.querySelector("[data-apprentice-search-status]");
        if (refreshedStatus) {
          refreshedStatus.textContent = "A Taverna foi sincronizada. Confira o candidato e o preço antes de agir novamente.";
        }
      } else {
        window.reportGameplayClientFailure?.(getFormSubmitAction(form, submitter), diagnosticId);
        lockTavernActionsUntilReload(form, submitter, previousUrl);
      }
      return;
    }
    form.querySelector("[data-client-action-error]")?.remove();
    window.reportGameplayClientFailure?.(getFormSubmitAction(form, submitter), diagnosticId);
    const notice = document.createElement("p");
    notice.className = "form-error";
    notice.setAttribute("role", "alert");
    notice.dataset.clientActionError = "true";
    notice.textContent = `Não foi possível confirmar a ação. Tente novamente e informe a referência ${diagnosticId}.`;
    form.prepend(notice);
  }
});

let draggedSortableItem = null;

document.addEventListener("dragstart", (event) => {
  const item = event.target.closest("[data-sortable-item]");
  if (!item) {
    return;
  }
  draggedSortableItem = item;
  item.classList.add("is-dragging");
  event.dataTransfer.effectAllowed = "move";
});

document.addEventListener("dragover", (event) => {
  const list = event.target.closest("[data-sortable-list]");
  if (!list || !draggedSortableItem || draggedSortableItem.parentElement !== list) {
    return;
  }
  event.preventDefault();
  const target = event.target.closest("[data-sortable-item]");
  if (!target || target === draggedSortableItem) {
    return;
  }
  const targetBox = target.getBoundingClientRect();
  const insertAfter = event.clientY > targetBox.top + targetBox.height / 2;
  list.insertBefore(draggedSortableItem, insertAfter ? target.nextSibling : target);
});

document.addEventListener("dragend", () => {
  if (draggedSortableItem) {
    draggedSortableItem.classList.remove("is-dragging");
  }
  draggedSortableItem = null;
});

document.addEventListener("click", (event) => {
  const moveButton = event.target.closest("[data-move-up], [data-move-down]");
  if (!moveButton) {
    return;
  }
  const item = moveButton.closest("[data-sortable-item]");
  if (!item) {
    return;
  }
  if (moveButton.matches("[data-move-up]") && item.previousElementSibling) {
    item.parentElement.insertBefore(item, item.previousElementSibling);
  }
  if (moveButton.matches("[data-move-down]") && item.nextElementSibling) {
    item.parentElement.insertBefore(item.nextElementSibling, item);
  }
});
