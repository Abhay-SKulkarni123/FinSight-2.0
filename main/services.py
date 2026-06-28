"""
FinSight Service Layer
All business logic lives here. Views are thin controllers only.
"""
import logging
from django.core.cache import cache
from .ml_models import PricePredictor, RiskAnalyzer, PortfolioOptimizer, clean_ticker, is_indian_ticker

logger = logging.getLogger('main')

CACHE_TTL_NEWS = 300       # 5 minutes
CACHE_TTL_RISK = 600       # 10 minutes
CACHE_TTL_SCREENER = 180   # 3 minutes


def resolve_ticker_for_market(ticker: str, market_type: str) -> str:
    """
    Strip exchange prefix and append .NS for Indian market tickers
    (unless it's already an index or already suffixed).
    """
    clean = ticker.split(":")[-1] if ":" in ticker else ticker
    if market_type == 'indian_markets':
        if not is_indian_ticker(clean) and clean.upper() not in (
            'NIFTY', 'NIFTY50', 'SENSEX', 'NIFTYBANK', 'BANKNIFTY'
        ):
            clean = f"{clean}.NS"
    return clean


def get_prediction(ticker: str, days_ahead: int, market_type: str = ''):
    resolved_ticker = resolve_ticker_for_market(ticker, market_type)
    predictor = PricePredictor()
    current, predicted, confidence = predictor.predict(resolved_ticker, days_ahead)
    if current is None:
        return None
    result = {
        'ticker': ticker,
        'current_price': round(float(current), 4),
        'predicted_price': round(float(predicted), 4),
        'price_change': round(float(predicted - current), 4),
        'price_change_pct': round(float((predicted - current) / current * 100), 2),
        'confidence': confidence,
        'metrics': predictor.metrics,
    }
    # Persist metrics to DB as a NEW history row — only when the model was
    # actually freshly trained this call (predictor.metrics is only populated
    # by train(), not by a cache-hit load), so repeated predictions against an
    # already-cached model don't spam duplicate rows with identical numbers.
    if predictor.metrics:
        try:
            from .models import ModelMetrics
            ModelMetrics.objects.create(
                ticker=clean_ticker(resolved_ticker),
                market_type=market_type,
                horizon_days=predictor.metrics.get('horizon_days', days_ahead),
                rmse=predictor.metrics.get('rmse', 0),
                mae=predictor.metrics.get('mae', 0),
                r2_score=predictor.metrics.get('r2', 0),
                training_samples=predictor.metrics.get('samples', 0),
            )
        except Exception as e:
            logger.warning(f"Could not save ModelMetrics: {e}")
    return result


def get_risk_analysis(ticker: str, market_type: str = '', period: str = '1y'):
    resolved_ticker = resolve_ticker_for_market(ticker, market_type)
    cache_key = f"risk:{resolved_ticker}:{period}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    result = RiskAnalyzer().calculate_risk_metrics(resolved_ticker, period)
    if result:
        cache.set(cache_key, result, CACHE_TTL_RISK)
    return result


def get_portfolio_optimization(tickers: list, risk_tolerance: str, investment_amount: float):
    return PortfolioOptimizer().optimize_allocation(tickers, risk_tolerance, investment_amount)


def get_market_news(market: str, limit: int = 12):
    cache_key = f"news:{market}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    import yfinance as yf
    from .views import MARKETS
    articles = []
    try:
        tickers_raw = MARKETS.get(market, {}).get('tickers', [])[:5]
        seen = set()
        for raw in tickers_raw:
            symbol = raw.split(':')[-1]
            try:
                news = yf.Ticker(symbol).news or []
                for item in news[:4]:
                    url = item.get('link', '')
                    if url and url not in seen:
                        seen.add(url)
                        articles.append({
                            'title': item.get('title', ''),
                            'publisher': item.get('publisher', ''),
                            'link': url,
                            'published': item.get('providerPublishTime', 0),
                            'related': item.get('relatedTickers', []),
                        })
            except Exception:
                continue
    except Exception as e:
        logger.error(f"News fetch error: {e}")

    articles = articles[:limit]
    if articles:
        cache.set(cache_key, articles, CACHE_TTL_NEWS)
    return articles


