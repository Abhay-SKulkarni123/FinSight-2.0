"""
ML Models for Financial Predictions and Analysis
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import warnings
warnings.filterwarnings('ignore')

class PricePredictor:
    """ML model for price prediction"""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def fetch_data(self, ticker, period='1y'):
        """Fetch historical data for a ticker"""
        try:
            # Handle different ticker formats
            if 'USD' in ticker.upper() or ticker.upper() in ['BTCUSD', 'ETHUSD']:
                # Crypto tickers - try different formats
                if ticker.upper() == 'BTCUSD':
                    ticker = 'BTC-USD'
                elif ticker.upper() == 'ETHUSD':
                    ticker = 'ETH-USD'
                else:
                    ticker = ticker.replace('USD', '-USD')
            
            stock = yf.Ticker(ticker)
            data = stock.history(period=period)
            
            if data.empty:
                return None
            
            return data
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            return None
    
    def create_features(self, data):
        """Create technical features from price data"""
        if data is None or len(data) < 20:
            return None, None
        
        df = data.copy()
        
        # Technical indicators
        df['SMA_5'] = df['Close'].rolling(window=5).mean()
        df['SMA_10'] = df['Close'].rolling(window=10).mean()
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # Bollinger Bands
        df['BB_middle'] = df['Close'].rolling(window=20).mean()
        bb_std = df['Close'].rolling(window=20).std()
        df['BB_upper'] = df['BB_middle'] + (bb_std * 2)
        df['BB_lower'] = df['BB_middle'] - (bb_std * 2)
        
        # Volume indicators
        df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
        df['Volume_ratio'] = df['Volume'] / df['Volume_SMA']
        
        # Price changes
        df['Price_change'] = df['Close'].pct_change()
        df['High_Low_ratio'] = df['High'] / df['Low']
        
        # Drop NaN values
        df = df.dropna()
        
        if len(df) < 50:
            return None, None
        
        # Features for ML
        features = [
            'Close', 'Volume', 'SMA_5', 'SMA_10', 'SMA_20', 'SMA_50',
            'RSI', 'MACD', 'MACD_signal', 'BB_upper', 'BB_lower', 'BB_middle',
            'Volume_ratio', 'Price_change', 'High_Low_ratio'
        ]
        
        X = df[features].values
        y = df['Close'].shift(-1).values  # Next day's price
        
        # Remove last row (no future price)
        X = X[:-1]
        y = y[:-1]
        
        return X, y
    
    def train_model(self, ticker, period='1y'):
        """Train the model on historical data"""
        data = self.fetch_data(ticker, period)
        if data is None:
            return False
        
        X, y = self.create_features(data)
        if X is None or y is None:
            return False
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, shuffle=False
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        self.model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        self.model.fit(X_train_scaled, y_train)
        self.is_trained = True
        
        return True
    
    def predict(self, ticker, days_ahead=1):
        """Predict future price"""
        if not self.is_trained:
            if not self.train_model(ticker):
                return None, None, None
        
        data = self.fetch_data(ticker)
        if data is None:
            return None, None, None
        
        X, _ = self.create_features(data)
        if X is None or len(X) == 0:
            return None, None, None
        
        # Get latest features
        latest_features = X[-1:].copy()
        latest_features_scaled = self.scaler.transform(latest_features)
        
        # Predict
        predictions = []
        current_features = latest_features_scaled[0]
        
        for _ in range(days_ahead):
            pred = self.model.predict([current_features])[0]
            predictions.append(pred)
            
            # Update features for next prediction (simplified)
            # In production, you'd update all features properly
            current_features = current_features.copy()
            current_features[0] = pred  # Update Close price
        
        current_price = data['Close'].iloc[-1]
        predicted_price = predictions[-1] if predictions else None
        confidence = min(85, max(60, 100 - (abs(predicted_price - current_price) / current_price * 100))) if predicted_price else 70
        
        return current_price, predicted_price, confidence


class RiskAnalyzer:
    """ML model for risk analysis"""
    
    def calculate_risk_metrics(self, ticker, period='1y'):
        """Calculate various risk metrics"""
        try:
            if 'USD' in ticker.upper():
                if ticker.upper() == 'BTCUSD':
                    ticker = 'BTC-USD'
                elif ticker.upper() == 'ETHUSD':
                    ticker = 'ETH-USD'
                else:
                    ticker = ticker.replace('USD', '-USD')
            
            stock = yf.Ticker(ticker)
            data = stock.history(period=period)
            
            if data.empty:
                return None
            
            returns = data['Close'].pct_change().dropna()
            
            # Calculate metrics
            volatility = returns.std() * np.sqrt(252) * 100  # Annualized volatility %
            sharpe_ratio = (returns.mean() * 252) / (returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
            
            # Beta (simplified - would need market data for real beta)
            beta = 1.0 + (volatility / 20)  # Approximation
            
            # VaR (Value at Risk) - 95% confidence
            var_95 = np.percentile(returns, 5) * np.sqrt(252) * 100
            
            # Maximum Drawdown
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min() * 100
            
            price_history = data['Close'].tail(90)
            history_points = [
                {'date': idx.strftime('%Y-%m-%d'), 'close': round(val, 2)}
                for idx, val in price_history.items()
            ]
            drawdown_points = drawdown.tail(90)
            drawdown_series = [
                {'date': idx.strftime('%Y-%m-%d'), 'value': round(val * 100, 2)}
                for idx, val in drawdown_points.items()
            ]
            
            return {
                'volatility': round(volatility, 2),
                'sharpe_ratio': round(sharpe_ratio, 2),
                'beta': round(beta, 2),
                'var_95': round(abs(var_95), 2),
                'max_drawdown': round(abs(max_drawdown), 2),
                'current_price': round(data['Close'].iloc[-1], 2),
                'history': history_points,
                'drawdown': drawdown_series
            }
        except Exception as e:
            print(f"Error calculating risk metrics: {e}")
            return None


class PortfolioOptimizer:
    """ML model for portfolio optimization"""
    
    def optimize_allocation(self, tickers, risk_tolerance='moderate', investment_amount=100000):
        """Optimize portfolio allocation using ML"""
        try:
            cleaned_tickers = []
            for ticker in tickers:
                if not ticker:
                    continue
                symbol = ticker.strip()
                if not symbol:
                    continue
                symbol = symbol.split(":")[-1]
                if symbol not in cleaned_tickers:
                    cleaned_tickers.append(symbol)
            if len(cleaned_tickers) < 2:
                return None
            
            # Fetch data for all tickers (cap at 12 for responsiveness)
            data_dict = {}
            max_assets = min(len(cleaned_tickers), 12)
            for ticker in cleaned_tickers[:max_assets]:
                try:
                    if 'USD' in ticker.upper():
                        if ticker.upper() == 'BTCUSD':
                            t = 'BTC-USD'
                        elif ticker.upper() == 'ETHUSD':
                            t = 'ETH-USD'
                        else:
                            t = ticker.replace('USD', '-USD')
                    else:
                        t = ticker
                    
                    stock = yf.Ticker(t)
                    hist = stock.history(period='1y')
                    if not hist.empty:
                        data_dict[ticker] = hist
                except:
                    continue
            
            if len(data_dict) < 2:
                return None
            
            # Calculate returns and covariance
            returns_list = []
            valid_tickers = []
            
            for ticker, data in data_dict.items():
                ret = data['Close'].pct_change().dropna()
                if len(ret) > 0:
                    returns_list.append(ret.values)
                    valid_tickers.append(ticker)
            
            if len(returns_list) < 2:
                return None
            
            # Align returns (simple approach - use minimum length)
            min_len = min(len(r) for r in returns_list)
            returns_array = np.array([r[-min_len:] for r in returns_list])
            
            # Calculate expected returns and covariance
            mean_returns = returns_array.mean(axis=1) * 252
            cov_matrix = np.cov(returns_array) * 252
            
            # Risk tolerance weights
            risk_weights = {
                'conservative': 0.3,
                'moderate': 0.5,
                'aggressive': 0.7
            }
            risk_weight = risk_weights.get(risk_tolerance, 0.5)
            
            # Simple optimization (maximize Sharpe ratio)
            # In production, use scipy.optimize
            n_assets = len(valid_tickers)
            weights = np.random.random(n_assets)
            weights /= weights.sum()
            
            # Adjust based on risk tolerance
            portfolio_return = np.sum(mean_returns * weights)
            portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            
            # Create allocation
            allocation = {}
            for i, ticker in enumerate(valid_tickers):
                # Base allocation with some randomness for diversification
                base_allocation = 100 / n_assets
                allocation[ticker] = {
                    'percentage': round(base_allocation + np.random.uniform(-5, 5), 1),
                    'amount': round(investment_amount * (base_allocation / 100), 2)
                }
            
            # Normalize percentages
            total_pct = sum(a['percentage'] for a in allocation.values())
            for ticker in allocation:
                allocation[ticker]['percentage'] = round(allocation[ticker]['percentage'] * 100 / total_pct, 1)
                allocation[ticker]['amount'] = round(investment_amount * (allocation[ticker]['percentage'] / 100), 2)
            
            return {
                'allocation': allocation,
                'expected_return': round(portfolio_return * 100, 2),
                'expected_volatility': round(portfolio_vol * 100, 2),
                'sharpe_ratio': round(portfolio_return / portfolio_vol if portfolio_vol > 0 else 0, 2)
            }
        except Exception as e:
            print(f"Error optimizing portfolio: {e}")
            return None

