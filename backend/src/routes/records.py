"""
Marcbantu Africa — Record routes.
Farm records: crop activities, livestock, inputs, harvests, sales, observations.
Includes offline sync support (delegated to jobs/sync_records.py).
"""
from utils import (
    success_response, error_response, parse_json, require_auth,
    now_iso, to_int, to_float, log_event, get_int_query, get_query,
    generate_reference, paginated_response,
    _sp,
)
from validators import ValidationError, validate_record
from constants import HTTP, ErrorCode, RecordType
from db import DB


# ============================================================
# HELPERS
# ============================================================
async def _get_owned_farm(db: DB, farm_id: int, farmer_id: int):
    """Fetch a farm ensuring the requesting farmer owns it."""
    return await db.query_one(
        "SELECT id FROM farms WHERE id = ? AND farmer_id = ?",
        [farm_id, farmer_id]
    )


async def _get_owned_record(db: DB, record_id: int, farmer_id: int):
    """Fetch a record ensuring the requesting farmer owns it (via farm)."""
    return await db.query_one("""
        SELECT r.* FROM records r
        JOIN farms f ON r.farm_id = f.id
        WHERE r.id = ? AND f.farmer_id = ?
    """, [record_id, farmer_id])


async def _validate_relations(db: DB, record: dict, farm_id: int):
    """
    Verify that enterprise_id and plot_id (if present) belong to the farm.
    Returns (clean_record, error_message).
    """
    if record.get("enterprise_id"):
        ent = await db.query_one(
            "SELECT id FROM enterprises WHERE id = ? AND farm_id = ?",
            [record["enterprise_id"], farm_id]
        )
        if not ent:
            return record, "Enterprise does not belong to this farm"

    if record.get("plot_id"):
        plot = await db.query_one(
            "SELECT id FROM plots WHERE id = ? AND farm_id = ?",
            [record["plot_id"], farm_id]
        )
        if not plot:
            return record, "Plot does not belong to this farm"

    return record, None


async def _auto_create_transaction(db: DB, record: dict, user_id: int):
    """
    Auto-create a matching transaction when a record is a sale or expense.
    Sale → income transaction
    Expense → expense transaction
    Skips if a transaction already exists for this record.
    """
    record_id = record.get("id")
    if not record_id:
        return None

    # Skip if transaction already exists
    existing = await db.query_one(
        "SELECT id FROM transactions WHERE record_id = ?",
        [record_id]
    )
    if existing:
        return None

    rtype = record.get("record_type")
    revenue = to_float(record.get("revenue")) or 0
    cost = to_float(record.get("cost")) or 0

    if rtype == "sale" and revenue > 0:
        tx_id = await db.insert("transactions", {
            "farm_id": record["farm_id"],
            "enterprise_id": record.get("enterprise_id"),
            "record_id": record_id,
            "type": "income",
            "category": "crop_sales",
            "description": record.get("description") or "Sale",
            "amount": revenue,
            "transaction_date": record["record_date"],
            "created_by": user_id,
        })
        return tx_id

    if rtype == "expense" and cost > 0:
        tx_id = await db.insert("transactions", {
            "farm_id": record["farm_id"],
            "enterprise_id": record.get("enterprise_id"),
            "record_id": record_id,
            "type": "expense",
            "category": "other_expense",
            "description": record.get("description") or "Expense",
            "amount": cost,
            "transaction_date": record["record_date"],
            "created_by": user_id,
        })
        return tx_id

    return None


