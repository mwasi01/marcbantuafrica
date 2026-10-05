"""
Marcbantu Africa — Planning routes.
Budgets, budget items, cash flow forecasts, seasonal planning.
"""
from utils import (
    success_response, error_response, parse_json, require_auth,
    now_iso, to_int, to_float, log_event, require_fields, paginated_response,
    _sp,
)
from constants import HTTP, ErrorCode, TransactionType
from db import DB


# ============================================================
# HELPERS
# ============================================================
async def _get_owned_farm(db: DB, farm_id: int, farmer_id: int):
    return await db.query_one(
        "SELECT id FROM farms WHERE id = ? AND farmer_id = ?",
        [farm_id, farmer_id]
    )


async def _get_owned_budget(db: DB, budget_id: int, farmer_id: int):
    return await db.query_one("""
        SELECT b.* FROM budgets b
        JOIN farms f ON b.farm_id = f.id
        WHERE b.id = ? AND f.farmer_id = ?
    """, [budget_id, farmer_id])


async def _recalc_budget_totals(db: DB, budget_id: int):
    """Recompute budget totals from its items."""
    totals = await db.query_one("""
        SELECT
            COALESCE(SUM(CASE WHEN item_type = 'income' THEN total ELSE 0 END), 0) as total_income,
            COALESCE(SUM(CASE WHEN item_type = 'expense' THEN total ELSE 0 END), 0) as total_expenses
        FROM budget_items WHERE budget_id = ?
    """, [budget_id])

    if totals:
        await db.update('budgets', {
            'total_income': totals['total_income'],
            'total_expenses': totals['total_expenses'],
        }, 'id = ?', [budget_id])

    return totals


