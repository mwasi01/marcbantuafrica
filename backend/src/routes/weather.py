"""
Marcbantu Africa — Weather routes.
Uses Open-Meteo (free, no API key) for forecasts and historical data.
Caches results in KV to reduce external calls.
"""

from js import fetch
import json
from utils import (
    success_response, error_response, require_auth,
    now_iso, to_int, to_float, log_event,
    _sp,
)
from constants import HTTP, ErrorCode
from db import DB


# ============================================================
# WEATHER CODE MAPPING (WMO codes)
# ============================================================
WMO_CODES = {
    0: 'Clear sky',
    1: 'Mainly clear',
    2: 'Partly cloudy',
    3: 'Overcast',
    45: 'Fog',
    48: 'Depositing rime fog',
    51: 'Light drizzle',
    53: 'Moderate drizzle',
    55: 'Dense drizzle',
    56: 'Light freezing drizzle',
    57: 'Dense freezing drizzle',
    61: 'Slight rain',
    63: 'Moderate rain',
    65: 'Heavy rain',
    66: 'Light freezing rain',
    67: 'Heavy freezing rain',
    71: 'Slight snow',
    73: 'Moderate snow',
    75: 'Heavy snow',
    77: 'Snow grains',
    80: 'Slight rain showers',
    81: 'Moderate rain showers',
    82: 'Violent rain showers',
    85: 'Slight snow showers',
    86: 'Heavy snow showers',
    95: 'Thunderstorm',
    96: 'Thunderstorm with slight hail',
    99: 'Thunderstorm with heavy hail',
}

WMO_ICONS = {
    0: 'sun', 1: 'sun', 2: 'cloud-sun', 3: 'cloud',
    45: 'smog', 48: 'smog',
    51: 'cloud-drizzle', 53: 'cloud-drizzle', 55: 'cloud-drizzle',
    56: 'cloud-drizzle', 57: 'cloud-drizzle',
    61: 'cloud-rain', 63: 'cloud-rain', 65: 'cloud-showers-heavy',
    66: 'cloud-rain', 67: 'cloud-showers-heavy',
    71: 'snowflake', 73: 'snowflake', 75: 'snowflake', 77: 'snowflake',
    80: 'cloud-rain', 81: 'cloud-showers-heavy', 82: 'cloud-showers-heavy',
    85: 'snowflake', 86: 'snowflake',
    95: 'bolt', 96: 'bolt', 99: 'bolt',
}


def _code_to_text(code: int) -> str:
    return WMO_CODES.get(int(code), 'Unknown')


def _code_to_icon(code: int) -> str:
    return WMO_ICONS.get(int(code), 'cloud')


def _summarize_current(current: dict) -> dict:
    code = current.get('weather_code', 0)
    return {
        'temperature': current.get('temperature_2m'),
        'humidity': current.get('relative_humidity_2m'),
        'wind_speed': current.get('wind_speed_10m'),
        'condition': _code_to_text(code),
        'icon': _code_to_icon(code),
        'code': code,
    }


def _summarize_daily(daily: dict) -> list:
    days = []
    dates = daily.get('time', [])
    for i, date in enumerate(dates):
        code = daily['weather_code'][i] if 'weather_code' in daily else 0
        days.append({
            'date': date,
            'temp_max': daily['temperature_2m_max'][i] if 'temperature_2m_max' in daily else None,
            'temp_min': daily['temperature_2m_min'][i] if 'temperature_2m_min' in daily else None,
            'precipitation': daily['precipitation_sum'][i] if 'precipitation_sum' in daily else 0,
            'condition': _code_to_text(code),
            'icon': _code_to_icon(code),
            'code': code,
        })
    return days


