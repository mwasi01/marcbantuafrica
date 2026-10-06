"""
Job: daily_weather
Fetches weather for all active farms and caches it.
Runs daily at 6am via cron.
"""
from utils import log_event, log_error
from db import DB
from services.weather_service import WeatherService


async def run(payload: dict, env):
    """Cache weather for all farm locations."""
    log_event("daily_weather_start")

    db = DB(env)

    # Get unique locations from active farms
    farms = await db.query("""
        SELECT DISTINCT latitude, longitude, county
        FROM farms
        WHERE active = 1
        AND latitude IS NOT NULL
        AND longitude IS NOT NULL
        LIMIT 500
    """)

    if not farms:
        log_event("daily_weather_no_farms")
        return

    svc = WeatherService(env)
    cached = 0
    failed = 0

    for farm in farms:
        try:
            lat = farm["latitude"]
            lon = farm["longitude"]
            location_name = farm.get("county") or ""

            result = await svc.get_forecast(lat, lon, days=7, location_name=location_name)
            if result:
                cached += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            log_error(f"Weather fetch failed for {farm}: {str(e)}")

    log_event("daily_weather_done", {
        "cached": cached,
        "failed": failed,
        "total": len(farms),
    })