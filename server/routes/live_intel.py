import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import datetime

try:
    import pytz
except ImportError:
    pytz = None

logger = logging.getLogger("void.routes.live_intel")
router = APIRouter()

class SearchRequest(BaseModel):
    query: str
    max_results: int = 10

# Safe import helpers
def get_weather_module():
    try:
        import tools.weather_control as weather
        return weather
    except Exception as e:
        logger.error(f"Failed to import weather_control: {e}")
        return None

def get_stocks_module():
    try:
        import tools.stocks_control as stocks
        return stocks
    except Exception as e:
        logger.error(f"Failed to import stocks_control: {e}")
        return None

def get_time_module():
    try:
        import tools.time_control as time_ctrl
        return time_ctrl
    except Exception as e:
        logger.error(f"Failed to import time_control: {e}")
        return None

def get_rss_engine():
    try:
        import news.rss_engine as rss
        return rss.get_engine()
    except Exception as e:
        logger.error(f"Failed to import rss_engine: {e}")
        return None

def get_ddg_provider():
    try:
        import search.duckduckgo_provider as ddg
        return ddg.get_provider()
    except Exception as e:
        logger.error(f"Failed to import duckduckgo_provider: {e}")
        return None


@router.get("/api/live/weather")
async def api_live_weather(city: str = "Delhi"):
    weather = get_weather_module()
    if not weather:
        return {"status": "unavailable", "message": "Weather module is not loaded."}
    try:
        res = weather.get_weather_report(city)
        return {"status": "ok", "weather": res}
    except Exception as e:
        logger.error(f"Error fetching weather for {city}: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/api/live/news")
async def api_live_news(limit: int = 20):
    engine = get_rss_engine()
    if not engine:
        return {"status": "unavailable", "message": "RSS News engine is not running.", "news": []}
    try:
        articles = engine.get_recent(limit)
        articles_list = [a.to_dict() for a in articles]
        return {"status": "ok", "news": articles_list}
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        # Try to fallback to reading from DB directly
        try:
            import sqlite3
            from pathlib import Path
            db_path = Path(__file__).parent.parent.parent / "memory" / "data" / "rss_cache.db"
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT title, url, snippet, source, category, published, fetched_at FROM articles ORDER BY published DESC LIMIT ?",
                    (limit,)
                )
                rows = cursor.fetchall()
                fallback_articles = [dict(row) for row in rows]
                conn.close()
                return {"status": "ok", "news": fallback_articles, "fallback": True}
        except Exception as db_err:
            logger.error(f"News fallback DB query failed: {db_err}")
        return {"status": "error", "message": str(e), "news": []}

@router.get("/api/live/stocks")
async def api_live_stocks(symbols: str = "AAPL,GOOGL,MSFT"):
    stocks = get_stocks_module()
    if not stocks:
        return {"status": "unavailable", "message": "Stocks module is not loaded.", "stocks": []}
    
    ticker_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    results = []
    for ticker in ticker_list:
        try:
            res = stocks.get_stock_quote(ticker)
            results.append(res)
        except Exception as e:
            logger.error(f"Error fetching stock {ticker}: {e}")
            results.append({"symbol": ticker, "status": "error", "message": str(e)})
            
    return {"status": "ok", "stocks": results}

@router.get("/api/live/time")
async def api_live_time(timezones: str = "UTC,US/Eastern,Asia/Kolkata,Europe/London"):
    time_ctrl = get_time_module()
    
    tz_list = [t.strip() for t in timezones.split(",") if t.strip()]
    results = {}
    
    for tz_name in tz_list:
        try:
            if time_ctrl:
                # Use project timezone function if available
                res = time_ctrl.get_timezone_time(tz_name)
                results[tz_name] = res.get("time") or res.get("current_time") or ""
            elif pytz:
                tz = pytz.timezone(tz_name)
                now = datetime.datetime.now(tz)
                results[tz_name] = now.strftime("%Y-%m-%d %H:%M:%S %Z")
            else:
                # Simple fallback
                results[tz_name] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception as e:
            logger.error(f"Error fetching time for {tz_name}: {e}")
            results[tz_name] = f"Error: {str(e)}"
            
    return {"status": "ok", "times": results}

@router.post("/api/live/search")
async def api_live_search(req: SearchRequest):
    provider = get_ddg_provider()
    if not provider:
        raise HTTPException(status_code=500, detail="DuckDuckGo provider is not loaded.")
    try:
        res = provider.search(req.query, req.max_results)
        return {"status": "ok", "results": res}
    except Exception as e:
        logger.error(f"Error performing web search for {req.query}: {e}")
        return {"status": "error", "message": str(e)}
