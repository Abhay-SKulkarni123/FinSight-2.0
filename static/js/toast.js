/* ==========================================================================
   FinSight Toast Notifications
   Extracted from base.html inline script. Loaded once, used everywhere.
   ========================================================================== */

(function () {
  const ICONS = {
    success:
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M5 13l4 4L19 7"/></svg>',
    error:
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    info: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 8v.01M12 11v5"/></svg>',
    warning:
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M12 9v4m0 4h.01M10.3 3.9L2.5 17a1.5 1.5 0 001.3 2.2h16.4a1.5 1.5 0 001.3-2.2L13.7 3.9a1.5 1.5 0 00-2.6 0z"/></svg>',
  };

  function showToast(title, message, type, duration) {
    type = type || "info";
    duration = duration || 4000;

    const container = document.getElementById("toastContainer");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.setAttribute("role", "status");

    const iconWrap = document.createElement("div");
    iconWrap.style.cssText = "display:flex; gap:10px; align-items:flex-start;";
    iconWrap.innerHTML = ICONS[type] || ICONS.info;

    const content = document.createElement("div");
    content.style.flex = "1";

    const titleEl = document.createElement("div");
    titleEl.style.cssText = "font-weight:600; margin-bottom:2px;";
    titleEl.textContent = title || "";

    const messageEl = document.createElement("div");
    messageEl.style.cssText = "color:var(--muted); font-size: var(--text-xs);";
    messageEl.textContent = message || "";

    content.appendChild(titleEl);
    content.appendChild(messageEl);

    const closeBtn = document.createElement("button");
    closeBtn.setAttribute("aria-label", "Dismiss notification");
    closeBtn.style.cssText =
      "background:none; border:none; color:var(--muted); cursor:pointer; font-size:16px; padding:0; margin-left:8px;";
    closeBtn.textContent = "\u00d7";
    closeBtn.addEventListener("click", () => toast.remove());

    iconWrap.appendChild(content);
    iconWrap.appendChild(closeBtn);
    toast.appendChild(iconWrap);
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.transition = "opacity 200ms ease, transform 200ms ease";
      toast.style.opacity = "0";
      toast.style.transform = "translateX(20px)";
      setTimeout(() => toast.remove(), 220);
    }, duration);
  }

  window.showToast = showToast;
})();
