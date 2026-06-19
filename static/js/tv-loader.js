/* ==========================================================================
   FinSight TradingView Loader
   Fixes the blank-chart bug: the old code force-hid loading spinners after
   a hardcoded 3000ms regardless of whether the widget actually rendered.
   This version waits for the real onchartready callback, with a generous
   timeout that shows an honest retry message instead of a silent blank box.
   ========================================================================== */

(function () {
  function waitForTradingView(callback, attempts) {
    attempts = attempts || 0;
    if (typeof TradingView !== "undefined") {
      callback();
    } else if (attempts < 100) {
      setTimeout(() => waitForTradingView(callback, attempts + 1), 100);
    } else {
      console.warn("TradingView script failed to load after 10s.");
    }
  }

  function renderChart(containerId, symbol, options) {
    options = options || {};
    const container = document.getElementById(containerId);
    const loadingEl = document.getElementById(
      "loading_" + containerId.replace("tv_", ""),
    );

    if (!container) return null;

    let settled = false;
    const FAILSAFE_MS = 12000;

    function markLoaded() {
      if (settled) return;
      settled = true;
      if (loadingEl) loadingEl.style.display = "none";
    }

    function markFailed(reason) {
      if (settled) return;
      settled = true;
      if (loadingEl) loadingEl.style.display = "none";

      const fallback = document.createElement("div");
      fallback.className = "fade-in";
      fallback.style.cssText =
        "padding:24px; color:var(--muted); text-align:center; display:flex; flex-direction:column; align-items:center; gap:8px; height:100%; justify-content:center;";

      const label = document.createElement("div");
      label.textContent =
        reason || `Chart unavailable for ${options.displayName || symbol}.`;
      fallback.appendChild(label);

      const retryBtn = document.createElement("button");
      retryBtn.className = "btn btn-secondary";
      retryBtn.textContent = "Retry";
      retryBtn.style.fontSize = "var(--text-xs)";
      retryBtn.addEventListener("click", () => {
        fallback.remove();
        if (loadingEl) loadingEl.style.display = "flex";
        renderChart(containerId, symbol, options);
      });
      fallback.appendChild(retryBtn);

      container.innerHTML = "";
      container.appendChild(fallback);
    }

    waitForTradingView(function () {
      try {
        const widget = new TradingView.widget({
          width: "100%",
          height: options.height || 400,
          symbol: symbol,
          interval: options.interval || "60",
          timezone: "Etc/UTC",
          theme: document.body.classList.contains("light") ? "light" : "dark",
          style: "1",
          locale: "en",
          toolbar_bg: "transparent",
          enable_publishing: false,
          container_id: containerId,
          onchartready: markLoaded,
        });

        setTimeout(() => {
          if (!settled) {
            markFailed("This chart is taking longer than expected to load.");
          }
        }, FAILSAFE_MS);

        return widget;
      } catch (e) {
        markFailed(`This symbol isn't supported by the chart widget.`);
        return null;
      }
    });
  }

  window.FinSightCharts = { waitForTradingView, renderChart };
})();
