"""
Marcbantu Africa — Monthly scheduled jobs.
1st of month: cleanup old data.
"""
from utils import log_event, log_error
from db import DB


async def cleanup(env):
    """Clean up old data."""
    db = DB(env)
    log_event('cleanup_start')

    # Delete read notifications older than 90 days
    await db.execute("""
        DELETE FROM notifications
        WHERE read = 1 AND created_at < datetime('now', '-90 days')
    """)

    # Delete expired sessions
    await db.execute("""
        DELETE FROM sessions
        WHERE expires_at < datetime('now')
    """)

    # Delete old communication logs (older than 180 days)
    await db.execute("""
        DELETE FROM communication_log
        WHERE created_at < datetime('now', '-180 days')
    """)

    # Clean old weather cache
    await db.execute("""
        DELETE FROM weather_cache
        WHERE forecast_date < date('now', '-7 days')
    """)

    # Clean old audit log (keep 1 year)
    await db.execute("""
        DELETE FROM audit_log
        WHERE created_at < datetime('now', '-1 year')
    """)

    # Clean rate limit log
    await db.execute("""
        DELETE FROM rate_limit_log
        WHERE window_start < datetime('now', '-1 day')
    """)

    log_event('cleanup_done')