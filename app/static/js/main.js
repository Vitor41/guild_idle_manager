const startupModalQueue = (() => {
  const pending = [];
  let active = null;
  let sequence = 0;
  const advance = () => {
    if (active?.open) return;
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
    enqueue(dialog, priority) {
      if (!(dialog instanceof HTMLDialogElement) || dialog.open || pending.some((row) => row.dialog === dialog)) return;
      pending.push({ dialog, priority, sequence: sequence++ });
      pending.sort((left, right) => left.priority - right.priority || left.sequence - right.sequence);
      advance();
    },
  };
})();
window.GIMStartupModalQueue = startupModalQueue;

function formatGenericRemaining(ms) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function updateGenericCountdowns() {
  document.querySelectorAll("[data-ends-at]").forEach((element) => {
    const endsAt = new Date(element.dataset.endsAt);
    const remaining = endsAt.getTime() - Date.now();
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
    if (preferenceKey && confirmationPreferences[preferenceKey] === false) {
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

function replaceGameContent(html, responseUrl, previousPath, scrollPosition, updateTopbar, formState, scrollToTop = false) {
  const parsedDocument = new DOMParser().parseFromString(html, "text/html");
  const incomingMain = parsedDocument.querySelector(".game-shell");
  const currentMain = document.querySelector(".game-shell");
  if (!incomingMain || !currentMain) {
    if (scrollToTop) window.scrollTo({ top: 0, behavior: "auto" });
    window.location.assign(responseUrl);
    return;
  }

  currentMain.innerHTML = incomingMain.innerHTML;
  window.initializeGatheringCycles?.();
  const incomingTopbar = parsedDocument.querySelector(".game-topbar");
  const currentTopbar = document.querySelector(".game-topbar");
  if (updateTopbar && incomingTopbar && currentTopbar) {
    currentTopbar.innerHTML = incomingTopbar.innerHTML;
  }

  document.title = parsedDocument.title || document.title;
  const nextUrl = new URL(responseUrl, window.location.origin);
  document.body.dataset.route = nextUrl.pathname;
  window.history.replaceState({}, "", `${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`);
  updateGenericCountdowns();
  initializeSalvagePreviews();
  restoreGameFormState(formState);
  showActionToast(currentMain);

  const targetScroll = scrollToTop ? 0 : nextUrl.pathname === previousPath ? scrollPosition : 0;
  window.requestAnimationFrame(() => {
    const maximumScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    window.scrollTo({ top: Math.min(targetScroll, maximumScroll), behavior: "auto" });
  });
}

document.addEventListener("click", async (event) => {
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
      response.url,
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
  if (document.body.dataset.route !== "/regional" || window.location.hash) return;
  window.requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: "auto" }));
});

document.addEventListener("submit", async (event) => {
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
  form.setAttribute("aria-busy", "true");
  if (submitter) {
    submitter.disabled = true;
    submitter.classList.add("is-loading");
  }

  try {
    const requestUrl = new URL(submitter?.formAction || form.action, window.location.origin);
    const requestOptions = {
      method: method.toUpperCase(),
      credentials: "same-origin",
      headers: { "Accept": "text/html", "X-Requested-With": "fetch" },
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
    if (submitter) {
      submitter.disabled = false;
      submitter.classList.remove("is-loading");
    }
    form.submit();
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
