from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
from datetime import datetime, timezone as dt_timezone
from collections import OrderedDict
import re
import yfinance as yf
import requests
import pandas as pd
import numpy as np
from .ml_models import PricePredictor, RiskAnalyzer, PortfolioOptimizer
from . import services
from django_ratelimit.decorators import ratelimit # type: ignore

# Market definitions with sample tickers - Updated with TradingView-compatible symbols
MARKETS = {
    "stocks": {
        "name": "Stocks",
        "tickers": ["NASDAQ:AAPL", "NASDAQ:GOOGL", "NASDAQ:MSFT", "NASDAQ:AMZN", "NASDAQ:TSLA", "NASDAQ:META", "NASDAQ:NVDA", "NASDAQ:NFLX"],
        "description": "Stock market analysis and trading insights",
        "detailed_description": "The stock market represents ownership shares in publicly traded companies. Stocks are one of the most popular investment vehicles, offering potential for capital appreciation and dividend income. Stock prices are influenced by company performance, economic indicators, market sentiment, and global events. Investors can trade stocks on major exchanges like NYSE and NASDAQ, with opportunities ranging from blue-chip stability to high-growth tech stocks. Understanding fundamental analysis, technical indicators, and market trends is crucial for successful stock trading."
    },
    "crypto": {
        "name": "Crypto",
        "tickers": ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BINANCE:BNBUSDT", "BINANCE:ADAUSDT", "BINANCE:SOLUSDT", "BINANCE:XRPUSDT", "BINANCE:DOTUSDT", "BINANCE:DOGEUSDT"],
        "description": "Cryptocurrency market trends and predictions",
        "detailed_description": "Cryptocurrency markets operate 24/7 and are known for high volatility and rapid price movements. Digital assets like Bitcoin and Ethereum have emerged as alternative investments and stores of value. Crypto markets are influenced by adoption rates, regulatory news, technological developments, and market sentiment. Trading cryptocurrencies requires understanding blockchain technology, market cycles, and risk management due to their inherent volatility. The decentralized nature of cryptocurrencies offers both opportunities and challenges for traders."
    },
    "indices": {
        "name": "Indices",
        "tickers": ["SP:SPX", "DJ:DJI", "NASDAQ:IXIC", "RUT", "CBOE:VIX", "LSE:UKX", "TSE:NKY", "XETR:DAX"],
        "description": "Market indices tracking and analysis",
        "detailed_description": "Market indices track the performance of a basket of stocks, representing overall market health. Major indices like the S&P 500, Dow Jones, and NASDAQ provide insights into economic trends and investor sentiment. Indices are less volatile than individual stocks and offer diversified exposure to market segments. They're used as benchmarks for portfolio performance and can be traded through ETFs and futures. Understanding index composition, sector weightings, and correlation patterns helps investors make informed decisions about market direction and portfolio allocation."
    },
    "forex": {
        "name": "Forex",
        "tickers": ["FX:EURUSD", "FX:GBPUSD", "FX:USDJPY", "FX:AUDUSD", "FX:USDCAD", "FX:USDCHF", "FX:NZDUSD", "FX:EURGBP"],
        "description": "Foreign exchange market analysis",
        "detailed_description": "The foreign exchange (Forex) market is the largest financial market globally, with over $6 trillion traded daily. Forex trading involves buying and selling currency pairs, profiting from exchange rate fluctuations. Major pairs like EUR/USD and GBP/USD are most liquid and widely traded. Forex markets are influenced by interest rates, economic data, geopolitical events, and central bank policies. Trading occurs 24/5, offering constant opportunities. Understanding currency correlations, economic calendars, and technical analysis is essential for successful forex trading."
    },
    "metals": {
        "name": "Metals",
        "tickers": ["TVC:GOLD", "TVC:SILVER", "TVC:PLATINUM", "TVC:PALLADIUM", "TVC:COPPER", "TVC:ALUMINUM", "TVC:ZINC", "TVC:NICKEL"],
        "description": "Precious and industrial metals trading",
        "detailed_description": "Metals markets include both precious metals (gold, silver, platinum, palladium) and industrial metals (copper, aluminum, zinc, nickel). Precious metals are often seen as safe-haven assets during economic uncertainty, while industrial metals reflect economic activity and manufacturing demand. Gold and silver are popular for portfolio diversification and inflation hedging. Metal prices are influenced by supply and demand, currency movements (especially USD), geopolitical tensions, and industrial production data. Understanding these factors helps traders navigate metal markets effectively."
    },
    "energy": {
        "name": "Energy",
        "tickers": ["NYMEX:CL1!", "NYMEX:NG1!", "NYMEX:RB1!", "NYMEX:HO1!", "TVC:UKOIL", "TVC:USOIL", "TVC:BRENT", "NYMEX:NG1!"],
        "description": "Energy commodities and futures",
        "detailed_description": "Energy markets encompass crude oil, natural gas, gasoline, and heating oil. These commodities are essential to global economies and are highly sensitive to geopolitical events, supply disruptions, and demand fluctuations. Oil prices (WTI and Brent) are key indicators of economic health. Energy trading involves understanding OPEC decisions, inventory reports, weather patterns (for natural gas), and global economic growth. Energy commodities offer opportunities for both short-term trading and long-term investment, with futures contracts providing leverage and hedging capabilities."
    },
    "bonds": {
        "name": "Bonds",
        "tickers": ["TVC:US10Y", "TVC:US30Y", "TVC:US5Y", "TVC:US2Y", "TVC:T10Y2Y", "TVC:T10Y3M", "TVC:DGS10", "TVC:DGS30"],
        "description": "Bond market yields and analysis",
        "detailed_description": "Bond markets represent debt securities issued by governments and corporations. Bond prices move inversely to yields, making them sensitive to interest rate changes and economic conditions. Government bonds (like US Treasuries) are considered safe-haven assets, while corporate bonds offer higher yields with increased risk. Bond markets are influenced by central bank policies, inflation expectations, credit ratings, and economic data. Understanding yield curves, duration, and credit spreads is crucial for bond trading. Bonds provide portfolio diversification and income generation opportunities."
    },
    "etfs": {
        "name": "ETFs",
        "tickers": ["AMEX:SPY", "NASDAQ:QQQ", "AMEX:IWM", "AMEX:VTI", "AMEX:VOO", "AMEX:ARKK", "AMEX:GLD", "AMEX:SLV"],
        "description": "Exchange-traded funds tracking",
        "detailed_description": "Exchange-Traded Funds (ETFs) are investment funds that trade like stocks and hold a basket of assets. ETFs offer diversification, liquidity, and lower costs compared to individual stocks. They track various indices, sectors, commodities, or strategies. Popular ETFs like SPY (S&P 500) and QQQ (NASDAQ) provide broad market exposure. Sector ETFs allow targeted exposure to specific industries. Understanding ETF composition, expense ratios, and tracking error helps investors choose appropriate funds. ETFs are ideal for both active trading and long-term investing strategies."
    },
    "futures": {
        "name": "Futures",
        "tickers": ["CME:ES1!", "CME:NQ1!", "CBOT:YM1!", "CME:RTY1!", "NYMEX:CL1!", "COMEX:GC1!", "COMEX:SI1!", "COMEX:HG1!"],
        "description": "Futures contracts and derivatives",
        "detailed_description": "Futures contracts are agreements to buy or sell assets at predetermined prices on future dates. Futures markets include equity indices (E-mini S&P 500, NASDAQ), commodities (crude oil, gold), and currencies. Futures offer leverage, allowing traders to control large positions with smaller capital. They're used for speculation, hedging, and portfolio management. Understanding contract specifications, margin requirements, and expiration dates is essential. Futures markets provide liquidity and price discovery, making them valuable tools for both institutional and retail traders."
    },
    "commodities": {
        "name": "Commodities",
        "tickers": ["CBOT:ZC1!", "CBOT:ZS1!", "CBOT:ZW1!", "ICE:KC1!", "ICE:CC1!", "ICE:CT1!", "ICE:SB1!", "ICE:OJ1!"],
        "description": "Agricultural and soft commodities",
        "detailed_description": "Agricultural commodities include grains (corn, wheat, soybeans), soft commodities (coffee, cocoa, sugar, cotton), and livestock. These markets are influenced by weather patterns, crop reports, global demand, and supply chain disruptions. Commodity prices can be volatile due to seasonal factors and geopolitical events. Trading agricultural commodities requires understanding growing seasons, USDA reports, and global trade dynamics. Commodities offer portfolio diversification and can serve as inflation hedges. They're essential for understanding global economic health and food security trends."
    },
    "indian_markets": {
        "name": "Indian Markets",
        "tickers": [
            "NSE:RELIANCE", "NSE:TCS", "NSE:INFY", "NSE:HDFCBANK", "NSE:ICICIBANK",
            "NSE:SBIN", "NSE:BHARTIARTL", "NSE:ITC", "BSE:SENSEX", "NSE:NIFTY"
        ],
        "description": "NSE & BSE — Nifty, Sensex, and India's top listed companies",
        "detailed_description": "India's equity markets are anchored by two exchanges: the National Stock Exchange (NSE) and the Bombay Stock Exchange (BSE). The Nifty 50 tracks the top 50 NSE-listed companies by market cap, while the Sensex tracks the top 30 on the BSE — both are closely correlated benchmarks for the Indian economy. India's market is driven by domestic consumption, IT services exports, banking sector health, and FII/DII (foreign and domestic institutional investor) flows. Understanding sector weightings — IT, banking, energy, and FMCG dominate — along with RBI policy and monsoon-linked agricultural cycles is key to navigating Indian equities."
    }
}