def _agronomic_advice(current: dict, daily: list) -> list:
    """Generate farming advice based on weather."""
    advice = []

    if not daily:
        return advice

    today = daily[0]
    rain_today = today.get('precipitation', 0) or 0
    rain_next_2 = sum(d.get('precipitation', 0) or 0 for d in daily[1:3])

    temp_max = today.get('temp_max', 25)

    # Spraying window
    if rain_today < 1 and rain_next_2 < 3:
        advice.append({
            'type': 'spraying',
            'priority': 'ok',
            'message': 'Good conditions for spraying today. Low rain expected.',
        })
    else:
        advice.append({
            'type': 'spraying',
            'priority': 'warn',
            'message': f"Rain expected ({rain_today:.1f}mm today, {rain_next_2:.1f}mm next 2 days). Delay spraying.",
        })

    # Harvesting
    if rain_next_2 > 10:
        advice.append({
            'type': 'harvesting',
            'priority': 'urgent',
            'message': f"Heavy rain coming ({rain_next_2:.1f}mm). Harvest and protect crops now.",
        })
    elif rain_next_2 < 2:
        advice.append({
            'type': 'harvesting',
            'priority': 'ok',
            'message': 'Dry window ahead. Good time for harvest and drying.',
        })

    # Irrigation
    if rain_next_2 < 2 and temp_max > 30:
        advice.append({
            'type': 'irrigation',
            'priority': 'warn',
            'message': f"Hot and dry ({temp_max:.0f}°C). Check irrigation needs.",
        })

    # Disease risk
    humidity = current.get('humidity', 0) or 0
    if humidity > 80 and rain_today > 5:
        advice.append({
            'type': 'disease',
            'priority': 'warn',
            'message': 'High humidity + rain. Watch for fungal diseases.',
        })

    # Livestock
    if temp_max > 32:
        advice.append({
            'type': 'livestock',
            'priority': 'warn',
            'message': 'High heat. Ensure livestock have shade and water.',
        })

    return advice


# ============================================================
# GET WEATHER
# ============================================================
async def get_weather(request, env):
    """GET /api/weather
    Query: lat, lon, days=7, location_name?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    url = _sp(request)
    lat = to_float(url.search_params.get('lat'), -1.286389)
    lon = to_float(url.search_params.get('lon'), 36.817223)
    days = min(max(to_int(url.search_params.get('days', 7), 7), 1), 16)
    location_name = url.search_params.get('location_name', '')

    # Cache key
    cache_key = f"weather:{round(lat, 3)}:{round(lon, 3)}:{days}"

    # Try cache first
    try:
        cached = await env.CACHE.get(cache_key)
        if cached:
            data = json.loads(cached)
            data['cached'] = True
            return success_response(data)
    except Exception:
        pass

    # Fetch from Open-Meteo
    api_url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&timezone=Africa/Nairobi&forecast_days={days}"
    )

    try:
        response = await fetch(api_url)
        if response.status != 200:
            return error_response("Weather service unavailable", status=HTTP.SERVICE_UNAVAILABLE)

        raw = await response.json()
    except Exception as e:
        log_event('weather_fetch_failed', {'error': str(e), 'lat': lat, 'lon': lon})
        return error_response("Weather fetch failed", status=HTTP.SERVICE_UNAVAILABLE)

    # Summarize
    current = _summarize_current(raw.get('current', {}))
    daily = _summarize_daily(raw.get('daily', {}))
    advice = _agronomic_advice(raw.get('current', {}), daily)

    result = {
        'location': {
            'latitude': lat,
            'longitude': lon,
            'name': location_name,
            'timezone': raw.get('timezone'),
        },
        'current': current,
        'daily': daily,
        'advice': advice,
        'fetched_at': now_iso(),
        'cached': False,
    }

    # Cache for 1 hour
    try:
        await env.CACHE.put(cache_key, json.dumps(result), expirationTtl=3600)
    except Exception:
        pass

    return success_response(result)


# ============================================================
# RAINFALL TRACKING
# ============================================================
async def rainfall_tracking(request, env):
    """GET /api/weather/rainfall
    Query: farm_id?, lat?, lon?, days=30
    Compares actual recent rainfall to historical.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    # Get location from farm if provided
    farm_id = url.search_params.get('farm_id')
    if farm_id:
        farm = await db.query_one("""
            SELECT f.latitude, f.longitude, f.name
            FROM farms f
            WHERE f.id = ? AND f.farmer_id = ?
        """, [to_int(farm_id), user['id']])

        if not farm:
            return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

        lat = farm.get('latitude') or -1.286389
        lon = farm.get('longitude') or 36.817223
        location_name = farm.get('name')
    else:
        lat = to_float(url.search_params.get('lat'), -1.286389)
        lon = to_float(url.search_params.get('lon'), 36.817223)
        location_name = url.search_params.get('location_name', '')

    days = min(max(to_int(url.search_params.get('days', 30), 30), 7), 92)

    cache_key = f"rainfall:{round(lat, 3)}:{round(lon, 3)}:{days}"

    try:
        cached = await env.CACHE.get(cache_key)
        if cached:
            data = json.loads(cached)
            data['cached'] = True
            return success_response(data)
    except Exception:
        pass

    # Fetch past rainfall from Open-Meteo archive API
    api_url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}"
        f"&start_date={(now_iso()[:10])}"
        f"&end_date={now_iso()[:10]}"
        f"&daily=precipitation_sum"
        f"&timezone=Africa/Nairobi"
    )

    # Actually use past_days feature on the forecast API
    api_url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&daily=precipitation_sum,temperature_2m_max,temperature_2m_min"
        f"&past_days={days}&forecast_days=0"
        f"&timezone=Africa/Nairobi"
    )

    try:
        response = await fetch(api_url)
        if response.status != 200:
            return error_response("Rainfall service unavailable", status=HTTP.SERVICE_UNAVAILABLE)
        raw = await response.json()
    except Exception as e:
        log_event('rainfall_fetch_failed', {'error': str(e)})
        return error_response("Rainfall fetch failed", status=HTTP.SERVICE_UNAVAILABLE)

    daily = raw.get('daily', {})
    dates = daily.get('time', [])
    precip = daily.get('precipitation_sum', [0] * len(dates))

    history = [
        {'date': dates[i], 'precipitation_mm': precip[i] or 0}
        for i in range(len(dates))
    ]

    total_rain = sum(p or 0 for p in precip)
    avg_daily = total_rain / days if days > 0 else 0

    result = {
        'location': {'latitude': lat, 'longitude': lon, 'name': location_name},
        'period_days': days,
        'total_precipitation_mm': round(total_rain, 2),
        'average_daily_mm': round(avg_daily, 2),
        'history': history,
        'summary': {
            'wet_days': sum(1 for p in precip if (p or 0) > 1),
            'dry_days': sum(1 for p in precip if (p or 0) < 1),
        },
        'fetched_at': now_iso(),
        'cached': False,
    }

    try:
        await env.CACHE.put(cache_key, json.dumps(result), expirationTtl=3600 * 6)
    except Exception:
        pass

    return success_response(result)


