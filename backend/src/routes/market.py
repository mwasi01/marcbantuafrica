"""
Marcbantu Africa — Market & Sales routes.
Market prices, farmer sales, buyer directory, forward contracts, price alerts,
and near-me market intelligence.
"""

from utils import (
    success_response,
    error_response,
    parse_json,
    require_auth,
    now_iso,
    to_int,
    to_float,
    log_event,
    require_fields,
    paginated_response,
    _sp,
)
from validators import ValidationError, validate_sale
from constants import HTTP, ErrorCode, PaymentStatus
from db import DB


# ============================================================
# HELPERS
# ============================================================
async def _get_owned_farm(db: DB, farm_id: int, farmer_id: int):
    return await db.query_one(
        "SELECT id FROM farms WHERE id = ? AND farmer_id = ?", [farm_id, farmer_id]
    )


async def _get_owned_sale(db: DB, sale_id: int, farmer_id: int):
    return await db.query_one(
        """
        SELECT s.* FROM sales s
        JOIN farms f ON s.farm_id = f.id
        WHERE s.id = ? AND f.farmer_id = ?
    """,
        [sale_id, farmer_id],
    )


# ============================================================
# MARKET PRICES
# ============================================================
async def prices(request, env):
    """GET /api/market/prices
    Query: crop?, county?, market?, date?, latest=true
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["1=1"]
    params = []

    crop = url.search_params.get("crop")
    if crop:
        where.append("crop = ?")
        params.append(crop)

    county = url.search_params.get("county")
    if county:
        where.append("county = ?")
        params.append(county)

    market = url.search_params.get("market")
    if market:
        where.append("market = ?")
        params.append(market)

    price_date = url.search_params.get("date")
    if price_date:
        where.append("price_date = ?")
        params.append(price_date)
    elif url.search_params.get("latest", "true") == "true":
        # Only the most recent date per crop
        where.append("price_date = (SELECT MAX(price_date) FROM market_prices)")

    prices_list = await db.query(
        f"""
        SELECT * FROM market_prices
        WHERE {" AND ".join(where)}
        ORDER BY crop, market
        LIMIT 500
    """,
        params,
    )

    return success_response(prices_list)


async def price_history(request, env):
    """GET /api/market/prices/history
    Query: crop, market?, days=30
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    crop = url.search_params.get("crop")
    if not crop:
        return error_response(
            "'crop' is required", status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD
        )

    days = min(max(to_int(url.search_params.get("days", 30), 30), 1), 365)

    where = ["crop = ?", f"price_date >= date('now', '-{days} days')"]
    params = [crop]

    market = url.search_params.get("market")
    if market:
        where.append("market = ?")
        params.append(market)

    history = await db.query(
        f"""
        SELECT price_date, market, county, price, unit
        FROM market_prices
        WHERE {" AND ".join(where)}
        ORDER BY price_date ASC
    """,
        params,
    )

    # Group by date (average across markets)
    daily = {}
    for h in history:
        d = h["price_date"]
        daily.setdefault(d, []).append(h["price"])

    trend = [
        {"date": d, "avg_price": round(sum(p) / len(p), 2), "markets": len(p)}
        for d, p in sorted(daily.items())
    ]

    return success_response(
        {
            "crop": crop,
            "days": days,
            "history": history,
            "daily_trend": trend,
        }
    )