def ratelimit_error_response(request, exception):
    """Friendly JSON response when rate limit is hit."""
    return JsonResponse({
        'error': 'Too many requests. Please wait a moment before trying again.',
        'retry_after_seconds': 60
    }, status=429)

# Feature definitions
FEATURES = [
    {
        "id": "prediction",
        "name": "Prediction",
        "icon": "🔮",
        "description": "Get price predictions for any ticker with date and timeline analysis"
    },
    {
        "id": "news",
        "name": "Trending News",
        "icon": "📰",
        "description": "Latest trending news and market updates"
    },
    {
        "id": "visualizations",
        "name": "Visualizations",
        "icon": "📊",
        "description": "Advanced charts and visualizations for selected tickers"
    },
    {
        "id": "portfolio",
        "name": "Portfolio Management",
        "icon": "💼",
        "description": "Manage and track your investment portfolio"
    },
    {
        "id": "screener",
        "name": "Screener",
        "icon": "🔍",
        "description": "Screen and filter assets based on criteria"
    },
    {
        "id": "risk",
        "name": "Risk Management",
        "icon": "⚠️",
        "description": "Analyze and manage portfolio risk"
    },
    {
        "id": "construction",
        "name": "Portfolio Construction",
        "icon": "🏗️",
        "description": "Build optimized portfolios with asset allocation"
    },
    {
        "id": "analysis",
        "name": "Market Analysis",
        "icon": "📈",
        "description": "Comprehensive market analysis and insights"
    },
    {
        "id": "comparison",
        "name": "Comparison",
        "icon": "⚖️",
        "description": "Compare multiple assets side by side"
    },
    {
        "id": "resources",
        "name": "Resources",
        "icon": "📚",
        "description": "Educational resources and official documentation"
    }
]

