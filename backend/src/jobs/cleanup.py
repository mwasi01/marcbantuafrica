"""
Job: cleanup
Removes old data to keep the database lean.
Runs on the 1st of every month at midnight via cron.
"""
from utils import log_event, log_error
from db import DB


async def run(payload: dict, env):
    """Clean up old data."""
    log_event("cleanup_start")

    db = DB(env)
    stats = {}

    # 1. Old read notifications (90 days)
    try:
        result = await db.execute("""
            DELETE FROM notifications
            WHERE read = 1 AND created_at < datetime('now', '-90 days')
        """)
        stats["notifications"] = result.meta.changes if hasattr(result, "meta") and result.meta else 0
    except Exception as e:
        log_error(f"Cleanup notifications: {str(e)}")

    # 2. Expired sessions
    try:
        result = await db.execute("""
            DELETE FROM sessions
            WHERE expires_at < datetime('now')
        """)
        stats["sessions"] = result.meta.changes if hasattr(result, "meta") and result.meta else 0
    except Exception as e:
        log_error(f"Cleanup sessions: {str(e)}")

    # 3. Old communication logs (180 days)
    try:
        result = await db.execute("""
            DELETE FROM communication_log
            WHERE created_at < datetime('now', '-180 days')
            AND status IN ('sent', 'delivered', 'failed')
        """)
        stats["comms"] = result.meta.changes if hasattr(result, "meta") and result.meta else 0
    except Exception as e:
        log_error(f"Cleanup comms: {str(e)}")

    # 4. Old weather cache (7 days old)
    try:
        result = await db.execute("""
            DELETE FROM weather_cache
            WHERE forecast_date < date('now', '-7 days')
        """)
        stats["weather"] = result.meta.changes if hasattr(result, "meta") and result.meta else 0
    except Exception as e:
        log_error(f"Cleanup weather: {str(e)}")

    # 5. Old audit logs (1 year)
    try:
        result = await db.execute("""
            DELETE FROM audit_log
            WHERE created_at < datetime('now', '-1 year')
            AND action NOT IN ('register', 'account_deleted')
        """)
        stats["audit"] = result.meta.changes if hasattr(result, "meta") and result.meta else 0
    except Exception as e:
        log_error(f"Cleanup audit: {str(e)}")

    # 6. Old rate limit logs (1 day)
    try:
        result = await db.execute("""
            DELETE FROM rate_limit_log
            WHERE window_start < datetime('now', '-1 day')
        """)
        stats["ratelimit"] = result.meta.changes if hasattr(result, "meta") and result.meta else 0
    except Exception as e:
        log_error(f"Cleanup ratelimit: {str(e)}")

    # 7. Old message queue (sent/failed 30+ days)
    try:
        result = await db.execute("""
            DELETE FROM message_queue
            WHERE status IN ('sent', 'failed')
            AND created_at < datetime('now', '-30 days')
        """)
        stats["queue"] = result.meta.changes if hasattr(result, "meta") and result.meta else 0
    except Exception as e:
        log_error(f"Cleanup queue: {str(e)}")

    # 8. Expired device tokens (inactive 90+ days)
    try:
        result = await db.execute("""
            DELETE FROM device_tokens
            WHERE active = 0
            AND last_used_at < datetime('now', '-90 days')
        """)
        stats["tokens"] = result.meta.changes if hasattr(result, "meta") and result.meta else 0
    except Exception as e:
        log_error(f"Cleanup tokens: {str(e)}")

    # 9. Triggered price alerts (30+ days after trigger)
    try:
        result = await db.execute("""
            DELETE FROM price_alerts
            WHERE active = 0
            AND triggered_at IS NOT NULL
            AND triggered_at < datetime('now', '-30 days')
        """)
        stats["alerts"] = result.meta.changes if hasattr(result, "meta") and result.meta else 0
    except Exception as e:
        log_error(f"Cleanup alerts: {str(e)}")

    # 10. Expired chemical inventory warnings — do NOT delete, just log
    try:
        expired = await db.query("""
            SELECT COUNT(*) as total FROM chemical_inventory
            WHERE expiry_date < date('now')
        """)
        stats["expired_chemicals"] = expired[0]["total"] if expired else 0
    except Exception:
        pass

    log_event("cleanup_done", stats)