document.addEventListener("click", (event) => {
  const link = event.target.closest("a[href]");
  if (!link) return;
  const destination = new URL(link.href, window.location.href);
  if (destination.origin !== window.location.origin) {
    event.preventDefault();
    event.stopPropagation();
  }
}, true);

const compactNavigation = document.querySelector(".compact-navigation");
const compactNavigationBreakpoint = window.matchMedia("(max-width: 980px)");
const syncCompactNavigation = () => {
  if (compactNavigation) compactNavigation.open = !compactNavigationBreakpoint.matches;
};
syncCompactNavigation();
compactNavigationBreakpoint.addEventListener("change", syncCompactNavigation);

document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;
  const destination = new URL(form.action, window.location.href);
  const isCampaignReturn = destination.pathname === "/desktop/return-to-campaigns";
  const isTutorialInvitation = form.closest("#tutorial-invite")
    && ["/tutorial/start", "/tutorial/decline"].includes(destination.pathname);
  if (destination.origin !== window.location.origin || (!isCampaignReturn && !isTutorialInvitation)) return;

  event.preventDefault();
  const submitButton = form.querySelector('button[type="submit"]');
  if (submitButton) submitButton.disabled = true;
  try {
    const response = await fetch(destination.href, {
      method: "POST",
      credentials: "same-origin",
      mode: "same-origin",
      redirect: "follow",
    });
    const result = new URL(response.url);
    const expectedPath = isCampaignReturn
      ? "/desktop/campaigns"
      : destination.pathname === "/tutorial/start" ? "/tutorial" : "/dashboard";
    if (!response.ok || result.origin !== window.location.origin || result.pathname !== expectedPath) {
      throw new Error("O servidor não confirmou a ação local.");
    }
    window.location.assign(result.href);
  } catch (error) {
    if (submitButton) submitButton.disabled = false;
    const notice = document.createElement("p");
    notice.className = "desktop-clock-warning";
    notice.setAttribute("role", "alert");
    notice.textContent = error.message || "Não foi possível voltar ao menu de campanhas.";
    document.querySelector(".page-shell")?.prepend(notice);
  }
});

const offlineWarning = sessionStorage.getItem("gim-offline-warning");
if (offlineWarning) {
  sessionStorage.removeItem("gim-offline-warning");
  const notice = document.createElement("p");
  notice.className = "desktop-clock-warning";
  notice.setAttribute("role", "alert");
  notice.textContent = offlineWarning;
  document.querySelector(".page-shell")?.prepend(notice);
}
