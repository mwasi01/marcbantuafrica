"""
Marcbantu Africa — Finance routes.
Transactions, P&L, cash flow, dashboards, expense analytics.
"""
from utils import (
    success_response, error_response, parse_json, require_auth,
    now_iso, to_int, to_float, log_event, get_int_query, paginated_response,
)
from validators import ValidationError, validate_transaction
from constants import (
    HTTP, ErrorCode, TransactionType, INCOME_CATEGORIES, EXPENSE_CATEGORIES,
    PaymentMethod,
)
from db import DB


# ============================================================
# HELPERS
# ============================================================
async def _get_owned_farm(db: DB, farm_id: int, farmer_id: int):
    return await db.query_one(
        "SELECT id FROM farms WHERE id = ? AND farmer_id = ?",
        [farm_id, farmer_id]
    )


async def _get_owned_transaction(db: DB, tx_id: int, farmer_id: int):
    return await db.query_one("""
        SELECT t.* FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE t.id = ? AND f.farmer_id = ?
    """, [tx_id, farmer_id])


def _parse_date_range(url) -> tuple:
    """Extract from/to date filters from query params."""
    date_from = url.search_params.get('from')
    date_to = url.search_params.get('to')
    return date_from, date_to


# ============================================================
# LIST TRANSACTIONS
# ============================================================
async def list_transactions(request, env):
    """GET /api/finance/transactions
    Query: farm_id, enterprise_id, type, category, from, to, page, page_size
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = request.url

    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("t.farm_id = ?")
        params.append(to_int(farm_id))

    enterprise_id = url.search_params.get('enterprise_id')
    if enterprise_id:
        where.append("t.enterprise_id = ?")
        params.append(to_int(enterprise_id))

    tx_type = url.search_params.get('type')
    if tx_type:
        where.append("t.type = ?")
        params.append(tx_type)

    category = url.search_params.get('category')
    if category:
        where.append("t.category = ?")
        params.append(category)

    date_from, date_to = _parse_date_range(url)
    if date_from:
        where.append("t.transaction_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("t.transaction_date <= ?")
        params.append(date_to)

    search = url.search_params.get('q')
    if search:
        where.append("(t.description LIKE ? OR t.reference LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])

    page = to_int(url.search_params.get('page', 1), 1)
    page_size = to_int(url.search_params.get('page_size', 50), 50)

    sql = f"""
        SELECT t.*,
               f.name as farm_name,
               e.name as enterprise_name
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        LEFT JOIN enterprises e ON t.enterprise_id = e.id
        WHERE {' AND '.join(where)}
        ORDER BY t.transaction_date DESC, t.id DESC
    """

    result = await db.paginate(sql, params, page=page, page_size=page_size)
    return paginated_response(result, message="Transactions retrieved")


# ============================================================
# CREATE TRANSACTION
# ============================================================
async def create_transaction(request, env):
    """POST /api/finance/transactions"""
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)

    try:
        clean = validate_transaction(data)
    except ValidationError as e:
        return error_response(e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)

    # Ownership
    farm = await _get_owned_farm(db, clean['farm_id'], user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # Enterprise ownership if provided
    if clean.get('enterprise_id'):
        ent = await db.query_one(
            "SELECT id FROM enterprises WHERE id = ? AND farm_id = ?",
            [clean['enterprise_id'], clean['farm_id']]
        )
        if not ent:
            return error_response("Enterprise does not belong to this farm",
                                 status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    clean['created_by'] = user['id']
    tx_id = await db.insert('transactions', clean)

    tx = await db.query_one("""
        SELECT t.*, f.name as farm_name, e.name as enterprise_name
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        LEFT JOIN enterprises e ON t.enterprise_id = e.id
        WHERE t.id = ?
    """, [tx_id])

    log_event('transaction_created', {
        'tx_id': tx_id,
        'farmer_id': user['id'],
        'type': clean['type'],
        'amount': clean['amount'],
    })

    return success_response(tx, message="Transaction recorded", status=HTTP.CREATED)


# ============================================================
# UPDATE TRANSACTION
# ============================================================
async def update_transaction(request, env, tx_id: int):
    """PUT /api/finance/transactions/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    tx = await _get_owned_transaction(db, tx_id, user['id'])
    if not tx:
        return error_response("Transaction not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    data = await parse_json(request)

    allowed = ['category', 'description', 'amount', 'payment_method',
               'reference', 'transaction_date', 'notes', 'enterprise_id']
    updates = {}
    for k in allowed:
        if k in data:
            if k == 'amount':
                updates[k] = to_float(data[k])
                if updates[k] <= 0:
                    return error_response("Amount must be > 0",
                                         status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)
            elif k == 'enterprise_id':
                updates[k] = to_int(data[k]) or None
            elif k == 'payment_method':
                if data[k] and data[k] not in PaymentMethod.ALL:
                    return error_response("Invalid payment method",
                                         status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)
                updates[k] = data[k]
            else:
                updates[k] = data[k]

    if not updates:
        return error_response("No valid fields to update",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    updates['updated_at'] = now_iso()
    await db.update('transactions', updates, 'id = ?', [tx_id])

    updated = await db.query_one("""
        SELECT t.*, f.name as farm_name, e.name as enterprise_name
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        LEFT JOIN enterprises e ON t.enterprise_id = e.id
        WHERE t.id = ?
    """, [tx_id])

    return success_response(updated, message="Transaction updated")


# ============================================================
# DELETE TRANSACTION
# ============================================================
async def delete_transaction(request, env, tx_id: int):
    """DELETE /api/finance/transactions/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    tx = await _get_owned_transaction(db, tx_id, user['id'])
    if not tx:
        return error_response("Transaction not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    await db.delete('transactions', 'id = ?', [tx_id])

    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': 'transaction_deleted',
        'entity': 'transaction',
        'entity_id': tx_id,
    })

    return success_response(None, message="Transaction deleted")


# ============================================================
# PROFIT & LOSS
# ============================================================
async def profit_loss(request, env):
    """GET /api/finance/profit-loss
    Query: farm_id?, enterprise_id?, from?, to?
    Returns full P&L statement with breakdowns.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = request.url

    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("t.farm_id = ?")
        params.append(to_int(farm_id))

    enterprise_id = url.search_params.get('enterprise_id')
    if enterprise_id:
        where.append("t.enterprise_id = ?")
        params.append(to_int(enterprise_id))

    date_from, date_to = _parse_date_range(url)
    if date_from:
        where.append("t.transaction_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("t.transaction_date <= ?")
        params.append(date_to)

    where_sql = ' AND '.join(where)

    # Totals
    totals = await db.query_one(f"""
        SELECT
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as total_income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as total_expenses,
            COUNT(*) as transaction_count
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql}
    """, params)

    total_income = totals['total_income'] if totals else 0
    total_expenses = totals['total_expenses'] if totals else 0
    net_profit = total_income - total_expenses
    margin = round((net_profit / total_income * 100), 2) if total_income > 0 else 0

    # Income by category
    income_by_category = await db.query(f"""
        SELECT t.category, COALESCE(SUM(t.amount), 0) as total, COUNT(*) as count
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql} AND t.type = 'income'
        GROUP BY t.category
        ORDER BY total DESC
    """, params)

    # Expense by category
    expense_by_category = await db.query(f"""
        SELECT t.category, COALESCE(SUM(t.amount), 0) as total, COUNT(*) as count
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql} AND t.type = 'expense'
        GROUP BY t.category
        ORDER BY total DESC
    """, params)

    # Monthly trend
    monthly = await db.query(f"""
        SELECT
            strftime('%Y-%m', t.transaction_date) as month,
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as expenses
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql}
        GROUP BY month
        ORDER BY month
    """, params)

    for m in monthly:
        m['profit'] = m['income'] - m['expenses']
        m['margin_percent'] = round((m['profit'] / m['income'] * 100), 2) if m['income'] > 0 else 0

    # By enterprise
    by_enterprise = await db.query(f"""
        SELECT
            COALESCE(e.id, 0) as enterprise_id,
            COALESCE(e.name, 'Unassigned') as enterprise,
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as expenses
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        LEFT JOIN enterprises e ON t.enterprise_id = e.id
        WHERE {where_sql}
        GROUP BY e.id
        ORDER BY (income - expenses) DESC
    """, params)

    for e in by_enterprise:
        e['profit'] = e['income'] - e['expenses']
        e['margin_percent'] = round((e['profit'] / e['income'] * 100), 2) if e['income'] > 0 else 0

    return success_response({
        'summary': {
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_profit': net_profit,
            'margin_percent': margin,
            'transaction_count': totals['transaction_count'] if totals else 0,
        },
        'period': {
            'from': date_from,
            'to': date_to,
        },
        'income_by_category': income_by_category,
        'expense_by_category': expense_by_category,
        'monthly_trend': monthly,
        'by_enterprise': by_enterprise,
    })


# ============================================================
# DASHBOARD SUMMARY (financial)
# ============================================================
async def dashboard_summary(request, env):
    """GET /api/finance/dashboard
    Query: farm_id?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = request.url

    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("t.farm_id = ?")
        params.append(to_int(farm_id))

    where_sql = ' AND '.join(where)

    # All time
    all_time = await db.query_one(f"""
        SELECT
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as expenses
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql}
    """, params)

    # This month
    this_month = await db.query_one(f"""
        SELECT
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as expenses
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql} AND t.transaction_date >= date('now', 'start of month')
    """, params)

    # Last month
    last_month = await db.query_one(f"""
        SELECT
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as expenses
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql}
        AND t.transaction_date >= date('now', 'start of month', '-1 month')
        AND t.transaction_date < date('now', 'start of month')
    """, params)

    # Last 6 months
    six_months = await db.query(f"""
        SELECT
            strftime('%Y-%m', t.transaction_date) as month,
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as expenses
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql} AND t.transaction_date >= date('now', '-6 months')
        GROUP BY month
        ORDER BY month
    """, params)

    for m in six_months:
        m['profit'] = m['income'] - m['expenses']

    # Top expenses this month
    top_expenses = await db.query(f"""
        SELECT t.category, SUM(t.amount) as total
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql}
        AND t.type = 'expense'
        AND t.transaction_date >= date('now', 'start of month')
        GROUP BY t.category
        ORDER BY total DESC
        LIMIT 5
    """, params)

    # Top income sources this month
    top_income = await db.query(f"""
        SELECT t.category, SUM(t.amount) as total
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql}
        AND t.type = 'income'
        AND t.transaction_date >= date('now', 'start of month')
        GROUP BY t.category
        ORDER BY total DESC
        LIMIT 5
    """, params)

    def pct_change(current, previous):
        if not previous or previous == 0:
            return 0
        return round(((current - previous) / previous) * 100, 1)

    income = this_month['income'] if this_month else 0
    expenses = this_month['expenses'] if this_month else 0

    return success_response({
        'all_time': {
            'income': all_time['income'] if all_time else 0,
            'expenses': all_time['expenses'] if all_time else 0,
            'profit': (all_time['income'] - all_time['expenses']) if all_time else 0,
        },
        'this_month': {
            'income': income,
            'expenses': expenses,
            'profit': income - expenses,
            'income_change_pct': pct_change(income, last_month['income'] if last_month else 0),
            'expense_change_pct': pct_change(expenses, last_month['expenses'] if last_month else 0),
            'profit_change_pct': pct_change(
                income - expenses,
                (last_month['income'] - last_month['expenses']) if last_month else 0,
            ),
        },
        'monthly_trend': six_months,
        'top_expenses': top_expenses,
        'top_income': top_income,
    })


# ============================================================
# CASH FLOW (actual + forecast)
# ============================================================
async def cash_flow(request, env):
    """GET /api/finance/cash-flow
    Query: farm_id?, months=6
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = request.url

    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("t.farm_id = ?")
        params.append(to_int(farm_id))

    where_sql = ' AND '.join(where)

    # Actual monthly flows for last 12 months
    actual = await db.query(f"""
        SELECT
            strftime('%Y-%m', t.transaction_date) as month,
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as inflow,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as outflow
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql} AND t.transaction_date >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month
    """, params)

    # Calculate running balance
    running = 0
    for m in actual:
        running += m['inflow'] - m['outflow']
        m['net'] = m['inflow'] - m['outflow']
        m['running_balance'] = running

    # Simple forecast: average of last 3 months
    recent = actual[-3:] if len(actual) >= 3 else actual
    avg_inflow = sum(m['inflow'] for m in recent) / len(recent) if recent else 0
    avg_outflow = sum(m['outflow'] for m in recent) / len(recent) if recent else 0
    avg_net = avg_inflow - avg_outflow

    # Forecast next 6 months
    from datetime import datetime, timedelta
    forecast = []
    current_date = datetime.now()
    for i in range(1, 7):
        future = current_date + timedelta(days=30 * i)
        month_str = future.strftime('%Y-%m')
        running += avg_net
        forecast.append({
            'month': month_str,
            'projected_inflow': round(avg_inflow, 2),
            'projected_outflow': round(avg_outflow, 2),
            'projected_net': round(avg_net, 2),
            'projected_balance': round(running, 2),
        })

    return success_response({
        'actual': actual,
        'forecast': forecast,
        'averages': {
            'monthly_inflow': round(avg_inflow, 2),
            'monthly_outflow': round(avg_outflow, 2),
            'monthly_net': round(avg_net, 2),
        },
    })


