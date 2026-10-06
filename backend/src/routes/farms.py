"""
Marcbantu Africa — Farm routes.
Create, read, update, delete farms. Ownership enforced on every operation.
"""
from utils import (
    success_response, error_response, parse_json, require_auth,
    now_iso, to_int, log_event, get_query,
)
from validators import ValidationError, validate_farm
from constants import HTTP, ErrorCode
from db import DB


# ============================================================
# HELPERS
# ============================================================
async def _get_owned_farm(db: DB, farm_id: int, farmer_id: int) -> dict | None:
    """Fetch a farm ensuring the requesting farmer owns it."""
    return await db.query_one(
        "SELECT * FROM farms WHERE id = ? AND farmer_id = ?",
        [farm_id, farmer_id]
    )


async def _enforce_farm_limit(db: DB, farmer_id: int, env):
    """Check if farmer can create another farm based on tier."""
    from constants import Tier
    tier_row = await db.query_one(
        "SELECT subscription_tier FROM farmers WHERE id = ?",
        [farmer_id]
    )
    tier = tier_row['subscription_tier'] if tier_row else Tier.STARTER
    limits = {
        Tier.STARTER: 1,
        Tier.PRO: 5,
        Tier.BUSINESS: 50,
    }
    max_farms = limits.get(tier, 1)
    current = await db.count('farms', 'farmer_id = ? AND active = 1', [farmer_id])
    if current >= max_farms:
        return False, max_farms
    return True, max_farms


# ============================================================
# LIST FARMS
# ============================================================
async def list_farms(request, env):
    """GET /api/farms
    Returns all farms for the current farmer.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    farms = await db.query("""
        SELECT f.*,
            (SELECT COUNT(*) FROM plots WHERE farm_id = f.id AND active = 1) as plot_count,
            (SELECT COUNT(*) FROM enterprises WHERE farm_id = f.id AND status = 'active') as enterprise_count,
            (SELECT COUNT(*) FROM records WHERE farm_id = f.id) as record_count
        FROM farms f
        WHERE f.farmer_id = ?
        ORDER BY f.active DESC, f.created_at DESC
    """, [user['id']])

    return success_response(farms)


# ============================================================
# CREATE FARM
# ============================================================
async def create_farm(request, env):
    """POST /api/farms
    Body: {name, size_acres?, latitude?, longitude?, altitude_m?, soil_type?,
           irrigation_type?, water_source?, notes?}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)

    try:
        clean = validate_farm(data)
    except ValidationError as e:
        return error_response(e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)

    # Check tier limit
    allowed, max_farms = await _enforce_farm_limit(db, user['id'], env)
    if not allowed:
        return error_response(
            f"Farm limit reached ({max_farms}). Upgrade your plan to add more farms.",
            status=HTTP.FORBIDDEN,
            code=ErrorCode.TIER_LIMIT_EXCEEDED,
        )

    clean['farmer_id'] = user['id']
    clean['active'] = 1

    farm_id = await db.insert('farms', clean)

    if not farm_id:
        return error_response(
            "Failed to create farm",
            status=HTTP.INTERNAL_ERROR,
            code=ErrorCode.INTERNAL_ERROR,
        )

    farm = await db.query_one("SELECT * FROM farms WHERE id = ?", [farm_id])

    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': 'farm_created',
        'entity': 'farm',
        'entity_id': farm_id,
        'details': clean.get('name', ''),
    })

    log_event('farm_created', {'farm_id': farm_id, 'farmer_id': user['id']})

    return success_response(farm, message="Farm created successfully", status=HTTP.CREATED)