RESOURCE_LIBRARY = {
    "stocks": [
        {
            "title": "Investopedia Stock Trading Guide",
            "description": "Plain-language playbook that covers orders, risk controls, and step-by-step walkthroughs.",
            "url": "https://www.investopedia.com/stock-trading-4689732",
            "category": "📘 Guides & Primers"
        },
        {
            "title": "Yahoo Finance Earnings Calendar",
            "description": "Daily refreshed corporate earnings calendar with consensus estimates and surprises.",
            "url": "https://finance.yahoo.com/calendar/earnings",
            "category": "📊 Analytics & Dashboards"
        },
        {
            "title": "AlphaVantage Stock API",
            "description": "Free tier API for quotes, indicators, and fundamental data with sample code.",
            "url": "https://www.alphavantage.co/documentation/",
            "category": "🛠️ Tools & APIs"
        }
    ],
    "crypto": [
        {
            "title": "CoinDesk Crypto Explainer",
            "description": "Beginner friendly hub that explains wallets, custody, and token design.",
            "url": "https://www.coindesk.com/learn/",
            "category": "📘 Guides & Primers"
        },
        {
            "title": "CoinMarketCap Analytics",
            "description": "Live market dashboards with dominance, volumes, and on-chain statistics.",
            "url": "https://coinmarketcap.com/",
            "category": "📊 Analytics & Dashboards"
        },
        {
            "title": "Glassnode Academy",
            "description": "Free on-chain analytics lessons covering UTXO age, exchange flows, and more.",
            "url": "https://academy.glassnode.com/",
            "category": "🎓 Deep Dives"
        }
    ],
    "forex": [
        {
            "title": "BabyPips School of Pipsology",
            "description": "Trusted FX curriculum that covers macro drivers, lot sizing, and playbooks.",
            "url": "https://www.babypips.com/learn/forex",
            "category": "📘 Guides & Primers"
        },
        {
            "title": "DailyFX Economic Calendar",
            "description": "Streaming macro calendar with impact scoring and consensus vs actual readings.",
            "url": "https://www.dailyfx.com/calendar",
            "category": "📊 Analytics & Dashboards"
        },
        {
            "title": "Oanda FX Labs",
            "description": "Open datasets for positioning, volatility, and currency strength meters.",
            "url": "https://www.oanda.com/forex-trading/analysis/",
            "category": "🛠️ Tools & APIs"
        }
    ],
    "default": [
        {
            "title": "OECD Data Explorer",
            "description": "Macro databank for rates, inflation, and trade flows with downloadable CSVs.",
            "url": "https://data.oecd.org/",
            "category": "📊 Analytics & Dashboards"
        },
        {
            "title": "IMF Data Access",
            "description": "International Financial Statistics portal with API support.",
            "url": "https://data.imf.org/",
            "category": "🛠️ Tools & APIs"
        },
        {
            "title": "World Bank Open Knowledge",
            "description": "Collection of market outlooks, research papers, and playbooks for emerging markets.",
            "url": "https://openknowledge.worldbank.org/",
            "category": "🎓 Deep Dives"
        }
    ]
}

SCREENER_DEFAULT_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA",
    "META", "NFLX", "JPM", "BAC", "V", "MA"
]

LIVE_NEWS_CATEGORIES = {
    "stocks": "business",
    "indices": "business",
    "bonds": "business",
    "etfs": "business",
    "crypto": "technology",
    "forex": "business",
    "metals": "science",
    "energy": "science",
    "futures": "business",
    "commodities": "science",
}

DEFAULT_NEWS_FALLBACK = [
    {
        "title": "FinSight Macro Watch: Global Risk Radar",
        "publisher": "FinSight Research Desk",
        "link": "https://www.imf.org/en/Topics/imf-and-covid19",
        "type": "analysis",
        "related_tickers": [],
        "published_at": datetime.now(tz=dt_timezone.utc).isoformat(),
        "summary": "Global PMIs and cross-asset volatility dashboards updated for the current macro regime."
    },
    {
        "title": "World Bank Commodity Outlook Released",
        "publisher": "World Bank",
        "link": "https://www.worldbank.org/en/research/commodity-markets",
        "type": "breaking",
        "related_tickers": [],
        "published_at": datetime.now(tz=dt_timezone.utc).isoformat(),
        "summary": "Fresh guidance on metals, energy, and agri demand with scenario analysis for 2026."
    },
    {
        "title": "SEC Investor Bulletin: Understanding Market Orders",
        "publisher": "SEC",
        "link": "https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins",
        "type": "regulation",
        "related_tickers": [],
        "published_at": datetime.now(tz=dt_timezone.utc).isoformat(),
        "summary": "Plain-English refresher on order routing, best execution, and protection rules."
    }
]


def slugify_title(title):
    if not title:
        return ""
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    return slug


def _parse_inshorts_timestamp(item):
    timestamp = item.get("timestamp")
    if timestamp:
        try:
            return datetime.fromtimestamp(int(timestamp), tz=dt_timezone.utc).isoformat()
        except Exception:
            pass
    date_str = item.get("date")
    time_str = item.get("time")
    if date_str and time_str:
        # Incoming format example: "18 Oct 2024,Friday" and "09:25 am"
        try:
            cleaned_date = date_str.split(",")[0].strip()
            combined = f"{cleaned_date} {time_str.upper()}"
            parsed = datetime.strptime(combined, "%d %b %Y %I:%M %p")
            return parsed.replace(tzinfo=dt_timezone.utc).isoformat()
        except Exception:
            pass
    return datetime.now(tz=dt_timezone.utc).isoformat()