# ============================================================
# EXPENSE BREAKDOWN
# ============================================================
async def expense_breakdown(request, env):
    """GET /api/finance/expense-breakdown
    Query: farm_id?, from?, to?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = request.url

    where = ["f.farmer_id = ?", "t.type = 'expense'"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("t.farm_id = ?")
        params.append(to_int(farm_id))

    date_from, date_to = _parse_date_range(url)
    if date_from:
        where.append("t.transaction_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("t.transaction_date <= ?")
        params.append(date_to)

    where_sql = ' AND '.join(where)

    by_category = await db.query(f"""
        SELECT
            t.category,
            SUM(t.amount) as total,
            COUNT(*) as count,
            ROUND(AVG(t.amount), 2) as average
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql}
        GROUP BY t.category
        ORDER BY total DESC
    """, params)

    total = sum(row['total'] for row in by_category)

    for row in by_category:
        row['percent'] = round((row['total'] / total * 100), 1) if total > 0 else 0

    # By month
    by_month = await db.query(f"""
        SELECT
            strftime('%Y-%m', t.transaction_date) as month,
            SUM(t.amount) as total
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql}
        GROUP BY month
        ORDER BY month
    """, params)

    return success_response({
        'total': total,
        'by_category': by_category,
        'by_month': by_month,
    })


# ============================================================
# ENTERPRISE PERFORMANCE (financial)
# ============================================================
async def enterprise_performance(request, env):
    """GET /api/finance/enterprise-performance
    Query: farm_id?, from?, to?
    Compares all enterprises side-by-side.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = request.url

    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("t.farm_id = ?")
        params.append(to_int(farm_id))

    date_from, date_to = _parse_date_range(url)
    if date_from:
        where.append("t.transaction_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("t.transaction_date <= ?")
        params.append(date_to)

    where_sql = ' AND '.join(where)

    enterprises = await db.query(f"""
        SELECT
            e.id as enterprise_id,
            e.name as enterprise,
            e.type,
            e.status,
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as expenses,
            COUNT(t.id) as transaction_count
        FROM enterprises e
        JOIN farms f ON e.farm_id = f.id
        LEFT JOIN transactions t ON t.enterprise_id = e.id
        WHERE f.farmer_id = ?
        GROUP BY e.id
        ORDER BY (income - expenses) DESC
    """, [user['id']])

    for e in enterprises:
        e['profit'] = e['income'] - e['expenses']
        e['margin_percent'] = round((e['profit'] / e['income'] * 100), 2) if e['income'] > 0 else 0
        e['cost_ratio'] = round((e['expenses'] / e['income'] * 100), 2) if e['income'] > 0 else 0

    return success_response({
        'enterprises': enterprises,
        'total_count': len(enterprises),
    })


# ============================================================
# BULK CREATE (for imports / offline)
# ============================================================
async def bulk_create(request, env):
    """POST /api/finance/transactions/bulk
    Body: {transactions: [...]}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    items = data.get('transactions', [])

    if not isinstance(items, list) or not items:
        return error_response("'transactions' must be a non-empty list",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    if len(items) > 500:
        return error_response("Max 500 transactions per request",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)

    # Get owned farm IDs
    farms = await db.query("SELECT id FROM farms WHERE farmer_id = ?", [user['id']])
    farm_ids = {f['id'] for f in farms}

    succeeded = []
    failed = []

    for item in items:
        try:
            clean = validate_transaction(item)
            if clean['farm_id'] not in farm_ids:
                failed.append({'item': item, 'error': 'Farm not owned'})
                continue
            clean['created_by'] = user['id']
            tx_id = await db.insert('transactions', clean)
            succeeded.append({'id': tx_id})
        except ValidationError as e:
            failed.append({'item': item, 'error': e.message})
        except Exception as e:
            failed.append({'item': item, 'error': str(e)})

    return success_response({
        'succeeded': succeeded,
        'failed': failed,
        'summary': {
            'total': len(items),
            'success_count': len(succeeded),
            'fail_count': len(failed),
        }
    }, message=f"Imported {len(succeeded)} of {len(items)} transactions")