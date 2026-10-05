"""
Marcbantu Africa — Decision routes.
Farm decision-support tools: break-even, gross margin, marginal analysis,
loan affordability, payback, what-if, risk assessment, enterprise comparison.
Each calculation is optionally saved to history for later review.
"""
from utils import (
    success_response, error_response, parse_json, require_auth,
    now_iso, to_int, to_float, log_event, require_fields,
    _sp,
)
from validators import (
    ValidationError,
    validate_breakeven, validate_gross_margin, validate_loan, validate_risk,
)
from constants import HTTP, ErrorCode
from db import DB


# ============================================================
# HELPERS
# ============================================================
async def _save_decision(db: DB, farmer_id: int, decision_type: str,
                        inputs: dict, result: dict, farm_id: int = None):
    """Store a decision calculation for history. Non-fatal if it fails."""
    try:
        import json
        await db.insert('audit_log', {
            'farmer_id': farmer_id,
            'action': f'decision_{decision_type}',
            'entity': 'decision',
            'details': json.dumps({'inputs': inputs, 'result': result}),
        })
    except Exception:
        pass


def _round(value, decimals: int = 2):
    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return 0


# ============================================================
# 1. BREAK-EVEN CALCULATOR
# ============================================================
async def breakeven(request, env):
    """POST /api/decisions/breakeven
    Body: {fixed_costs, variable_cost_per_unit, price_per_unit, unit?}
    Returns: contribution margin, break-even units, break-even revenue.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    try:
        clean = validate_breakeven(data)
    except ValidationError as e:
        return error_response(e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    fixed = clean['fixed_costs']
    vc = clean['variable_cost_per_unit']
    price = clean['price_per_unit']

    cm = price - vc
    be_units = fixed / cm
    be_revenue = be_units * price

    # Additional insights
    unit = data.get('unit', 'units')
    margin_percent = (cm / price * 100) if price > 0 else 0

    result = {
        'contribution_margin_per_unit': _round(cm),
        'contribution_margin_percent': _round(margin_percent, 1),
        'breakeven_units': _round(be_units, 1),
        'breakeven_revenue': _round(be_revenue),
        'unit': unit,
        'interpretation': (
            f"You need to sell at least {_round(be_units, 0):.0f} {unit} "
            f"at KES {price:,.2f} each to cover all costs."
        ),
    }

    # Scenario analysis: what if price changes?
    scenarios = []
    for pct in [-20, -10, 0, 10, 20]:
        new_price = price * (1 + pct / 100)
        if new_price > vc:
            new_be = fixed / (new_price - vc)
            scenarios.append({
                'price_change_percent': pct,
                'new_price': _round(new_price),
                'new_breakeven_units': _round(new_be, 1),
            })
    result['price_scenarios'] = scenarios

    db = DB(env)
    await _save_decision(db, user['id'], 'breakeven', clean, result)

    return success_response(result)


# ============================================================
# 2. GROSS MARGIN CALCULATOR
# ============================================================
async def gross_margin(request, env):
    """POST /api/decisions/gross-margin
    Body: {revenue, variable_costs, enterprise?}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    try:
        clean = validate_gross_margin(data)
    except ValidationError as e:
        return error_response(e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    revenue = clean['revenue']
    vc = clean['variable_costs']
    margin = revenue - vc
    margin_pct = (margin / revenue * 100) if revenue > 0 else 0
    cost_ratio = (vc / revenue * 100) if revenue > 0 else 0

    # Rating
    if margin_pct >= 60:
        rating = "Excellent"
    elif margin_pct >= 40:
        rating = "Good"
    elif margin_pct >= 20:
        rating = "Fair"
    elif margin_pct >= 0:
        rating = "Poor"
    else:
        rating = "Loss-making"

    result = {
        'gross_margin': _round(margin),
        'gross_margin_percent': _round(margin_pct, 1),
        'cost_ratio_percent': _round(cost_ratio, 1),
        'rating': rating,
        'interpretation': (
            f"Revenue: KES {revenue:,.2f} | Costs: KES {vc:,.2f} | "
            f"Margin: KES {margin:,.2f} ({_round(margin_pct, 1)}%)"
        ),
    }

    db = DB(env)
    await _save_decision(db, user['id'], 'gross_margin', clean, result)

    return success_response(result)


# ============================================================
# 3. MARGINAL ANALYSIS
# ============================================================
async def marginal_analysis(request, env):
    """POST /api/decisions/marginal
    Body: {additional_revenue, additional_cost, unit?}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ['additional_revenue', 'additional_cost'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    rev = to_float(data['additional_revenue'])
    cost = to_float(data['additional_cost'])
    profit = rev - cost

    if profit > 0:
        recommendation = "Proceed"
        reason = f"Each additional unit adds KES {profit:,.2f} to profit."
    elif profit == 0:
        recommendation = "Break-even"
        reason = "Additional unit adds no profit and no loss."
    else:
        recommendation = "Do not proceed"
        reason = f"Each additional unit loses KES {abs(profit):,.2f}."

    result = {
        'marginal_revenue': _round(rev),
        'marginal_cost': _round(cost),
        'marginal_profit': _round(profit),
        'recommendation': recommendation,
        'reason': reason,
        'ratio': _round(rev / cost, 2) if cost > 0 else 0,
    }

    # Sensitivity: what if marginal revenue drops?
    scenarios = []
    for pct in [-30, -20, -10, 0, 10]:
        new_rev = rev * (1 + pct / 100)
        new_profit = new_rev - cost
        scenarios.append({
            'revenue_change_percent': pct,
            'new_marginal_profit': _round(new_profit),
            'still_profitable': new_profit > 0,
        })
    result['sensitivity'] = scenarios

    db = DB(env)
    await _save_decision(db, user['id'], 'marginal', data, result)

    return success_response(result)


# ============================================================
# 4. LOAN AFFORDABILITY
# ============================================================
async def loan_affordability(request, env):
    """POST /api/decisions/loan
    Body: {loan_amount, annual_rate, term_months, monthly_profit}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    try:
        clean = validate_loan(data)
    except ValidationError as e:
        return error_response(e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    amount = clean['loan_amount']
    annual_rate = clean['annual_rate'] / 100
    term = clean['term_months']
    profit = clean['monthly_profit']

    monthly_rate = annual_rate / 12
    if monthly_rate > 0:
        payment = amount * monthly_rate * ((1 + monthly_rate) ** term) / (((1 + monthly_rate) ** term) - 1)
    else:
        payment = amount / term

    total_paid = payment * term
    total_interest = total_paid - amount
    pct_of_profit = (payment / profit * 100) if profit > 0 else 999

    # Verdict
    if pct_of_profit < 20:
        verdict = "Safe"
        verdict_detail = "Loan repayment comfortably within your profit."
    elif pct_of_profit < 35:
        verdict = "Manageable"
        verdict_detail = "Feasible, but leaves less buffer for surprises."
    elif pct_of_profit < 50:
        verdict = "Risky"
        verdict_detail = "Over a third of your profit goes to loan repayment."
    else:
        verdict = "Not recommended"
        verdict_detail = "Repayment exceeds a safe share of your profit."

    result = {
        'monthly_payment': _round(payment),
        'total_paid': _round(total_paid),
        'total_interest': _round(total_interest),
        'percent_of_monthly_profit': _round(pct_of_profit, 1),
        'verdict': verdict,
        'verdict_detail': verdict_detail,
    }

    # Alternative scenarios: shorter/longer terms
    alternatives = []
    for alt_term in [term - 12, term, term + 12]:
        if alt_term <= 0:
            continue
        if monthly_rate > 0:
            alt_pay = amount * monthly_rate * ((1 + monthly_rate) ** alt_term) / (((1 + monthly_rate) ** alt_term) - 1)
        else:
            alt_pay = amount / alt_term
        alternatives.append({
            'term_months': alt_term,
            'monthly_payment': _round(alt_pay),
            'total_paid': _round(alt_pay * alt_term),
            'pct_of_profit': _round((alt_pay / profit * 100) if profit > 0 else 999, 1),
        })
    result['alternatives'] = alternatives

    db = DB(env)
    await _save_decision(db, user['id'], 'loan', clean, result)

    return success_response(result)


# ============================================================
# 5. INVESTMENT PAYBACK
# ============================================================
async def payback_period(request, env):
    """POST /api/decisions/payback
    Body: {investment_cost, additional_annual_income, years?}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ['investment_cost', 'additional_annual_income'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    cost = to_float(data['investment_cost'])
    income = to_float(data['additional_annual_income'])

    if cost <= 0:
        return error_response("Investment cost must be positive",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)
    if income <= 0:
        return error_response("Additional income must be positive",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    payback_years = cost / income
    payback_months = payback_years * 12
    roi_year1 = (income / cost * 100)

    # Discounted payback over multiple years (simple)
    horizon = min(int(data.get('years', 5)), 20)
    cumulative = []
    cum = 0
    for i in range(1, horizon + 1):
        cum += income
        cumulative.append({
            'year': i,
            'cumulative_income': _round(cum),
            'net_position': _round(cum - cost),
            'payback_reached': cum >= cost,
        })

    result = {
        'payback_years': _round(payback_years, 2),
        'payback_months': _round(payback_months, 1),
        'roi_year1_percent': _round(roi_year1, 1),
        'interpretation': (
            f"Investment of KES {cost:,.0f} pays back in "
            f"{_round(payback_years, 1)} years ({_round(payback_months, 0):.0f} months)."
        ),
        'cumulative': cumulative,
    }

    db = DB(env)
    await _save_decision(db, user['id'], 'payback', data, result)

    return success_response(result)


# ============================================================
# 6. WHAT-IF SIMULATOR
# ============================================================
async def what_if(request, env):
    """POST /api/decisions/what-if
    Body: {current_profit, current_revenue, current_costs,
           revenue_change_pct, cost_change_pct}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ['current_profit', 'current_revenue', 'current_costs'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    profit = to_float(data['current_profit'])
    revenue = to_float(data['current_revenue'])
    costs = to_float(data['current_costs'])
    rev_change = to_float(data.get('revenue_change_pct', 0)) / 100
    cost_change = to_float(data.get('cost_change_pct', 0)) / 100

    new_revenue = revenue * (1 + rev_change)
    new_costs = costs * (1 + cost_change)
    new_profit = new_revenue - new_costs
    change_pct = ((new_profit - profit) / abs(profit) * 100) if profit != 0 else 0

    result = {
        'current': {
            'revenue': _round(revenue),
            'costs': _round(costs),
            'profit': _round(profit),
        },
        'simulated': {
            'revenue': _round(new_revenue),
            'costs': _round(new_costs),
            'profit': _round(new_profit),
        },
        'change': {
            'revenue': _round(new_revenue - revenue),
            'costs': _round(new_costs - costs),
            'profit': _round(new_profit - profit),
            'profit_percent': _round(change_pct, 1),
        },
        'interpretation': (
            f"New profit would be KES {new_profit:,.2f} "
            f"({'increase' if change_pct > 0 else 'decrease'} of {abs(_round(change_pct, 1))}%)."
        ),
    }

    # Sensitivity grid
    grid = []
    for r_pct in [-20, -10, 0, 10, 20]:
        row = {'revenue_change': r_pct}
        for c_pct in [-10, 0, 10, 20]:
            r = revenue * (1 + r_pct / 100)
            c = costs * (1 + c_pct / 100)
            row[f'cost_{c_pct}'] = _round(r - c)
        grid.append(row)
    result['sensitivity_grid'] = grid

    db = DB(env)
    await _save_decision(db, user['id'], 'what_if', data, result)

    return success_response(result)


# ============================================================
# 7. RISK ASSESSMENT
# ============================================================
async def risk_assessment(request, env):
    """POST /api/decisions/risk
    Body: {scores: {drought: 3, pest: 4, price: 3, market: 2, finance: 3}}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    try:
        clean = validate_risk(data)
    except ValidationError as e:
        return error_response(e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    scores = clean['scores']
    total = sum(scores.values())
    count = len(scores)
    avg = total / count if count else 0

    if avg < 2:
        level = "Low"
    elif avg < 3.5:
        level = "Moderate"
    elif avg < 4.5:
        level = "High"
    else:
        level = "Critical"

    # Sorted by severity
    ranked = sorted(scores.items(), key=lambda x: -x[1])

    # Mitigation suggestions
    mitigations = {
        'drought': 'Invest in water harvesting, drip irrigation, drought-resistant varieties, crop insurance.',
        'pest': 'Scout weekly, use IPM, rotate chemicals, maintain field sanitation.',
        'price': 'Diversify crops, contract farming, price alerts, storage to sell at peak.',
        'market': 'Build multiple buyer relationships, join cooperative, add value locally.',
        'finance': 'Build cash reserves, access credit before crisis, keep tight records.',
        'weather': 'Monitor forecasts, adjust planting dates, protect structures.',
        'labour': 'Train workers, document procedures, cross-train staff.',
        'disease': 'Vaccinate livestock, quarantine new animals, keep records.',
        'theft': 'Fence perimeter, install lighting, hire watchman.',
        'flood': 'Build drainage, raised beds, avoid low-lying areas.',
    }

    recommendations = []
    for risk, score in ranked[:3]:
        recommendations.append({
            'risk': risk,
            'score': score,
            'priority': 'High' if score >= 4 else 'Medium' if score >= 3 else 'Low',
            'mitigation': mitigations.get(risk, 'Review and manage this risk closely.'),
        })

    result = {
        'scores': scores,
        'total_score': _round(total),
        'average_score': _round(avg, 2),
        'max_possible': count * 5,
        'level': level,
        'ranked_risks': [{'risk': r, 'score': s} for r, s in ranked],
        'recommendations': recommendations,
    }

    db = DB(env)
    await _save_decision(db, user['id'], 'risk', clean, result)

    return success_response(result)


# ============================================================
# 8. ENTERPRISE COMPARISON
# ============================================================
async def enterprise_comparison(request, env):
    """GET /api/decisions/compare
    Query: farm_id?, from?, to?
    Compares all enterprises side-by-side with rankings.
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
        where.append("e.farm_id = ?")
        params.append(to_int(farm_id))

    date_from = url.search_params.get('from')
    date_to = url.search_params.get('to')

    date_clause = ''
    if date_from:
        date_clause += f" AND t.transaction_date >= '{date_from}'"
    if date_to:
        date_clause += f" AND t.transaction_date <= '{date_to}'"

    where_sql = ' AND '.join(where)

    enterprises = await db.query(f"""
        SELECT
            e.id as enterprise_id,
            e.name,
            e.type,
            e.status,
            e.quantity,
            e.unit,
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as expenses,
            COUNT(DISTINCT r.id) as record_count
        FROM enterprises e
        JOIN farms f ON e.farm_id = f.id
        LEFT JOIN transactions t ON t.enterprise_id = e.id {date_clause}
        LEFT JOIN records r ON r.enterprise_id = e.id
        WHERE {where_sql}
        GROUP BY e.id
    """, params)

    for e in enterprises:
        e['profit'] = e['income'] - e['expenses']
        e['margin_percent'] = _round((e['profit'] / e['income'] * 100), 1) if e['income'] > 0 else 0

    # Rankings
    by_profit = sorted(enterprises, key=lambda x: -x['profit'])
    by_income = sorted(enterprises, key=lambda x: -x['income'])
    by_margin = sorted(enterprises, key=lambda x: -x['margin_percent'])

    rankings = {
        'by_profit': [
            {'rank': i + 1, 'enterprise': e['name'], 'value': e['profit']}
            for i, e in enumerate(by_profit)
        ],
        'by_income': [
            {'rank': i + 1, 'enterprise': e['name'], 'value': e['income']}
            for i, e in enumerate(by_income)
        ],
        'by_margin': [
            {'rank': i + 1, 'enterprise': e['name'], 'value': e['margin_percent']}
            for i, e in enumerate(by_margin)
        ],
    }

    return success_response({
        'enterprises': enterprises,
        'rankings': rankings,
        'total_count': len(enterprises),
    })


# ============================================================
# DECISION HISTORY
# ============================================================
async def decision_history(request, env):
    """GET /api/decisions/history
    Query: type?, limit=20
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)
    limit = min(to_int(url.search_params.get('limit', 20), 20), 100)

    where = ["farmer_id = ?", "action LIKE 'decision_%'"]
    params = [user['id']]

    decision_type = url.search_params.get('type')
    if decision_type:
        where.append("action = ?")
        params.append(f'decision_{decision_type}')

    params.append(limit)

    history = await db.query(f"""
        SELECT id, action, details, created_at
        FROM audit_log
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC
        LIMIT ?
    """, params)

    # Parse details
    import json
    for h in history:
        h['type'] = h['action'].replace('decision_', '')
        try:
            h['data'] = json.loads(h['details']) if h['details'] else {}
        except Exception:
            h['data'] = {}
        del h['details']

    return success_response(history)