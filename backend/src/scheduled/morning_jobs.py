"""
Marcbantu Africa — Morning scheduled jobs.
Daily 6am: weather + prices
Daily 7am: SMS reminders
"""
from utils import log_event, log_error
from db import DB


async def daily_weather(env):
    """Fetch weather for all active farms and cache it."""
    db = DB(env)
    farms = await db.query("""
        SELECT DISTINCT latitude, longitude
        FROM farms
        WHERE active = 1 AND latitude IS NOT NULL AND longitude IS NOT NULL
    """)

    log_event('daily_weather_start', {'farms': len(farms)})

    for farm in farms:
        try:
            lat, lon = farm['latitude'], farm['longitude']
            key = f"weather:{round(lat, 2)}:{round(lon, 2)}"

            api_url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
                f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum"
                f"&timezone=Africa/Nairobi&forecast_days=7"
            )

            response = await fetch(api_url)
            if response.status == 200:
                data = await response.json()
                import json
                await env.CACHE.put(key, json.dumps(data), expirationTtl=3600 * 6)
        except Exception as e:
            log_error(f"Weather fetch failed for {lat},{lon}: {str(e)}")

    log_event('daily_weather_done')


async def daily_prices(env):
    """Fetch market prices from external sources and store."""
    db = DB(env)
    log_event('daily_prices_start')

    # In production: fetch from AMIS or other sources
    # For now, this is a placeholder that would call external APIs
    try:
        # Example: fetch from AMIS Kenya
        # response = await fetch("https://amis.co.ke/api/prices")
        # prices = await response.json()
        # for price in prices:
        #     await db.insert('market_prices', {...})
        pass
    except Exception as e:
        log_error(f"Price fetch failed: {str(e)}")

    log_event('daily_prices_done')


async def sms_reminders(env):
    """Send daily SMS reminders to farmers."""
    db = DB(env)
    log_event('sms_reminders_start')

    # Get farmers with Pro+ tier who want SMS
    farmers = await db.query("""
        SELECT id, phone, full_name FROM farmers
        WHERE subscription_tier IN ('pro', 'business')
        AND verified = 1
        LIMIT 1000
    """)

    log_event('sms_reminders_farmers', {'count': len(farmers)})

    # In production: batch queue SMS messages
    for farmer in farmers:
        await env.JOBS.send({
            'type': 'send_sms',
            'payload': {
                'to': farmer['phone'],
                'farmer_id': farmer['id'],
                'template_code': 'MILK_REMINDER',
                'variables': {'name': farmer['full_name'].split()[0]},
            }
        })

    log_event('sms_reminders_done')