# ============================================================
# LIST RECORDS (filterable, paginated)
# ============================================================
async def list_records(request, env):
    """GET /api/records
    Query params:
      farm_id, enterprise_id, plot_id, type, activity,
      from, to, q (search), sort, page, page_size
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
        where.append("r.farm_id = ?")
        params.append(to_int(farm_id))

    enterprise_id = url.search_params.get("enterprise_id")
    if enterprise_id:
        where.append("r.enterprise_id = ?")
        params.append(to_int(enterprise_id))

    plot_id = url.search_params.get("plot_id")
    if plot_id:
        where.append("r.plot_id = ?")
        params.append(to_int(plot_id))

    rec_type = url.search_params.get("type")
    if rec_type:
        where.append("r.record_type = ?")
        params.append(rec_type)

    activity = url.search_params.get("activity")
    if activity:
        where.append("r.activity = ?")
        params.append(activity)

    date_from = url.search_params.get("from")
    if date_from:
        where.append("r.record_date >= ?")
        params.append(date_from)

    date_to = url.search_params.get("to")
    if date_to:
        where.append("r.record_date <= ?")
        params.append(date_to)

    search = url.search_params.get("q")
    if search:
        where.append("(r.description LIKE ? OR r.notes LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])

    # Sort
    sort_map = {
        "date_desc": "r.record_date DESC, r.id DESC",
        "date_asc": "r.record_date ASC, r.id ASC",
        "created_desc": "r.created_at DESC",
        "amount_desc": "r.cost DESC",
        "amount_asc": "r.cost ASC",
    }
    sort = sort_map.get(
        url.search_params.get("sort", "date_desc"),
        "r.record_date DESC, r.id DESC",
    )

    page = to_int(url.search_params.get("page", 1), 1)
    page_size = to_int(url.search_params.get("page_size", 50), 50)

    sql = f"""
        SELECT r.*,
               f.name as farm_name,
               e.name as enterprise_name,
               p.name as plot_name
        FROM records r
        JOIN farms f ON r.farm_id = f.id
        LEFT JOIN enterprises e ON r.enterprise_id = e.id
        LEFT JOIN plots p ON r.plot_id = p.id
        WHERE {' AND '.join(where)}
        ORDER BY {sort}
    """

    result = await db.paginate(sql, params, page=page, page_size=page_size)
    return paginated_response(result, message="Records retrieved")


# ============================================================
# CREATE RECORD
# ============================================================
async def create_record(request, env):
    """POST /api/records"""
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)

    try:
        clean = validate_record(data)
    except ValidationError as e:
        return error_response(e.message,
                             status=HTTP.BAD_REQUEST,
                             code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)

    # Ownership
    farm = await _get_owned_farm(db, clean["farm_id"], user["id"])
    if not farm:
        return error_response("Farm not found",
                             status=HTTP.NOT_FOUND,
                             code=ErrorCode.NOT_FOUND)

    # Validate enterprise / plot belong to farm
    clean, rel_err = await _validate_relations(db, clean, clean["farm_id"])
    if rel_err:
        return error_response(rel_err,
                             status=HTTP.BAD_REQUEST,
                             code=ErrorCode.VALIDATION_ERROR)

    clean["created_by"] = user["id"]
    clean["sync_source"] = "online"

    record_id = await db.insert("records", clean)
    record = await db.query_one("""
        SELECT r.*, f.name as farm_name, e.name as enterprise_name, p.name as plot_name
        FROM records r
        JOIN farms f ON r.farm_id = f.id
        LEFT JOIN enterprises e ON r.enterprise_id = e.id
        LEFT JOIN plots p ON r.plot_id = p.id
        WHERE r.id = ?
    """, [record_id])

    # Auto-create transaction (sale → income, expense → expense)
    await _auto_create_transaction(db, record, user["id"])

    log_event("record_created", {
        "record_id": record_id,
        "farmer_id": user["id"],
        "type": clean["record_type"],
    })

    return success_response(record, message="Record created", status=HTTP.CREATED)


# ============================================================
# GET RECORD
# ============================================================
async def get_record(request, env, record_id: int):
    """GET /api/records/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    record = await db.query_one("""
        SELECT r.*,
               f.name as farm_name,
               e.name as enterprise_name,
               p.name as plot_name
        FROM records r
        JOIN farms f ON r.farm_id = f.id
        LEFT JOIN enterprises e ON r.enterprise_id = e.id
        LEFT JOIN plots p ON r.plot_id = p.id
        WHERE r.id = ? AND f.farmer_id = ?
    """, [record_id, user["id"]])

    if not record:
        return error_response("Record not found",
                             status=HTTP.NOT_FOUND,
                             code=ErrorCode.NOT_FOUND)

    # Linked transactions
    record["transactions"] = await db.query(
        "SELECT id, type, category, amount, transaction_date "
        "FROM transactions WHERE record_id = ?",
        [record_id]
    )

    return success_response(record)