async def add_price(request, env):
    """POST /api/market/prices
    Body: {crop, market, price, unit?, county?, price_date, source?}
    Note: In production, restrict to admin role.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ["crop", "market", "price", "price_date"])
    if err_msg:
        return error_response(
            err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD
        )

    price_val = to_float(data["price"])
    if price_val <= 0:
        return error_response(
            "Price must be positive",
            status=HTTP.BAD_REQUEST,
            code=ErrorCode.VALIDATION_ERROR,
        )

    db = DB(env)
    price_id = await db.insert(
        "market_prices",
        {
            "crop": data["crop"],
            "variety": data.get("variety"),
            "market": data["market"],
            "county": data.get("county"),
            "country": data.get("country", "Kenya"),
            "price": price_val,
            "unit": data.get("unit", "kg"),
            "price_date": data["price_date"],
            "source": data.get("source", "Manual"),
            "quality_grade": data.get("quality_grade"),
            "notes": data.get("notes"),
        },
    )

    price = await db.query_one("SELECT * FROM market_prices WHERE id = ?", [price_id])

    # Trigger price alerts
    await check_price_alerts(data["crop"], price_val, env)

    return success_response(price, message="Price added", status=HTTP.CREATED)


# ============================================================
# NEAREST-MARKET PRICES (GPS-aware)
# ============================================================
async def prices_near_me(request, env):
    """GET /api/market/prices/near-me
    Query:
      farm_id             — use the farm's saved GPS (preferred)
      OR  lat + lon       — explicit coordinates
      radius_km=200       — max 1000
      crop=<name>         — optional single-crop filter
      limit=5             — max 20 markets

    Returns today's prices at the N nearest markets, sorted by distance.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    farm_id = url.search_params.get("farm_id")
    if farm_id:
        farm = await db.query_one(
            "SELECT latitude, longitude FROM farms WHERE id = ? AND farmer_id = ?",
            [to_int(farm_id), user["id"]],
        )
        if not farm or farm.get("latitude") is None or farm.get("longitude") is None:
            return error_response(
                "Farm has no GPS coordinates — edit the farm and add lat/lon first",
                status=HTTP.BAD_REQUEST,
                code=ErrorCode.MISSING_FIELD,
            )
        lat, lon = farm["latitude"], farm["longitude"]
    else:
        lat = to_float(url.search_params.get("lat"))
        lon = to_float(url.search_params.get("lon"))
        if not lat or not lon:
            return error_response(
                "Provide either farm_id or lat+lon",
                status=HTTP.BAD_REQUEST,
                code=ErrorCode.MISSING_FIELD,
            )

    radius_km = min(to_int(url.search_params.get("radius_km", 200), 200), 1000)
    crop = url.search_params.get("crop")
    limit = min(to_int(url.search_params.get("limit", 5), 5), 20)

    from services.market_intelligence import prices_near_me as svc_near_me

    data = await svc_near_me(db, lat, lon, radius_km, crop, limit)
    return success_response(data)


# ============================================================
# MANUAL INGEST TRIGGER (admin only)
# ============================================================
async def trigger_ingest(request, env):
    """POST /api/market/prices/ingest
    Admin-only manual trigger for the daily cron.
    Requires the caller's email to match env.SUPPORT_EMAIL and be verified.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    me = await db.query_one(
        "SELECT email, verified FROM farmers WHERE id = ?",
        [user["id"]],
    )
    admin_email = getattr(env, "SUPPORT_EMAIL", "support@marcbantuafrica.com")
    if not me or me.get("email") != admin_email or not me.get("verified"):
        return error_response(
            "Admin access required",
            status=HTTP.FORBIDDEN,
            code=ErrorCode.FORBIDDEN,
        )

    from services.market_intelligence import ingest_all

    result = await ingest_all(env)
    return success_response(result, message="Ingest complete")


# ============================================================
# SALES
# ============================================================
async def list_sales(request, env):
    """GET /api/market/sales
    Query: farm_id?, buyer_id?, status?, from?, to?, page, page_size
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["f.farmer_id = ?"]
    params = [user["id"]]

    farm_id = url.search_params.get("farm_id")
    if farm_id:
        where.append("s.farm_id = ?")
        params.append(to_int(farm_id))

    buyer_id = url.search_params.get("buyer_id")
    if buyer_id:
        where.append("s.buyer_id = ?")
        params.append(to_int(buyer_id))

    status = url.search_params.get("status")
    if status:
        where.append("s.payment_status = ?")
        params.append(status)

    date_from = url.search_params.get("from")
    if date_from:
        where.append("s.sale_date >= ?")
        params.append(date_from)

    date_to = url.search_params.get("to")
    if date_to:
        where.append("s.sale_date <= ?")
        params.append(date_to)

    page = to_int(url.search_params.get("page", 1), 1)
    page_size = to_int(url.search_params.get("page_size", 50), 50)

    sql = f"""
        SELECT s.*,
               f.name as farm_name,
               b.name as buyer_name,
               e.name as enterprise_name
        FROM sales s
        JOIN farms f ON s.farm_id = f.id
        LEFT JOIN buyers b ON s.buyer_id = b.id
        LEFT JOIN enterprises e ON s.enterprise_id = e.id
        WHERE {" AND ".join(where)}
        ORDER BY s.sale_date DESC, s.id DESC
    """

    result = await db.paginate(sql, params, page=page, page_size=page_size)
    return paginated_response(result, message="Sales retrieved")


