"""
Marcbantu Africa — Weather Service.
Open-Meteo integration (free, no API key), caching, agronomic advice.
"""
import json
from utils import now_iso, log_event


# ============================================================
# CONSTANTS
# ============================================================
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
TIMEZONE = "Africa/Nairobi"

WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}

WMO_ICONS = {
    0: "sun", 1: "sun", 2: "cloud-sun", 3: "cloud",
    45: "smog", 48: "smog",
    51: "cloud-drizzle", 53: "cloud-drizzle", 55: "cloud-drizzle",
    56: "cloud-drizzle", 57: "cloud-drizzle",
    61: "cloud-rain", 63: "cloud-rain", 65: "cloud-showers-heavy",
    66: "cloud-rain", 67: "cloud-showers-heavy",
    71: "snowflake", 73: "snowflake", 75: "snowflake", 77: "snowflake",
    80: "cloud-rain", 81: "cloud-showers-heavy", 82: "cloud-showers-heavy",
    85: "snowflake", 86: "snowflake",
    95: "bolt", 96: "bolt", 99: "bolt",
}


# ============================================================
# HELPERS
# ============================================================
def code_to_text(code) -> str:
    try:
        return WMO_CODES.get(int(code), "Unknown")
    except (TypeError, ValueError):
        return "Unknown"


def code_to_icon(code) -> str:
    try:
        return WMO_ICONS.get(int(code), "cloud")
    except (TypeError, ValueError):
        return "cloud"


def summarize_current(current: dict) -> dict:
    code = current.get("weather_code", 0)
    return {
        "temperature": current.get("temperature_2m"),
        "humidity": current.get("relative_humidity_2m"),
        "wind_speed": current.get("wind_speed_10m"),
        "condition": code_to_text(code),
        "icon": code_to_icon(code),
        "code": code,
    }


def summarize_daily(daily: dict) -> list:
    days = []
    dates = daily.get("time", []) or []
    for i, date in enumerate(dates):
        code = (daily.get("weather_code") or [0])[i] if daily.get("weather_code") else 0
        days.append({
            "date": date,
            "temp_max": (daily.get("temperature_2m_max") or [None])[i],
            "temp_min": (daily.get("temperature_2m_min") or [None])[i],
            "precipitation": (daily.get("precipitation_sum") or [0])[i] or 0,
            "condition": code_to_text(code),
            "icon": code_to_icon(code),
            "code": code,
        })
    return days


def agronomic_advice(current: dict, daily: list) -> list:
    """Generate actionable farm advice from weather."""
    advice = []
    if not daily:
        return advice

    today = daily[0]
    rain_today = today.get("precipitation", 0) or 0
    rain_next_2 = sum((d.get("precipitation", 0) or 0) for d in daily[1:3])
    temp_max = today.get("temp_max", 25) or 25
    humidity = current.get("humidity", 0) or 0

    # Spraying
    if rain_today < 1 and rain_next_2 < 3:
        advice.append({
            "type": "spraying", "priority": "ok",
            "message": "Good conditions for spraying today. Low rain expected.",
        })
    else:
        advice.append({
            "type": "spraying", "priority": "warn",
            "message": f"Rain expected ({rain_today:.1f}mm today, {rain_next_2:.1f}mm next 2 days). Delay spraying.",
        })

    # Harvesting
    if rain_next_2 > 10:
        advice.append({
            "type": "harvesting", "priority": "urgent",
            "message": f"Heavy rain coming ({rain_next_2:.1f}mm). Harvest and protect crops now.",
        })
    elif rain_next_2 < 2:
        advice.append({
            "type": "harvesting", "priority": "ok",
            "message": "Dry window ahead. Good time for harvest and drying.",
        })

    # Irrigation
    if rain_next_2 < 2 and temp_max > 30:
        advice.append({
            "type": "irrigation", "priority": "warn",
            "message": f"Hot and dry ({temp_max:.0f}°C). Check irrigation needs.",
        })

    # Disease risk
    if humidity > 80 and rain_today > 5:
        advice.append({
            "type": "disease", "priority": "warn",
            "message": "High humidity + rain. Watch for fungal diseases.",
        })

    # Livestock heat stress
    if temp_max > 32:
        advice.append({
            "type": "livestock", "priority": "warn",
            "message": "High heat. Ensure livestock have shade and water.",
        })

    return advice