def fetch_live_news_from_api(market, limit=12):
    """Fetch latest headlines from Inshorts, falling back silently on failure."""
    category = LIVE_NEWS_CATEGORIES.get(market, "business")
    try:
        response = requests.get(
            "https://inshortsapi.vercel.app/news",
            params={"category": category},
            headers={"Cache-Control": "no-cache"},
            timeout=6
        )
        response.raise_for_status()
        payload = response.json() or {}
        data = payload.get("data", [])
        articles = []
        for item in data:
            link = None
            if item.get("id"):
                slug = slugify_title(item.get("title", ""))
                link = f"https://inshorts.com/en/news/{slug}-{item.get('id')}"
            link = link or item.get("readMoreUrl") or item.get("url")
            if not link:
                continue
            articles.append({
                "title": item.get("title", "Live Market Update"),
                "publisher": item.get("author") or payload.get("category") or "Inshorts Live Desk",
                "link": link,
                "type": (item.get("category") or category or "general").lower(),
                "related_tickers": [],
                "published_at": _parse_inshorts_timestamp(item),
                "summary": item.get("content") or "Tap to read the full story on Inshorts."
            })
            if len(articles) >= limit:
                break
        return articles
    except Exception:
        return []


def compute_rsi(series, window=14):
    """Compute RSI for a pandas Series"""
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    roll_up = up.rolling(window=window).mean()
    roll_down = down.rolling(window=window).mean()
    rs = roll_up / roll_down.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi

TICKER_OVERRIDES = {
    "SP:SPX": "^GSPC",
    "DJ:DJI": "^DJI",
    "NASDAQ:IXIC": "^IXIC",
    "RUT": "^RUT",
    "CBOE:VIX": "^VIX",
    "LSE:UKX": "^FTSE",
    "TSE:NKY": "^N225",
    "XETR:DAX": "^GDAXI",
    "TVC:US10Y": "^TNX",
    "TVC:US30Y": "^TYX",
    "TVC:US5Y": "^FVX",
    "TVC:US2Y": "^IRX",
    "TVC:T10Y2Y": "T10Y2Y",
    "TVC:T10Y3M": "T10Y3M",
    "TVC:DGS10": "DGS10",
    "TVC:DGS30": "DGS30",
    "TVC:GOLD": "GC=F",
    "TVC:SILVER": "SI=F",
    "TVC:PLATINUM": "PL=F",
    "TVC:PALLADIUM": "PA=F",
    "TVC:COPPER": "HG=F",
    "TVC:ALUMINUM": "ALI=F",
    "TVC:ZINC": "ZNC=F",
    "TVC:NICKEL": "NI=F",
    "TVC:UKOIL": "BZ=F",
    "TVC:USOIL": "CL=F",
    "TVC:BRENT": "BZ=F",
    "NYMEX:CL1!": "CL=F",
    "NYMEX:NG1!": "NG=F",
    "NYMEX:RB1!": "RB=F",
    "NYMEX:HO1!": "HO=F",
    "CME:ES1!": "ES=F",
    "CME:NQ1!": "NQ=F",
    "CBOT:YM1!": "YM=F",
    "CME:RTY1!": "RTY=F",
    "COMEX:GC1!": "GC=F",
    "COMEX:SI1!": "SI=F",
    "COMEX:HG1!": "HG=F",
    "CBOT:ZC1!": "ZC=F",
    "CBOT:ZS1!": "ZS=F",
    "CBOT:ZW1!": "ZW=F",
    "ICE:KC1!": "KC=F",
    "ICE:CC1!": "CC=F",
    "ICE:CT1!": "CT=F",
    "ICE:SB1!": "SB=F",
    "ICE:OJ1!": "OJ=F",
}


def get_resource_sections(market):
    custom = RESOURCE_LIBRARY.get(market, [])
    fallback = RESOURCE_LIBRARY.get("default", []) if market != "default" else []
    combined = custom + fallback
    sections = OrderedDict()
    for entry in combined:
        category = entry.get("category", "Resources")
        sections.setdefault(category, []).append(entry)
    result = []
    for category, items in sections.items():
        result.append({
            "category": category,
            "items": items
        })
    return result


def normalize_ticker_for_yfinance(symbol):
    if not symbol:
        return None
    original = symbol
    symbol = symbol.upper()
    if symbol in TICKER_OVERRIDES:
        return TICKER_OVERRIDES[symbol]
    if ":" in symbol:
        prefix, code = symbol.split(":", 1)
    else:
        prefix, code = "", symbol
    candidate = TICKER_OVERRIDES.get(code)
    if candidate:
        return candidate
    if prefix in {"NASDAQ", "NYSE", "AMEX"}:
        return code
    if prefix == "BINANCE":
        base = code.replace("USDT", "").replace("USD", "")
        return f"{base}-USD"
    if prefix == "FX":
        return f"{code}=X"
    if prefix in {"TVC", "CBOE"}:
        # Some TradingView symbols map to FRED style without prefix
        return TICKER_OVERRIDES.get(original, code)
    if prefix in {"NYMEX", "CME", "CBOT", "COMEX", "ICE"} or "!" in code:
        clean = code.replace("1", "").replace("!", "")
        if clean.endswith("1"):
            clean = clean[:-1]
        return f"{clean}=F"
    if prefix == "CRYPTO":
        base = code.replace("USD", "").replace("USDT", "")
        return f"{base}-USD"
    return code


def short_symbol(symbol):
    return symbol.split(":")[-1] if ":" in symbol else symbol

