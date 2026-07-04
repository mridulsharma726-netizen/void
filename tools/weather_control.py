import logging
import requests
from typing import Dict, Any

logger = logging.getLogger("void.weather_control")

# Weather code definitions from Open-Meteo
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}

def get_weather_report(location: str = "Delhi") -> Dict[str, Any]:
    """
    Retrieves current weather conditions and forecast for a given location.
    Uses Open-Meteo geocoding and forecast APIs (no API key required).
    """
    if not location:
        return {"status": "error", "message": "Location name is required, Sir."}
        
    headers = {"User-Agent": "VOID/2.0 Weather Module"}
    
    # Step 1: Geocoding
    geocoding_url = f"https://geocoding-api.open-meteo.com/v1/search?name={requests.utils.quote(location)}&count=1&language=en&format=json"
    try:
        geo_resp = requests.get(geocoding_url, headers=headers, timeout=10)
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        
        results = geo_data.get("results", [])
        if not results:
            return {"status": "error", "message": f"Could not find coordinates for location '{location}', Sir."}
            
        loc_data = results[0]
        lat = loc_data["latitude"]
        lon = loc_data["longitude"]
        resolved_name = f"{loc_data.get('name', location)}, {loc_data.get('country', '')}"
        
    except requests.exceptions.Timeout:
        logger.error("[WEATHER] Geocoding request timed out.")
        return {"status": "error", "message": "Geocoding request timed out. Please try again later."}
    except requests.exceptions.RequestException as re_err:
        logger.error(f"[WEATHER] Geocoding network error: {re_err}")
        return {"status": "error", "message": f"Network error during geocoding: {str(re_err)}"}
    except Exception as err:
        logger.error(f"[WEATHER] Geocoding failed: {err}")
        return {"status": "error", "message": f"Failed to resolve location coordinates: {str(err)}"}
        
    # Step 2: Forecast conditions
    forecast_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
    try:
        fore_resp = requests.get(forecast_url, headers=headers, timeout=10)
        fore_resp.raise_for_status()
        fore_data = fore_resp.json()
        
        current = fore_data.get("current", {})
        if not current:
            return {"status": "error", "message": "Weather data payload is empty, Sir."}
            
        temp = current.get("temperature_2m", 0.0)
        feels_like = current.get("apparent_temperature", temp)
        humidity = current.get("relative_humidity_2m", 0)
        wind = current.get("wind_speed_10m", 0.0)
        precip = current.get("precipitation", 0.0)
        code = current.get("weather_code", 0)
        
        condition = WEATHER_CODES.get(code, "Unspecified conditions")
        
        # Privacy-by-default: only return the essential metrics
        report = (
            f"🌦️ **Weather Report for {resolved_name}**:\n"
            f"- **Condition**: {condition}\n"
            f"- **Temperature**: {temp}°C (Feels like: {feels_like}°C)\n"
            f"- **Humidity**: {humidity}%\n"
            f"- **Wind Speed**: {wind} km/h\n"
            f"- **Precipitation**: {precip} mm"
        )
        
        return {
            "status": "ok",
            "message": report,
            "data": {
                "location": resolved_name,
                "temperature": temp,
                "apparent_temperature": feels_like,
                "humidity": humidity,
                "condition": condition,
                "wind_speed": wind,
                "precipitation": precip
            }
        }
        
    except requests.exceptions.Timeout:
        logger.error("[WEATHER] Forecast request timed out.")
        return {"status": "error", "message": "Weather forecast service timed out. Please try again later."}
    except requests.exceptions.RequestException as re_err:
        logger.error(f"[WEATHER] Forecast network error: {re_err}")
        return {"status": "error", "message": f"Network error during weather fetch: {str(re_err)}"}
    except Exception as err:
        logger.error(f"[WEATHER] Forecast fetch failed: {err}")
        return {"status": "error", "message": f"Failed to retrieve weather details: {str(err)}"}