CACHE_TTL_ANALYSIS = 600  # 10 minutes

SECTOR_LABELS = {
    'stocks': 'Equities', 'crypto': 'Crypto', 'indices': 'Broad market', 'forex': 'Currencies',
    'metals': 'Precious metals', 'energy': 'Energy', 'bonds': 'Fixed income', 'etfs': 'Funds',
    'futures': 'Derivatives', 'commodities': 'Commodities', 'indian_markets': 'Indian equities',
}


def get_market_analysis(market: str, tickers: list):
    """
    Aggregate real per-ticker quote + momentum data across a market's tickers
    into a genuine market overview. Replaces the previous hardcoded template values.
    """
    cache_key = f"analysis:{market}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    import yfinance as yf
    from .ml_models import clean_ticker as norm_ticker

    symbols = [t.split(':')[-1] for t in tickers[:8]]
    if market == 'indian_markets':
        symbols = [s if (s.endswith('.NS') or s.endswith('.BO') or s.upper() in ('SENSEX', 'NIFTY')) else f"{s}.NS" for s in symbols]

    rows = []
    for sym in symbols:
        try:
            resolved = norm_ticker(sym)
            hist = yf.Ticker(resolved).history(period='5d')
            if hist.empty or len(hist) < 2:
                continue
            last_close = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2])
            change_pct = ((last_close - prev_close) / prev_close) * 100 if prev_close else 0
            volume = float(hist['Volume'].iloc[-1]) if 'Volume' in hist else 0
            rows.append({
                'symbol': sym.replace('.NS', '').replace('.BO', ''),
                'price': last_close,
                'change_pct': change_pct,
                'volume': volume,
            })
        except Exception:
            continue

    if not rows:
        return None

    gainers = sorted([r for r in rows if r['change_pct'] > 0], key=lambda r: -r['change_pct'])
    losers = sorted([r for r in rows if r['change_pct'] < 0], key=lambda r: r['change_pct'])
    avg_change = sum(r['change_pct'] for r in rows) / len(rows)
    total_volume = sum(r['volume'] for r in rows)

    sentiment = 'Bullish' if avg_change > 0.5 else ('Bearish' if avg_change < -0.5 else 'Neutral')

    result = {
        'sentiment': sentiment,
        'avg_change_pct': round(avg_change, 2),
        'total_volume': total_volume,
        'tickers_analyzed': len(rows),
        'top_gainer': gainers[0] if gainers else None,
        'top_loser': losers[0] if losers else None,
        'breakdown': sorted(rows, key=lambda r: -r['change_pct']),
        'sector_label': SECTOR_LABELS.get(market, market.title()),
    }
    cache.set(cache_key, result, CACHE_TTL_ANALYSIS)
    return result


def get_model_health(limit_per_ticker: int = 30):
    """
    Aggregate ModelMetrics history into a dashboard-ready summary:
    per-ticker latest accuracy plus a trend series for charting.
    Honest by construction — if a ticker has only ever been trained once,
    its "trend" is a single point, and the dashboard should say so rather
    than imply a history that doesn't exist.
    """
    from .models import ModelMetrics

    # NOTE: ModelMetrics.Meta.ordering = ['-trained_at'] by default, which
    # breaks .distinct() at the SQL level when the ordering column isn't in
    # the SELECT (a classic Django gotcha — ORDER BY columns leak into
    # DISTINCT). Using .order_by() explicitly here resets that.
    tickers = (ModelMetrics.objects
               .order_by('ticker')
               .values_list('ticker', flat=True)
               .distinct())

    summary = []
    for ticker in tickers:
        rows = list(
            ModelMetrics.objects.filter(ticker=ticker)
            .order_by('-trained_at')[:limit_per_ticker]
        )
        if not rows:
            continue
        rows = list(reversed(rows))  # chronological for charting
        latest = rows[-1]
        summary.append({
            'ticker': ticker,
            'market_type': latest.market_type,
            'horizon_days': latest.horizon_days,
            'latest_rmse': round(latest.rmse, 4),
            'latest_mae': round(latest.mae, 4),
            'latest_r2': round(latest.r2_score, 4),
            'training_samples': latest.training_samples,
            'last_trained': latest.trained_at.isoformat(),
            'retrain_count': len(rows),
            'history': [
                {
                    'trained_at': r.trained_at.isoformat(),
                    'rmse': round(r.rmse, 4),
                    'mae': round(r.mae, 4),
                    'r2': round(r.r2_score, 4),
                }
                for r in rows
            ],
        })

    summary.sort(key=lambda s: s['last_trained'], reverse=True)
    return {
        'tickers': summary,
        'total_tracked': len(summary),
        'total_retrains': sum(s['retrain_count'] for s in summary),
    }


