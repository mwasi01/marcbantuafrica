"""
Marcbantu Africa — Market Intelligence Service.
Aggregates prices from KAMIS, AMIS, FEWS NET, WFP VAM, FAO GIEWS
+ farmer crowdsourced submissions.

Normalizes everything to a common schema, deduplicates,
computes trends, and prefers the freshest source.

Schema contract (from Migration 010 v2):
  crops(id, name, category, default_unit, aliases, icon, active)
  markets(id, name, market_type, county_or_region, country, country_code,
          latitude, longitude, currency, timezone, active,
          data_source, created_at)
  market_prices(id, crop, market, market_id, county, country, country_code,
                currency, price, unit, price_date, source, source_url,
                latitude, longitude, confidence,
                trend_7d_pct, trend_30d_pct, fetched_at)
  market_aliases(alias, market_id, source, confidence, created_at)
  unmatched_market_names(raw_name, country_code, source,
                         occurrences, first_seen, last_seen)
  farmer_price_reports(...)
"""

import json
import math
from datetime import datetime, timedelta
from js import fetch


# ============================================================
# HAVERSINE — GPS nearest market
# ============================================================
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


# ============================================================
# HELPERS — safe JSON / attribute access
# ============================================================
def _to_py(obj):
    """Pyodide returns JsProxy objects — unwrap to plain Python."""
    if hasattr(obj, "to_py"):
        return obj.to_py()
    return obj


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _s(v, default=""):
    return (v or default).strip() if isinstance(v, str) else (v or default)


def _today_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


# ============================================================
# SOURCE: KAMIS (Kenya) — daily, free
# ============================================================
async def fetch_kamis(env) -> list:
    """
    Kenya Agricultural Market Information System.
    Get API key from https://kamis.kilimo.go.ke
    Returns rows like: {market, county, commodity, unit, price, date}
    """
    api_key = getattr(env, "KAMIS_API_KEY", "")
    if not api_key:
        return []

    url = "https://kamis.kilimo.go.ke/api/v1/market-prices?limit=5000"
    try:
        resp = await fetch(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
        )
        if resp.status != 200:
            return []
        data = _to_py(await resp.json())
    except Exception:
        return []

    rows = []
    for item in data.get("data", []):
        rows.append(
            {
                "crop": _s(item.get("commodity")),
                "market": _s(item.get("market")),
                "county": item.get("county"),
                "country": "Kenya",
                "country_code": "KE",
                "currency": "KES",
                "price": _f(item.get("price")),
                "unit": _s(item.get("unit"), "kg"),
                "price_date": item.get("date"),
                "source": "KAMIS",
                "source_url": url,
                "confidence": "high",
            }
        )
    return rows


# ============================================================
# SOURCE: FEWS NET — pan-African, monthly, free
# ============================================================
async def fetch_fews_net(env, country_code: str = None, db=None) -> list:
    """
    FEWS NET datawarehouse — staple food prices.
    Public API: https://fdw.fews.net/api/marketpricefact

    If country_code is None, derives the country list from the
    `markets` table so it stays in sync with the 500-market seed.
    """
    base = "https://fdw.fews.net/api/marketpricefact"

    if country_code:
        countries = [country_code]
    elif db is not None:
        rows = await db.query(
            "SELECT DISTINCT country_code FROM markets WHERE active = 1"
        )
        countries = sorted({r["country_code"] for r in rows if r["country_code"]})
    else:
        # Fallback — full AU membership (matches the expanded seed)
        countries = [
            "KE",
            "UG",
            "TZ",
            "RW",
            "ET",
            "NG",
            "GH",
            "ZM",
            "ZW",
            "ZA",
            "EG",
            "MA",
            "SN",
            "CI",
            "CM",
            "MZ",
            "AO",
            "CD",
            "SD",
            "TN",
            "BF",
            "ML",
            "NE",
            "TD",
            "CF",
            "CG",
            "GA",
            "GQ",
            "BJ",
            "TG",
            "GN",
            "SL",
            "LR",
            "GW",
            "GM",
            "MR",
            "EH",
            "DZ",
            "LY",
            "ER",
            "DJ",
            "SO",
            "SS",
            "BI",
            "MW",
            "MG",
            "MU",
            "SC",
            "KM",
            "CV",
            "ST",
            "SZ",
            "LS",
            "BW",
            "NA",
        ]

    start = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")
    all_rows = []

    for cc in countries:
        url = f"{base}?country_code={cc}&start_date={start}&format=json&limit=1000"
        try:
            resp = await fetch(url)
            if resp.status != 200:
                continue
            data = _to_py(await resp.json())
        except Exception:
            continue

        for item in data.get("results", []):
            all_rows.append(
                {
                    "crop": _s(item.get("commodity_name")),
                    "market": _s(item.get("market_name")),
                    "country": item.get("country_name"),
                    "country_code": cc,
                    "currency": _s(item.get("currency_code"), "USD"),
                    "price": _f(item.get("price")),
                    "unit": _s(item.get("unit"), "kg"),
                    "price_date": item.get("period_date"),
                    "source": "FEWS NET",
                    "source_url": url,
                    "confidence": "medium",
                }
            )

    return all_rows


