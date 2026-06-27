(function () {
  const PALETTE = {
    accent: "#D4A24C",
    accentBright: "#E8B868",
    gain: "#4A9D78",
    gainBright: "#6BC299",
    loss: "#C45A4E",
    lossBright: "#DD7A6D",
    info: "#4C7FD4",
    infoBright: "#6FA0F0",
    purple: "#8B6FB3",
    purpleBright: "#A88FD0",
    muted: "#7A8699",
    grid: "rgba(122, 134, 153, 0.12)",
  };

  const SERIES_COLORS = [
    PALETTE.accent,
    PALETTE.gain,
    PALETTE.info,
    PALETTE.loss,
    PALETTE.purple,
    "#3D8C9E",
    "#B3893D",
    "#6F9C4A",
  ];

  const EASE = "easeOutQuart";
  const DURATION = 700;

  /**
   * Creates a tall, soft vertical gradient fill for area/line charts.
   * Pass the chart's canvas context (available inside a dataset's
   * backgroundColor callback) — Chart.js calls this lazily once layout
   * is known, which is required for gradients to size correctly.
   */
  function verticalGradient(
    ctx,
    colorHex,
    opacityTop = 0.35,
    opacityBottom = 0,
  ) {
    const chartArea = ctx.chart.chartArea;
    if (!chartArea) return colorHex; // not yet laid out — fallback to flat color
    const gradient = ctx.chart.ctx.createLinearGradient(
      0,
      chartArea.top,
      0,
      chartArea.bottom,
    );
    gradient.addColorStop(0, hexToRgba(colorHex, opacityTop));
    gradient.addColorStop(1, hexToRgba(colorHex, opacityBottom));
    return gradient;
  }

  function hexToRgba(hex, alpha) {
    const clean = hex.replace("#", "");
    const r = parseInt(clean.substring(0, 2), 16);
    const g = parseInt(clean.substring(2, 4), 16);
    const b = parseInt(clean.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  /**
   * Applies a soft drop-shadow glow to a chart's canvas element via CSS.
   * Call after the Chart instance is created and canvas exists in the DOM.
   */
  function applyGlow(canvasEl, colorHex, intensity = 10) {
    if (!canvasEl) return;
    canvasEl.style.filter = `drop-shadow(0 0 ${intensity}px ${hexToRgba(colorHex, 0.25)})`;
  }

  /** Shared base options every chart should spread in. */
  function baseOptions(overrides = {}) {
    return Object.assign(
      {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: DURATION, easing: EASE },
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              color: PALETTE.muted,
              font: { size: 11, family: "'Inter', sans-serif" },
              usePointStyle: true,
              pointStyle: "circle",
              padding: 16,
            },
          },
          tooltip: {
            backgroundColor: "#151F35",
            titleColor: "#E9EDF5",
            bodyColor: "#B6BFD4",
            borderColor: "rgba(212,162,76,0.3)",
            borderWidth: 1,
            padding: 12,
            cornerRadius: 10,
            displayColors: true,
            boxPadding: 4,
            titleFont: {
              family: "'JetBrains Mono', monospace",
              size: 12,
              weight: "600",
            },
            bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
          },
        },
        scales: {
          x: {
            grid: { color: PALETTE.grid, drawTicks: false },
            border: { display: false },
            ticks: {
              color: PALETTE.muted,
              font: { size: 10.5 },
              maxRotation: 0,
            },
          },
          y: {
            grid: { color: PALETTE.grid, drawTicks: false },
            border: { display: false },
            ticks: { color: PALETTE.muted, font: { size: 10.5 } },
          },
        },
      },
      overrides,
    );
  }

  /** Line/area dataset preset with gradient fill, smooth curve, glowing point on hover. */
  function lineDataset(label, data, colorHex, opts = {}) {
    return Object.assign(
      {
        label,
        data,
        borderColor: colorHex,
        backgroundColor: (ctx) =>
          verticalGradient(ctx, colorHex, opts.fillOpacity ?? 0.32, 0),
        fill: true,
        tension: 0.35,
        borderWidth: 2.5,
        pointRadius: 0,
        pointHoverRadius: 6,
        pointHoverBackgroundColor: colorHex,
        pointHoverBorderColor: "#fff",
        pointHoverBorderWidth: 2,
      },
      opts,
    );
  }

  /** Bar dataset preset with per-bar gradient and rounded corners. */
  function barDataset(label, data, colorHex, opts = {}) {
    return Object.assign(
      {
        label,
        data,
        backgroundColor: (ctx) => verticalGradient(ctx, colorHex, 0.85, 0.45),
        borderRadius: 6,
        borderSkipped: false,
        barPercentage: 0.7,
      },
      opts,
    );
  }

  /** Doughnut dataset preset with the shared palette and a soft border. */
  function doughnutDataset(data, opts = {}) {
    return Object.assign(
      {
        data,
        backgroundColor: SERIES_COLORS,
        borderColor: "#0B1220",
        borderWidth: 3,
        hoverOffset: 10,
        spacing: 2,
      },
      opts,
    );
  }

  window.FinSightChartTheme = {
    PALETTE,
    SERIES_COLORS,
    EASE,
    DURATION,
    verticalGradient,
    hexToRgba,
    applyGlow,
    baseOptions,
    lineDataset,
    barDataset,
    doughnutDataset,
  };
})();
