"""
Marcbantu Africa — Report routes.
Generate PDF/CSV/JSON reports for farmers.
"""
from utils import (
    success_response, error_response, require_auth,
    now_iso, to_int, to_float, log_event, json_response,
)
from constants import HTTP, ErrorCode
from db import DB


# ============================================================
# HELPER: Date range from query
# ============================================================
def _date_range(url, default_days: int = 90):
    date_from = url.search_params.get('from')
    date_to = url.search_params.get('to')
    if not date_from:
        from datetime import datetime, timedelta
        date_from = (datetime.now() - timedelta(days=default_days)).strftime('%Y-%m-%d')
    if not date_to:
        from datetime import datetime
        date_to = datetime.now().strftime('%Y-%m-%d')
    return date_from, date_to


# ============================================================
# PROFIT & LOSS REPORT
# ============================================================
async def profit_loss_report(request, env):
    """GET /api/reports/profit-loss
    Query: farm_id?, from?, to?, format=json|csv
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = request.url

    date_from, date_to = _date_range(url)
    farm_id = url.search_params.get('farm_id')

    where = ["f.farmer_id = ?", "t.transaction_date BETWEEN ? AND ?"]
    params = [user['id'], date_from, date_to]

    if farm_id:
        where.append("t.farm_id = ?")
        params.append(to_int(farm_id))

    where_sql = ' AND '.join(where)

    income = await db.query(f"""
        SELECT t.category as item, SUM(t.amount) as amount, COUNT(*) as count
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql} AND t.type = 'income'
        GROUP BY t.category ORDER BY amount DESC
    """, params)

    expenses = await db.query(f"""
        SELECT t.category as item, SUM(t.amount) as amount, COUNT(*) as count
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql} AND t.type = 'expense'
        GROUP BY t.category ORDER BY amount DESC
    """, params)

    total_income = sum(i['amount'] for i in income)
    total_expenses = sum(e['amount'] for e in expenses)
    net = total_income - total_expenses
    margin = round((net / total_income * 100), 2) if total_income > 0 else 0

    report = {
        'type': 'profit_loss',
        'generated_at': now_iso(),
        'period': {'from': date_from, 'to': date_to},
        'farm_id': to_int(farm_id) if farm_id else None,
        'summary': {
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_profit': net,
            'margin_percent': margin,
        },
        'income': income,
        'expenses': expenses,
    }

    if url.search_params.get('format') == 'csv':
        return _report_as_csv(report)

    return success_response(report)


# ============================================================
# ENTERPRISE PERFORMANCE REPORT
# ============================================================
async def enterprise_report(request, env):
    """GET /api/reports/enterprise-performance
    Query: farm_id?, from?, to?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = request.url

    date_from, date_to = _date_range(url)
    farm_id = url.search_params.get('farm_id')

    farm_filter = ""
    params = [user['id'], date_from, date_to]
    if farm_id:
        farm_filter = " AND e.farm_id = ?"
        params.append(to_int(farm_id))

    enterprises = await db.query(f"""
        SELECT
            e.id as enterprise_id,
            e.name as enterprise,
            e.type,
            e.status,
            COALESCE(SUM(CASE WHEN t.type = 'income' AND t.transaction_date BETWEEN ? AND ? THEN t.amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' AND t.transaction_date BETWEEN ? AND ? THEN t.amount ELSE 0 END), 0) as expenses
        FROM enterprises e
        JOIN farms f ON e.farm_id = f.id
        LEFT JOIN transactions t ON t.enterprise_id = e.id
        WHERE f.farmer_id = ? {farm_filter}
        GROUP BY e.id
    """, [date_from, date_to, date_from, date_to, user['id']] + ([to_int(farm_id)] if farm_id else []))

    for e in enterprises:
        e['profit'] = e['income'] - e['expenses']
        e['margin_percent'] = round((e['profit'] / e['income'] * 100), 2) if e['income'] > 0 else 0
        e['roi_percent'] = round((e['profit'] / e['expenses'] * 100), 2) if e['expenses'] > 0 else 0

    ranked = sorted(enterprises, key=lambda x: -x['profit'])
    for i, e in enumerate(ranked):
        e['rank'] = i + 1

    return success_response({
        'type': 'enterprise_performance',
        'generated_at': now_iso(),
        'period': {'from': date_from, 'to': date_to},
        'enterprises': enterprises,
        'best_performer': ranked[0] if ranked else None,
        'worst_performer': ranked[-1] if ranked else None,
    })


