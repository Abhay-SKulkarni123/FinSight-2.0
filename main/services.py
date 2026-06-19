"""
FinSight Service Layer
All business logic lives here. Views are thin controllers only.
"""
import logging
from django.core.cache import cache
from .ml_models import PricePredictor, RiskAnalyzer, PortfolioOptimizer, clean_ticker

logger = logging.getLogger('main')

CACHE_TTL_NEWS = 300       # 5 minutes
CACHE_TTL_RISK = 600       # 10 minutes
CACHE_TTL_SCREENER = 180   # 3 minutes


def get_prediction(ticker: str, days_ahead: int, market_type: str = ''):
    predictor = PricePredictor()
    current, predicted, confidence = predictor.predict(ticker, days_ahead)
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
    # Persist metrics to DB (non-blocking)
    try:
        from .models import ModelMetrics
        ModelMetrics.objects.update_or_create(
            ticker=clean_ticker(ticker),
            defaults={
                'market_type': market_type,
                'rmse': predictor.metrics.get('rmse', 0),
                'mae': predictor.metrics.get('mae', 0),
                'r2_score': predictor.metrics.get('r2', 0),
                'training_samples': predictor.metrics.get('samples', 0),
            }
        )
    except Exception as e:
        logger.warning(f"Could not save ModelMetrics: {e}")
    return result


def get_risk_analysis(ticker: str, period: str = '1y'):
    cache_key = f"risk:{ticker}:{period}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    result = RiskAnalyzer().calculate_risk_metrics(ticker, period)
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