# ============================================================
# SOURCE: WFP VAM — pan-African, monthly, free
# ============================================================
async def fetch_wfp_vam(env, country_code: str = None, db=None) -> list:
    """
    World Food Programme Vulnerability Analysis & Mapping.
    https://data.humdata.org/dataset/wfp-food-prices
    """
    base = "https://api.hungermapdata.org/v2/food-prices"

    if country_code:
        countries = [country_code]
    elif db is not None:
        rows = await db.query(
            "SELECT DISTINCT country_code FROM markets WHERE active = 1"
        )
        countries = sorted({r["country_code"] for r in rows if r["country_code"]})
    else:
        countries = [
            "KE",
            "UG",
            "TZ",
            "RW",
            "ET",
            "NG",
            "GH",
            "ZM",
            "ZW",
            "ZA",
            "EG",
            "MA",
            "SN",
            "CI",
            "CM",
            "MZ",
            "AO",
            "CD",
            "SD",
            "TN",
            "BF",
            "ML",
            "NE",
            "TD",
            "CF",
            "CG",
            "GA",
            "GQ",
            "BJ",
            "TG",
            "GN",
            "SL",
            "LR",
            "GW",
            "GM",
            "MR",
            "EH",
            "DZ",
            "LY",
            "ER",
            "DJ",
            "SO",
            "SS",
            "BI",
            "MW",
            "MG",
            "MU",
            "SC",
            "KM",
            "CV",
            "ST",
            "SZ",
            "LS",
            "BW",
            "NA",
        ]

    all_rows = []
    for cc in countries:
        try:
            resp = await fetch(f"{base}?country={cc}&limit=1000")
            if resp.status != 200:
                continue
            data = _to_py(await resp.json())
        except Exception:
            continue

        for item in data.get("data", []):
            all_rows.append(
                {
                    "crop": _s(item.get("commodity")),
                    "market": _s(item.get("market")),
                    "country": item.get("country"),
                    "country_code": cc,
                    "currency": _s(item.get("currency"), "USD"),
                    "price": _f(item.get("price")),
                    "unit": _s(item.get("unit"), "kg"),
                    "price_date": item.get("date"),
                    "source": "WFP VAM",
                    "source_url": base,
                    "confidence": "medium",
                }
            )

    return all_rows


# ============================================================
# SOURCE: AMIS (stub) — African Market Information System
# ============================================================
async def fetch_amis(env) -> list:
    """
    AMIS — https://www.amis-outlook.org/
    Placeholder until an API key / feed is provisioned.
    """
    return []


# ============================================================
# SOURCE: FAO GIEWS (stub)
# ============================================================
async def fetch_fao_giews(env) -> list:
    """
    FAO GIEWS Food Price Monitoring — https://fpma.apps.fao.org/
    Placeholder until the CSV ingest endpoint is wired up.
    """
    return []


