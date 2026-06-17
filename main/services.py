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