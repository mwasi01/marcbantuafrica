"""
Marcbantu Africa — Enterprise routes.
Crops, livestock, poultry, horticulture enterprises within a farm.
"""
from utils import (
    success_response, error_response, parse_json, require_auth,
    now_iso, to_int, to_float, log_event, require_fields,
)
from validators import ValidationError, validate_enterprise
from constants import HTTP, ErrorCode, EnterpriseType
from db import DB


# ============================================================
# HELPERS
# ============================================================
async def _get_owned_farm(db: DB, farm_id: int, farmer_id: int) -> dict | None:
    return await db.query_one(
        "SELECT id FROM farms WHERE id = ? AND farmer_id = ?",
        [farm_id, farmer_id]
    )


async def _get_owned_enterprise(db: DB, enterprise_id: int, farmer_id: int) -> dict | None:
    return await db.query_one("""
        SELECT e.* FROM enterprises e
        JOIN farms f ON e.farm_id = f.id
        WHERE e.id = ? AND f.farmer_id = ?
    """, [enterprise_id, farmer_id])


# ============================================================
# LIST ENTERPRISES
# ============================================================
async def list_enterprises(request, env, farm_id: int):
    """GET /api/farms/:id/enterprises"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    farm = await _get_owned_farm(db, farm_id, user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    enterprises = await db.query("""
        SELECT e.*,
            (SELECT COUNT(*) FROM records WHERE enterprise_id = e.id) as record_count
        FROM enterprises e
        WHERE e.farm_id = ?
        ORDER BY CASE e.status
                    WHEN 'active' THEN 1
                    WHEN 'planning' THEN 2
                    WHEN 'harvested' THEN 3
                    ELSE 4
                 END, e.name
    """, [farm_id])

    return success_response(enterprises)


# ============================================================
# CREATE ENTERPRISE
# ============================================================
async def create_enterprise(request, env, farm_id: int):
    """POST /api/farms/:id/enterprises"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    farm = await _get_owned_farm(db, farm_id, user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    data = await parse_json(request)

    try:
        clean = validate_enterprise(data)
    except ValidationError as e:
        return error_response(e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    clean['farm_id'] = farm_id
    enterprise_id = await db.insert('enterprises', clean)

    enterprise = await db.query_one("SELECT * FROM enterprises WHERE id = ?", [enterprise_id])

    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': 'enterprise_created',
        'entity': 'enterprise',
        'entity_id': enterprise_id,
        'details': clean['name'],
    })

    return success_response(enterprise, message="Enterprise created", status=HTTP.CREATED)


# ============================================================
# GET ENTERPRISE
# ============================================================
async def get_enterprise(request, env, enterprise_id: int):
    """GET /api/enterprises/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    ent = await _get_owned_enterprise(db, enterprise_id, user['id'])
    if not ent:
        return error_response("Enterprise not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # Financial totals
    financials = await db.query_one("""
        SELECT
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses
        FROM transactions WHERE enterprise_id = ?
    """, [enterprise_id])

    ent['financials'] = {
        'income': financials['income'] if financials else 0,
        'expenses': financials['expenses'] if financials else 0,
        'profit': (financials['income'] - financials['expenses']) if financials else 0,
    }

    # Record counts by type
    records_by_type = await db.query("""
        SELECT record_type, COUNT(*) as count
        FROM records WHERE enterprise_id = ?
        GROUP BY record_type
    """, [enterprise_id])
    ent['records_by_type'] = records_by_type

    # Recent records
    ent['recent_records'] = await db.query("""
        SELECT id, record_type, activity, description, quantity, unit, cost, revenue, record_date
        FROM records WHERE enterprise_id = ?
        ORDER BY record_date DESC LIMIT 20
    """, [enterprise_id])

    # Recent transactions
    ent['recent_transactions'] = await db.query("""
        SELECT id, type, category, description, amount, transaction_date
        FROM transactions WHERE enterprise_id = ?
        ORDER BY transaction_date DESC LIMIT 10
    """, [enterprise_id])

    return success_response(ent)


# ============================================================
# UPDATE ENTERPRISE
# ============================================================
async def update_enterprise(request, env, enterprise_id: int):
    """PUT /api/enterprises/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    ent = await _get_owned_enterprise(db, enterprise_id, user['id'])
    if not ent:
        return error_response("Enterprise not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    data = await parse_json(request)

    allowed = ['name', 'type', 'species_or_crop', 'quantity', 'unit',
               'start_date', 'expected_end_date', 'status', 'notes']
    updates = {}
    for k in allowed:
        if k in data:
            if k == 'quantity':
                updates[k] = to_float(data[k]) or None
            else:
                updates[k] = data[k]

    if 'type' in updates and updates['type'] not in EnterpriseType.ALL:
        return error_response("Invalid enterprise type", status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    if not updates:
        return error_response("No valid fields to update", status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    updates['updated_at'] = now_iso()
    await db.update('enterprises', updates, 'id = ?', [enterprise_id])

    updated = await db.query_one("SELECT * FROM enterprises WHERE id = ?", [enterprise_id])

    return success_response(updated, message="Enterprise updated")


# ============================================================
# DELETE ENTERPRISE
# ============================================================
async def delete_enterprise(request, env, enterprise_id: int):
    """DELETE /api/enterprises/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    ent = await _get_owned_enterprise(db, enterprise_id, user['id'])
    if not ent:
        return error_response("Enterprise not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    record_count = await db.count('records', 'enterprise_id = ?', [enterprise_id])

    if record_count > 0:
        await db.update('enterprises', {
            'status': 'closed',
            'updated_at': now_iso(),
        }, 'id = ?', [enterprise_id])
        message = f"Enterprise closed (has {record_count} records)"
    else:
        await db.delete('enterprises', 'id = ?', [enterprise_id])
        message = "Enterprise deleted"

    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': 'enterprise_deleted',
        'entity': 'enterprise',
        'entity_id': enterprise_id,
    })

    return success_response(None, message=message)


# ============================================================
# ENTERPRISE PERFORMANCE
# ============================================================
async def get_performance(request, env, enterprise_id: int):
    """GET /api/enterprises/:id/performance
    Financial + operational performance over time.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    ent = await _get_owned_enterprise(db, enterprise_id, user['id'])
    if not ent:
        return error_response("Enterprise not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # Monthly breakdown (last 12 months)
    monthly = await db.query("""
        SELECT
            strftime('%Y-%m', transaction_date) as month,
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses
        FROM transactions
        WHERE enterprise_id = ?
        AND transaction_date >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month
    """, [enterprise_id])

    # Compute profit per month
    for m in monthly:
        m['profit'] = m['income'] - m['expenses']

    # Overall summary
    totals = await db.query_one("""
        SELECT
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses
        FROM transactions WHERE enterprise_id = ?
    """, [enterprise_id])

    total_income = totals['income'] if totals else 0
    total_expenses = totals['expenses'] if totals else 0
    total_profit = total_income - total_expenses
    margin = round((total_profit / total_income * 100), 2) if total_income > 0 else 0

    # Top cost categories
    categories = await db.query("""
        SELECT category, SUM(amount) as total
        FROM transactions
        WHERE enterprise_id = ? AND type = 'expense'
        GROUP BY category
        ORDER BY total DESC
        LIMIT 5
    """, [enterprise_id])

    return success_response({
        'enterprise': {
            'id': ent['id'],
            'name': ent['name'],
            'type': ent['type'],
            'status': ent['status'],
        },
        'totals': {
            'income': total_income,
            'expenses': total_expenses,
            'profit': total_profit,
            'margin_percent': margin,
        },
        'monthly': monthly,
        'top_costs': categories,
    })