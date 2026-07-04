import logging
import csv
import requests
from io import StringIO
from typing import Dict, Any

logger = logging.getLogger("void.stocks_control")

def get_stock_quote(ticker: str) -> Dict[str, Any]:
    """
    Performs basic quote lookup (price, change, percent change) for a ticker symbol.
    Uses the free Stooq CSV endpoint (no API key required).
    """
    if not ticker or not ticker.strip():
        return {"status": "error", "message": "Ticker symbol is required, Sir."}
        
    symbol = ticker.strip().upper()
    
    # Normalize ticker: if no suffix (e.g., Apple as AAPL), default to US market (.US)
    # Stooq requires specific market suffixes, e.g., AAPL.US, BTC.V, ^DJI
    if "." not in symbol and not symbol.startswith("^"):
        symbol = f"{symbol}.US"
        
    headers = {"User-Agent": "VOID/2.0 Stocks Module"}
    url = f"https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlc1&e=csv"
    
    try:
        logger.info(f"[STOCKS] Fetching quote from Stooq: {url}")
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        # Read CSV data
        csv_data = resp.text
        f = StringIO(csv_data)
        reader = csv.DictReader(f)
        
        rows = list(reader)
        if not rows:
            return {"status": "error", "message": f"Empty response received from quote service for '{symbol}'."}
            
        row = rows[0]
        
        # Check if the symbol was not found (Close/Price will be empty or N/A)
        price_str = row.get("Close") or row.get("Price")
        if not price_str or price_str.upper() == "N/A" or price_str == "":
            return {"status": "error", "message": f"Could not find stock quote or ticker symbol '{symbol}', Sir."}
            
        try:
            price = float(price_str)
            change = float(row.get("Change", "0.0") or 0.0)
            
            # Open price
            open_price_str = row.get("Open")
            open_price = float(open_price_str) if open_price_str else None
            
            if open_price:
                pct_change = (change / open_price) * 100.0
            else:
                pct_change = 0.0
                
        except ValueError:
            # Fallback if parsing floats fails
            return {"status": "error", "message": f"Failed to parse stock quote values for '{symbol}'."}
            
        date = row.get("Date", "N/A")
        time_val = row.get("Time", "N/A")
        
        sign = "+" if change > 0 else ""
        pct_sign = "+" if pct_change > 0 else ""
        
        report = (
            f"📈 **Stock Quote for {symbol}**:\n"
            f"- **Latest Price**: ${price:.2f}\n"
            f"- **Net Change**: {sign}{change:.2f} ({pct_sign}{pct_change:.2f}%)\n"
            f"- **As of**: {date} at {time_val}"
        )
        
        return {
            "status": "ok",
            "message": report,
            "data": {
                "symbol": symbol,
                "price": price,
                "change": change,
                "percent_change": pct_change,
                "date": date,
                "time": time_val
            }
        }
        
    except requests.exceptions.Timeout:
        logger.error(f"[STOCKS] Request timed out for {symbol}.")
        return {"status": "error", "message": "Stocks quote lookup timed out. Please try again later."}
    except requests.exceptions.RequestException as re_err:
        logger.error(f"[STOCKS] Network error for {symbol}: {re_err}")
        return {"status": "error", "message": f"Network error during stocks lookup: {str(re_err)}"}
    except Exception as err:
        logger.error(f"[STOCKS] Failed to fetch quote for {symbol}: {err}", exc_info=True)
        return {"status": "error", "message": f"Failed to fetch stock quote: {str(err)}"}
