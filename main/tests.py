"""
FinSight Test Suite
Run: python manage.py test main
"""
import json
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User
from .models import Watchlist, UserPortfolio, ModelMetrics


class HomePageTest(TestCase):
    def test_home_returns_200(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_home_contains_finsight(self):
        response = self.client.get('/')
        self.assertContains(response, 'FinSight')


class MarketPageTest(TestCase):
    def test_valid_markets_return_200(self):
        for market in ['stocks', 'crypto', 'forex', 'metals', 'indian_markets']:
            response = self.client.get(f'/markets/{market}/')
            self.assertEqual(response.status_code, 200, f"Market '{market}' failed")

    def test_invalid_market_falls_back_to_stocks(self):
        """views.py intentionally falls back to 'stocks' for unknown market slugs
        instead of raising 404 — this documents that deliberate behavior."""
        response = self.client.get('/markets/unicorns/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Stocks')


class PredictAPITest(TestCase):
    @patch('main.services.PricePredictor')
    def test_predict_api_success(self, MockPredictor):
        instance = MockPredictor.return_value
        instance.predict.return_value = (175.5, 182.3, 78.5)
        instance.metrics = {'rmse': 2.1, 'mae': 1.5, 'r2': 0.85, 'samples': 400}

        response = self.client.post(
            '/api/predict/',
            data=json.dumps({'ticker': 'AAPL', 'timeline': '1m', 'market_type': 'stocks'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body.get('success'))
        self.assertEqual(body['current_price'], 175.5)

    def test_predict_api_rejects_get(self):
        response = self.client.get('/api/predict/')
        self.assertEqual(response.status_code, 405)

    def test_predict_api_empty_ticker(self):
        response = self.client.post(
            '/api/predict/',
            data=json.dumps({'ticker': '', 'timeline': '1m'}),
            content_type='application/json',
        )
        data = json.loads(response.content)
        self.assertIn('error', data)


class RiskAPITest(TestCase):
    @patch('main.services.RiskAnalyzer')
    def test_risk_api_returns_all_keys(self, MockAnalyzer):
        instance = MockAnalyzer.return_value
        instance.calculate_risk_metrics.return_value = {
            'volatility': 25.3, 'sharpe_ratio': 1.45, 'beta': 1.12,
            'var_95': 2.5, 'var_99': 3.8, 'max_drawdown': 12.5,
            'annualized_return': 18.2, 'current_price': 175.5,
            'history': [], 'drawdown': [],
        }
        response = self.client.post(
            '/api/risk/',
            data=json.dumps({'ticker': 'AAPL'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))
        for key in ['volatility', 'sharpe_ratio', 'beta', 'var_95', 'max_drawdown']:
            self.assertIn(key, data.get('metrics', {}))

    def test_risk_api_requires_ticker(self):
        response = self.client.post(
            '/api/risk/',
            data=json.dumps({'ticker': ''}),
            content_type='application/json',
        )
        data = json.loads(response.content)
        self.assertIn('error', data)


class PortfolioOptimizeAPITest(TestCase):
    def test_rejects_single_ticker(self):
        response = self.client.post(
            '/api/optimize/',
            data=json.dumps({'tickers': ['AAPL']}),
            content_type='application/json',
        )
        data = json.loads(response.content)
        self.assertIn('error', data)

    @patch('main.services.PortfolioOptimizer')
    def test_optimize_success(self, MockOptimizer):
        instance = MockOptimizer.return_value
        instance.optimize_allocation.return_value = {
            'allocation': {'AAPL': {'percentage': 50.0, 'amount': 50000.0},
                            'MSFT': {'percentage': 50.0, 'amount': 50000.0}},
            'expected_return': 12.5, 'expected_volatility': 18.2,
            'sharpe_ratio': 0.68, 'efficient_frontier': [], 'optimizer': 'scipy',
        }
        response = self.client.post(
            '/api/optimize/',
            data=json.dumps({'tickers': ['AAPL', 'MSFT'], 'investment_amount': 100000}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))
        self.assertIn('efficient_frontier', data)


class ModelMetricsTest(TestCase):
    def test_create_model_metrics(self):
        m = ModelMetrics.objects.create(ticker='AAPL', rmse=2.1, mae=1.5, r2_score=0.85)
        self.assertEqual(m.ticker, 'AAPL')
        self.assertGreater(m.rmse, 0)

    def test_model_metrics_str(self):
        m = ModelMetrics(ticker='TSLA', rmse=3.2, mae=2.1)
        self.assertIn('TSLA', str(m))


class WatchlistTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'password')

    def test_add_to_watchlist(self):
        Watchlist.objects.create(user=self.user, ticker='AAPL', market='stocks')
        self.assertEqual(Watchlist.objects.filter(user=self.user).count(), 1)

    def test_watchlist_unique_per_user(self):
        Watchlist.objects.create(user=self.user, ticker='AAPL', market='stocks')
        with self.assertRaises(Exception):
            Watchlist.objects.create(user=self.user, ticker='AAPL', market='stocks')


class UserPortfolioTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('portfoliouser', 'p@test.com', 'password')

    def test_add_holding(self):
        holding = UserPortfolio.objects.create(
            user=self.user, ticker='AAPL', market='stocks',
            quantity=10, cost_basis=1750.00
        )
        self.assertEqual(holding.ticker, 'AAPL')