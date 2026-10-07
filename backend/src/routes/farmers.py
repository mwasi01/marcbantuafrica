"""
Marcbantu Africa — Farmer routes.
Profile management, stats, preferences.
"""
from utils import (
    success_response, error_response, parse_json, require_auth,
    now_iso, is_valid_email, validate_phone, is_valid_phone,
    to_int, log_event,
)
from validators import ValidationError
from constants import HTTP, ErrorCode, Tier, Language
from db import DB


# ============================================================
# GET PROFILE
# ============================================================
async def get_profile(request, env):
    """GET /api/farmers/me
    Returns the current farmer's full profile.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    farmer = await db.query_one("""
        SELECT id, phone, email, full_name, country, county, location,
               language, profile_photo_url, subscription_tier,
               subscription_expires_at, verified, verified_at,
               last_login_at, created_at, updated_at
        FROM farmers WHERE id = ?
    """, [user['id']])

    if not farmer:
        return error_response("Farmer not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # Enrich with counts
    farmer['farm_count'] = await db.count('farms', 'farmer_id = ?', [user['id']])
    _rc = await db.query_one("""
        SELECT COUNT(*) as total FROM records r
        JOIN farms f ON r.farm_id = f.id
        WHERE f.farmer_id = ?
    """, [user['id']])
    farmer['record_count'] = _rc['total'] if _rc else 0

    _ec = await db.query_one("""
        SELECT COUNT(*) as total FROM enterprises e
        JOIN farms f ON e.farm_id = f.id
        WHERE f.farmer_id = ? AND e.status = 'active'
    """, [user['id']])
    farmer['enterprise_count'] = _ec['total'] if _ec else 0

    return success_response(farmer)


# ============================================================
# UPDATE PROFILE
# ============================================================
async def update_profile(request, env):
    """PUT /api/farmers/me
    Body: {full_name?, email?, county?, location?, language?, profile_photo_url?}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    db = DB(env)

    updates = {}

    if 'full_name' in data:
        name = str(data['full_name']).strip()
        if len(name) < 2:
            return error_response("Full name is too short", status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)
        updates['full_name'] = name

    if 'email' in data:
        email = data['email']
        if email:
            email = str(email).strip().lower()
            if not is_valid_email(email):
                return error_response("Invalid email format", status=HTTP.BAD_REQUEST, code=ErrorCode.INVALID_FORMAT)
            # Check uniqueness
            existing = await db.query_one(
                "SELECT id FROM farmers WHERE email = ? AND id != ?",
                [email, user['id']]
            )
            if existing:
                return error_response(
                    "This email is already in use",
                    status=HTTP.CONFLICT,
                    code=ErrorCode.EMAIL_EXISTS,
                )
        updates['email'] = email or None

    if 'county' in data:
        updates['county'] = data['county']

    if 'location' in data:
        updates['location'] = data['location']

    if 'country' in data:
        updates['country'] = data['country']

    if 'language' in data:
        lang = data['language']
        if lang not in Language.ALL:
            return error_response(
                f"Language must be one of: {', '.join(Language.ALL)}",
                status=HTTP.BAD_REQUEST,
                code=ErrorCode.VALIDATION_ERROR,
            )
        updates['language'] = lang

    if 'profile_photo_url' in data:
        updates['profile_photo_url'] = data['profile_photo_url']

    if not updates:
        return error_response("No valid fields to update", status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    updates['updated_at'] = now_iso()

    await db.update('farmers', updates, 'id = ?', [user['id']])

    # Return updated record
    farmer = await db.query_one("""
        SELECT id, phone, email, full_name, country, county, location,
               language, profile_photo_url, subscription_tier,
               subscription_expires_at, verified, updated_at
        FROM farmers WHERE id = ?
    """, [user['id']])

    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': 'profile_updated',
        'entity': 'farmer',
        'entity_id': user['id'],
        'details': ','.join(updates.keys()),
    })

    log_event('profile_updated', {'farmer_id': user['id']})

    return success_response(farmer, message="Profile updated successfully")