def format_symbol_for_tradingview(symbol, market_type):
    """Format symbol for TradingView compatibility"""
    if not symbol:
        return "SPX"  # Default fallback
    
    # If already formatted with exchange, return as is
    if ":" in symbol:
        return symbol
    
    # Format based on market type
    if market_type == "stocks":
        # Try NASDAQ first, fallback to NYSE
        if symbol in ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "META", "NVDA", "NFLX"]:
            return f"NASDAQ:{symbol}"
        return f"NYSE:{symbol}"
    
    elif market_type == "crypto":
        # TradingView crypto format
        if symbol.endswith("USD") or symbol.endswith("USDT"):
            base = symbol.replace("USD", "").replace("USDT", "")
            return f"BINANCE:{base}USDT"
        return f"BINANCE:{symbol}USDT"
    
    elif market_type == "indices":
        # Common index mappings
        index_map = {
            "SPX": "SP:SPX",
            "DJI": "DJ:DJI",
            "IXIC": "NASDAQ:IXIC",
            "RUT": "RUT",
            "VIX": "CBOE:VIX",
            "FTSE": "LSE:UKX",
            "N225": "TSE:NKY",
            "GDAXI": "XETR:DAX"
        }
        return index_map.get(symbol, symbol)
    
    elif market_type == "forex":
        # Forex pairs
        if not symbol.startswith("FX:"):
            return f"FX:{symbol}"
        return symbol
    
    elif market_type == "metals":
        # Metals mapping
        metal_map = {
            "XAUUSD": "TVC:GOLD",
            "XAGUSD": "TVC:SILVER",
            "XPTUSD": "TVC:PLATINUM",
            "XPDUSD": "TVC:PALLADIUM"
        }
        return metal_map.get(symbol, f"TVC:{symbol}")
    
    elif market_type == "energy":
        # Energy futures
        if "!" in symbol:
            if symbol.startswith("CL"):
                return f"NYMEX:{symbol}"
            elif symbol.startswith("NG"):
                return f"NYMEX:{symbol}"
        return symbol
    
    elif market_type == "bonds":
        # Bond yields
        bond_map = {
            "10Y": "TVC:US10Y",
            "30Y": "TVC:US30Y",
            "5Y": "TVC:US5Y",
            "2Y": "TVC:US2Y"
        }
        return bond_map.get(symbol, f"TVC:{symbol}")
    
    elif market_type == "etfs":
        # ETFs - most are on AMEX
        etf_exchanges = {
            "SPY": "AMEX",
            "QQQ": "NASDAQ",
            "IWM": "AMEX",
            "VTI": "AMEX",
            "VOO": "AMEX"
        }
        exchange = etf_exchanges.get(symbol, "AMEX")
        return f"{exchange}:{symbol}"
    
    elif market_type == "futures":
        # Futures with exchange prefixes
        if "!" in symbol:
            if symbol.startswith("ES") or symbol.startswith("NQ") or symbol.startswith("RTY"):
                return f"CME:{symbol}"
            elif symbol.startswith("YM"):
                return f"CBOT:{symbol}"
            elif symbol.startswith("CL") or symbol.startswith("NG"):
                return f"NYMEX:{symbol}"
            elif symbol.startswith("GC") or symbol.startswith("SI") or symbol.startswith("HG"):
                return f"COMEX:{symbol}"
    
    elif market_type == "commodities":
        # Commodities futures
        if "!" in symbol:
            if symbol.startswith("ZC") or symbol.startswith("ZS") or symbol.startswith("ZW"):
                return f"CBOT:{symbol}"
            elif symbol.startswith("KC") or symbol.startswith("CC") or symbol.startswith("CT") or symbol.startswith("SB") or symbol.startswith("OJ"):
                return f"ICE:{symbol}"
    
    # Default: return as is
    return symbol

def home(request):
    context = {
        "markets_json": json.dumps(MARKETS),
        "default_market": "stocks",
        "tickers_json": json.dumps([t.replace("NASDAQ:", "") for t in MARKETS["stocks"]["tickers"]]),
    }
    return render(request, "home.html", context)

def safe_id(symbol):
    """Create a safe ID from symbol by removing special characters"""
    if not symbol:
        return "default"
    # Remove special characters and keep only alphanumeric and underscore
    import re
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', symbol)
    return safe

def market_detail(request, market):
    if market not in MARKETS:
        market = "stocks"
    
    market_data = MARKETS[market]
    # Extract display names (without exchange prefixes for display)
    display_tickers = [t.split(":")[-1] if ":" in t else t for t in market_data["tickers"]]
    
    # Create charts with safe IDs
    charts_data = []
    for i, ticker in enumerate(market_data["tickers"][:4]):
        charts_data.append({
            "symbol": ticker,
            "display": display_tickers[i],
            "safe_id": safe_id(ticker)
        })
    
    context = {
        "page_title": f"{market_data['name']} Market",
        "page_description": market_data.get("detailed_description", market_data["description"]),
        "market_name": market,
        "market_type": market,
        "charts": charts_data,
        "features": FEATURES,
        "tickers": market_data["tickers"],  # Full formatted tickers for TradingView
        "display_tickers": display_tickers,  # Display names for UI
    }
    return render(request, "market_detail.html", context)

def feature_view(request, market, feature_id):
    if market not in MARKETS:
        market = "stocks"
    
    feature = next((f for f in FEATURES if f["id"] == feature_id), None)
    if not feature:
        feature = FEATURES[0]
    
    market_data = MARKETS[market]
    display_tickers = [t.split(":")[-1] if ":" in t else t for t in market_data["tickers"]]
    
    context = {
        "market": market,
        "market_name": market_data["name"],
        "market_type": market,
        "feature": feature,
        "tickers": market_data["tickers"],  # Full formatted for TradingView
        "display_tickers": display_tickers,  # Display names for dropdowns
    }
    if feature_id == "resources":
        context["resource_sections"] = get_resource_sections(market)
    else:
        context["resource_sections"] = []
    
    template_map = {
        "prediction": "features/prediction.html",
        "news": "features/news.html",
        "visualizations": "features/visualizations.html",
        "portfolio": "features/portfolio.html",
        "screener": "features/screener.html",
        "risk": "features/risk.html",
        "construction": "features/construction.html",
        "analysis": "features/analysis.html",
        "comparison": "features/comparison.html",
        "resources": "features/resources.html",
    }
    
    template = template_map.get(feature_id, "features/prediction.html")
    return render(request, template, context)