# ============================================================
# SERVICE CLASS
# ============================================================
class WeatherService:
    def __init__(self, env):
        self.env = env

    async def get_forecast(self, lat: float, lon: float, days: int = 7,
                           location_name: str = "") -> dict:
        """Fetch and cache a forecast."""
        cache_key = f"weather:{round(lat, 3)}:{round(lon, 3)}:{days}"

        cached = await self._get_cache(cache_key)
        if cached:
            cached["cached"] = True
            return cached

        url = (
            f"{FORECAST_URL}?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum"
            f"&timezone={TIMEZONE}&forecast_days={days}"
        )

        try:
            response = await fetch(url)
            if response.status != 200:
                log_event("weather_fetch_status", {"status": response.status})
                return None
            raw = await response.json()
        except Exception as e:
            log_event("weather_fetch_failed", {"error": str(e)})
            return None

        current = summarize_current(raw.get("current", {}))
        daily = summarize_daily(raw.get("daily", {}))
        advice = agronomic_advice(raw.get("current", {}), daily)

        result = {
            "location": {
                "latitude": lat, "longitude": lon,
                "name": location_name, "timezone": raw.get("timezone"),
            },
            "current": current,
            "daily": daily,
            "advice": advice,
            "fetched_at": now_iso(),
            "cached": False,
        }

        await self._set_cache(cache_key, result, ttl=3600)
        return result

    async def get_rainfall(self, lat: float, lon: float, days: int = 30,
                          location_name: str = "") -> dict:
        """Fetch past rainfall."""
        cache_key = f"rainfall:{round(lat, 3)}:{round(lon, 3)}:{days}"

        cached = await self._get_cache(cache_key)
        if cached:
            cached["cached"] = True
            return cached

        url = (
            f"{FORECAST_URL}?latitude={lat}&longitude={lon}"
            f"&daily=precipitation_sum,temperature_2m_max,temperature_2m_min"
            f"&past_days={days}&forecast_days=0&timezone={TIMEZONE}"
        )

        try:
            response = await fetch(url)
            if response.status != 200:
                return None
            raw = await response.json()
        except Exception as e:
            log_event("rainfall_fetch_failed", {"error": str(e)})
            return None

        daily = raw.get("daily", {})
        dates = daily.get("time", []) or []
        precip = daily.get("precipitation_sum", [0] * len(dates)) or [0] * len(dates)

        history = [
            {"date": dates[i], "precipitation_mm": precip[i] or 0}
            for i in range(len(dates))
        ]

        total = sum(p or 0 for p in precip)
        avg = total / days if days > 0 else 0

        result = {
            "location": {"latitude": lat, "longitude": lon, "name": location_name},
            "period_days": days,
            "total_precipitation_mm": round(total, 2),
            "average_daily_mm": round(avg, 2),
            "history": history,
            "summary": {
                "wet_days": sum(1 for p in precip if (p or 0) > 1),
                "dry_days": sum(1 for p in precip if (p or 0) < 1),
            },
            "fetched_at": now_iso(),
            "cached": False,
        }

        await self._set_cache(cache_key, result, ttl=3600 * 6)
        return result

    async def get_alerts(self, lat: float, lon: float, location_name: str = "") -> dict:
        """Check for farm-relevant weather warnings."""
        weather = await self.get_forecast(lat, lon, days=7, location_name=location_name)
        if not weather:
            return {"warnings": [], "count": 0}

        daily = weather.get("daily", [])
        warnings = []

        next_3_rain = sum((d.get("precipitation", 0) or 0) for d in daily[:3])
        if next_3_rain > 30:
            warnings.append({
                "type": "heavy_rain", "severity": "high",
                "title": "Heavy rain expected",
                "message": f"{next_3_rain:.0f}mm rain expected in next 3 days. Protect crops and livestock.",
            })
        elif next_3_rain > 15:
            warnings.append({
                "type": "moderate_rain", "severity": "medium",
                "title": "Moderate rain expected",
                "message": f"{next_3_rain:.0f}mm rain expected in next 3 days.",
            })

        next_7_rain = sum((d.get("precipitation", 0) or 0) for d in daily)
        if next_7_rain < 5:
            warnings.append({
                "type": "dry_spell", "severity": "medium",
                "title": "Dry spell ahead",
                "message": "Little to no rain expected in next 7 days. Plan irrigation.",
            })

        max_temp = max((d.get("temp_max", 0) or 0) for d in daily) if daily else 0
        if max_temp > 35:
            warnings.append({
                "type": "heat", "severity": "high",
                "title": "Extreme heat warning",
                "message": f"Temperatures up to {max_temp:.0f}°C expected. Protect livestock and irrigate.",
            })
        elif max_temp > 32:
            warnings.append({
                "type": "heat", "severity": "medium",
                "title": "High temperatures",
                "message": f"Temperatures up to {max_temp:.0f}°C expected.",
            })

        min_temp = min((d.get("temp_min", 99) or 99) for d in daily) if daily else 99
        if min_temp < 5:
            warnings.append({
                "type": "frost", "severity": "high",
                "title": "Frost risk",
                "message": f"Temperatures as low as {min_temp:.0f}°C expected. Protect sensitive crops.",
            })

        return {
            "location": weather.get("location", {}),
            "warnings": warnings,
            "count": len(warnings),
            "generated_at": now_iso(),
        }

    async def get_historical(self, lat: float, lon: float,
                             date_from: str, date_to: str) -> dict:
        """Fetch historical weather for a date range."""
        cache_key = f"historical:{round(lat, 3)}:{round(lon, 3)}:{date_from}:{date_to}"

        cached = await self._get_cache(cache_key)
        if cached:
            cached["cached"] = True
            return cached

        url = (
            f"{ARCHIVE_URL}?latitude={lat}&longitude={lon}"
            f"&start_date={date_from}&end_date={date_to}"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
            f"&timezone={TIMEZONE}"
        )

        try:
            response = await fetch(url)
            if response.status != 200:
                return None
            raw = await response.json()
        except Exception as e:
            log_event("historical_weather_failed", {"error": str(e)})
            return None

        daily = raw.get("daily", {})
        dates = daily.get("time", []) or []

        records = []
        total_rain = 0
        for i, date in enumerate(dates):
            precip = (daily.get("precipitation_sum") or [0])[i] or 0
            total_rain += precip
            records.append({
                "date": date,
                "temp_max": (daily.get("temperature_2m_max") or [None])[i],
                "temp_min": (daily.get("temperature_2m_min") or [None])[i],
                "precipitation_mm": precip,
            })

        result = {
            "location": {"latitude": lat, "longitude": lon},
            "from": date_from, "to": date_to,
            "total_precipitation_mm": round(total_rain, 2),
            "average_daily_mm": round(total_rain / len(dates), 2) if dates else 0,
            "records": records,
            "fetched_at": now_iso(),
            "cached": False,
        }

        await self._set_cache(cache_key, result, ttl=3600 * 24)
        return result

    # ---------------- CACHE ----------------
    async def _get_cache(self, key: str):
        try:
            data = await self.env.CACHE.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    async def _set_cache(self, key: str, value: dict, ttl: int = 3600):
        try:
            await self.env.CACHE.put(key, json.dumps(value), expirationTtl=ttl)
        except Exception:
            pass