# ============================================================
# GET STATS
# ============================================================
async def get_stats(request, env):
    """GET /api/farmers/stats
    Returns summary stats for the current farmer.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)

    # Farms
    farm_count = await db.count('farms', 'farmer_id = ? AND active = 1', [user['id']])

    # Enterprises by type
    enterprises_by_type = await db.query("""
        SELECT e.type, COUNT(*) as count
        FROM enterprises e
        JOIN farms f ON e.farm_id = f.id
        WHERE f.farmer_id = ? AND e.status = 'active'
        GROUP BY e.type
    """, [user['id']])

    # Records
    record_stats = await db.query_one("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN record_date >= date('now', '-30 days') THEN 1 END) as last_30_days,
            COUNT(CASE WHEN record_date >= date('now', '-7 days') THEN 1 END) as last_7_days
        FROM records r
        JOIN farms f ON r.farm_id = f.id
        WHERE f.farmer_id = ?
    """, [user['id']])

    # Financial totals (all time)
    financials = await db.query_one("""
        SELECT
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as total_income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as total_expenses
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE f.farmer_id = ?
    """, [user['id']])

    total_income = financials['total_income'] if financials else 0
    total_expenses = financials['total_expenses'] if financials else 0

    # Tasks
    task_stats = await db.query_one("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed
        FROM tasks t
        JOIN farms f ON t.farm_id = f.id
        WHERE f.farmer_id = ?
    """, [user['id']])

    # Sales totals
    sales_totals = await db.query_one("""
        SELECT
            COUNT(*) as total_sales,
            COALESCE(SUM(total), 0) as total_revenue
        FROM sales s
        JOIN farms f ON s.farm_id = f.id
        WHERE f.farmer_id = ?
    """, [user['id']])

    return success_response({
        'farms': {
            'total': farm_count,
        },
        'enterprises': {
            'by_type': enterprises_by_type,
            'total': sum(e['count'] for e in enterprises_by_type),
        },
        'records': {
            'total': record_stats['total'] if record_stats else 0,
            'last_30_days': record_stats['last_30_days'] if record_stats else 0,
            'last_7_days': record_stats['last_7_days'] if record_stats else 0,
        },
        'finance': {
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_profit': total_income - total_expenses,
        },
        'tasks': {
            'total': task_stats['total'] if task_stats else 0,
            'pending': task_stats['pending'] if task_stats else 0,
            'completed': task_stats['completed'] if task_stats else 0,
        },
        'sales': {
            'total_count': sales_totals['total_sales'] if sales_totals else 0,
            'total_revenue': sales_totals['total_revenue'] if sales_totals else 0,
        },
    })


# ============================================================
# SUBSCRIPTION INFO
# ============================================================
async def subscription_info(request, env):
    """GET /api/farmers/subscription
    Returns tier, expiry, and usage limits.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    farmer = await db.query_one("""
        SELECT subscription_tier, subscription_expires_at
        FROM farmers WHERE id = ?
    """, [user['id']])

    if not farmer:
        return error_response("Farmer not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    tier = farmer['subscription_tier'] or Tier.STARTER
    limits = {
        Tier.STARTER: {'farms': 1, 'records_per_month': 500, 'sms_per_month': 30},
        Tier.PRO: {'farms': 5, 'records_per_month': 5000, 'sms_per_month': 300},
        Tier.BUSINESS: {'farms': 50, 'records_per_month': 50000, 'sms_per_month': 3000},
    }.get(tier, {'farms': 1, 'records_per_month': 500, 'sms_per_month': 30})

    # Current usage
    farm_count = await db.count('farms', 'farmer_id = ?', [user['id']])

    _rcm = await db.query_one("""
        SELECT COUNT(*) as total FROM records r
        JOIN farms f ON r.farm_id = f.id
        WHERE f.farmer_id = ? AND r.record_date >= date('now', 'start of month')
    """, [user['id']])
    record_count_month = _rcm['total'] if _rcm else 0

    return success_response({
        'tier': tier,
        'expires_at': farmer['subscription_expires_at'],
        'limits': limits,
        'usage': {
            'farms': farm_count,
            'records_this_month': record_count_month,
        },
        'pricing': {
            'starter': 0,
            'pro': 500,
            'business': 2000,
        },
    })


# ============================================================
# UPGRADE SUBSCRIPTION
# ============================================================
async def upgrade_subscription(request, env):
    """POST /api/farmers/upgrade
    Body: {tier, payment_reference?}
    In production, this would integrate with M-Pesa.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    new_tier = data.get('tier')

    if new_tier not in Tier.ALL:
        return error_response(
            f"Tier must be one of: {', '.join(Tier.ALL)}",
            status=HTTP.BAD_REQUEST,
            code=ErrorCode.VALIDATION_ERROR,
        )

    db = DB(env)
    farmer = await db.query_one(
        "SELECT subscription_tier FROM farmers WHERE id = ?",
        [user['id']]
    )

    if farmer['subscription_tier'] == new_tier:
        return error_response("Already on this tier", status=HTTP.BAD_REQUEST, code=ErrorCode.CONFLICT)

    # In production: verify payment_reference with M-Pesa
    # For now, just upgrade

    from datetime import datetime, timedelta, timezone
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')

    await db.update('farmers', {
        'subscription_tier': new_tier,
        'subscription_expires_at': expires,
        'updated_at': now_iso(),
    }, 'id = ?', [user['id']])

    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': 'subscription_upgraded',
        'entity': 'farmer',
        'entity_id': user['id'],
        'details': f"Upgraded to {new_tier}",
    })

    await db.insert('notifications', {
        'farmer_id': user['id'],
        'type': 'system',
        'title': f'Upgraded to {new_tier.title()}',
        'message': f'Your subscription has been upgraded. Enjoy the new features!',
        'priority': 'high',
    })

    log_event('subscription_upgraded', {'farmer_id': user['id'], 'tier': new_tier})

    return success_response({
        'tier': new_tier,
        'expires_at': expires,
    }, message=f"Upgraded to {new_tier.title()}")


# ============================================================
# PREFERENCES
# ============================================================
async def get_preferences(request, env):
    """GET /api/farmers/preferences
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)

    farmer = await db.query_one(
        "SELECT language FROM farmers WHERE id = ?",
        [user['id']]
    )

    return success_response({
        'language': farmer['language'] if farmer else 'en',
        'notifications': {
            'sms': True,
            'whatsapp': True,
            'push': True,
            'email': False,
        },
        'categories': {
            'weather': True,
            'market': True,
            'reminders': True,
            'pest_alerts': True,
            'learning': True,
            'finance': True,
        },
    })


async def update_preferences(request, env):
    """PUT /api/farmers/preferences
    Body: {language?, notifications?, categories?}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    db = DB(env)

    updates = {}

    if 'language' in data:
        if data['language'] not in Language.ALL:
            return error_response("Invalid language", status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)
        updates['language'] = data['language']

    if updates:
        updates['updated_at'] = now_iso()
        await db.update('farmers', updates, 'id = ?', [user['id']])

    # Store notification prefs in KV
    if 'notifications' in data or 'categories' in data:
        try:
            prefs_key = f"prefs:{user['id']}"
            existing = await env.CACHE.get(prefs_key)
            import json
            prefs = json.loads(existing) if existing else {}
            if 'notifications' in data:
                prefs['notifications'] = data['notifications']
            if 'categories' in data:
                prefs['categories'] = data['categories']
            await env.CACHE.put(prefs_key, json.dumps(prefs))
        except Exception:
            pass

    return success_response(None, message="Preferences updated")


# ============================================================
# ACTIVITY LOG
# ============================================================
async def activity_log(request, env):
    """GET /api/farmers/activity?limit=50
    Returns the recent activity for the current farmer.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    from utils import get_int_query
    limit = min(get_int_query(request, 'limit', 50), 200)

    db = DB(env)

    activities = await db.query("""
        SELECT id, action, entity, entity_id, details, created_at
        FROM audit_log
        WHERE farmer_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    """, [user['id'], limit])

    return success_response(activities)


# ============================================================
# DASHBOARD SUMMARY (personalized home)
# ============================================================
async def dashboard(request, env):
    """GET /api/farmers/dashboard
    Returns everything the dashboard needs in one call.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)

    # Farmer info
    farmer = await db.query_one("""
        SELECT id, full_name, county, location, subscription_tier, verified
        FROM farmers WHERE id = ?
    """, [user['id']])

    # Total farms
    farm_count = await db.count('farms', 'farmer_id = ? AND active = 1', [user['id']])

    # Get farm IDs
    farms = await db.query("SELECT id FROM farms WHERE farmer_id = ? AND active = 1", [user['id']])
    farm_ids = [f['id'] for f in farms]

    if not farm_ids:
        return success_response({
            'farmer': farmer,
            'needs_setup': True,
            'message': 'Add your first farm to get started',
            'farms': 0,
        })

    placeholders = ','.join(['?'] * len(farm_ids))

    # Financial (all time)
    financials = await db.query_one(f"""
        SELECT
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses
        FROM transactions WHERE farm_id IN ({placeholders})
    """, farm_ids)

    # This month
    this_month = await db.query_one(f"""
        SELECT
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses
        FROM transactions
        WHERE farm_id IN ({placeholders})
        AND transaction_date >= date('now', 'start of month')
    """, farm_ids)

    # Last month (for comparison)
    last_month = await db.query_one(f"""
        SELECT
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses
        FROM transactions
        WHERE farm_id IN ({placeholders})
        AND transaction_date >= date('now', 'start of month', '-1 month')
        AND transaction_date < date('now', 'start of month')
    """, farm_ids)

    # Active enterprises
    enterprise_count = await db.query_one(f"""
        SELECT COUNT(*) as total FROM enterprises
        WHERE farm_id IN ({placeholders}) AND status = 'active'
    """, farm_ids)

    # Pending tasks
    tasks = await db.query_one(f"""
        SELECT COUNT(*) as total FROM tasks
        WHERE farm_id IN ({placeholders}) AND status = 'pending'
    """, farm_ids)

    # Unread notifications
    notif_count = await db.count('notifications', 'farmer_id = ? AND read_at IS NULL', [user['id']])

    # Recent records
    recent_records = await db.query(f"""
        SELECT r.id, r.record_type, r.activity, r.description, r.quantity, r.unit, r.record_date
        FROM records r
        WHERE r.farm_id IN ({placeholders})
        ORDER BY r.record_date DESC, r.id DESC
        LIMIT 5
    """, farm_ids)

    # Recent transactions
    recent_transactions = await db.query(f"""
        SELECT t.id, t.type, t.category, t.description, t.amount, t.transaction_date
        FROM transactions t
        WHERE t.farm_id IN ({placeholders})
        ORDER BY t.transaction_date DESC, t.id DESC
        LIMIT 5
    """, farm_ids)

    # Today's market prices (top 5)
    market_prices = await db.query("""
        SELECT crop, market, price, unit
        FROM market_prices
        WHERE price_date = (SELECT MAX(price_date) FROM market_prices)
        LIMIT 5
    """)

    # Unread notifications (recent 3)
    notifications = await db.query("""
        SELECT id, type, title, message, priority, created_at
        FROM notifications
        WHERE farmer_id = ? AND read_at IS NULL
        ORDER BY created_at DESC
        LIMIT 3
    """, [user['id']])

    # Calculate change percentages
    def pct_change(current, previous):
        if not previous or previous == 0:
            return 0
        return round(((current - previous) / previous) * 100, 1)

    return success_response({
        'farmer': farmer,
        'needs_setup': False,
        'farms': farm_count,
        'enterprises': enterprise_count['total'] if enterprise_count else 0,
        'pending_tasks': tasks['total'] if tasks else 0,
        'unread_notifications': notif_count,
        'finance': {
            'all_time_income': financials['income'] if financials else 0,
            'all_time_expenses': financials['expenses'] if financials else 0,
            'all_time_profit': (financials['income'] - financials['expenses']) if financials else 0,
            'this_month_income': this_month['income'] if this_month else 0,
            'this_month_expenses': this_month['expenses'] if this_month else 0,
            'this_month_profit': (this_month['income'] - this_month['expenses']) if this_month else 0,
            'income_change_pct': pct_change(
                this_month['income'] if this_month else 0,
                last_month['income'] if last_month else 0,
            ),
            'expense_change_pct': pct_change(
                this_month['expenses'] if this_month else 0,
                last_month['expenses'] if last_month else 0,
            ),
        },
        'recent_records': recent_records,
        'recent_transactions': recent_transactions,
        'market_prices': market_prices,
        'notifications': notifications,
    })


# ============================================================
# VERIFY ACCOUNT (sends OTP)
# ============================================================
async def verify_account(request, env):
    """POST /api/farmers/verify
    Sends an OTP to verify the farmer's phone number.
    """
    import random

    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    farmer = await db.query_one(
        "SELECT id, phone, verified FROM farmers WHERE id = ?",
        [user['id']]
    )
    if not farmer:
        return error_response("Farmer not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    if farmer['verified']:
        return success_response(None, message="Account already verified")

    otp = f"{random.randint(100000, 999999)}"
    try:
        await env.CACHE.put(f"verify:{farmer['phone']}", otp, expirationTtl=600)
    except Exception:
        return error_response("Failed to generate OTP", status=HTTP.INTERNAL_ERROR)

    # Queue SMS
    try:
        await env.JOBS.send({
            "type": "send_sms",
            "payload": {
                "to": farmer['phone'],
                "farmer_id": farmer['id'],
                "body": f"Your Marcbantu verification code is: {otp}. Valid for 10 minutes.",
            }
        })
    except Exception:
        pass

    return success_response(None, message="Verification code sent")