# ============================================================
# UPDATE RECORD
# ============================================================
async def update_record(request, env, record_id: int):
    """PUT /api/records/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    record = await _get_owned_record(db, record_id, user["id"])
    if not record:
        return error_response("Record not found",
                             status=HTTP.NOT_FOUND,
                             code=ErrorCode.NOT_FOUND)

    data = await parse_json(request)

    allowed = ["activity", "description", "quantity", "unit", "cost",
               "revenue", "record_date", "notes", "photo_url",
               "enterprise_id", "plot_id"]
    updates = {}
    for k in allowed:
        if k in data:
            if k in ("quantity", "cost", "revenue"):
                updates[k] = to_float(data[k])
            elif k in ("enterprise_id", "plot_id"):
                updates[k] = to_int(data[k]) or None
            else:
                updates[k] = data[k]

    if not updates:
        return error_response("No valid fields to update",
                             status=HTTP.BAD_REQUEST,
                             code=ErrorCode.VALIDATION_ERROR)

    # Re-validate relations if changed
    if "enterprise_id" in updates or "plot_id" in updates:
        check = {**record, **updates}
        _, rel_err = await _validate_relations(db, check, record["farm_id"])
        if rel_err:
            return error_response(rel_err,
                                 status=HTTP.BAD_REQUEST,
                                 code=ErrorCode.VALIDATION_ERROR)

    updates["updated_at"] = now_iso()
    await db.update("records", updates, "id = ?", [record_id])

    updated = await db.query_one("""
        SELECT r.*, f.name as farm_name, e.name as enterprise_name
        FROM records r
        JOIN farms f ON r.farm_id = f.id
        LEFT JOIN enterprises e ON r.enterprise_id = e.id
        WHERE r.id = ?
    """, [record_id])

    # Update linked transaction amounts if revenue/cost changed
    if "revenue" in updates or "cost" in updates:
        await _sync_linked_transaction(db, record_id, updated)

    return success_response(updated, message="Record updated")


async def _sync_linked_transaction(db: DB, record_id: int, record: dict):
    """Keep the linked transaction in sync with record revenue/cost."""
    tx = await db.query_one(
        "SELECT id, type FROM transactions WHERE record_id = ?",
        [record_id]
    )
    if not tx:
        return

    if tx["type"] == "income" and record.get("revenue") is not None:
        await db.update("transactions", {
            "amount": to_float(record["revenue"]),
            "transaction_date": record.get("record_date"),
        }, "id = ?", [tx["id"]])

    if tx["type"] == "expense" and record.get("cost") is not None:
        await db.update("transactions", {
            "amount": to_float(record["cost"]),
            "transaction_date": record.get("record_date"),
        }, "id = ?", [tx["id"]])


# ============================================================
# DELETE RECORD
# ============================================================
async def delete_record(request, env, record_id: int):
    """DELETE /api/records/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    record = await _get_owned_record(db, record_id, user["id"])
    if not record:
        return error_response("Record not found",
                             status=HTTP.NOT_FOUND,
                             code=ErrorCode.NOT_FOUND)

    # Delete linked transactions first
    await db.delete("transactions", "record_id = ?", [record_id])
    await db.delete("records", "id = ?", [record_id])

    await db.insert("audit_log", {
        "farmer_id": user["id"],
        "action": "record_deleted",
        "entity": "record",
        "entity_id": record_id,
    })

    return success_response(None, message="Record deleted")


