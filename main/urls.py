from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('markets/<str:market>/', views.market_detail, name='market_detail'),
    path('markets/<str:market>/<str:feature_id>/', views.feature_view, name='feature_view'),
    path('api/predict/', views.predict_price_api, name='predict_api'),
    path('api/risk/', views.risk_analysis_api, name='risk_api'),
    path('api/optimize/', views.optimize_portfolio_api, name='optimize_api'),
    path('api/news/', views.market_news_api, name='market_news_api'),
    path('api/analysis/<str:market>/', views.market_analysis_api, name='market_analysis_api'),
    path('api/portfolio/snapshot/', views.portfolio_snapshot_api, name='portfolio_snapshot_api'),
    path('api/screener/', views.screener_api, name='screener_api'),
    path('api/comparison/', views.comparison_api, name='comparison_api'),
    path('api/tickers/', views.ticker_search_api, name='ticker_search_api'),
    path('model-health/', views.model_health_page, name='model_health'),
    path('how-it-works/', views.how_it_works_page, name='how_it_works'),
]