# ============================================================
# CASH FLOW REPORT
# ============================================================
async def cash_flow_report(request, env):
    """GET /api/reports/cash-flow
    Query: farm_id?, months=6
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = request.url
    months = min(max(to_int(url.search_params.get('months', 6), 6), 1), 24)
    farm_id = url.search_params.get('farm_id')

    where = ["f.farmer_id = ?"]
    params = [user['id']]
    if farm_id:
        where.append("t.farm_id = ?")
        params.append(to_int(farm_id))

    where_sql = ' AND '.join(where)

    monthly = await db.query(f"""
        SELECT
            strftime('%Y-%m', t.transaction_date) as month,
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as inflow,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as outflow
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE {where_sql}
        AND t.transaction_date >= date('now', '-{months} months')
        GROUP BY month ORDER BY month
    """, params)

    running = 0
    for m in monthly:
        m['net'] = m['inflow'] - m['outflow']
        running += m['net']
        m['cumulative_balance'] = running

    return success_response({
        'type': 'cash_flow',
        'generated_at': now_iso(),
        'months': months,
        'monthly': monthly,
        'final_balance': running,
    })


# ============================================================
# CREDIT SCORE
# ============================================================
async def credit_score(request, env):
    """GET /api/reports/credit-score
    Computes a simple credit score from farm records. Range: 300-850
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)

    farmer = await db.query_one("""
        SELECT id, created_at, verified FROM farmers WHERE id = ?
    """, [user['id']])

    if not farmer:
        return error_response("Farmer not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    score = 300

    from datetime import datetime
    try:
        created = datetime.fromisoformat(farmer['created_at'].replace('Z', '+00:00').split('+')[0])
        days_old = (datetime.now() - created).days
    except Exception:
        days_old = 0
    age_score = min(int(days_old / 3.65), 80)
    score += age_score

    verification_score = 50 if farmer['verified'] else 0
    score += verification_score

    record_count = await db.query_one("""
        SELECT COUNT(*) as total FROM records r
        JOIN farms f ON r.farm_id = f.id WHERE f.farmer_id = ?
    """, [user['id']])
    record_count = record_count['total'] if record_count else 0
    record_score = min(record_count, 150)
    score += record_score

    tx_count = await db.query_one("""
        SELECT COUNT(*) as total FROM transactions t
        JOIN farms f ON t.farm_id = f.id WHERE f.farmer_id = ?
    """, [user['id']])
    tx_count = tx_count['total'] if tx_count else 0
    tx_score = min(tx_count // 2, 150)
    score += tx_score

    profit_row = await db.query_one("""
        SELECT
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as expenses
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id WHERE f.farmer_id = ?
    """, [user['id']])
    income = profit_row['income'] if profit_row else 0
    expenses = profit_row['expenses'] if profit_row else 0
    if income > 0:
        margin = (income - expenses) / income
        profit_score = int(min(max(margin, 0), 1) * 120)
    else:
        profit_score = 0
    score += profit_score

    score = min(score, 850)

    if score >= 750:
        rating = 'Excellent'
    elif score >= 650:
        rating = 'Good'
    elif score >= 550:
        rating = 'Fair'
    elif score >= 450:
        rating = 'Poor'
    else:
        rating = 'Very poor'

    avg_monthly_income = income / max(1, tx_count) * 10
    recommended_loan = min(avg_monthly_income * 6, 500000)

    return success_response({
        'score': score,
        'rating': rating,
        'range': {'min': 300, 'max': 850},
        'components': {
            'account_age': age_score,
            'verification': verification_score,
            'record_volume': record_score,
            'transaction_history': tx_score,
            'profitability': profit_score,
        },
        'metrics': {
            'days_active': days_old,
            'record_count': record_count,
            'transaction_count': tx_count,
            'total_income': income,
            'total_expenses': expenses,
            'net_profit': income - expenses,
        },
        'recommended_loan_limit': round(recommended_loan),
        'note': 'Credit score is an estimate based on farm records. Lenders may use their own criteria.',
    })


# ============================================================
# CSV EXPORT HELPER
# ============================================================
def _report_as_csv(report: dict):
    """Convert a report dict to a CSV-format JSON response.
    Returns a json_response wrapper containing the CSV text.
    Client extracts and downloads.
    """
    lines = []
    lines.append(f"# Marcbantu Report: {report.get('type')}")
    lines.append(f"# Generated: {report.get('generated_at')}")

    period = report.get('period', {})
    lines.append(f"# Period: {period.get('from')} to {period.get('to')}")
    lines.append("")

    summary = report.get('summary', {})
    lines.append("Summary")
    for k, v in summary.items():
        lines.append(f"{k},{v}")
    lines.append("")

    if 'income' in report:
        lines.append("Income by Category")
        lines.append("item,amount,count")
        for row in report['income']:
            lines.append(f"{row['item']},{row['amount']},{row['count']}")
        lines.append("")

    if 'expenses' in report:
        lines.append("Expenses by Category")
        lines.append("item,amount,count")
        for row in report['expenses']:
            lines.append(f"{row['item']},{row['amount']},{row['count']}")

    csv_text = "\n".join(lines)
    filename = f"marcbantu-{report.get('type')}-{now_iso()[:10]}.csv"

    return json_response({
        "csv": csv_text,
        "filename": filename,
    }, headers={
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': f"attachment; filename={filename}",
    })