async def create_sale(request, env):
    """POST /api/market/sales"""
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    try:
        clean = validate_sale(data)
    except ValidationError as e:
        return error_response(
            e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR
        )

    db = DB(env)
    farm = await _get_owned_farm(db, clean["farm_id"], user["id"])
    if not farm:
        return error_response(
            "Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND
        )

    # Buyer validation
    if clean.get("buyer_id"):
        buyer = await db.query_one(
            "SELECT id FROM buyers WHERE id = ?", [clean["buyer_id"]]
        )
        if not buyer:
            clean["buyer_id"] = None

    sale_id = await db.insert("sales", clean)

    # Auto-create income transaction
    if clean["total"] > 0:
        await db.insert(
            "transactions",
            {
                "farm_id": clean["farm_id"],
                "enterprise_id": clean.get("enterprise_id"),
                "type": "income",
                "category": "crop_sales",
                "description": f"{clean['product']} sale — {clean['quantity']} {clean['unit']}",
                "amount": clean["total"],
                "payment_method": clean.get("payment_method"),
                "transaction_date": clean["sale_date"],
            },
        )

    sale = await db.query_one(
        """
        SELECT s.*, b.name as buyer_name, f.name as farm_name
        FROM sales s
        JOIN farms f ON s.farm_id = f.id
        LEFT JOIN buyers b ON s.buyer_id = b.id
        WHERE s.id = ?
    """,
        [sale_id],
    )

    log_event(
        "sale_created",
        {
            "sale_id": sale_id,
            "farmer_id": user["id"],
            "total": clean["total"],
        },
    )

    return success_response(sale, message="Sale recorded", status=HTTP.CREATED)


async def update_sale(request, env, sale_id: int):
    """PUT /api/market/sales/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    sale = await _get_owned_sale(db, sale_id, user["id"])
    if not sale:
        return error_response(
            "Sale not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND
        )

    data = await parse_json(request)
    allowed = [
        "buyer_id",
        "product",
        "quantity",
        "unit",
        "unit_price",
        "payment_status",
        "payment_method",
        "amount_paid",
        "payment_date",
        "sale_date",
        "notes",
    ]
    updates = {}
    for k in allowed:
        if k in data:
            if k in ("quantity", "unit_price", "amount_paid"):
                updates[k] = to_float(data[k])
            elif k in ("buyer_id", "enterprise_id"):
                updates[k] = to_int(data[k]) or None
            elif k == "payment_status":
                if data[k] not in PaymentStatus.ALL:
                    return error_response(
                        "Invalid payment_status",
                        status=HTTP.BAD_REQUEST,
                        code=ErrorCode.VALIDATION_ERROR,
                    )
                updates[k] = data[k]
            else:
                updates[k] = data[k]

    # Recalculate total if quantity/unit_price changed
    qty = updates.get("quantity", sale["quantity"])
    price = updates.get("unit_price", sale["unit_price"])
    if "quantity" in updates or "unit_price" in updates:
        updates["total"] = qty * price

    if not updates:
        return error_response(
            "No valid fields to update",
            status=HTTP.BAD_REQUEST,
            code=ErrorCode.VALIDATION_ERROR,
        )

    updates["updated_at"] = now_iso()
    await db.update("sales", updates, "id = ?", [sale_id])

    updated = await db.query_one("SELECT * FROM sales WHERE id = ?", [sale_id])
    return success_response(updated, message="Sale updated")


async def delete_sale(request, env, sale_id: int):
    """DELETE /api/market/sales/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    sale = await _get_owned_sale(db, sale_id, user["id"])
    if not sale:
        return error_response(
            "Sale not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND
        )

    # Delete linked transaction (match by amount + date + description)
    await db.execute(
        """
        DELETE FROM transactions
        WHERE farm_id = ? AND type = 'income' AND amount = ? AND transaction_date = ?
        AND description LIKE ?
    """,
        [
            sale["farm_id"],
            sale["total"],
            sale["sale_date"],
            f"%{sale['product']}%",
        ],
    )

    await db.delete("sales", "id = ?", [sale_id])

    await db.insert(
        "audit_log",
        {
            "farmer_id": user["id"],
            "action": "sale_deleted",
            "entity": "sale",
            "entity_id": sale_id,
        },
    )

    return success_response(None, message="Sale deleted")