# ============================================================
# RECORD SUMMARY
# ============================================================
async def get_summary(request, env):
    """GET /api/records/summary
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
        where.append("r.farm_id = ?")
        params.append(to_int(farm_id))

    date_from = url.search_params.get("from")
    if date_from:
        where.append("r.record_date >= ?")
        params.append(date_from)

    date_to = url.search_params.get("to")
    if date_to:
        where.append("r.record_date <= ?")
        params.append(date_to)

    where_sql = " AND ".join(where)

    # By type
    by_type = await db.query(f"""
        SELECT r.record_type, COUNT(*) as count
        FROM records r
        JOIN farms f ON r.farm_id = f.id
        WHERE {where_sql}
        GROUP BY r.record_type
    """, params)

    # By activity (top 10)
    by_activity = await db.query(f"""
        SELECT r.activity, COUNT(*) as count
        FROM records r
        JOIN farms f ON r.farm_id = f.id
        WHERE {where_sql} AND r.activity IS NOT NULL
        GROUP BY r.activity
        ORDER BY count DESC
        LIMIT 10
    """, params)

    # Totals
    totals = await db.query_one(f"""
        SELECT
            COUNT(*) as total,
            COALESCE(SUM(r.cost), 0) as total_cost,
            COALESCE(SUM(r.revenue), 0) as total_revenue
        FROM records r
        JOIN farms f ON r.farm_id = f.id
        WHERE {where_sql}
    """, params)

    return success_response({
        "totals": totals,
        "by_type": by_type,
        "by_activity": by_activity,
    })


# ============================================================
# OFFLINE SYNC (delegates to jobs/sync_records.py)
# ============================================================
async def sync_offline(request, env):
    """POST /api/records/sync
    Body: {records: [{client_id, ...record_fields}, ...], source?}
    Queues a sync job. Falls back to synchronous processing if queue fails.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    records = data.get("records", [])

    if not isinstance(records, list):
        return error_response("'records' must be a list",
                             status=HTTP.BAD_REQUEST,
                             code=ErrorCode.VALIDATION_ERROR)

    if len(records) == 0:
        return error_response("'records' cannot be empty",
                             status=HTTP.BAD_REQUEST,
                             code=ErrorCode.VALIDATION_ERROR)

    if len(records) > 500:
        return error_response("Max 500 records per sync",
                             status=HTTP.BAD_REQUEST,
                             code=ErrorCode.VALIDATION_ERROR)

    source = data.get("source", "pwa")

    # Try queue first
    queued = False
    try:
        await env.JOBS.send({
            "type": "sync_records",
            "payload": {
                "farmer_id": user["id"],
                "records": records,
                "source": source,
            },
        })
        queued = True
    except Exception as e:
        log_event("sync_queue_failed", {"error": str(e)})

    # Synchronous fallback
    if not queued:
        try:
            from jobs.sync_records import run as sync_run
            await sync_run({
                "farmer_id": user["id"],
                "records": records,
                "source": source,
            }, env)
        except Exception as e:
            log_event("sync_sync_failed", {"error": str(e)})
            return error_response("Sync failed. Please retry.",
                                 status=HTTP.INTERNAL_ERROR,
                                 code=ErrorCode.INTERNAL_ERROR)

    log_event("sync_queued", {
        "farmer_id": user["id"],
        "count": len(records),
        "queued": queued,
    })

    return success_response({
        "queued": queued,
        "count": len(records),
        "message": "Records are being synced. You'll receive a notification when done."
                   if queued else
                   "Records synced immediately.",
    })


# ============================================================
# RECORDS BY ENTERPRISE
# ============================================================
async def list_by_enterprise(request, env, enterprise_id: int):
    """GET /api/enterprises/:id/records"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)

    # Ownership
    ent = await db.query_one("""
        SELECT e.id FROM enterprises e
        JOIN farms f ON e.farm_id = f.id
        WHERE e.id = ? AND f.farmer_id = ?
    """, [enterprise_id, user["id"]])

    if not ent:
        return error_response("Enterprise not found",
                             status=HTTP.NOT_FOUND,
                             code=ErrorCode.NOT_FOUND)

    url = _sp(request)
    page = to_int(url.search_params.get("page", 1), 1)
    page_size = to_int(url.search_params.get("page_size", 50), 50)

    sql = """
        SELECT r.*, p.name as plot_name
        FROM records r
        LEFT JOIN plots p ON r.plot_id = p.id
        WHERE r.enterprise_id = ?
        ORDER BY r.record_date DESC, r.id DESC
    """

    result = await db.paginate(sql, [enterprise_id], page=page, page_size=page_size)
    return paginated_response(result, message="Enterprise records retrieved")


# ============================================================
# RECORDS BY PLOT
# ============================================================
async def list_by_plot(request, env, plot_id: int):
    """GET /api/plots/:id/records"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)

    plot = await db.query_one("""
        SELECT p.id FROM plots p
        JOIN farms f ON p.farm_id = f.id
        WHERE p.id = ? AND f.farmer_id = ?
    """, [plot_id, user["id"]])

    if not plot:
        return error_response("Plot not found",
                             status=HTTP.NOT_FOUND,
                             code=ErrorCode.NOT_FOUND)

    url = _sp(request)
    page = to_int(url.search_params.get("page", 1), 1)
    page_size = to_int(url.search_params.get("page_size", 50), 50)

    sql = """
        SELECT r.*, e.name as enterprise_name
        FROM records r
        LEFT JOIN enterprises e ON r.enterprise_id = e.id
        WHERE r.plot_id = ?
        ORDER BY r.record_date DESC, r.id DESC
    """

    result = await db.paginate(sql, [plot_id], page=page, page_size=page_size)
    return paginated_response(result, message="Plot records retrieved")