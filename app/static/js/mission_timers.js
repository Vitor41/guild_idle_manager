function secondsRemaining(endsAt) {
  const raw = endsAt || "";
  const deadline = window.parseUtcTimestamp ? window.parseUtcTimestamp(raw) : Date.parse(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw) ? raw : `${raw}Z`);
  return Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
}

function formatRemaining(seconds) {
  if (seconds <= 0) {
    return "Concluida";
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function updateMissionTimers() {
  document.querySelectorAll(".mission-timer").forEach((timer) => {
    const remaining = secondsRemaining(timer.dataset.endsAt);
    timer.textContent = formatRemaining(remaining);
  });

  document.querySelectorAll(".claim-button").forEach((button) => {
    const remaining = secondsRemaining(button.dataset.endsAt);
    if (remaining <= 0) {
      button.disabled = false;
    }
  });
}

updateMissionTimers();
setInterval(updateMissionTimers, 1000);