# ============================================================
# CROP NORMALIZATION
# ============================================================
# Fallback aliases — union of `crops.aliases` JSON across the 100 crops.
# At startup we merge these with the DB column so the two never drift.
_BASE_CROP_ALIASES = {
    # Staples
    "corn": "Maize",
    "mahindi": "Maize",
    "mais": "Maize",
    "maïs": "Maize",
    "maize (white)": "Maize",
    "maize (yellow)": "Maize",
    "haricot": "Beans",
    "maharagwe": "Beans",
    "kidney beans": "Beans",
    "mchele": "Rice",
    "paddy": "Rice",
    "rice (imported)": "Rice",
    "ngano": "Wheat",
    "triticum": "Wheat",
    "wheat flour": "Wheat",
    "muhogo": "Cassava",
    "manioc": "Cassava",
    "yuca": "Cassava",
    "mtama": "Sorghum",
    "durra": "Sorghum",
    "bajra": "Millet",
    "wimbi": "Finger Millet",
    "ragi": "Finger Millet",
    "eleusine": "Finger Millet",
    "viazi vitamu": "Sweet Potato",
    "kumara": "Sweet Potato",
    "viazi": "Irish Potato",
    "waru": "Irish Potato",
    "potato": "Irish Potato",
    "viazi vikuu": "Yam",
    "gonja": "Plantain",
    "ndizi": "Banana",
    "kunde": "Cowpeas",
    "black-eyed peas": "Cowpeas",
    "mbaazi": "Pigeon Peas",
    "ndengu": "Green Grams",
    "mung beans": "Green Grams",
    "njugu": "Groundnuts",
    "peanuts": "Groundnuts",
    "simsim": "Sesame",
    "benne": "Sesame",
    "tef": "Teff",
    "dagi": "Teff",
    "shairi": "Barley",
    "jai": "Oats",
    # Cash crops
    "kahawa": "Coffee (Arabica)",
    "arabica": "Coffee (Arabica)",
    "robusta": "Coffee (Robusta)",
    "chai": "Tea",
    "camellia": "Tea",
    "kakao": "Cocoa",
    "cacao": "Cocoa",
    "pamba": "Cotton",
    "cotton lint": "Cotton",
    "tumbaku": "Tobacco",
    "miwa": "Sugarcane",
    "cane": "Sugarcane",
    "katani": "Sisal",
    "korosho": "Cashew Nuts",
    "cashew nuts": "Cashew Nuts",
    "parachichi": "Avocado",
    "nazi": "Coconut",
    "mafuta ya mawese": "Palm Oil",
    "palm": "Palm Oil",
    # Livestock & animal products
    "ngombe": "Cattle",
    "ng ombe": "Cattle",
    "cows": "Cattle",
    "bulls": "Cattle",
    "mbuzi": "Goats",
    "goat": "Goats",
    "kondoo": "Sheep",
    "nguruwe": "Pigs",
    "pig": "Pigs",
    "ngamia": "Camels",
    "camel": "Camels",
    "punda": "Donkeys",
    "donkey": "Donkeys",
    "sungura": "Rabbits",
    "rabbit": "Rabbits",
    "kuku": "Chicken (Broiler)",
    "broiler": "Chicken (Broiler)",
    "kuku wa kienyeji": "Chicken (Local)",
    "mayai": "Eggs",
    "eggs": "Eggs",
    "maziwa": "Milk",
    "nyama ya ngombe": "Beef",
    "nyama ya ng ombe": "Beef",
    "beef": "Beef",
    "nyama ya mbuzi": "Goat Meat",
    "chevon": "Goat Meat",
    "nyama ya kondoo": "Mutton",
    "mutton": "Mutton",
    "nyama ya nguruwe": "Pork",
    "pork": "Pork",
    "asali": "Honey",
    # Vegetables
    "nyanya": "Tomatoes",
    "tomato": "Tomatoes",
    "vitunguu": "Onions",
    "onion": "Onions",
    "sukuma wiki": "Kale",
    "collards": "Kale",
    "kabichi": "Cabbage",
    "karoti": "Carrots",
    "carrot": "Carrots",
    "mchicha": "Spinach",
    "spinach": "Spinach",
    "pilipili hoho": "Green Pepper",
    "capsicum": "Green Pepper",
    "green pepper": "Green Pepper",
    "pilipili": "Red Pepper",
    "red pepper": "Red Pepper",
    "tango": "Cucumber",
    "cucumber": "Cucumber",
    "kabeji ya majani": "Lettuce",
    "lettuce": "Lettuce",
    "brokoli": "Broccoli",
    "broccoli": "Broccoli",
    "cauliflower": "Cauliflower",
    "beetroot": "Beetroot",
    "kitunguu saumu": "Garlic",
    "garlic": "Garlic",
    "tangawizi": "Ginger",
    "ginger": "Ginger",
    "bamia": "Okra",
    "okra": "Okra",
    "biringanya": "Eggplant",
    "brinjal": "Eggplant",
    "eggplant": "Eggplant",
    "malenge": "Pumpkin",
    "pumpkin": "Pumpkin",
    "butternut": "Butternut",
    "squash": "Butternut",
    "zucchini": "Zucchini",
    "courgette": "Zucchini",
    # Fruits
    "embe": "Mango",
    "mango": "Mango",
    "chungwa": "Oranges",
    "orange": "Oranges",
    "nanasi": "Pineapple",
    "pineapple": "Pineapple",
    "papai": "Papaya",
    "papaya": "Papaya",
    "tikiti maji": "Watermelon",
    "watermelon": "Watermelon",
    "zabibu": "Grapes",
    "grapes": "Grapes",
    "stroberi": "Strawberry",
    "strawberry": "Strawberry",
    "limau": "Lemon",
    "lemon": "Lemon",
    "ndimu": "Lime",
    "lime": "Lime",
    "pasheni": "Passion Fruit",
    "passion fruit": "Passion Fruit",
    "mapera": "Guava",
    "guava": "Guava",
    "komamanga": "Pomegranate",
    "pomegranate": "Pomegranate",
    "kiwi": "Kiwi",
    "pichi": "Peach",
    "peach": "Peach",
    "pear": "Pear",
    "plamu": "Plum",
    "plum": "Plum",
    # Other
    "alizeti": "Sunflower",
    "sunflower": "Sunflower",
    "soya": "Soya Beans",
    "soybean": "Soya Beans",
    "soya beans": "Soya Beans",
    "vanilla": "Vanilla",
    "vanili": "Vanilla",
    "iliki": "Cardamom",
    "mdalasini": "Cinnamon",
    "manjano": "Turmeric",
    "turmeric": "Turmeric",
}

