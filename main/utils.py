"""
FinSight Utility Functions
Common validation, sanitization, and helper functions.
"""
import re
from datetime import datetime
from typing import Optional


def validate_ticker(ticker: str) -> tuple[bool, str]:
    """
    Validate ticker symbol format.
    Returns (is_valid, error_message)
    """
    if not ticker or not isinstance(ticker, str):
        return False, "Ticker is required"
    
    ticker = ticker.strip()
    if not ticker:
        return False, "Ticker cannot be empty"
    
    if len(ticker) > 50:
        return False, "Ticker symbol too long (max 50 characters)"
    
    # Allow alphanumeric, dots, colons, hyphens, exclamation marks, carets
    if not re.match(r'^[A-Za-z0-9:.^!\-]+$', ticker):
        return False, "Ticker contains invalid characters"
    
    return True, ""


def validate_date(date_str: str) -> tuple[bool, str, Optional[datetime]]:
    """
    Validate date string format (YYYY-MM-DD).
    Returns (is_valid, error_message, parsed_date)
    """
    if not date_str:
        return True, "", None  # Date is optional
    
    try:
        parsed = datetime.strptime(date_str, '%Y-%m-%d')
        return True, "", parsed
    except ValueError:
        return False, "Invalid date format. Use YYYY-MM-DD", None


def validate_timeline(timeline: str) -> tuple[bool, str]:
    """
    Validate timeline selection.
    Returns (is_valid, error_message)
    """
    valid_timelines = ['1d', '1w', '1m', '3m', '6m', '1y']
    
    if not timeline:
        return False, "Timeline is required"
    
    if timeline not in valid_timelines:
        return False, f"Invalid timeline. Must be one of: {', '.join(valid_timelines)}"
    
    return True, ""


def validate_risk_tolerance(risk_tolerance: str) -> tuple[bool, str]:
    """
    Validate risk tolerance selection.
    Returns (is_valid, error_message)
    """
    valid_options = ['conservative', 'moderate', 'aggressive']
    
    if not risk_tolerance:
        return False, "Risk tolerance is required"
    
    if risk_tolerance not in valid_options:
        return False, f"Invalid risk tolerance. Must be one of: {', '.join(valid_options)}"
    
    return True, ""


def validate_investment_amount(amount: any) -> tuple[bool, str, Optional[float]]:
    """
    Validate investment amount.
    Returns (is_valid, error_message, parsed_amount)
    """
    try:
        amount_float = float(amount)
        if amount_float <= 0:
            return False, "Investment amount must be greater than 0", None
        if amount_float > 1_000_000_000:  # 1 billion limit
            return False, "Investment amount exceeds maximum limit", None
        return True, "", amount_float
    except (ValueError, TypeError):
        return False, "Invalid investment amount", None


def validate_tickers_list(tickers: list, min_count: int = 2, max_count: int = 10) -> tuple[bool, str]:
    """
    Validate list of tickers.
    Returns (is_valid, error_message)
    """
    if not tickers or not isinstance(tickers, list):
        return False, "Tickers list is required"
    
    if len(tickers) < min_count:
        return False, f"At least {min_count} tickers are required"
    
    if len(tickers) > max_count:
        return False, f"Maximum {max_count} tickers allowed"
    
    # Validate each ticker
    for ticker in tickers:
        is_valid, error = validate_ticker(ticker)
        if not is_valid:
            return False, f"Invalid ticker '{ticker}': {error}"
    
    return True, ""


def validate_period(period: str) -> tuple[bool, str]:
    """
    Validate time period selection.
    Returns (is_valid, error_message)
    """
    valid_periods = ['1m', '3m', '6m', '1y']
    
    if not period:
        return False, "Period is required"
    
    if period not in valid_periods:
        return False, f"Invalid period. Must be one of: {', '.join(valid_periods)}"
    
    return True, ""


def sanitize_text(text: str, max_length: int = 1000) -> str:
    """
    Sanitize text input by stripping whitespace and limiting length.
    """
    if not text:
        return ""
    return text.strip()[:max_length]


def validate_market(market: str) -> tuple[bool, str]:
    """
    Validate market type.
    Returns (is_valid, error_message)
    """
    valid_markets = [
        'stocks', 'crypto', 'indices', 'forex', 'metals',
        'energy', 'bonds', 'etfs', 'futures', 'commodities',
        'indian_markets'
    ]
    
    if not market:
        return False, "Market type is required"
    
    if market not in valid_markets:
        return False, f"Invalid market type. Must be one of: {', '.join(valid_markets)}"
    
    return True, ""