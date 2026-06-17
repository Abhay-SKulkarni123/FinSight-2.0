"""
FinSight ML Models — Production Grade
- PricePredictor: GBM with joblib serialization
- RiskAnalyzer: Full risk metrics suite
- PortfolioOptimizer: Real mean-variance optimization via scipy
"""
import os
import logging
import warnings
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

import yfinance as yf
import joblib
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

try:
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

warnings.filterwarnings('ignore')
logger = logging.getLogger('main')

# Cache directory for serialized models
try:
    from django.conf import settings
    ML_CACHE_DIR = Path(settings.ML_MODELS_DIR)
except Exception:
    ML_CACHE_DIR = Path(__file__).parent / 'ml_cache'
ML_CACHE_DIR.mkdir(exist_ok=True)


def clean_ticker(ticker: str) -> str:
    """Normalize ticker for yfinance — handles US, crypto, and Indian (NSE/BSE) tickers."""
    t = ticker.strip().split(":")[-1]
    upper = t.upper()

    # Indian indices (exact match)
    indian_index_map = {
        'NIFTY50': '^NSEI', 'NIFTY': '^NSEI',
        'SENSEX': '^BSESN',
        'NIFTYBANK': '^NSEBANK', 'BANKNIFTY': '^NSEBANK',
        'NIFTYNEXT50': '^NSEMDCP50',
    }
    if upper in indian_index_map:
        return indian_index_map[upper]

    # Already has NSE/BSE suffix or is an index — leave as-is
    if upper.endswith('.NS') or upper.endswith('.BO') or t.startswith('^'):
        return t

    # Crypto
    crypto_map = {'BTCUSD': 'BTC-USD', 'ETHUSD': 'ETH-USD', 'SOLUSD': 'SOL-USD',
                  'BNBUSDT': 'BNB-USD', 'BTCUSDT': 'BTC-USD', 'ETHUSDT': 'ETH-USD'}
    if upper in crypto_map:
        return crypto_map[upper]
    if upper.endswith('USDT'):
        return upper.replace('USDT', '-USD')
    if upper.endswith('USD') and '-' not in upper:
        return upper[:-3] + '-USD'

    return t


def is_indian_ticker(ticker: str) -> bool:
    """Check if a ticker belongs to an Indian exchange."""
    t = ticker.strip().upper()
    return t.endswith('.NS') or t.endswith('.BO') or t in (
        'NIFTY50', 'NIFTY', 'SENSEX', 'NIFTYBANK', 'BANKNIFTY', 'NIFTYNEXT50',
        '^NSEI', '^BSESN', '^NSEBANK', '^NSEMDCP50'
    )


