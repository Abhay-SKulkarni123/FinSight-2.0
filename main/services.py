"""
FinSight Service Layer
Business logic for predict/risk/portfolio lives here.
News logic stays in views.py (Inshorts + yfinance) — this just adds a caching wrapper.
"""
import logging
from django.core.cache import cache
from .ml_models import PricePredictor, RiskAnalyzer, PortfolioOptimizer, clean_ticker, is_indian_ticker

logger = logging.getLogger('main')

CACHE_TTL_NEWS = 300       # 5 minutes
CACHE_TTL_RISK = 600       # 10 minutes


def resolve_ticker_for_market(ticker: str, market_type: str) -> str:
    """
    Strip exchange prefix and append .NS for Indian market tickers
    (unless it's already an index or suffixed).
    """
    clean = ticker.split(":")[-1] if ":" in ticker else ticker
    if market_type == 'indian_markets':
        if not is_indian_ticker(clean) and clean.upper() not in (
            'NIFTY', 'NIFTY50', 'SENSEX', 'NIFTYBANK', 'BANKNIFTY'
        ):
            clean = f"{clean}.NS"
    return clean


def get_prediction(ticker: str, days_ahead: int, market_type: str = ''):
    """Run prediction and persist model metrics. Returns dict or None."""
    clean = resolve_ticker_for_market(ticker, market_type)
    predictor = PricePredictor()
    current, predicted, confidence = predictor.predict(clean, days_ahead)
    if current is None:
        return None

    result = {
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
            ticker=clean_ticker(clean),
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


def get_risk_analysis(ticker: str, market_type: str = '', period: str = '1y'):
    """Run risk analysis with a 10-minute cache."""
    clean = resolve_ticker_for_market(ticker, market_type)
    cache_key = f"risk:{clean}:{period}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    result = RiskAnalyzer().calculate_risk_metrics(clean, period)
    if result:
        cache.set(cache_key, result, CACHE_TTL_RISK)
    return result


def get_portfolio_optimization(tickers: list, risk_tolerance: str, investment_amount: float):
    """Run portfolio optimization. No caching — allocations should always be fresh."""
    return PortfolioOptimizer().optimize_allocation(tickers, risk_tolerance, investment_amount)