@ratelimit(key='ip', rate='10/m', method='POST', block=True)
@require_http_methods(["POST"])
def predict_price_api(request):
    """API endpoint for price prediction"""
    try:
        data = json.loads(request.body)
        ticker = data.get('ticker', '')
        target_date = data.get('target_date', '')
        timeline = data.get('timeline', '1m')
        market_type = data.get('market_type', 'stocks')
        
        if not ticker:
            return JsonResponse({'error': 'Ticker is required'}, status=400)
        
        # Map timeline to days
        timeline_days = {
            '1d': 1,
            '1w': 7,
            '1m': 30,
            '3m': 90,
            '6m': 180,
            '1y': 365
        }
        days_ahead = timeline_days.get(timeline, 30)
        
        result = services.get_prediction(ticker, days_ahead, market_type)
        
        if result is None:
            return JsonResponse({
                'error': 'Unable to fetch data or make prediction. Please try a different ticker.'
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'ticker': ticker,
            'current_price': result['current_price'],
            'predicted_price': result['predicted_price'],
            'price_change': result['price_change'],
            'price_change_pct': result['price_change_pct'],
            'confidence': result['confidence'],
            'timeline': timeline,
            'target_date': target_date,
            'model_metrics': result.get('metrics', {}),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@ratelimit(key='ip', rate='10/m', method='POST', block=True)
@require_http_methods(["POST"])
def risk_analysis_api(request):
    """API endpoint for risk analysis"""
    try:
        data = json.loads(request.body)
        ticker = data.get('ticker', '')
        market_type = data.get('market_type', '')
        
        if not ticker:
            return JsonResponse({'error': 'Ticker is required'}, status=400)
        
        metrics = services.get_risk_analysis(ticker, market_type)
        
        if metrics is None:
            return JsonResponse({
                'error': 'Unable to calculate risk metrics. Please try a different ticker.'
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'ticker': ticker,
            'metrics': metrics
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@ratelimit(key='ip', rate='10/m', method='POST', block=True)
@require_http_methods(["POST"])
def optimize_portfolio_api(request):
    """API endpoint for portfolio optimization"""
    try:
        data = json.loads(request.body)
        tickers = data.get('tickers', [])
        risk_tolerance = data.get('risk_tolerance', 'moderate')
        investment_amount = float(data.get('investment_amount', 100000))
        
        if not tickers or len(tickers) < 2:
            return JsonResponse({'error': 'At least 2 tickers are required'}, status=400)
        
        # Clean tickers for yfinance (remove exchange prefixes)
        clean_tickers = [t.split(":")[-1] if ":" in t else t for t in tickers]
        
        result = services.get_portfolio_optimization(clean_tickers, risk_tolerance, investment_amount)
        
        if result is None:
            return JsonResponse({
                'error': 'Unable to optimize portfolio. Please try different tickers.'
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'allocation': result['allocation'],
            'expected_return': result['expected_return'],
            'expected_volatility': result['expected_volatility'],
            'sharpe_ratio': result['sharpe_ratio'],
            'efficient_frontier': result.get('efficient_frontier', []),
            'optimizer': result.get('optimizer', 'scipy'),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def market_news_api(request):
    """Return aggregated market news for a given market."""
    market = request.GET.get('market', 'stocks').lower()
    limit = int(request.GET.get('limit', 12))
    if market not in MARKETS:
        market = 'stocks'

    from django.core.cache import cache
    cache_key = f"news:{market}:{limit}"
    cached_articles = cache.get(cache_key)
    if cached_articles:
        cached_response = JsonResponse({'success': True, 'market': market, 'articles': cached_articles, 'cached': True})
        cached_response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return cached_response

    tickers = MARKETS[market]['tickers']
    articles = fetch_live_news_from_api(market, limit=limit)
    seen_links = set()

    for article in articles:
        seen_links.add(article['link'])

    for symbol in tickers:
        normalized = normalize_ticker_for_yfinance(symbol)
        if not normalized:
            continue
        try:
            ticker_obj = yf.Ticker(normalized)
            ticker_news = getattr(ticker_obj, 'news', []) or []
        except Exception:
            ticker_news = []

        for item in ticker_news:
            link = item.get('link')
            if not link or link in seen_links:
                continue
            seen_links.add(link)

            published_ts = item.get('providerPublishTime') or item.get('published_at')
            if published_ts:
                try:
                    published_at = datetime.fromtimestamp(int(published_ts), tz=dt_timezone.utc).isoformat()
                except Exception:
                    published_at = None
            else:
                published_at = None

            articles.append({
                'title': item.get('title') or 'Untitled Story',
                'publisher': item.get('publisher') or item.get('provider') or 'Unknown',
                'link': link,
                'type': item.get('type') or 'general',
                'related_tickers': item.get('relatedTickers') or item.get('symbols') or [],
                'published_at': published_at,
                'summary': item.get('summary') or item.get('description')
            })

            if len(articles) >= limit:
                break

        if len(articles) >= limit:
            break

    if not articles:
        articles = DEFAULT_NEWS_FALLBACK[:limit]

    if articles:
        cache.set(cache_key, articles, 300)  # 5 min cache

    response = JsonResponse({
        'success': True,
        'market': market,
        'articles': articles
    })
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@require_http_methods(["POST"])
def portfolio_snapshot_api(request):
    """Aggregate holdings level analytics for the portfolio page."""
    try:
        data = json.loads(request.body)
        holdings = data.get('holdings', [])
        if not holdings:
            return JsonResponse({'error': 'Add at least one holding first.'}, status=400)
        
        history_frames = []
        quantity_map = {}
        enriched = []
        total_value = 0.0
        total_cost = 0.0
        
        for entry in holdings[:15]:
            ticker = (entry.get('ticker') or '').strip().upper()
            quantity = float(entry.get('quantity') or 0)
            cost_basis = float(entry.get('cost_basis') or 0)
            if not ticker or quantity <= 0:
                continue
            
            normalized = normalize_ticker_for_yfinance(ticker)
            if not normalized:
                continue
            
            try:
                ticker_obj = yf.Ticker(normalized)
                hist = ticker_obj.history(period='6mo', interval='1d')
            except Exception:
                continue
            
            if hist.empty or 'Close' not in hist:
                continue
            
            close = hist['Close']
            current_price = float(close.iloc[-1])
            start_price = float(close.iloc[0])
            change_pct = ((current_price - start_price) / start_price) * 100 if start_price else 0
            basis_price = cost_basis if cost_basis > 0 else start_price
            position_cost = basis_price * quantity
            current_value = current_price * quantity
            gain = current_value - position_cost
            
            enriched.append({
                'ticker': ticker,
                'quantity': round(quantity, 4),
                'current_price': round(current_price, 2),
                'current_value': round(current_value, 2),
                'cost_basis': round(basis_price, 2),
                'gain': round(gain, 2),
                'gain_pct': round((gain / position_cost) * 100, 2) if position_cost else 0,
                'change_pct': round(change_pct, 2)
            })
            quantity_map[ticker] = quantity
            history_frames.append(close.rename(ticker))
            total_value += current_value
            total_cost += position_cost
        
        if not enriched:
            return JsonResponse({'error': 'Unable to load live prices for those holdings.'}, status=400)
        
        history_df = pd.concat(history_frames, axis=1).ffill().dropna()
        weighted = history_df.mul(pd.Series(quantity_map))
        portfolio_series = weighted.sum(axis=1)
        history_payload = [
            {'date': idx.strftime('%Y-%m-%d'), 'value': round(val, 2)}
            for idx, val in portfolio_series.items()
        ]
        distribution = [
            {'label': row['ticker'], 'value': row['current_value']}
            for row in enriched
        ]
        total_gain = total_value - total_cost

        returns_histogram = []
        volatility_series = []
        returns = portfolio_series.pct_change().dropna()
        if not returns.empty:
            hist, edges = np.histogram(returns, bins=15)
            for i in range(len(hist)):
                bucket = f"{round(edges[i]*100, 2)}% to {round(edges[i+1]*100, 2)}%"
                returns_histogram.append({'bucket': bucket, 'count': int(hist[i])})
            rolling_vol = returns.rolling(window=5).std().dropna() * np.sqrt(252) * 100
            volatility_series = [
                {'date': idx.strftime('%Y-%m-%d'), 'value': round(val, 2)}
                for idx, val in rolling_vol.items()
            ]
        
        return JsonResponse({
            'success': True,
            'summary': {
                'total_value': round(total_value, 2),
                'total_cost': round(total_cost, 2),
                'total_gain': round(total_gain, 2),
                'total_gain_pct': round((total_gain / total_cost) * 100, 2) if total_cost else 0
            },
            'holdings': enriched,
            'history': history_payload,
            'distribution': distribution,
            'returns_histogram': returns_histogram,
            'volatility_series': volatility_series
        })
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@require_http_methods(["POST"])
def screener_api(request):
    """Filter tickers by user supplied thresholds."""
    try:
        data = json.loads(request.body)
        market = data.get('market', 'stocks')
        filters = data.get('filters', {})
        custom_tickers = data.get('tickers') or []
        base = custom_tickers or MARKETS.get(market, MARKETS['stocks'])['tickers']
        tickers = base[:20]
        results = []
        
        price_min = float(filters.get('price_min') or 0)
        price_max = float(filters.get('price_max') or 0)
        change_filter = filters.get('change_direction')
        pe_min = float(filters.get('pe_min') or 0)
        pe_max = float(filters.get('pe_max') or 0)
        div_min = float(filters.get('dividend_min') or 0)
        
        for symbol in tickers:
            normalized = normalize_ticker_for_yfinance(symbol)
            if not normalized:
                continue
            try:
                ticker_obj = yf.Ticker(normalized)
                hist = ticker_obj.history(period='1mo', interval='1d')
            except Exception:
                continue
            if hist.empty or 'Close' not in hist:
                continue
            
            last_close = float(hist['Close'].iloc[-1])
            first_close = float(hist['Close'].iloc[0])
            change_pct = ((last_close - first_close) / first_close) * 100 if first_close else 0
            volume = int(hist['Volume'].iloc[-1]) if 'Volume' in hist else 0
            fast_info = getattr(ticker_obj, 'fast_info', {}) or {}
            market_cap = fast_info.get('market_cap')
            pe_ratio = fast_info.get('trailing_pe') or fast_info.get('pe_ratio')
            dividend_yield = fast_info.get('dividend_yield') or 0
            
            if price_min and last_close < price_min:
                continue
            if price_max and price_max > 0 and last_close > price_max:
                continue
            if change_filter == 'gainers' and change_pct < 0:
                continue
            if change_filter == 'losers' and change_pct > 0:
                continue
            if pe_min and (not pe_ratio or pe_ratio < pe_min):
                continue
            if pe_max and pe_ratio and pe_ratio > pe_max:
                continue
            if div_min and dividend_yield * 100 < div_min:
                continue
            
            results.append({
                'ticker': short_symbol(symbol),
                'price': round(last_close, 2),
                'change_pct': round(change_pct, 2),
                'volume': volume,
                'market_cap': market_cap,
                'pe_ratio': round(pe_ratio, 2) if pe_ratio else None,
                'dividend_yield': round(dividend_yield * 100, 2) if dividend_yield else None
            })
        
        if not results and not custom_tickers:
            for fallback in SCREENER_DEFAULT_SYMBOLS:
                normalized = normalize_ticker_for_yfinance(fallback)
                if not normalized:
                    continue
                try:
                    ticker_obj = yf.Ticker(normalized)
                    hist = ticker_obj.history(period='1mo', interval='1d')
                except Exception:
                    continue
                if hist.empty or 'Close' not in hist:
                    continue
                last_close = float(hist['Close'].iloc[-1])
                first_close = float(hist['Close'].iloc[0])
                change_pct = ((last_close - first_close) / first_close) * 100 if first_close else 0
                results.append({
                    'ticker': fallback,
                    'price': round(last_close, 2),
                    'change_pct': round(change_pct, 2),
                    'volume': int(hist['Volume'].iloc[-1]) if 'Volume' in hist else None,
                    'market_cap': getattr(ticker_obj, 'fast_info', {}).get('market_cap'),
                    'pe_ratio': getattr(ticker_obj, 'fast_info', {}).get('trailing_pe'),
                    'dividend_yield': getattr(ticker_obj, 'fast_info', {}).get('dividend_yield')
                })
                if len(results) >= 5:
                    break
        
        return JsonResponse({'success': True, 'results': results})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@require_http_methods(["POST"])
def comparison_api(request):
    """Return head-to-head metrics and normalized price series for comparison feature."""
    try:
        data = json.loads(request.body)
        tickers = data.get('tickers', [])
        period = data.get('period', '3m')
        if len(tickers) < 2:
            return JsonResponse({'error': 'Select at least two tickers to compare.'}, status=400)
        
        period_map = {
            '1m': ('1mo', '1d'),
            '3m': ('3mo', '1d'),
            '6m': ('6mo', '1d'),
            '1y': ('1y', '1wk')
        }
        yf_period, interval = period_map.get(period, ('3mo', '1d'))
        
        frames = []
        assets = []
        
        for symbol in tickers[:5]:
            normalized = normalize_ticker_for_yfinance(symbol)
            if not normalized:
                continue
            short = short_symbol(symbol)
            try:
                ticker_obj = yf.Ticker(normalized)
                hist = ticker_obj.history(period=yf_period, interval=interval)
            except Exception:
                continue
            if hist.empty or 'Close' not in hist:
                continue
            
            close = hist['Close']
            last_close = float(close.iloc[-1])
            first_close = float(close.iloc[0])
            change_pct = ((last_close - first_close) / first_close) * 100 if first_close else 0
            fast_info = getattr(ticker_obj, 'fast_info', {}) or {}
            volume = int(hist['Volume'].iloc[-1]) if 'Volume' in hist else 0
            pe_ratio = fast_info.get('trailing_pe') or fast_info.get('pe_ratio')
            div_yield = fast_info.get('dividend_yield')
            fifty_two_high = fast_info.get('year_high')
            fifty_two_low = fast_info.get('year_low')
            rsi_series = compute_rsi(close)
            rsi_value = float(rsi_series.iloc[-1]) if not rsi_series.empty else None
            
            assets.append({
                'ticker': short,
                'price': round(last_close, 2),
                'change_pct': round(change_pct, 2),
                'market_cap': fast_info.get('market_cap'),
                'volume': volume,
                'pe_ratio': round(pe_ratio, 2) if pe_ratio else None,
                'dividend_yield': round(div_yield * 100, 2) if div_yield else None,
                'fifty_two_week_high': round(fifty_two_high, 2) if fifty_two_high else None,
                'fifty_two_week_low': round(fifty_two_low, 2) if fifty_two_low else None,
                'rsi': round(rsi_value, 2) if rsi_value else None
            })
            frames.append(close.rename(short))
        
        if not assets:
            return JsonResponse({'error': 'Unable to load market data for your selection.'}, status=400)
        
        chart = {'labels': [], 'series': []}
        if frames:
            chart_df = pd.concat(frames, axis=1).ffill().dropna()
            chart['labels'] = [idx.strftime('%Y-%m-%d') for idx in chart_df.index]
            for column in chart_df.columns:
                chart['series'].append({
                    'label': column,
                    'data': [round(val, 2) for val in chart_df[column].tolist()]
                })
        
        return JsonResponse({'success': True, 'assets': assets, 'chart': chart})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@require_http_methods(["GET"])
def ticker_search_api(request):
    """Proxy Yahoo Finance autocomplete to unlock any public ticker."""
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'success': True, 'results': []})
    try:
        resp = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": query, "quotesCount": 10, "newsCount": 0},
            timeout=5
        )
        resp.raise_for_status()
        payload = resp.json() or {}
        quotes = payload.get('quotes', [])
        results = []
        for quote in quotes:
            symbol = quote.get('symbol')
            name = quote.get('shortname') or quote.get('longname')
            if not symbol or not name:
                continue
            results.append({
                'symbol': symbol.upper(),
                'name': name,
                'exchange': quote.get('exchDisp') or quote.get('exchange'),
                'type': quote.get('typeDisp'),
            })
        return JsonResponse({'success': True, 'results': results})
    except Exception as exc:
        return JsonResponse({'success': False, 'results': [], 'error': str(exc)}, status=500)
    
@require_http_methods(["GET"])
@ratelimit(key='ip', rate='20/m', method='GET', block=True)
def market_analysis_api(request, market):
    """Return real, aggregated market analysis (replaces hardcoded template values)."""
    if market not in MARKETS:
        return JsonResponse({'error': 'Unknown market'}, status=404)

    tickers = MARKETS[market]['tickers']
    analysis = services.get_market_analysis(market, tickers)

    if analysis is None:
        return JsonResponse({'error': 'Unable to fetch market analysis right now.'}, status=503)

    return JsonResponse({'success': True, 'market': market, 'analysis': analysis})

@require_http_methods(["GET"])
def model_health_page(request):
    """Server-rendered dashboard showing real ModelMetrics history per ticker."""
    health = services.get_model_health()
    return render(request, "model_health.html", {"health": health})

@require_http_methods(["GET"])
def how_it_works_page(request):
    return render(request, "how_it_works.html", {})