class PricePredictor:
    """
    GBM price predictor with:
    - joblib model serialization (train once, predict fast)
    - RMSE / MAE / R2 tracking
    - Iterative multi-day roll-forward
    """

    FEATURES = [
        'Close', 'Volume', 'SMA_5', 'SMA_10', 'SMA_20', 'SMA_50',
        'RSI', 'MACD', 'MACD_signal', 'BB_upper', 'BB_lower',
        'Volume_ratio', 'Price_change', 'High_Low_ratio'
    ]

    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.metrics = {}

    def _model_path(self, ticker: str):
        safe = ticker.replace('/', '_').replace('-', '_')
        return ML_CACHE_DIR / f"predictor_{safe}.joblib"

    def _scaler_path(self, ticker: str):
        safe = ticker.replace('/', '_').replace('-', '_')
        return ML_CACHE_DIR / f"scaler_{safe}.joblib"

    def load_cached(self, ticker: str) -> bool:
        mp, sp = self._model_path(ticker), self._scaler_path(ticker)
        if mp.exists() and sp.exists():
            try:
                self.model = joblib.load(mp)
                self.scaler = joblib.load(sp)
                self.is_trained = True
                logger.info(f"Loaded cached model for {ticker}")
                return True
            except Exception as e:
                logger.warning(f"Cache load failed for {ticker}: {e}")
        return False

    def save_cached(self, ticker: str):
        joblib.dump(self.model, self._model_path(ticker))
        joblib.dump(self.scaler, self._scaler_path(ticker))

    def fetch_data(self, ticker: str, period: str = '2y'):
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period=period)
            return None if data.empty else data
        except Exception as e:
            logger.error(f"Data fetch error for {ticker}: {e}")
            return None

    def build_features(self, data: pd.DataFrame):
        if data is None or len(data) < 60:
            return None, None
        df = data.copy()
        df['SMA_5'] = df['Close'].rolling(5).mean()
        df['SMA_10'] = df['Close'].rolling(10).mean()
        df['SMA_20'] = df['Close'].rolling(20).mean()
        df['SMA_50'] = df['Close'].rolling(50).mean()
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + gain / loss.replace(0, 1e-9)))
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        bb_mid = df['Close'].rolling(20).mean()
        bb_std = df['Close'].rolling(20).std()
        df['BB_upper'] = bb_mid + bb_std * 2
        df['BB_lower'] = bb_mid - bb_std * 2
        vol_sma = df['Volume'].rolling(20).mean()
        df['Volume_ratio'] = df['Volume'] / vol_sma.replace(0, 1)
        df['Price_change'] = df['Close'].pct_change()
        df['High_Low_ratio'] = df['High'] / df['Low'].replace(0, 1)
        df = df.dropna()
        if len(df) < 50:
            return None, None
        X = df[self.FEATURES].values[:-1]
        y = df['Close'].values[1:]
        return X, y

    def train(self, ticker: str) -> dict:
        data = self.fetch_data(ticker)
        if data is None:
            return {}
        X, y = self.build_features(data)
        if X is None:
            return {}
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, shuffle=False)
        X_tr_s = self.scaler.fit_transform(X_tr)
        X_te_s = self.scaler.transform(X_te)
        self.model = GradientBoostingRegressor(
            n_estimators=200, learning_rate=0.05, max_depth=4,
            subsample=0.8, random_state=42
        )
        self.model.fit(X_tr_s, y_tr)
        self.is_trained = True
        preds = self.model.predict(X_te_s)
        self.metrics = {
            'rmse': float(np.sqrt(mean_squared_error(y_te, preds))),
            'mae': float(mean_absolute_error(y_te, preds)),
            'r2': float(r2_score(y_te, preds)),
            'samples': len(X_tr),
        }
        self.save_cached(ticker)
        logger.info(f"Trained model for {ticker} — RMSE: {self.metrics['rmse']:.4f}")
        return self.metrics

    def predict(self, ticker: str, days_ahead: int = 30):
        clean = clean_ticker(ticker)
        if not self.load_cached(clean):
            m = self.train(clean)
            if not m:
                return None, None, None

        data = self.fetch_data(clean)
        if data is None:
            return None, None, None
        X, _ = self.build_features(data)
        if X is None or len(X) == 0:
            return None, None, None

        current_price = float(data['Close'].iloc[-1])
        feats = self.scaler.transform(X[-1:])
        cur = feats[0].copy()
        for _ in range(days_ahead):
            pred = float(self.model.predict([cur])[0])
            cur = cur.copy()
            cur[0] = pred
        predicted_price = pred

        rmse = self.metrics.get('rmse', abs(predicted_price - current_price) * 0.1)
        price_range = max(current_price * 0.001, rmse)
        confidence = max(55.0, min(92.0, 100 - (price_range / current_price * 100)))
        return current_price, predicted_price, round(confidence, 1)


class RiskAnalyzer:
    """Comprehensive risk metrics with real beta vs SPY."""

    def calculate_risk_metrics(self, ticker: str, period: str = '1y'):
        try:
            clean = clean_ticker(ticker)
            stock = yf.Ticker(clean)
            data = stock.history(period=period)
            if data.empty:
                return None

            spy = yf.Ticker('SPY').history(period=period)
            returns = data['Close'].pct_change().dropna()
            volatility = float(returns.std() * np.sqrt(252) * 100)
            ann_return = float(returns.mean() * 252 * 100)
            sharpe = float((returns.mean() * 252) / (returns.std() * np.sqrt(252))) if returns.std() > 0 else 0

            # Real beta vs SPY
            beta = 1.0
            if not spy.empty:
                spy_ret = spy['Close'].pct_change().dropna()
                common = returns.index.intersection(spy_ret.index)
                if len(common) > 30:
                    r = returns.loc[common].values
                    m = spy_ret.loc[common].values
                    beta = float(np.cov(r, m)[0, 1] / np.var(m)) if np.var(m) > 0 else 1.0

            var_95 = float(np.percentile(returns, 5) * 100)
            var_99 = float(np.percentile(returns, 1) * 100)
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_dd = float(drawdown.min() * 100)

            price_history = data['Close'].tail(252)
            history = [{'date': str(idx.date()), 'close': round(float(v), 4)} for idx, v in price_history.items()]
            dd_series = [{'date': str(idx.date()), 'value': round(float(v * 100), 4)} for idx, v in drawdown.tail(252).items()]

            return {
                'volatility': round(volatility, 2),
                'sharpe_ratio': round(sharpe, 2),
                'beta': round(beta, 2),
                'var_95': round(abs(var_95), 2),
                'var_99': round(abs(var_99), 2),
                'max_drawdown': round(abs(max_dd), 2),
                'annualized_return': round(ann_return, 2),
                'current_price': round(float(data['Close'].iloc[-1]), 4),
                'history': history,
                'drawdown': dd_series,
            }
        except Exception as e:
            logger.error(f"Risk analysis error for {ticker}: {e}")
            return None