# ============================================================
# BUYERS
# ============================================================
async def list_buyers(request, env):
    """GET /api/market/buyers
    Query: search?, type?, county?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["active = 1"]
    params = []

    search = url.search_params.get("search")
    if search:
        where.append("(name LIKE ? OR phone LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])

    buyer_type = url.search_params.get("type")
    if buyer_type:
        where.append("type = ?")
        params.append(buyer_type)

    county = url.search_params.get("county")
    if county:
        where.append("county = ?")
        params.append(county)

    buyers = await db.query(
        f"""
        SELECT * FROM buyers
        WHERE {" AND ".join(where)}
        ORDER BY rating DESC, name
        LIMIT 200
    """,
        params,
    )

    return success_response(buyers)


async def create_buyer(request, env):
    """POST /api/market/buyers"""
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ["name"])
    if err_msg:
        return error_response(
            err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD
        )

    db = DB(env)

    # Dedup by name+phone
    existing = await db.query_one(
        "SELECT id FROM buyers WHERE name = ? AND (phone = ? OR ? IS NULL)",
        [data["name"], data.get("phone"), data.get("phone")],
    )
    if existing:
        return error_response(
            "Buyer already exists", status=HTTP.CONFLICT, code=ErrorCode.ALREADY_EXISTS
        )

    buyer_id = await db.insert(
        "buyers",
        {
            "name": data["name"],
            "type": data.get("type"),
            "phone": data.get("phone"),
            "email": data.get("email"),
            "location": data.get("location"),
            "county": data.get("county"),
            "country": data.get("country", "Kenya"),
            "rating": to_float(data.get("rating", 0)),
            "payment_terms": data.get("payment_terms"),
            "products_bought": data.get("products_bought"),
            "notes": data.get("notes"),
            "active": 1,
        },
    )

    buyer = await db.query_one("SELECT * FROM buyers WHERE id = ?", [buyer_id])
    return success_response(buyer, message="Buyer created", status=HTTP.CREATED)


async def update_buyer(request, env, buyer_id: int):
    """PUT /api/market/buyers/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    buyer = await db.query_one("SELECT id FROM buyers WHERE id = ?", [buyer_id])
    if not buyer:
        return error_response(
            "Buyer not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND
        )

    data = await parse_json(request)
    allowed = [
        "name",
        "type",
        "phone",
        "email",
        "location",
        "county",
        "rating",
        "payment_terms",
        "products_bought",
        "notes",
        "active",
    ]
    updates = {}
    for k in allowed:
        if k in data:
            if k == "rating":
                updates[k] = to_float(data[k])
            elif k == "active":
                updates[k] = 1 if data[k] else 0
            else:
                updates[k] = data[k]

    if not updates:
        return error_response(
            "No valid fields to update",
            status=HTTP.BAD_REQUEST,
            code=ErrorCode.VALIDATION_ERROR,
        )

    updates["updated_at"] = now_iso()
    await db.update("buyers", updates, "id = ?", [buyer_id])

    updated = await db.query_one("SELECT * FROM buyers WHERE id = ?", [buyer_id])
    return success_response(updated, message="Buyer updated")