# ============================================================
# GET FARM
# ============================================================
async def get_farm(request, env, farm_id: int):
    """GET /api/farms/:id
    Returns a farm with plots and enterprises embedded.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    farm = await _get_owned_farm(db, farm_id, user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # Plots
    farm['plots'] = await db.query(
        "SELECT * FROM plots WHERE farm_id = ? ORDER BY name",
        [farm_id]
    )

    # Enterprises
    farm['enterprises'] = await db.query(
        "SELECT * FROM enterprises WHERE farm_id = ? ORDER BY status, name",
        [farm_id]
    )

    # Counts
    farm['record_count'] = await db.count('records', 'farm_id = ?', [farm_id])
    farm['worker_count'] = await db.count('workers', 'farm_id = ? AND active = 1', [farm_id])
    farm['pending_tasks'] = await db.count(
        'tasks', "farm_id = ? AND status = 'pending'", [farm_id]
    )

    return success_response(farm)


# ============================================================
# UPDATE FARM
# ============================================================
async def update_farm(request, env, farm_id: int):
    """PUT /api/farms/:id
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    farm = await _get_owned_farm(db, farm_id, user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    data = await parse_json(request)
    clean = validate_farm({**farm, **data})

    updates = {
        k: v for k, v in clean.items()
        if k in ('name', 'size_acres', 'latitude', 'longitude', 'altitude_m',
                 'soil_type', 'irrigation_type', 'water_source', 'notes')
    }

    if 'active' in data:
        updates['active'] = 1 if data['active'] else 0

    if not updates:
        return error_response("No valid fields to update", status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    updates['updated_at'] = now_iso()
    await db.update('farms', updates, 'id = ?', [farm_id])

    updated = await db.query_one("SELECT * FROM farms WHERE id = ?", [farm_id])

    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': 'farm_updated',
        'entity': 'farm',
        'entity_id': farm_id,
        'details': ','.join(updates.keys()),
    })

    return success_response(updated, message="Farm updated")


# ============================================================
# DELETE FARM
# ============================================================
async def delete_farm(request, env, farm_id: int):
    """DELETE /api/farms/:id
    Soft delete if records exist, hard delete otherwise.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    farm = await _get_owned_farm(db, farm_id, user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    record_count = await db.count('records', 'farm_id = ?', [farm_id])

    if record_count > 0:
        # Soft delete — keep historical data
        await db.update('farms', {
            'active': 0,
            'updated_at': now_iso(),
        }, 'id = ?', [farm_id])
        action = 'farm_archived'
        message = f"Farm archived (has {record_count} records). Data preserved."
    else:
        await db.delete('farms', 'id = ?', [farm_id])
        action = 'farm_deleted'
        message = "Farm deleted"

    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': action,
        'entity': 'farm',
        'entity_id': farm_id,
        'details': farm.get('name', ''),
    })

    log_event(action, {'farm_id': farm_id, 'farmer_id': user['id']})

    return success_response(None, message=message)


# ============================================================
# FARM SUMMARY
# ============================================================
async def get_summary(request, env, farm_id: int):
    """GET /api/farms/:id/summary
    Full financial + operational snapshot of one farm.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    farm = await _get_owned_farm(db, farm_id, user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # All-time financials
    financials = await db.query_one("""
        SELECT
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses
        FROM transactions WHERE farm_id = ?
    """, [farm_id])

    # This month
    this_month = await db.query_one("""
        SELECT
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses
        FROM transactions
        WHERE farm_id = ? AND transaction_date >= date('now', 'start of month')
    """, [farm_id])

    # Enterprise breakdown
    by_enterprise = await db.query("""
        SELECT
            COALESCE(e.id, 0) as enterprise_id,
            COALESCE(e.name, 'General') as enterprise,
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as expenses
        FROM transactions t
        LEFT JOIN enterprises e ON t.enterprise_id = e.id
        WHERE t.farm_id = ?
        GROUP BY e.id
        ORDER BY (income - expenses) DESC
    """, [farm_id])

    # Category breakdown (expenses)
    by_category = await db.query("""
        SELECT category, SUM(amount) as total
        FROM transactions
        WHERE farm_id = ? AND type = 'expense'
        GROUP BY category
        ORDER BY total DESC
    """, [farm_id])

    # Records in last 30 days
    records_30d = await db.count(
        'records',
        "farm_id = ? AND record_date >= date('now', '-30 days')",
        [farm_id]
    )

    return success_response({
        'farm': {
            'id': farm['id'],
            'name': farm['name'],
            'size_acres': farm['size_acres'],
            'active': farm['active'],
        },
        'financials': {
            'all_time_income': financials['income'] if financials else 0,
            'all_time_expenses': financials['expenses'] if financials else 0,
            'all_time_profit': (financials['income'] - financials['expenses']) if financials else 0,
            'this_month_income': this_month['income'] if this_month else 0,
            'this_month_expenses': this_month['expenses'] if this_month else 0,
            'this_month_profit': (this_month['income'] - this_month['expenses']) if this_month else 0,
        },
        'by_enterprise': by_enterprise,
        'by_category': by_category,
        'records_last_30_days': records_30d,
    })