# ============================================================
# WEATHER ALERTS
# ============================================================
async def alerts(request, env):
    """GET /api/weather/alerts
    Query: farm_id?, lat?, lon?
    Returns any weather warnings relevant to farming.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        farm = await db.query_one("""
            SELECT f.latitude, f.longitude, f.name
            FROM farms f
            WHERE f.id = ? AND f.farmer_id = ?
        """, [to_int(farm_id), user['id']])
        if not farm:
            return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)
        lat = farm.get('latitude') or -1.286389
        lon = farm.get('longitude') or 36.817223
        location_name = farm.get('name')
    else:
        lat = to_float(url.search_params.get('lat'), -1.286389)
        lon = to_float(url.search_params.get('lon'), 36.817223)
        location_name = url.search_params.get('location_name', '')

    # Reuse weather service
    cache_key = f"weather:{round(lat, 3)}:{round(lon, 3)}:7"

    raw_weather = None
    try:
        cached = await env.CACHE.get(cache_key)
        if cached:
            raw_weather = json.loads(cached)
    except Exception:
        pass

    if not raw_weather:
        api_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum"
            f"&timezone=Africa/Nairobi&forecast_days=7"
        )
        try:
            response = await fetch(api_url)
            raw = await response.json()
            current = _summarize_current(raw.get('current', {}))
            daily = _summarize_daily(raw.get('daily', {}))
            raw_weather = {
                'location': {'latitude': lat, 'longitude': lon, 'name': location_name},
                'current': current,
                'daily': daily,
            }
        except Exception:
            return error_response("Weather unavailable", status=HTTP.SERVICE_UNAVAILABLE)

    daily = raw_weather.get('daily', [])
    current = raw_weather.get('current', {})
    warnings = []

    # Heavy rain warning
    next_3_rain = sum(d.get('precipitation', 0) or 0 for d in daily[:3])
    if next_3_rain > 30:
        warnings.append({
            'type': 'heavy_rain',
            'severity': 'high',
            'title': 'Heavy rain expected',
            'message': f"{next_3_rain:.0f}mm rain expected in next 3 days. Protect crops and livestock.",
        })
    elif next_3_rain > 15:
        warnings.append({
            'type': 'moderate_rain',
            'severity': 'medium',
            'title': 'Moderate rain expected',
            'message': f"{next_3_rain:.0f}mm rain expected in next 3 days.",
        })

    # Drought warning
    next_7_rain = sum(d.get('precipitation', 0) or 0 for d in daily)
    if next_7_rain < 5:
        warnings.append({
            'type': 'dry_spell',
            'severity': 'medium',
            'title': 'Dry spell ahead',
            'message': 'Little to no rain expected in next 7 days. Plan irrigation.',
        })

    # Heat warning
    max_temp = max((d.get('temp_max', 0) or 0) for d in daily) if daily else 0
    if max_temp > 35:
        warnings.append({
            'type': 'heat',
            'severity': 'high',
            'title': 'Extreme heat warning',
            'message': f"Temperatures up to {max_temp:.0f}°C expected. Protect livestock and irrigate.",
        })
    elif max_temp > 32:
        warnings.append({
            'type': 'heat',
            'severity': 'medium',
            'title': 'High temperatures',
            'message': f"Temperatures up to {max_temp:.0f}°C expected.",
        })

    # Frost warning (relevant for highlands)
    min_temp = min((d.get('temp_min', 99) or 99) for d in daily) if daily else 99
    if min_temp < 5:
        warnings.append({
            'type': 'frost',
            'severity': 'high',
            'title': 'Frost risk',
            'message': f"Temperatures as low as {min_temp:.0f}°C expected. Protect sensitive crops.",
        })

    return success_response({
        'location': raw_weather.get('location', {}),
        'warnings': warnings,
        'count': len(warnings),
        'generated_at': now_iso(),
    })


# ============================================================
# HISTORICAL WEATHER
# ============================================================
async def historical(request, env):
    """GET /api/weather/historical
    Query: farm_id?, lat?, lon?, from, to
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        farm = await db.query_one("""
            SELECT f.latitude, f.longitude FROM farms f
            WHERE f.id = ? AND f.farmer_id = ?
        """, [to_int(farm_id), user['id']])
        if not farm:
            return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)
        lat = farm.get('latitude') or -1.286389
        lon = farm.get('longitude') or 36.817223
    else:
        lat = to_float(url.search_params.get('lat'), -1.286389)
        lon = to_float(url.search_params.get('lon'), 36.817223)

    date_from = url.search_params.get('from')
    date_to = url.search_params.get('to')

    if not date_from or not date_to:
        return error_response("'from' and 'to' dates required",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    # Limit to 1 year range
    from datetime import datetime, timedelta
    try:
        start = datetime.strptime(date_from, '%Y-%m-%d')
        end = datetime.strptime(date_to, '%Y-%m-%d')
    except Exception:
        return error_response("Invalid date format. Use YYYY-MM-DD.",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.INVALID_FORMAT)

    if (end - start).days > 366:
        return error_response("Date range cannot exceed 1 year",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    cache_key = f"historical:{round(lat, 3)}:{round(lon, 3)}:{date_from}:{date_to}"

    try:
        cached = await env.CACHE.get(cache_key)
        if cached:
            data = json.loads(cached)
            data['cached'] = True
            return success_response(data)
    except Exception:
        pass

    api_url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}"
        f"&start_date={date_from}&end_date={date_to}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&timezone=Africa/Nairobi"
    )

    try:
        response = await fetch(api_url)
        if response.status != 200:
            return error_response("Historical weather unavailable", status=HTTP.SERVICE_UNAVAILABLE)
        raw = await response.json()
    except Exception as e:
        log_event('historical_weather_failed', {'error': str(e)})
        return error_response("Fetch failed", status=HTTP.SERVICE_UNAVAILABLE)

    daily = raw.get('daily', {})
    dates = daily.get('time', [])

    records = []
    total_rain = 0
    for i, date in enumerate(dates):
        precip = (daily.get('precipitation_sum') or [0])[i] or 0
        total_rain += precip
        records.append({
            'date': date,
            'temp_max': (daily.get('temperature_2m_max') or [None])[i],
            'temp_min': (daily.get('temperature_2m_min') or [None])[i],
            'precipitation_mm': precip,
        })

    result = {
        'location': {'latitude': lat, 'longitude': lon},
        'from': date_from,
        'to': date_to,
        'total_precipitation_mm': round(total_rain, 2),
        'average_daily_mm': round(total_rain / len(dates), 2) if dates else 0,
        'records': records,
        'fetched_at': now_iso(),
        'cached': False,
    }

    try:
        await env.CACHE.put(cache_key, json.dumps(result), expirationTtl=3600 * 24)
    except Exception:
        pass

    return success_response(result)