# ============================================================
# CONTRACTS
# ============================================================
async def list_contracts(request, env):
    """GET /api/market/contracts
    Query: farm_id?, buyer_id?, status?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["f.farmer_id = ?"]
    params = [user["id"]]

    farm_id = url.search_params.get("farm_id")
    if farm_id:
        where.append("c.farm_id = ?")
        params.append(to_int(farm_id))

    buyer_id = url.search_params.get("buyer_id")
    if buyer_id:
        where.append("c.buyer_id = ?")
        params.append(to_int(buyer_id))

    status = url.search_params.get("status")
    if status:
        where.append("c.status = ?")
        params.append(status)

    contracts = await db.query(
        f"""
        SELECT c.*, b.name as buyer_name, f.name as farm_name, e.name as enterprise_name
        FROM contracts c
        JOIN farms f ON c.farm_id = f.id
        JOIN buyers b ON c.buyer_id = b.id
        LEFT JOIN enterprises e ON c.enterprise_id = e.id
        WHERE {" AND ".join(where)}
        ORDER BY c.delivery_start_date DESC, c.id DESC
    """,
        params,
    )

    return success_response(contracts)


async def create_contract(request, env):
    """POST /api/market/contracts"""
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ["farm_id", "buyer_id", "product"])
    if err_msg:
        return error_response(
            err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD
        )

    db = DB(env)

    farm = await _get_owned_farm(db, to_int(data["farm_id"]), user["id"])
    if not farm:
        return error_response(
            "Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND
        )

    buyer = await db.query_one(
        "SELECT id FROM buyers WHERE id = ?", [to_int(data["buyer_id"])]
    )
    if not buyer:
        return error_response(
            "Buyer not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND
        )

    quantity = to_float(data.get("quantity"))
    price_per_unit = to_float(data.get("price_per_unit"))
    total_value = quantity * price_per_unit if quantity and price_per_unit else None

    contract_id = await db.insert(
        "contracts",
        {
            "farm_id": to_int(data["farm_id"]),
            "buyer_id": to_int(data["buyer_id"]),
            "enterprise_id": to_int(data.get("enterprise_id")) or None,
            "product": data["product"],
            "quantity": quantity,
            "unit": data.get("unit", "kg"),
            "price_per_unit": price_per_unit,
            "total_value": total_value,
            "delivery_start_date": data.get("delivery_start_date"),
            "delivery_end_date": data.get("delivery_end_date"),
            "delivery_location": data.get("delivery_location"),
            "payment_terms": data.get("payment_terms"),
            "status": data.get("status", "draft"),
            "signed_date": data.get("signed_date"),
            "notes": data.get("notes"),
        },
    )

    contract = await db.query_one(
        """
        SELECT c.*, b.name as buyer_name
        FROM contracts c
        JOIN buyers b ON c.buyer_id = b.id
        WHERE c.id = ?
    """,
        [contract_id],
    )

    return success_response(contract, message="Contract created", status=HTTP.CREATED)


# ============================================================
# PRICE ALERTS
# ============================================================
async def list_alerts(request, env):
    """GET /api/market/alerts"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    alerts = await db.query(
        """
        SELECT * FROM price_alerts
        WHERE farmer_id = ?
        ORDER BY active DESC, created_at DESC
    """,
        [user["id"]],
    )

    return success_response(alerts)


async def create_alert(request, env):
    """POST /api/market/alerts
    Body: {crop, target_price, direction: 'above'|'below'}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ["crop", "target_price"])
    if err_msg:
        return error_response(
            err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD
        )

    direction = data.get("direction", "above")
    if direction not in ("above", "below"):
        return error_response(
            "direction must be 'above' or 'below'",
            status=HTTP.BAD_REQUEST,
            code=ErrorCode.VALIDATION_ERROR,
        )

    db = DB(env)
    alert_id = await db.insert(
        "price_alerts",
        {
            "farmer_id": user["id"],
            "crop": data["crop"],
            "target_price": to_float(data["target_price"]),
            "direction": direction,
            "active": 1,
        },
    )

    alert = await db.query_one("SELECT * FROM price_alerts WHERE id = ?", [alert_id])
    return success_response(alert, message="Alert created", status=HTTP.CREATED)


async def delete_alert(request, env, alert_id: int):
    """DELETE /api/market/alerts/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    alert = await db.query_one(
        "SELECT id FROM price_alerts WHERE id = ? AND farmer_id = ?",
        [alert_id, user["id"]],
    )
    if not alert:
        return error_response(
            "Alert not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND
        )

    await db.delete("price_alerts", "id = ?", [alert_id])
    return success_response(None, message="Alert deleted")