# Legacy aliases for items outside the 100-crop catalog that occasionally
# appear in FEWS/WFP feeds. Kept so nothing gets dropped silently.
_EXTRA_ALIASES = {
    "samaki": "Fish",
    "sukari": "Sugar",
    "mafuta": "Cooking Oil",
    "unga wa ngano": "Wheat Flour",
    "unga wa mahindi": "Maize Flour",
    "mahindi ya kuchoma": "Roasted Maize",
}

CROP_ALIASES = {**_BASE_CROP_ALIASES, **_EXTRA_ALIASES}


async def load_aliases_from_db(db) -> dict:
    """
    Merge the aliases stored in the `crops` table (JSON column)
    into CROP_ALIASES so adding a crop in SQL auto-extends the service.
    """
    global CROP_ALIASES
    try:
        rows = await db.query("SELECT name, aliases FROM crops")
    except Exception:
        return CROP_ALIASES

    for r in rows:
        canonical = r["name"]
        raw = r.get("aliases")
        if not raw:
            continue
        try:
            aliases = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            continue
        for a in aliases:
            CROP_ALIASES[_s(a).lower()] = canonical

    return CROP_ALIASES


def normalize_crop(raw: str) -> str:
    if not raw:
        return raw
    key = raw.strip().lower()
    if key in CROP_ALIASES:
        return CROP_ALIASES[key]
    # Try without parenthetical suffixes: "Maize (white)" → "maize"
    stripped = key.split("(")[0].strip()
    if stripped in CROP_ALIASES:
        return CROP_ALIASES[stripped]
    return raw.strip().title()


