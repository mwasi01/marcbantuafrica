"""
Job: daily_prices
Fetches market prices from multiple external sources and stores them.
Runs daily at 6am via cron.

Sources (in priority order):
1. AMIS Kenya (https://amis.co.ke/api) — main Kenyan price aggregator
2. KAMIS — Kenya Agricultural Market Information System
3. Manual entries (already in DB)
"""
from utils import now_iso, log_event, log_error
from db import DB


# ============================================================
# DEFAULT TRACKED CROPS
# ============================================================
DEFAULT_CROPS = [
    "Maize", "Beans", "Rice", "Wheat", "Sorghum", "Millet",
    "Tomatoes", "Kale", "Spinach", "Cabbage", "Onions", "Carrots",
    "Potatoes", "Sweet Potatoes", "Bananas", "Avocado",
    "Milk", "Eggs", "Beef", "Chicken",
]

# Major markets per county
MARKETS_BY_COUNTY = {
    "Nakuru":   ["Nakuru Market", "Njoro Market", "Naivasha Market"],
    "Kiambu":   ["Limuru Market", "Kiambu Town Market", "Thika Market"],
    "Nairobi":  ["Wakulima Market", "Kangemi Market", "Gikomba Market"],
    "Machakos": ["Machakos Market", "Kangundo Market"],
    "Kisumu":   ["Ahero Market", "Kisumu Main Market"],
    "Uasin Gishu": ["Eldoret Market"],
    "Narok":    ["Narok Market"],
    "Meru":     ["Meru Market"],
}


# ============================================================
# MAIN JOB
# ============================================================
async def run(payload: dict, env):
    """Fetch and store market prices for today."""
    log_event("daily_prices_start")

    db = DB(env)

    # 1. Discover crops to track
    crops = await _discover_crops(db, payload)
    log_event("daily_prices_crops", {"count": len(crops)})

    # 2. Discover markets to track
    markets = await _discover_markets(db, payload)
    log_event("daily_prices_markets", {"count": len(markets)})

    # 3. Fetch from each source
    all_prices = []

    # Source: AMIS
    if payload.get("source", "all") in ("all", "amis"):
        try:
            amis = await _fetch_amis_prices(crops, env)
            all_prices.extend(amis)
            log_event("daily_prices_amis", {"fetched": len(amis)})
        except Exception as e:
            log_error(f"AMIS fetch failed: {str(e)}")

    # Source: KAMIS (if configured)
    if payload.get("source", "all") in ("all", "kamis"):
        try:
            kamis = await _fetch_kamis_prices(crops, env)
            all_prices.extend(kamis)
            log_event("daily_prices_kamis", {"fetched": len(kamis)})
        except Exception as e:
            log_error(f"KAMIS fetch failed: {str(e)}")

    # Source: Manual / API provided in payload
    if payload.get("manual_prices"):
        all_prices.extend(payload["manual_prices"])
        log_event("daily_prices_manual", {"fetched": len(payload["manual_prices"])})

    # Source: Fallback (moving average of last 7 days)
    if not all_prices:
        try:
            fallback = await _fallback_from_history(db, crops)
            all_prices.extend(fallback)
            log_event("daily_prices_fallback", {"fetched": len(fallback)})
        except Exception as e:
            log_error(f"Fallback fetch failed: {str(e)}")

    # 4. Store + dedupe
    stored = 0
    skipped = 0
    alerts_triggered = 0

    for price in all_prices:
        try:
            # Validate
            if not price.get("crop") or not price.get("market") or price.get("price") is None:
                skipped += 1
                continue

            # Normalize date
            price["price_date"] = price.get("price_date") or now_iso()[:10]

            # Dedupe check
            existing = await db.query_one("""
                SELECT id FROM market_prices
                WHERE crop = ? AND market = ? AND price_date = ?
            """, [price["crop"], price["market"], price["price_date"]])

            if existing:
                skipped += 1
                continue

            # Insert
            await db.insert("market_prices", {
                "crop": price["crop"],
                "variety": price.get("variety"),
                "market": price["market"],
                "county": price.get("county"),
                "country": price.get("country", "Kenya"),
                "price": float(price["price"]),
                "currency": price.get("currency", "KES"),
                "unit": price.get("unit", "kg"),
                "price_date": price["price_date"],
                "source": price.get("source", "Auto"),
                "quality_grade": price.get("quality_grade"),
                "notes": price.get("notes"),
            })
            stored += 1

            # Check price alerts
            from services.market_service import MarketService
            svc = MarketService(env)
            triggered = await svc.check_alerts(price["crop"], float(price["price"]))
            alerts_triggered += len(triggered)

        except Exception as e:
            log_error(f"Price store failed: {str(e)}", {"price": price})
            skipped += 1

    # 5. Compute trends
    try:
        await _compute_trends(db, crops, env)
    except Exception as e:
        log_error(f"Trend computation failed: {str(e)}")

    log_event("daily_prices_done", {
        "stored": stored,
        "skipped": skipped,
        "alerts": alerts_triggered,
        "total_fetched": len(all_prices),
    })