async def check_price_alerts(crop: str, new_price: float, env):
    """Called after a new price is added. Triggers matching alerts."""
    db = DB(env)
    alerts = await db.query(
        """
        SELECT pa.*, f.phone, f.full_name, f.id as farmer_id
        FROM price_alerts pa
        JOIN farmers f ON pa.farmer_id = f.id
        WHERE pa.crop = ? AND pa.active = 1
    """,
        [crop],
    )

    for alert in alerts:
        triggered = False
        if alert["direction"] == "above" and new_price >= alert["target_price"]:
            triggered = True
        elif alert["direction"] == "below" and new_price <= alert["target_price"]:
            triggered = True

        if not triggered:
            continue

        # Queue SMS
        await env.JOBS.send(
            {
                "type": "send_sms",
                "payload": {
                    "to": alert["phone"],
                    "farmer_id": alert["farmer_id"],
                    "template_code": "PRICE_TARGET",
                    "variables": {
                        "crop": crop,
                        "market": "local market",
                        "price": f"{new_price:,.2f}",
                        "target": f"{alert['target_price']:,.2f}",
                    },
                },
            }
        )

        # Mark triggered
        await db.update(
            "price_alerts",
            {
                "triggered_at": now_iso(),
                "active": 0,
            },
            "id = ?",
            [alert["id"]],
        )

        log_event(
            "price_alert_triggered",
            {
                "alert_id": alert["id"],
                "crop": crop,
                "price": new_price,
            },
        )


# ============================================================
# SALES SUMMARY
# ============================================================
async def sales_summary(request, env):
    """GET /api/market/sales/summary
    Query: farm_id?, from?, to?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["f.farmer_id = ?"]
    params = [user["id"]]

    farm_id = url.search_params.get("farm_id")
    if farm_id:
        where.append("s.farm_id = ?")
        params.append(to_int(farm_id))

    date_from = url.search_params.get("from")
    if date_from:
        where.append("s.sale_date >= ?")
        params.append(date_from)

    date_to = url.search_params.get("to")
    if date_to:
        where.append("s.sale_date <= ?")
        params.append(date_to)

    where_sql = " AND ".join(where)

    # Totals
    totals = await db.query_one(
        f"""
        SELECT
            COUNT(*) as total_sales,
            COALESCE(SUM(s.total), 0) as total_revenue,
            COALESCE(SUM(s.amount_paid), 0) as total_collected,
            COUNT(CASE WHEN s.payment_status = 'pending' THEN 1 END) as pending_count,
            COALESCE(SUM(CASE WHEN s.payment_status = 'pending' THEN s.total ELSE 0 END), 0) as pending_amount
        FROM sales s
        JOIN farms f ON s.farm_id = f.id
        WHERE {where_sql}
    """,
        params,
    )

    # Top products
    top_products = await db.query(
        f"""
        SELECT s.product,
            COUNT(*) as count,
            SUM(s.quantity) as total_quantity,
            SUM(s.total) as total_revenue
        FROM sales s
        JOIN farms f ON s.farm_id = f.id
        WHERE {where_sql}
        GROUP BY s.product
        ORDER BY total_revenue DESC
        LIMIT 10
    """,
        params,
    )

    # Top buyers
    top_buyers = await db.query(
        f"""
        SELECT b.id as buyer_id, b.name as buyer_name,
            COUNT(*) as count,
            SUM(s.total) as total_revenue
        FROM sales s
        JOIN farms f ON s.farm_id = f.id
        LEFT JOIN buyers b ON s.buyer_id = b.id
        WHERE {where_sql}
        GROUP BY b.id
        ORDER BY total_revenue DESC
        LIMIT 10
    """,
        params,
    )

    # By month
    monthly = await db.query(
        f"""
        SELECT strftime('%Y-%m', s.sale_date) as month,
            COUNT(*) as count,
            SUM(s.total) as revenue
        FROM sales s
        JOIN farms f ON s.farm_id = f.id
        WHERE {where_sql}
        GROUP BY month
        ORDER BY month
    """,
        params,
    )

    return success_response(
        {
            "totals": totals,
            "top_products": top_products,
            "top_buyers": top_buyers,
            "monthly": monthly,
        }
    )