# ============================================================
# MARKET NAME NORMALIZATION (fuzzy join to `markets` table)
# ============================================================
_NOISE_SUFFIXES = (
    " market",
    " central",
    " central market",
    " main market",
    " wholesale market",
    " retail market",
)

# Strip diacritics common in Francophone/Lusophone market names
_ACCENT_MAP = str.maketrans(
    {
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "á": "a",
        "à": "a",
        "â": "a",
        "ä": "a",
        "ã": "a",
        "í": "i",
        "ì": "i",
        "î": "i",
        "ï": "i",
        "ó": "o",
        "ò": "o",
        "ô": "o",
        "ö": "o",
        "õ": "o",
        "ú": "u",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ç": "c",
        "ñ": "n",
        "’": "'",
    }
)


def normalize_market_name(name: str) -> str:
    """
    'Wakulima Market'  → 'wakulima'
    'Nakasero Market'  → 'nakasero'
    'Marché Central'   → 'marche'
    'N''Djamena Central Market' → "n'djamena"
    """
    n = (name or "").strip().lower()
    n = n.translate(_ACCENT_MAP)
    for s in _NOISE_SUFFIXES:
        if n.endswith(s):
            n = n[: -len(s)]
            break
    return n.strip()


def build_market_lookup(markets: list) -> dict:
    """
    Two-key lookup: (normalized_name, country_code) and
    (normalized_name, None) for feeds that omit country_code.
    """
    lookup = {}
    for m in markets:
        n = normalize_market_name(m["name"])
        lookup[(n, m["country_code"])] = m
        lookup.setdefault((n, None), m)
    return lookup


async def build_market_lookup_with_aliases(db) -> dict:
    """
    Same as build_market_lookup, but also merges rows from `market_aliases`
    so curated aliases participate in matching.
    """
    markets = await db.query("""
        SELECT id, name, country, country_code,
               latitude, longitude, currency
        FROM markets WHERE active = 1
    """)
    lookup = build_market_lookup(markets)

    # Overlay curated aliases
    try:
        aliases = await db.query("""
            SELECT ma.alias, m.id, m.name, m.country, m.country_code,
                   m.latitude, m.longitude, m.currency
            FROM market_aliases ma
            JOIN markets m ON m.id = ma.market_id
            WHERE m.active = 1
        """)
    except Exception:
        aliases = []

    for a in aliases:
        n = normalize_market_name(a["alias"])
        m = {
            "id": a["id"],
            "name": a["name"],
            "country": a["country"],
            "country_code": a["country_code"],
            "latitude": a["latitude"],
            "longitude": a["longitude"],
            "currency": a["currency"],
        }
        lookup[(n, a["country_code"])] = m
        lookup.setdefault((n, None), m)

    return lookup


def match_market(raw_name: str, country_code: str, lookup: dict):
    """Try exact normalized, then country-agnostic."""
    n = normalize_market_name(raw_name)
    return lookup.get((n, country_code)) or lookup.get((n, None)) or None


# ============================================================
# UNMATCHED MARKET LOGGING
# ============================================================
async def log_unmatched_market(db, raw_name: str, country_code: str, source: str):
    """Record a market name we couldn't match — reviewed weekly."""
    try:
        await db.execute(
            """
            INSERT INTO unmatched_market_names (raw_name, country_code, source)
            VALUES (?, ?, ?)
            ON CONFLICT(raw_name, country_code, source) DO UPDATE SET
                occurrences = occurrences + 1,
                last_seen   = CURRENT_TIMESTAMP
        """,
            [raw_name, country_code, source],
        )
    except Exception:
        pass


# ============================================================
# DEDUP + RANK
# ============================================================
_CONF_RANK = {"high": 3, "medium": 2, "low": 1}


def dedup_and_rank(rows: list) -> list:
    """
    Keep the best row per (crop, market, price_date).
    Tiebreak: higher confidence → newer fetched_at → first seen.
    """
    seen = {}
    for r in rows:
        key = (r["crop"].lower(), r["market"].lower(), r["price_date"])
        new_rank = _CONF_RANK.get(r.get("confidence", "low"), 1)
        existing = seen.get(key)
        if existing is None:
            seen[key] = r
            continue
        old_rank = _CONF_RANK.get(existing.get("confidence", "low"), 1)
        if new_rank > old_rank:
            seen[key] = r
        elif new_rank == old_rank:
            if (r.get("fetched_at") or "") > (existing.get("fetched_at") or ""):
                seen[key] = r
    return list(seen.values())


