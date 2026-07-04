import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

logger = logging.getLogger("void.time_control")

# Common location/timezone mapping for local offsets (failsafe on Windows)
TIMEZONE_OFFSETS = {
    # US / Canada Timezones
    "est": -5.0,
    "edt": -4.0,
    "cst": -6.0,
    "cdt": -5.0,
    "mst": -7.0,
    "mdt": -6.0,
    "pst": -8.0,
    "pdt": -7.0,
    "eastern": -5.0,
    "central": -6.0,
    "mountain": -7.0,
    "pacific": -8.0,
    "new york": -5.0,
    "washington": -5.0,
    "chicago": -6.0,
    "denver": -7.0,
    "los angeles": -8.0,
    "san francisco": -8.0,
    "seattle": -8.0,
    
    # Europe
    "gmt": 0.0,
    "utc": 0.0,
    "bst": 1.0,
    "cet": 1.0,
    "cest": 2.0,
    "london": 0.0,
    "paris": 1.0,
    "berlin": 1.0,
    "rome": 1.0,
    
    # Asia / Oceania
    "ist": 5.5,
    "india": 5.5,
    "delhi": 5.5,
    "mumbai": 5.5,
    "bangalore": 5.5,
    "jst": 9.0,
    "tokyo": 9.0,
    "japan": 9.0,
    "china": 8.0,
    "beijing": 8.0,
    "singapore": 8.0,
    "sydney": 10.0,
    "aest": 10.0,
    "aedt": 11.0,
    "melbourne": 10.0
}

def get_timezone_time(location: str = None) -> Dict[str, Any]:
    """
    Computes current local time/date for a given location or timezone.
    Performs computations locally using standard library ZoneInfo, falling back
    to key-word offset lookup if the local OS tzdata is missing (common on Windows).
    """
    now_utc = datetime.now(timezone.utc)
    
    if not location or not location.strip():
        # Default: local system time
        local_now = datetime.now()
        report = f"🕒 **Current Local Time**:\n- **Time**: {local_now.strftime('%I:%M %p')}\n- **Date**: {local_now.strftime('%A, %B %d, %Y')}"
        return {
            "status": "ok",
            "message": report,
            "data": {
                "time": local_now.strftime("%H:%M:%S"),
                "date": local_now.strftime("%Y-%m-%d"),
                "timezone": "Local System Time"
            }
        }
        
    query = location.strip().lower()
    
    # Step 1: Try ZoneInfo
    try:
        from zoneinfo import ZoneInfo
        # Format query for ZoneInfo if it looks like America/New_York
        if "/" in query:
            parts = [p.capitalize() for p in query.split("/")]
            zi_key = "/".join(parts)
            tz = ZoneInfo(zi_key)
            local_dt = now_utc.astimezone(tz)
            report = f"🕒 **Current Time in {zi_key}**:\n- **Time**: {local_dt.strftime('%I:%M %p')}\n- **Date**: {local_dt.strftime('%A, %B %d, %Y')}"
            return {
                "status": "ok",
                "message": report,
                "data": {
                    "time": local_dt.strftime("%H:%M:%S"),
                    "date": local_dt.strftime("%Y-%m-%d"),
                    "timezone": zi_key
                }
            }
    except Exception:
        # Failsafe fallback if ZoneInfo key lookup fails (e.g. missing IANA db on Windows)
        pass
        
    # Step 2: Try Keyword/Offset Map Fallback
    offset = None
    resolved_tz_name = None
    
    # Look for exact timezone matching
    if query in TIMEZONE_OFFSETS:
        offset = TIMEZONE_OFFSETS[query]
        resolved_tz_name = query.upper()
    else:
        # Look for substring matching
        for k, val in TIMEZONE_OFFSETS.items():
            if k in query:
                offset = val
                resolved_tz_name = k.title()
                break
                
    if offset is None:
        logger.warning(f"[TIME] Timezone/location '{location}' could not be resolved. Defaulting to local system time.")
        local_now = datetime.now()
        report = (
            f"⚠️ Could not resolve timezone for '{location}', Sir. Defaulting to system time:\n"
            f"- **Time**: {local_now.strftime('%I:%M %p')}\n"
            f"- **Date**: {local_now.strftime('%A, %B %d, %Y')}"
        )
        return {
            "status": "ok",
            "message": report,
            "data": {
                "time": local_now.strftime("%H:%M:%S"),
                "date": local_now.strftime("%Y-%m-%d"),
                "timezone": "Local System Time (Fallback)"
            }
        }
        
    # Compute local offset time
    local_dt = now_utc + timedelta(hours=offset)
    
    # Formulate signs for offset
    sign = "+" if offset >= 0 else "-"
    abs_hours = int(abs(offset))
    minutes = int((abs(offset) % 1) * 60)
    offset_str = f"UTC{sign}{abs_hours:02d}:{minutes:02d}"
    
    report = (
        f"🕒 **Current Time in {resolved_tz_name} ({offset_str})**:\n"
        f"- **Time**: {local_dt.strftime('%I:%M %p')}\n"
        f"- **Date**: {local_dt.strftime('%A, %B %d, %Y')}"
    )
    
    return {
        "status": "ok",
        "message": report,
        "data": {
            "time": local_dt.strftime("%H:%M:%S"),
            "date": local_dt.strftime("%Y-%m-%d"),
            "timezone": resolved_tz_name,
            "offset": offset_str
        }
    }
