const mockPages = [
  ["campaigns", "Campanhas e coleta", "evolution-campaigns.html", "gathering-kit.png"],
  ["vigilia", "Vigília Regional", "evolution-vigilia.html", "vigil-tower.png"],
  ["events", "Portais e rebeliões", "evolution-events.html", "portal-gate.png"],
  ["offline", "Retorno offline", "evolution-offline.html", "vigil-tower.png"],
  ["codex", "Conquistas e Códex", "evolution-codex.html", "achievement-medal.png"],
];

const currentMock = document.body.dataset.mockPage;
const dialogTriggers = new WeakMap();
document.querySelectorAll(".mock-footer").forEach((footer) => {
  footer.append(document.createTextNode(" · Interações locais demonstrativas: nada é salvo e nenhuma regra do backend é executada."));
});
const nav = document.querySelector("[data-mock-nav]");
if (nav) {
  const brand = document.createElement("a");
  brand.className = "brand";
  brand.href = "evolution.html";
  brand.innerHTML = '<img src="../../app/static/assets/desktop/sprites/64/guild-sigil.png" alt=""><span><strong>GUILD IDLE</strong><small>MANAGER · DA</small></span>';
  const links = document.createElement("nav");
  links.setAttribute("aria-label", "Telas da evolução");
  const label = document.createElement("span");
  label.className = "nav-label";
  label.textContent = "FLUXOS DA CAMPANHA";
  links.append(label);
  for (const [key, title, href, icon] of mockPages) {
    const link = document.createElement("a");
    link.href = href;
    if (key === currentMock) link.setAttribute("aria-current", "page");
    const image = document.createElement("img");
    image.src = `../../app/static/assets/desktop/evolution/sprites/ui_64/${icon}`;
    image.alt = "";
    link.append(image, document.createTextNode(title));
    links.append(link);
  }
  const overview = document.createElement("a");
  overview.href = "evolution.html";
  overview.textContent = "Visão geral da arte";
  overview.className = "mock-overview-link";
  nav.replaceChildren(brand, links, overview);
}

document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-dialog]");
  if (trigger) {
    const dialog = document.getElementById(trigger.dataset.dialog);
    if (dialog instanceof HTMLDialogElement) {
      dialogTriggers.set(dialog, trigger);
      dialog.showModal();
      dialog.querySelector("[data-initial-focus], .button.primary, .close")?.focus();
    }
  }
  const viewport = event.target.closest("[data-toggle-viewport]");
  if (viewport) {
    const narrow = document.body.classList.toggle("mock-narrow");
    viewport.setAttribute("aria-pressed", String(narrow));
    viewport.textContent = narrow ? "Ver largura desktop" : "Ver janela estreita";
  }
  const filter = event.target.closest("[data-filter]");
  if (filter) {
    const group = filter.closest("[data-filter-group]");
    const chosen = filter.dataset.filter;
    group?.querySelectorAll("[data-filter]").forEach((item) => item.setAttribute("aria-pressed", String(item === filter)));
    document.querySelectorAll("[data-track]").forEach((card) => {
      card.hidden = chosen !== "all" && card.dataset.track !== chosen;
    });
  }
  const codexFilter = event.target.closest("[data-codex-filter]");
  if (codexFilter) {
    const group = codexFilter.closest("[data-codex-filter-group]");
    const chosen = codexFilter.dataset.codexFilter;
    group?.querySelectorAll("[data-codex-filter]").forEach((item) => item.setAttribute("aria-pressed", String(item === codexFilter)));
    document.querySelectorAll("[data-codex-category]").forEach((card) => {
      card.hidden = chosen !== "all" && card.dataset.codexCategory !== chosen;
    });
  }
  const demoClaim = event.target.closest("[data-demo-claim]");
  if (demoClaim) {
    const card = document.querySelector("[data-claim-card]");
    const status = card?.querySelector(".status");
    if (status) {
      status.className = "status claimed";
      status.textContent = "Resgatada · prévia";
    }
    card?.querySelector("[data-dialog]")?.remove();
  }
  const demoState = event.target.closest("[data-demo-state]");
  if (demoState) {
    const target = document.getElementById(demoState.dataset.demoTarget);
    const label = target?.querySelector("[data-demo-status]");
    const detail = target?.querySelector("[data-demo-detail]");
    if (label) {
      label.className = `status ${demoState.dataset.demoTone || "active"}`;
      label.textContent = demoState.dataset.demoState;
    }
    if (detail) detail.textContent = demoState.dataset.demoDescription || "Estado alterado apenas nesta prévia; nenhum dado foi salvo.";
    target?.scrollIntoView({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }
  const offlineConfirm = event.target.closest("[data-demo-offline-confirm]");
  if (offlineConfirm) {
    const status = document.querySelector("[data-offline-status]");
    const detail = document.querySelector("[data-offline-detail]");
    if (status) { status.className = "status claimed"; status.textContent = "Leitura confirmada nesta prévia"; }
    if (detail) detail.textContent = "Confirmação visual local. Recarregar a página restaura o exemplo pendente; nada foi persistido.";
  }
});

document.addEventListener("change", (event) => {
  const supply = event.target.closest("[data-demo-supply]");
  if (!supply) return;
  const container = supply.closest(".mock-supply");
  const chance = container?.querySelector("[data-demo-supply-chance]");
  const feedback = container?.querySelector("[data-demo-supply-feedback]");
  if (chance) chance.textContent = `Chance nesta prévia: ${supply.checked ? 87 : 82}%`;
  if (feedback) feedback.textContent = supply.checked
    ? "Suprimento selecionado: custo mostrado acima. Este mock não consome recursos nem inicia a expedição."
    : "Sem suprimento selecionado; nenhum recurso será gasto nesta prévia.";
  container?.classList.toggle("is-selected", supply.checked);
});

document.querySelectorAll("dialog").forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener("close", () => {
    dialogTriggers.get(dialog)?.focus();
  });
});

const initialDialog = document.querySelector("dialog[data-demo-open]");
if (initialDialog instanceof HTMLDialogElement) {
  const reopen = document.querySelector(`[data-dialog="${initialDialog.id}"]`);
  if (reopen) dialogTriggers.set(initialDialog, reopen);
  initialDialog.showModal();
  initialDialog.querySelector("[data-initial-focus], .button.primary, .close")?.focus();
}
