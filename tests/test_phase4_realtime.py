import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

import pytest
from unittest.mock import patch, MagicMock
import requests
from backend.intent_router import detect_intent_and_params
from tools.registry import tool_registry
from news.rss_engine import Article

def test_intent_classification_realtime():
    # 1. Weather
    res = detect_intent_and_params("what is the weather in Delhi")
    assert res["intent"] == "get_weather"
    assert res["parameters"]["location"] == "delhi"

    res = detect_intent_and_params("check weather")
    assert res["intent"] == "get_weather"

    # 2. News
    res = detect_intent_and_params("latest news about tech")
    assert res["intent"] == "get_news"
    assert res["parameters"]["topic"] == "tech"

    res = detect_intent_and_params("read the breaking news")
    assert res["intent"] == "get_news"

    # 3. Web Search
    res = detect_intent_and_params("search for fastify framework")
    assert res["intent"] == "web_search"
    assert res["parameters"]["query"] == "fastify framework"

    # 4. Stock quote
    res = detect_intent_and_params("stock price of AAPL")
    assert res["intent"] == "get_stock"
    assert res["parameters"]["ticker"] == "aapl"

    res = detect_intent_and_params("current price of BTC.V")
    assert res["intent"] == "get_stock"
    assert res["parameters"]["ticker"] == "btc.v"

    # 5. Time
    res = detect_intent_and_params("current time in America/New_York")
    assert res["intent"] == "get_time"
    assert res["parameters"]["location"] == "america/new_york"

    res = detect_intent_and_params("what time is it in Tokyo")
    assert res["intent"] == "get_time"
    assert res["parameters"]["location"] == "tokyo"


@patch("requests.get")
def test_weather_control_success(mock_get):
    # Mock geocoding and forecast response
    geo_mock = MagicMock()
    geo_mock.status_code = 200
    geo_mock.json.return_value = {
        "results": [{"latitude": 28.6, "longitude": 77.2, "name": "Delhi", "country": "India"}]
    }

    forecast_mock = MagicMock()
    forecast_mock.status_code = 200
    forecast_mock.json.return_value = {
        "current": {
            "temperature_2m": 32.5,
            "apparent_temperature": 35.0,
            "relative_humidity_2m": 60,
            "wind_speed_10m": 12.0,
            "precipitation": 0.0,
            "weather_code": 1
        }
    }

    # First requests.get handles geocoding, second handles forecast
    mock_get.side_effect = [geo_mock, forecast_mock]

    get_weather_func = tool_registry.get_tool("get_weather")
    res = get_weather_func(location="Delhi")
    
    assert res["status"] == "ok"
    assert "Delhi" in res["data"]["location"]
    assert res["data"]["temperature"] == 32.5
    assert "Mainly clear" in res["data"]["condition"]


@patch("requests.get")
def test_weather_control_failure_geocoding(mock_get):
    # Simulate a geocoding failure (empty coordinates result list)
    geo_mock = MagicMock()
    geo_mock.status_code = 200
    geo_mock.json.return_value = {"results": []}
    mock_get.return_value = geo_mock

    get_weather_func = tool_registry.get_tool("get_weather")
    res = get_weather_func(location="Atlantis")
    assert res["status"] == "error"
    assert "Could not find coordinates" in res["message"]


@patch("requests.get")
def test_weather_control_failure_timeout(mock_get):
    # Simulate geocoding timeout
    mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

    get_weather_func = tool_registry.get_tool("get_weather")
    res = get_weather_func(location="Delhi")
    assert res["status"] == "error"
    assert "timed out" in res["message"]


@patch("search.duckduckgo_provider.DuckDuckGoProvider.search")
def test_websearch_control_success(mock_search):
    mock_search.return_value = [
        {"title": "Fastify", "url": "https://fastify.io", "snippet": "Fast and low overhead web framework", "source": "fastify.io"}
    ]

    web_search_func = tool_registry.get_tool("web_search")
    res = web_search_func(query="fastify")
    
    assert res["status"] == "ok"
    assert len(res["data"]) == 1
    assert res["data"][0]["title"] == "Fastify"
    assert "Fastify" in res["message"]


@patch("news.rss_engine.RSSEngine.search_articles")
@patch("news.rss_engine.RSSEngine.get_recent")
def test_news_control_success(mock_get_recent, mock_search_articles):
    # Mock models
    art = Article(title="Hacker News 1", url="https://hn.com/1", summary="Tech sync updates", source="Hacker News", category="tech", published_at="2026-07-03T16:00:00")
    
    mock_search_articles.return_value = [art]
    mock_get_recent.return_value = [art]

    get_news_func = tool_registry.get_tool("get_news")
    
    # Check general news
    res_general = get_news_func()
    assert res_general["status"] == "ok"
    assert len(res_general["data"]) == 1
    assert res_general["data"][0]["title"] == "Hacker News 1"

    # Check search topic
    res_topic = get_news_func(topic="Tech sync")
    assert res_topic["status"] == "ok"
    assert "Hacker News 1" in res_topic["message"]


@patch("requests.get")
def test_stocks_control_success(mock_get):
    csv_mock = MagicMock()
    csv_mock.status_code = 200
    csv_mock.text = "Symbol,Date,Time,Open,High,Low,Close,Change\nAAPL.US,2026-07-03,16:00:00,185.00,186.00,184.00,185.50,+1.50\n"
    mock_get.return_value = csv_mock

    get_stock_func = tool_registry.get_tool("get_stock")
    res = get_stock_func(ticker="AAPL")
    
    assert res["status"] == "ok"
    assert res["data"]["symbol"] == "AAPL.US"
    assert res["data"]["price"] == 185.50
    assert res["data"]["change"] == 1.50
    assert res["data"]["percent_change"] > 0.0
    assert "$185.50" in res["message"]


@patch("requests.get")
def test_stocks_control_failure_not_found(mock_get):
    csv_mock = MagicMock()
    csv_mock.status_code = 200
    csv_mock.text = "Symbol,Date,Time,Open,High,Low,Close,Change\nINVALID,N/A,N/A,N/A,N/A,N/A,N/A,N/A\n"
    mock_get.return_value = csv_mock

    get_stock_func = tool_registry.get_tool("get_stock")
    res = get_stock_func(ticker="INVALID")
    assert res["status"] == "error"
    assert "Could not find stock quote" in res["message"]


def test_time_control_success():
    get_time_func = tool_registry.get_tool("get_time")
    
    # UTC / GMT
    res_gmt = get_time_func(location="gmt")
    assert res_gmt["status"] == "ok"
    assert "GMT" in res_gmt["data"]["timezone"].upper()

    # India
    res_ist = get_time_func(location="India")
    assert res_ist["status"] == "ok"
    assert "INDIA" in res_ist["data"]["timezone"].upper() or "IST" in res_ist["data"]["timezone"].upper()
    assert res_ist["data"]["offset"] == "UTC+05:30"

    # New York
    res_ny = get_time_func(location="New York")
    assert res_ny["status"] == "ok"
    assert "NEW YORK" in res_ny["data"]["timezone"].upper()
    assert res_ny["data"]["offset"] == "UTC-05:00"

    # Default Fallback (System Time)
    res_sys = get_time_func()
    assert res_sys["status"] == "ok"
    assert "Local System Time" in res_sys["data"]["timezone"]