# ============================================================
# TRENDS
# ============================================================
async def compute_trends(db, crop: str, market_id: int, country_code: str):
    """7d and 30d price change % for a crop at a market."""
    d7 = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    d30 = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    current = await db.query_one(
        """
        SELECT price FROM market_prices
        WHERE crop = ? AND market_id = ? AND country_code = ?
        ORDER BY price_date DESC LIMIT 1
    """,
        [crop, market_id, country_code],
    )

    week_ago = await db.query_one(
        """
        SELECT price FROM market_prices
        WHERE crop = ? AND market_id = ? AND country_code = ?
          AND price_date <= ?
        ORDER BY price_date DESC LIMIT 1
    """,
        [crop, market_id, country_code, d7],
    )

    month_ago = await db.query_one(
        """
        SELECT price FROM market_prices
        WHERE crop = ? AND market_id = ? AND country_code = ?
          AND price_date <= ?
        ORDER BY price_date DESC LIMIT 1
    """,
        [crop, market_id, country_code, d30],
    )

    trend_7d = trend_30d = None
    if current and week_ago and week_ago["price"]:
        trend_7d = round(
            (current["price"] - week_ago["price"]) / week_ago["price"] * 100, 1
        )
    if current and month_ago and month_ago["price"]:
        trend_30d = round(
            (current["price"] - month_ago["price"]) / month_ago["price"] * 100, 1
        )

    return trend_7d, trend_30d


# ============================================================
# INGEST — daily job entry point
# ============================================================
async def ingest_all(env):
    """
    06:00 EAT cron entry point.
      1. Fetch from every available source.
      2. Merge DB aliases + normalize crop names.
      3. Dedup + rank by confidence / freshness.
      4. Attach market_id + lat/lon by lookup (incl. curated aliases).
      5. Upsert into market_prices.
      6. Recompute trends.
      7. Log unmatched markets for weekly review.
    """
    from db import DB

    db = DB(env)

    await load_aliases_from_db(db)
    market_lookup = await build_market_lookup_with_aliases(db)

    all_rows = []
    all_rows += await fetch_kamis(env)
    all_rows += await fetch_fews_net(env, db=db)
    all_rows += await fetch_wfp_vam(env, db=db)
    all_rows += await fetch_amis(env)
    all_rows += await fetch_fao_giews(env)

    now_iso = datetime.utcnow().isoformat(timespec="seconds")
    normalized = []
    unmatched_count = 0

    for r in all_rows:
        r["crop"] = normalize_crop(r["crop"])
        if not r["crop"]:
            continue
        r["fetched_at"] = now_iso

        m = match_market(r.get("market", ""), r.get("country_code"), market_lookup)
        if not m:
            unmatched_count += 1
            await log_unmatched_market(
                db, r.get("market", ""), r.get("country_code"), r.get("source", "")
            )
            continue

        r["market_id"] = m["id"]
        r["latitude"] = m["latitude"]
        r["longitude"] = m["longitude"]
        r["country"] = m.get("country") or r.get("country")
        r["currency"] = m.get("currency") or r.get("currency", "USD")
        normalized.append(r)

    deduped = dedup_and_rank(normalized)

    inserted = 0
    touched_keys = set()
    for r in deduped:
        try:
            await db.execute(
                """
                INSERT INTO market_prices (
                    crop, market, market_id, county, country, country_code,
                    currency, price, unit, price_date, source, source_url,
                    latitude, longitude, confidence, fetched_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(crop, market_id, price_date, source) DO UPDATE SET
                    price        = excluded.price,
                    unit         = excluded.unit,
                    currency     = excluded.currency,
                    source_url   = excluded.source_url,
                    confidence   = excluded.confidence,
                    fetched_at   = excluded.fetched_at
            """,
                [
                    r["crop"],
                    r["market"],
                    r["market_id"],
                    r.get("county"),
                    r.get("country"),
                    r["country_code"],
                    r["currency"],
                    r["price"],
                    r.get("unit", "kg"),
                    r["price_date"],
                    r["source"],
                    r.get("source_url"),
                    r.get("latitude"),
                    r.get("longitude"),
                    r.get("confidence", "medium"),
                    r["fetched_at"],
                ],
            )
            inserted += 1
            touched_keys.add((r["crop"], r["market_id"], r["country_code"]))
        except Exception:
            pass

    # --- Recompute trends for the crops we just touched -------------
    for crop, market_id, cc in touched_keys:
        try:
            t7, t30 = await compute_trends(db, crop, market_id, cc)
            await db.execute(
                """
                UPDATE market_prices
                SET trend_7d_pct = ?, trend_30d_pct = ?
                WHERE crop = ? AND market_id = ? AND country_code = ?
                  AND price_date = (
                      SELECT MAX(price_date) FROM market_prices
                      WHERE crop = ? AND market_id = ? AND country_code = ?
                  )
            """,
                [t7, t30, crop, market_id, cc, crop, market_id, cc],
            )
        except Exception:
            pass

    return {
        "fetched": len(all_rows),
        "normalized": len(normalized),
        "unmatched": unmatched_count,
        "deduped": len(deduped),
        "upserted": inserted,
    }