# ============================================================
# DISCOVERY
# ============================================================
async def _discover_crops(db: DB, payload: dict) -> list:
    """Find crops to track: payload > recent activity > defaults."""
    if payload.get("crops"):
        return payload["crops"]

    crops = await db.query("""
        SELECT DISTINCT crop as name FROM market_prices
        WHERE price_date >= date('now', '-30 days')
        UNION
        SELECT DISTINCT product as name FROM sales
        WHERE sale_date >= date('now', '-90 days')
        UNION
        SELECT DISTINCT species_or_crop as name FROM enterprises
        WHERE status = 'active' AND species_or_crop IS NOT NULL
    """)

    names = [c["name"] for c in crops if c.get("name")]
    # Merge with defaults
    merged = list(dict.fromkeys(names + DEFAULT_CROPS))
    return merged[:30]  # cap


async def _discover_markets(db: DB, payload: dict) -> list:
    """Find markets to track."""
    if payload.get("markets"):
        return payload["markets"]

    # Get markets from active farm counties
    counties = await db.query("""
        SELECT DISTINCT county FROM farms
        WHERE active = 1 AND county IS NOT NULL
    """)

    markets = []
    for c in counties:
        county = c["county"]
        if county in MARKETS_BY_COUNTY:
            for m in MARKETS_BY_COUNTY[county]:
                markets.append({"market": m, "county": county})

    # Add existing tracked markets
    existing = await db.query("""
        SELECT DISTINCT market, county FROM market_prices
        WHERE price_date >= date('now', '-30 days')
    """)
    for e in existing:
        markets.append({"market": e["market"], "county": e.get("county")})

    # Dedupe
    seen = set()
    unique = []
    for m in markets:
        key = (m["market"], m.get("county"))
        if key not in seen:
            seen.add(key)
            unique.append(m)

    return unique


# ============================================================
# SOURCE ADAPTERS
# ============================================================
async def _fetch_amis_prices(crops: list, env) -> list:
    """
    Fetch from AMIS Kenya.
    Production: GET https://amis.co.ke/api/prices or similar.
    Currently a stub that returns [] until the API contract is confirmed.
    """
    amis_key = getattr(env, "AMIS_API_KEY", "")
    if not amis_key:
        log_event("amis_skipped", {"reason": "no_api_key"})
        return []

    # Placeholder — real implementation:
    # url = f"https://amis.co.ke/api/prices?key={amis_key}&crops={','.join(crops)}"
    # response = await fetch(url)
    # raw = await response.json()
    # return normalize_amis(raw)

    return []


async def _fetch_kamis_prices(crops: list, env) -> list:
    """Fetch from KAMIS. Same pattern as AMIS."""
    kamis_key = getattr(env, "KAMIS_API_KEY", "")
    if not kamis_key:
        return []

    # Placeholder
    return []


async def _fallback_from_history(db: DB, crops: list) -> list:
    """
    If no external source is available, reuse the average of the last 7 days
    and write it as today's price. This keeps trends continuous.
    """
    today = now_iso()[:10]
    results = []

    for crop in crops[:20]:
        row = await db.query_one("""
            SELECT crop, market, county, unit, AVG(price) as avg_price
            FROM market_prices
            WHERE crop = ?
            AND price_date >= date('now', '-7 days')
            AND price_date < ?
            GROUP BY crop, market, county, unit
        """, [crop, today])

        if row and row["avg_price"]:
            results.append({
                "crop": row["crop"],
                "market": row["market"],
                "county": row.get("county"),
                "unit": row.get("unit", "kg"),
                "price": round(row["avg_price"], 2),
                "price_date": today,
                "source": "Carried forward (7-day avg)",
            })

    return results


# ============================================================
# TREND COMPUTATION
# ============================================================
async def _compute_trends(db: DB, crops: list, env):
    """Compute and cache trend direction for each crop."""
    from services.market_service import MarketService
    svc = MarketService(env)

    for crop in crops[:20]:
        try:
            trend = await svc.trend(crop, days=30)
            if trend and trend.get("direction") != "unknown":
                # Cache in KV for fast lookup
                cache_key = f"trend:{crop}:30d"
                import json
                await env.CACHE.put(
                    cache_key,
                    json.dumps(trend),
                    expirationTtl=3600 * 12,
                )
        except Exception as e:
            log_error(f"Trend failed for {crop}: {str(e)}")


# ============================================================
# HELPERS
# ============================================================
def _normalize_price(value) -> float | None:
    """Extract a numeric price from varied API formats."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("KES", "").strip())
    except (ValueError, TypeError):
        return None