class PortfolioOptimizer:
    """
    Mean-variance portfolio optimizer.
    Uses scipy minimize for proper efficient frontier when available,
    falls back to Monte Carlo otherwise.
    """

    def optimize_allocation(self, tickers: list, risk_tolerance: str = 'moderate', investment_amount: float = 100000):
        try:
            clean_tickers = list(dict.fromkeys([clean_ticker(t) for t in tickers if t.strip()]))
            if len(clean_tickers) < 2:
                return None

            returns_dict = {}
            for t in clean_tickers[:10]:
                try:
                    hist = yf.Ticker(t).history(period='1y')
                    if not hist.empty:
                        returns_dict[t] = hist['Close'].pct_change().dropna()
                except Exception:
                    continue

            valid = list(returns_dict.keys())
            if len(valid) < 2:
                return None

            min_len = min(len(r) for r in returns_dict.values())
            arr = np.array([returns_dict[t].values[-min_len:] for t in valid])
            mu = arr.mean(axis=1) * 252
            cov = np.cov(arr) * 252
            n = len(valid)

            risk_map = {'conservative': 0.3, 'moderate': 0.5, 'aggressive': 0.8}
            risk_w = risk_map.get(risk_tolerance, 0.5)

            if SCIPY_AVAILABLE:
                def neg_sharpe(w):
                    ret = float(np.dot(w, mu))
                    vol = float(np.sqrt(w @ cov @ w))
                    return -(ret / vol) if vol > 1e-9 else 0

                def neg_return(w):
                    return -float(np.dot(w, mu))

                objective = neg_return if risk_w > 0.65 else neg_sharpe
                constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
                bounds = [(0.02, 0.60)] * n
                w0 = np.ones(n) / n
                result = minimize(objective, w0, method='SLSQP', bounds=bounds, constraints=constraints)
                weights = result.x if result.success else w0
            else:
                best_sharpe, weights = -np.inf, np.ones(n) / n
                for _ in range(5000):
                    w = np.random.dirichlet(np.ones(n))
                    ret = float(np.dot(w, mu))
                    vol = float(np.sqrt(w @ cov @ w))
                    s = ret / vol if vol > 0 else 0
                    if s > best_sharpe:
                        best_sharpe, weights = s, w

            weights = np.clip(weights, 0, 1)
            weights /= weights.sum()
            port_return = float(np.dot(weights, mu) * 100)
            port_vol = float(np.sqrt(weights @ cov @ weights) * 100)
            sharpe = port_return / port_vol if port_vol > 0 else 0

            allocation = {}
            for i, t in enumerate(valid):
                pct = round(float(weights[i] * 100), 2)
                allocation[t] = {'percentage': pct, 'amount': round(investment_amount * weights[i], 2)}

            # Efficient frontier (20 points)
            frontier = []
            if SCIPY_AVAILABLE:
                target_returns = np.linspace(mu.min(), mu.max(), 20)
                for target in target_returns:
                    def port_vol_fn(w): return float(np.sqrt(w @ cov @ w))
                    res = minimize(port_vol_fn, np.ones(n)/n, method='SLSQP',
                                   bounds=[(0,1)]*n,
                                   constraints=[{'type':'eq','fun':lambda w: np.sum(w)-1},
                                                {'type':'eq','fun':lambda w: np.dot(w,mu)-target}])
                    if res.success:
                        frontier.append({'return': round(float(target*100),2), 'volatility': round(float(res.fun*100),2)})

            return {
                'allocation': allocation,
                'expected_return': round(port_return, 2),
                'expected_volatility': round(port_vol, 2),
                'sharpe_ratio': round(sharpe, 2),
                'efficient_frontier': frontier,
                'optimizer': 'scipy' if SCIPY_AVAILABLE else 'montecarlo',
            }
        except Exception as e:
            logger.error(f"Portfolio optimization error: {e}")
            return None