# ============================================================
# QUERY: nearest markets + prices
# ============================================================
async def prices_near_me(
    db, lat: float, lon: float, radius_km: int = 200, crop: str = None, limit: int = 5
) -> dict:
    """Return today's prices at the N nearest markets."""
    markets = await db.query("""
        SELECT id, name, county_or_region, country, country_code,
               latitude, longitude, currency
        FROM markets
        WHERE active = 1
    """)

    with_distance = []
    for m in markets:
        if m["latitude"] is None or m["longitude"] is None:
            continue
        d = haversine_km(lat, lon, m["latitude"], m["longitude"])
        if d <= radius_km:
            m["distance_km"] = round(d, 1)
            with_distance.append(m)

    with_distance.sort(key=lambda x: x["distance_km"])
    nearest = with_distance[:limit]

    if not nearest:
        return {"markets": [], "radius_km": radius_km}

    market_ids = [m["id"] for m in nearest]
    placeholders = ",".join(["?"] * len(market_ids))

    crop_filter = " AND crop = ?" if crop else ""
    params = market_ids + ([crop] if crop else [])

    prices = await db.query(
        f"""
        SELECT mp.id, mp.crop, mp.market_id, mp.price, mp.unit, mp.currency,
               mp.price_date, mp.source, mp.confidence,
               mp.trend_7d_pct, mp.trend_30d_pct
        FROM market_prices mp
        WHERE mp.market_id IN ({placeholders}) {crop_filter}
          AND mp.price_date >= date('now', '-30 days')
        ORDER BY mp.crop, mp.price_date DESC
    """,
        params,
    )

    by_market = {m["id"]: {**m, "prices": []} for m in nearest}
    for p in prices:
        if p["market_id"] in by_market:
            by_market[p["market_id"]]["prices"].append(p)

    return {
        "reference": {"latitude": lat, "longitude": lon},
        "radius_km": radius_km,
        "markets": list(by_market.values()),
    }


# ============================================================
# QUERY: top movers (7d trend leaders)
# ============================================================
async def top_movers(
    db, country_code: str = None, days: int = 7, limit: int = 20
) -> list:
    """
    Rank crops by absolute 7d price change for a country (or continent).
    Useful for a dashboard "what's spiking this week" widget.
    """
    cc_filter = " AND country_code = ?" if country_code else ""
    params = [country_code] if country_code else []

    rows = await db.query(
        f"""
        SELECT crop, market_id, country_code, price, currency, unit,
               trend_7d_pct, price_date
        FROM market_prices
        WHERE trend_7d_pct IS NOT NULL
          AND price_date >= date('now', '-{int(days)} days')
          {cc_filter}
        ORDER BY ABS(trend_7d_pct) DESC
        LIMIT ?
    """,
        params + [limit],
    )

    return rows
