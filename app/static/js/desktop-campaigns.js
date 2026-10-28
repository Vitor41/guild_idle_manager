(() => {
  const message = document.getElementById("status-message");

  function showMessage(value, isError = false) {
    message.textContent = value || "";
    message.classList.toggle("error", isError);
  }

  async function request(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "A operação não foi concluída.");
    return result;
  }

  async function nativeCall(name, ...args) {
    if (!window.pywebview?.api?.[name]) throw new Error("Esta ação exige a janela desktop do Guild Idle Manager.");
    const result = await window.pywebview.api[name](...args);
    if (result?.error) throw new Error(result.error);
    if (result?.cancelled) return result;
    return result;
  }

  function ask({ title, message: detail, input = false, value = "", confirmText = "Confirmar", danger = false }) {
    const dialog = document.getElementById("action-dialog");
    const form = dialog.querySelector("form");
    const field = dialog.querySelector("input");
    dialog.querySelector("h2").textContent = title;
    dialog.querySelector(".dialog-message").textContent = detail;
    dialog.querySelector("label").hidden = !input;
    field.hidden = !input;
    field.required = input;
    field.value = value;
    dialog.querySelector(".dialog-confirm").textContent = confirmText;
    dialog.querySelector(".dialog-confirm").classList.toggle("danger", danger);
    dialog.showModal();
    if (input) field.focus();
    return new Promise((resolve) => {
      dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm" ? (input ? field.value.trim() : true) : null), { once: true });
      form.addEventListener("submit", (event) => {
        if (event.submitter?.value === "confirm" && input && !field.reportValidity()) event.preventDefault();
      }, { once: true });
    });
  }

  document.getElementById("create-campaign-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      showMessage("Preparando a campanha...");
      const result = await request("/desktop/api/campaigns", {
        method: "POST",
        body: JSON.stringify({ guild_name: form.get("guild_name") }),
      });
      window.location.assign(result.redirect);
    } catch (error) { showMessage(error.message, true); }
  });

  document.getElementById("import-campaign").addEventListener("click", async () => {
    try {
      const result = await nativeCall("import_campaign");
      if (!result.cancelled) {
        showMessage(result.message || "Campanha importada.");
        window.location.reload();
      }
    } catch (error) { showMessage(error.message, true); }
  });

  document.querySelectorAll(".campaign-card").forEach((card) => {
    const id = card.dataset.campaignId;
    card.querySelector(".open-campaign").addEventListener("click", async () => {
      try {
        showMessage("Validando e abrindo a campanha...");
        const result = await request(`/desktop/api/campaigns/${id}/open`, { method: "POST", body: "{}" });
        if (result.offline_summary?.warning) sessionStorage.setItem("gim-offline-warning", result.offline_summary.warning);
        window.location.assign(result.redirect);
      } catch (error) { showMessage(error.message, true); }
    });
    card.querySelector(".rename-campaign").addEventListener("click", async () => {
      const name = await ask({ title: "Renomear guilda", message: "Escolha um novo nome para sua guilda.", input: true, value: card.querySelector("h3").textContent });
      if (name === null) return;
      try {
        const result = await request(`/desktop/api/campaigns/${id}`, { method: "PATCH", body: JSON.stringify({ guild_name: name }) });
        card.querySelector("h3").textContent = result.guild_name;
      } catch (error) { showMessage(error.message, true); }
    });
    card.querySelector(".backup-campaign").addEventListener("click", async () => {
      try {
        const result = await request(`/desktop/api/campaigns/${id}/backup`, { method: "POST", body: "{}" });
        showMessage(`${result.message} ${result.backup_name}`);
      } catch (error) { showMessage(error.message, true); }
    });
    card.querySelector(".export-campaign").addEventListener("click", async () => {
      try {
        let result = await nativeCall("export_campaign", id);
        if (result.needs_confirmation) {
          if (!await ask({ title: "Substituir arquivo?", message: "Já existe um arquivo neste local. Deseja substituí-lo pela exportação atual?", confirmText: "Substituir" })) return;
          result = await nativeCall("confirm_export", result.confirmation_token, true);
        }
        if (!result.cancelled) showMessage(result.message || "Campanha exportada.");
      } catch (error) { showMessage(error.message, true); }
    });
    card.querySelector(".restore-campaign").addEventListener("click", async () => {
      if (!await ask({ title: "Restaurar cópia de segurança", message: "O progresso atual será substituído. Uma cópia de segurança será criada antes da restauração. Continuar?", confirmText: "Restaurar" })) return;
      try {
        const result = await nativeCall("restore_backup", id);
        if (!result.cancelled) showMessage(result.message || "Cópia de segurança restaurada.");
      } catch (error) { showMessage(error.message, true); }
    });
    card.querySelector(".delete-campaign").addEventListener("click", async () => {
      if (!await ask({ title: "Excluir campanha", message: "Uma cópia de segurança será mantida fora da pasta do aplicativo. Deseja excluir esta campanha?", confirmText: "Excluir", danger: true })) return;
      try {
        const result = await request(`/desktop/api/campaigns/${id}`, { method: "DELETE" });
        showMessage(`${result.message} Cópia: ${result.backup_name}`);
        card.remove();
      } catch (error) { showMessage(error.message, true); }
    });
  });

  document.querySelectorAll(".restore-unavailable").forEach((button) => {
    button.addEventListener("click", async () => {
      const confirmed = await ask({ title: "Recuperar campanha", message: "O arquivo atual será preservado para diagnóstico e substituído pela cópia de segurança selecionada, se ela pertencer a esta campanha.", confirmText: "Selecionar cópia" });
      if (!confirmed) return;
      try {
        const result = await nativeCall("restore_backup", button.dataset.campaignId);
        if (!result.cancelled) {
          showMessage(result.message || "Campanha recuperada.");
          window.location.reload();
        }
      } catch (error) { showMessage(error.message, true); }
    });
  });
})();
