document.addEventListener("click", (event) => {
  const link = event.target.closest("a[href]");
  if (!link) return;
  const destination = new URL(link.href, window.location.href);
  if (destination.origin !== window.location.origin) {
    event.preventDefault();
    event.stopPropagation();
  }
}, true);

const offlineWarning = sessionStorage.getItem("gim-offline-warning");
if (offlineWarning) {
  sessionStorage.removeItem("gim-offline-warning");
  const notice = document.createElement("p");
  notice.className = "desktop-clock-warning";
  notice.setAttribute("role", "alert");
  notice.textContent = offlineWarning;
  document.querySelector(".page-shell")?.prepend(notice);
}