# ============================================================
# LIST BUDGETS
# ============================================================
async def list_budgets(request, env):
    """GET /api/planning/budgets
    Query: farm_id?, enterprise_id?, period_start?, period_end?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("b.farm_id = ?")
        params.append(to_int(farm_id))

    enterprise_id = url.search_params.get('enterprise_id')
    if enterprise_id:
        where.append("b.enterprise_id = ?")
        params.append(to_int(enterprise_id))

    period_start = url.search_params.get('period_start')
    if period_start:
        where.append("b.period_start >= ?")
        params.append(period_start)

    period_end = url.search_params.get('period_end')
    if period_end:
        where.append("b.period_end <= ?")
        params.append(period_end)

    budgets = await db.query(f"""
        SELECT b.*,
               f.name as farm_name,
               e.name as enterprise_name,
               (SELECT COUNT(*) FROM budget_items WHERE budget_id = b.id) as item_count
        FROM budgets b
        JOIN farms f ON b.farm_id = f.id
        LEFT JOIN enterprises e ON b.enterprise_id = e.id
        WHERE {' AND '.join(where)}
        ORDER BY b.period_start DESC, b.id DESC
    """, params)

    for b in budgets:
        b['projected_profit'] = (b['total_income'] or 0) - (b['total_expenses'] or 0)

    return success_response(budgets)


# ============================================================
# CREATE BUDGET
# ============================================================
async def create_budget(request, env):
    """POST /api/planning/budgets
    Body: {farm_id, name, enterprise_id?, period_start, period_end, notes?, items?: [...]}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ['farm_id', 'name', 'period_start', 'period_end'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    db = DB(env)

    farm = await _get_owned_farm(db, to_int(data['farm_id']), user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    budget_id = await db.insert('budgets', {
        'farm_id': to_int(data['farm_id']),
        'enterprise_id': to_int(data.get('enterprise_id')) or None,
        'name': str(data['name']).strip(),
        'period_start': data['period_start'],
        'period_end': data['period_end'],
        'total_income': 0,
        'total_expenses': 0,
        'notes': data.get('notes'),
    })

    # If items provided, insert them
    items = data.get('items', [])
    if isinstance(items, list) and items:
        for item in items:
            await db.insert('budget_items', {
                'budget_id': budget_id,
                'item_type': item.get('item_type', 'expense'),
                'category': item.get('category'),
                'description': item.get('description'),
                'quantity': to_float(item.get('quantity')) or None,
                'unit_cost': to_float(item.get('unit_cost')) or None,
                'total': to_float(item.get('total')) or 0,
            })
        await _recalc_budget_totals(db, budget_id)

    budget = await db.query_one("""
        SELECT b.*, f.name as farm_name, e.name as enterprise_name
        FROM budgets b
        JOIN farms f ON b.farm_id = f.id
        LEFT JOIN enterprises e ON b.enterprise_id = e.id
        WHERE b.id = ?
    """, [budget_id])

    log_event('budget_created', {'budget_id': budget_id, 'farmer_id': user['id']})

    return success_response(budget, message="Budget created", status=HTTP.CREATED)


# ============================================================
# GET BUDGET
# ============================================================
async def get_budget(request, env, budget_id: int):
    """GET /api/planning/budgets/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    budget = await _get_owned_budget(db, budget_id, user['id'])
    if not budget:
        return error_response("Budget not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # Enrich with farm/enterprise names
    meta = await db.query_one("""
        SELECT f.name as farm_name, e.name as enterprise_name
        FROM farms f
        LEFT JOIN enterprises e ON e.id = ?
        WHERE f.id = ?
    """, [budget['enterprise_id'], budget['farm_id']])

    budget['farm_name'] = meta['farm_name'] if meta else None
    budget['enterprise_name'] = meta['enterprise_name'] if meta else None

    # Items
    budget['items'] = await db.query("""
        SELECT * FROM budget_items
        WHERE budget_id = ?
        ORDER BY item_type DESC, id
    """, [budget_id])

    # Totals
    budget['projected_profit'] = (budget['total_income'] or 0) - (budget['total_expenses'] or 0)
    budget['margin_percent'] = (
        round((budget['projected_profit'] / budget['total_income'] * 100), 2)
        if budget['total_income'] and budget['total_income'] > 0 else 0
    )

    # Actual performance vs budget (for the same period)
    actual = await db.query_one("""
        SELECT
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as actual_income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as actual_expenses
        FROM transactions
        WHERE farm_id = ?
        AND (enterprise_id = ? OR ? IS NULL)
        AND transaction_date BETWEEN ? AND ?
    """, [
        budget['farm_id'],
        budget['enterprise_id'],
        budget['enterprise_id'],
        budget['period_start'],
        budget['period_end'],
    ])

    budget['actual_income'] = actual['actual_income'] if actual else 0
    budget['actual_expenses'] = actual['actual_expenses'] if actual else 0
    budget['actual_profit'] = budget['actual_income'] - budget['actual_expenses']
    budget['income_variance'] = budget['actual_income'] - (budget['total_income'] or 0)
    budget['expense_variance'] = budget['actual_expenses'] - (budget['total_expenses'] or 0)
    budget['profit_variance'] = budget['actual_profit'] - budget['projected_profit']

    return success_response(budget)


# ============================================================
# UPDATE BUDGET
# ============================================================
async def update_budget(request, env, budget_id: int):
    """PUT /api/planning/budgets/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    budget = await _get_owned_budget(db, budget_id, user['id'])
    if not budget:
        return error_response("Budget not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    data = await parse_json(request)

    allowed = ['name', 'enterprise_id', 'period_start', 'period_end', 'notes']
    updates = {}
    for k in allowed:
        if k in data:
            if k == 'enterprise_id':
                updates[k] = to_int(data[k]) or None
            elif k == 'name':
                updates[k] = str(data[k]).strip()
            else:
                updates[k] = data[k]

    if not updates:
        return error_response("No valid fields to update",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    updates['updated_at'] = now_iso()
    await db.update('budgets', updates, 'id = ?', [budget_id])

    updated = await db.query_one("SELECT * FROM budgets WHERE id = ?", [budget_id])
    return success_response(updated, message="Budget updated")


# ============================================================
# DELETE BUDGET
# ============================================================
async def delete_budget(request, env, budget_id: int):
    """DELETE /api/planning/budgets/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    budget = await _get_owned_budget(db, budget_id, user['id'])
    if not budget:
        return error_response("Budget not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    await db.delete('budget_items', 'budget_id = ?', [budget_id])
    await db.delete('budgets', 'id = ?', [budget_id])

    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': 'budget_deleted',
        'entity': 'budget',
        'entity_id': budget_id,
    })

    return success_response(None, message="Budget deleted")


# ============================================================
# BUDGET ITEMS — ADD
# ============================================================
async def add_budget_item(request, env, budget_id: int):
    """POST /api/planning/budgets/:id/items"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    budget = await _get_owned_budget(db, budget_id, user['id'])
    if not budget:
        return error_response("Budget not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    data = await parse_json(request)
    err_msg = require_fields(data, ['item_type', 'description'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    if data['item_type'] not in TransactionType.ALL:
        return error_response("item_type must be 'income' or 'expense'",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    quantity = to_float(data.get('quantity')) or None
    unit_cost = to_float(data.get('unit_cost')) or None
    total = to_float(data.get('total'))
    if not total and quantity and unit_cost:
        total = quantity * unit_cost

    item_id = await db.insert('budget_items', {
        'budget_id': budget_id,
        'item_type': data['item_type'],
        'category': data.get('category'),
        'description': data['description'],
        'quantity': quantity,
        'unit_cost': unit_cost,
        'total': total or 0,
    })

    await _recalc_budget_totals(db, budget_id)

    item = await db.query_one("SELECT * FROM budget_items WHERE id = ?", [item_id])
    return success_response(item, message="Item added", status=HTTP.CREATED)


# ============================================================
# BUDGET ITEMS — UPDATE
# ============================================================
async def update_budget_item(request, env, budget_id: int, item_id: int):
    """PUT /api/planning/budgets/:id/items/:item_id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    budget = await _get_owned_budget(db, budget_id, user['id'])
    if not budget:
        return error_response("Budget not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    item = await db.query_one(
        "SELECT * FROM budget_items WHERE id = ? AND budget_id = ?",
        [item_id, budget_id]
    )
    if not item:
        return error_response("Budget item not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    data = await parse_json(request)
    updates = {}

    if 'item_type' in data:
        if data['item_type'] not in TransactionType.ALL:
            return error_response("Invalid item_type",
                                 status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)
        updates['item_type'] = data['item_type']

    for k in ['category', 'description']:
        if k in data:
            updates[k] = data[k]

    for k in ['quantity', 'unit_cost']:
        if k in data:
            updates[k] = to_float(data[k]) or None

    # Recalculate total if quantity and unit_cost are both present
    qty = updates.get('quantity', item.get('quantity'))
    uc = updates.get('unit_cost', item.get('unit_cost'))
    if 'total' in data:
        updates['total'] = to_float(data['total'])
    elif qty and uc:
        updates['total'] = qty * uc

    if not updates:
        return error_response("No valid fields to update",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    await db.update('budget_items', updates, 'id = ?', [item_id])
    await _recalc_budget_totals(db, budget_id)

    updated = await db.query_one("SELECT * FROM budget_items WHERE id = ?", [item_id])
    return success_response(updated, message="Item updated")


# ============================================================
# BUDGET ITEMS — DELETE
# ============================================================
async def delete_budget_item(request, env, budget_id: int, item_id: int):
    """DELETE /api/planning/budgets/:id/items/:item_id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    budget = await _get_owned_budget(db, budget_id, user['id'])
    if not budget:
        return error_response("Budget not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    item = await db.query_one(
        "SELECT id FROM budget_items WHERE id = ? AND budget_id = ?",
        [item_id, budget_id]
    )
    if not item:
        return error_response("Budget item not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    await db.delete('budget_items', 'id = ?', [item_id])
    await _recalc_budget_totals(db, budget_id)

    return success_response(None, message="Item deleted")


# ============================================================
# CASH FLOW FORECAST
# ============================================================
async def cash_flow_forecast(request, env):
    """GET /api/planning/cash-flow-forecast
    Query: farm_id?, months=6
    Returns forecast based on historical averages + budget if available.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("t.farm_id = ?")
        params.append(to_int(farm_id))

    months = min(max(to_int(url.search_params.get('months', 6), 6), 1), 24)
    where_sql = ' AND '.join(where)

    # Historical 12-month average
    historical = await db.query(f"""
        SELECT
            strftime('%Y-%m', t.transaction_date) as month,
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as expenses
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql} AND t.transaction_date >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month
    """, params)

    # Compute averages (last 3 months weighted more)
    if historical:
        recent = historical[-3:]
        avg_income = sum(m['income'] for m in recent) / len(recent)
        avg_expenses = sum(m['expenses'] for m in recent) / len(recent)
    else:
        avg_income = 0
        avg_expenses = 0

    # Forecast
    from datetime import datetime, timedelta
    forecast = []
    running_balance = historical[-1]['income'] - historical[-1]['expenses'] if historical else 0
    current = datetime.now()

    for i in range(1, months + 1):
        future = current + timedelta(days=30 * i)
        month_str = future.strftime('%Y-%m')
        running_balance += (avg_income - avg_expenses)

        forecast.append({
            'month': month_str,
            'projected_income': round(avg_income, 2),
            'projected_expenses': round(avg_expenses, 2),
            'projected_net': round(avg_income - avg_expenses, 2),
            'projected_balance': round(running_balance, 2),
        })

    return success_response({
        'historical_months': historical,
        'forecast': forecast,
        'averages': {
            'monthly_income': round(avg_income, 2),
            'monthly_expenses': round(avg_expenses, 2),
            'monthly_net': round(avg_income - avg_expenses, 2),
        },
        'forecast_months': months,
    })


# ============================================================
# SEASONAL PLAN
# ============================================================
async def seasonal_plan(request, env):
    """GET /api/planning/seasonal-plan
    Query: farm_id
    Returns upcoming season recommendations based on past data.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    url = _sp(request)
    farm_id = url.search_params.get('farm_id')

    if not farm_id:
        return error_response("farm_id is required",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    db = DB(env)
    farm = await _get_owned_farm(db, to_int(farm_id), user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # Last year's performance by enterprise
    performance = await db.query("""
        SELECT
            e.id as enterprise_id,
            e.name as enterprise,
            e.type,
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as expenses
        FROM enterprises e
        LEFT JOIN transactions t ON t.enterprise_id = e.id
            AND t.transaction_date >= date('now', '-1 year')
        WHERE e.farm_id = ?
        GROUP BY e.id
    """, [to_int(farm_id)])

    for p in performance:
        p['profit'] = p['income'] - p['expenses']
        p['roi'] = round((p['profit'] / p['expenses'] * 100), 1) if p['expenses'] > 0 else 0

    # Recommendations
    recommendations = []
    best = sorted(performance, key=lambda x: x['profit'], reverse=True)

    if best and best[0]['profit'] > 0:
        recommendations.append({
            'type': 'expand',
            'enterprise': best[0]['enterprise'],
            'reason': f"Top performer with KES {best[0]['profit']:,.0f} profit and {best[0]['roi']}% ROI",
        })

    for p in performance:
        if p['profit'] < 0:
            recommendations.append({
                'type': 'review',
                'enterprise': p['enterprise'],
                'reason': f"Lost KES {abs(p['profit']):,.0f} last year. Consider reducing or restructuring.",
            })

    return success_response({
        'farm_id': to_int(farm_id),
        'performance': performance,
        'recommendations': recommendations,
    })