# ---- Financial sentiment scoring ----
# VADER extended with a domain-specific keyword boost for common financial
# headline terms that VADER's social-media-trained dictionary underweights.
# Honest limitation: keyword-based context-free approaches have ~60-70%
# directional accuracy on financial text — we display this as a signal,
# not a guarantee, and the badge is labelled with a question mark in the UI
# when confidence is low (compound near 0).

_BULLISH_TERMS = frozenset([
    'rally', 'surge', 'surges', 'beat', 'beats', 'record', 'bullish', 'rise',
    'rises', 'gain', 'gains', 'upbeat', 'recovery', 'upgrade', 'outperform',
    'strong', 'above', 'exceed', 'exceeds', 'high', 'highs', 'positive',
    'growth', 'profit', 'profits', 'boost', 'boosted', 'optimism', 'optimistic',
])

_BEARISH_TERMS = frozenset([
    'crash', 'crashes', 'fear', 'fears', 'crackdown', 'tumble', 'tumbles',
    'plunge', 'plunges', 'miss', 'misses', 'downgrade', 'underperform',
    'weak', 'below', 'overvalued', 'risk', 'risks', 'default', 'recession',
    'inflation', 'tariff', 'tariffs', 'sanction', 'sanctions', 'concern',
    'concerns', 'warning', 'sell', 'drop', 'drops', 'fell', 'fall', 'falls',
    'decline', 'declines', 'loss', 'losses', 'deficit',
])

_vader_analyzer = None


def _get_vader():
    global _vader_analyzer
    if _vader_analyzer is None:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer # type: ignore
            _vader_analyzer = SentimentIntensityAnalyzer()
        except ImportError:
            logger.warning("vaderSentiment not installed — sentiment scoring disabled")
    return _vader_analyzer


def score_sentiment(text: str) -> dict:
    """
    Score a single financial headline and return:
      - label: 'Bullish' | 'Bearish' | 'Neutral'
      - score: float in [-1, 1]
      - confidence: 'high' | 'medium' | 'low'
    Returns None if VADER is not available.
    """
    if not text:
        return None
    analyzer = _get_vader()
    if analyzer is None:
        return None

    base = analyzer.polarity_scores(text)['compound']
    words = text.lower().split()
    boost = sum(0.12 for w in words if w in _BULLISH_TERMS)
    boost -= sum(0.12 for w in words if w in _BEARISH_TERMS)
    score = round(max(-1.0, min(1.0, base + boost)), 3)

    abs_score = abs(score)
    confidence = 'high' if abs_score >= 0.3 else ('medium' if abs_score >= 0.1 else 'low')

    if score >= 0.05:
        label = 'Bullish'
    elif score <= -0.05:
        label = 'Bearish'
    else:
        label = 'Neutral'

    return {'label': label, 'score': score, 'confidence': confidence}


def score_articles(articles: list) -> list:
    """Add sentiment scoring to a list of news article dicts in-place."""
    for article in articles:
        text = article.get('title', '') + ' ' + (article.get('summary') or '')
        article['sentiment'] = score_sentiment(text.strip())
    return articles