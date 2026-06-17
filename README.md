<div align="center">

# FinSight — Unified Multi-Market Intelligence

All-in-one analytics, ML-assisted predictions, and curated resources covering ten global market segments. Built with Django 5, TradingView widgets, and lightweight scikit-learn models for rapid demos or deployment.

</div>

---

## Contents

1. [Why FinSight](#why-finsight)  
2. [System Overview](#system-overview)  
3. [Key Features](#key-features)  
4. [Algorithms & Rationale](#algorithms--rationale)  
5. [API Surface](#api-surface)  
6. [Getting Started](#getting-started)  
7. [Demo & Deployment](#demo--deployment)  
8. [Verification Checklist](#verification-checklist)

---

## Why FinSight

- **Complete market coverage** — Stocks, crypto, indices, forex, metals, energy, bonds, ETFs, futures, and commodities backed by curated tickers per segment.  
- **Feature parity** — Ten feature modules (prediction, news, visualizations, portfolio tools, screeners, risk, resources, etc.) now driven by live data or ML helpers instead of placeholders.  
- **Operational confidence** — Health checks, explicit error messaging, and curated fallbacks keep demos smooth even if upstream data is intermittent.

---

## System Overview

| Layer          | Tech / Responsibility |
| -------------- | --------------------- |
| Web server     | Django 5 project (`core`, `main` app) |
| Data fetch     | `yfinance`, Inshorts API, custom pandas transforms, selective TradingView |
| ML utilities   | `scikit-learn`, `numpy`, `pandas` inside `main/ml_models.py` |
| Front end      | HTML templates + vanilla JS + Chart.js visual layers |
| Storage        | SQLite (default), easy swap via Django settings |

**Routing highlights**

- `/` — Home with live overview widgets.  
- `/markets/<market>/` — Market hub plus feature shortcuts.  
- `/markets/<market>/<feature>/` — Dedicated feature pages.  
- `/api/predict`, `/api/risk`, `/api/optimize`, `/api/news` — JSON endpoints powering interactive tools.

---

## Key Features

- **Prediction Lab** — Gradient Boosting regressor trained on technical factors delivers forward-looking price targets with confidence scoring.  
- **Live News Center** — Calls the Inshorts live news API + Yahoo Finance backfill so every card links to a real publisher.  
- **Visual Studio** — TradingView reserved for the global macro board; intra-feature visualizations now use Chart.js portfolios, drawdowns, and comparison matrices.  
- **Risk Desk** — Annualized volatility, Sharpe estimate, beta approximation, VaR, drawdown metrics, and ML-generated insights per user input.  
- **Portfolio Workspace** — Users feed any holdings, the backend rebuilds valuations, allocations, and equity curves on demand.  
- **Smart Screener** — Server-side `yfinance` screener API with filters (price, trend, P/E, dividends) and live reload UI.  
- **Resource Library** — Market-specific official docs (SEC, BIS, IMF, CFTC, Coinbase Learn, Babypips, etc.) grouped by category with deep links.  
- **Global Home** — One hero TradingView chart for SPX; everything else is now AI-driven or custom-rendered to avoid TV overload.

---

## Algorithms & Rationale

| Module | Approach | Why this choice |
| ------ | -------- | --------------- |
| Prediction (`PricePredictor`) | GradientBoostingRegressor + technical feature engineering (SMA, RSI, MACD, Bollinger, volume ratios). Iterative day-ahead roll-forward for multi-horizon estimates. | Gradient boosting works well on tabular technical inputs, trains quickly without GPUs, and is stable for demos without hyper-parameter sweeps. |
| Risk (`RiskAnalyzer`) | Daily pct returns → annualized volatility, Sharpe (252-day factor), heuristic beta from vol scaling, 95% VaR from percentile, rolling max drawdown. | Provides a concise but informative risk packet using data that is always available via yfinance. |
| Portfolio (`PortfolioOptimizer`) | Fetch up to six assets, align series, compute mean returns + covariance, seed random weights with diversification bias, normalize allocations, estimate expected return/volatility/ShAR. | Light-weight alternative to full quadratic programming; avoids SciPy dependency while still demonstrating allocation logic. |
| News aggregation | Inshorts public API for live headlines + yfinance `Ticker.news` fallback with dedupe + timestamp normalization. | Guarantees real URLs for every resource card, while remaining resilient to rate limits. |
| Resource curator | Deterministic resource map per market + default set, merged and grouped by category via `OrderedDict`. | Guarantees every market has actionable official documentation, fulfilling compliance-focused requirements. |
| Portfolio snapshot | Server-side pandas aggregation of user holdings with historical equity curve + allocation data. | Enables unlimited ticker inputs and realistic EDA visuals without exposing API keys to the browser. |
| Comparison analytics | yfinance multi-series fetch + RSI overlay + Chart.js rendering. | Removes TradingView dependency for pairwise studies while keeping multi-asset lineups reactive. |

---

## API Surface

| Endpoint | Method | Payload | Response |
| -------- | ------ | ------- | -------- |
| `/api/predict/` | POST | `ticker`, `target_date`, `timeline`, `market_type` | Current & predicted price, delta %, confidence |
| `/api/risk/` | POST | `ticker` | Volatility, Sharpe, beta, VaR, drawdown, price |
| `/api/optimize/` | POST | `tickers[]`, `risk_tolerance`, `investment_amount` | Allocation dict + expected return/vol/ShAR |
| `/api/news/?market=<slug>&limit=12` | GET | Query params | Aggregated article list with publisher, type, related tickers |
| `/api/portfolio/snapshot/` | POST | `holdings[{ticker,quantity,cost_basis}]` | Portfolio totals, allocation mix, equity curve |
| `/api/screener/` | POST | `market`, `filters`, optional `tickers[]` | Filtered asset rows with price/change/volume/valuation |
| `/api/comparison/` | POST | `tickers[]`, `period` | Head-to-head metrics + normalized Chart.js series |

All endpoints return JSON with a `success` flag or `error` field for consistent handling.

---

## Getting Started

1. **Install deps**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. **Database**
   ```bash
   python manage.py migrate
   ```
3. **Run server**
   ```bash
   python manage.py runserver
   ```
4. **Visit**
   - Home: `http://127.0.0.1:8000/`
   - Markets: `http://127.0.0.1:8000/markets/stocks/`

> **Tip:** TradingView widgets need an internet connection; allowlist `https://s3.tradingview.com`.

---

## Demo & Deployment

- **Demo mode** — SQLite + embedded fallbacks already seeded. Ensure outbound HTTPS for yfinance + TradingView.  
- **Production tweaks**
  - Set `DEBUG=False` and configure `ALLOWED_HOSTS` in `core/settings.py`.  
  - Swap SQLite for Postgres via `DATABASES` setting.  
  - Add cache (Redis/Memcached) for `market_news_api` if traffic is heavy.  
  - Serve static files via WhiteNoise/CDN and front with nginx.  
  - Configure background refresh (Celery/CRON) if you want to pre-fetch ML models instead of on-demand training.
- **Logging/Monitoring**
  - Django logging captures API exceptions; extend with Sentry or ELK for production telemetry.  
  - TradingView widgets can emit console warnings if symbols are invalid; front-end now surfaces graceful error states.

---

## Verification Checklist

- [x] All feature pages load without console errors across markets.  
- [x] News cards hydrate from `/api/news/` with fallback content.  
- [x] Resource cards open publishers in new tabs (SEC, BIS, IMF, CFTC, etc.).  
- [x] Prediction form validates ticker/date and shows ML output + TradingView chart.  
- [x] Risk/Portfolio APIs respond with meaningful metrics for at least the default tickers.  
- [x] Home page renders nav and macro overview without JS crashes or redundant charts.  
- [x] README delivered with architecture, algorithm explainers, and deployment notes.

FinSight is now demo-ready and can be deployed with minimal configuration changes. Happy shipping!


