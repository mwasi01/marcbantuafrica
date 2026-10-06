"""
Job: sms_reminders
Sends daily reminders to farmers who opted in.
Runs daily at 7am via cron.
"""
from utils import now_iso, log_event, log_error
from db import DB


async def run(payload: dict, env):
    """Queue daily SMS reminders."""
    log_event("sms_reminders_start")

    db = DB(env)

    # Get farmers with Pro+ tier who haven't received a reminder today
    farmers = await db.query("""
        SELECT f.id, f.phone, f.full_name, f.language
        FROM farmers f
        WHERE f.subscription_tier IN ('pro', 'business')
        AND f.verified = 1
        AND f.phone IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM communication_log cl
            WHERE cl.farmer_id = f.id
            AND cl.channel = 'sms'
            AND cl.direction = 'outbound'
            AND cl.created_at >= date('now')
            AND cl.reference LIKE 'REMINDER%'
        )
        LIMIT 1000
    """)

    if not farmers:
        log_event("sms_reminders_none")
        return

    queued = 0
    failed = 0

    for farmer in farmers:
        try:
            first_name = (farmer["full_name"] or "farmer").split()[0]

            # Personalize based on records count
            recent_records = await db.query_one("""
                SELECT COUNT(*) as total FROM records r
                JOIN farms f ON r.farm_id = f.id
                WHERE f.farmer_id = ?
                AND r.record_date >= date('now', '-1 day')
            """, [farmer["id"]])

            if recent_records and recent_records["total"] == 0:
                message = (
                    f"Hi {first_name}, don't forget to record today's farm activities. "
                    "Reply MILK [litres] or open the app. Consistency pays!"
                )
            else:
                message = (
                    f"Hi {first_name}, keep up the great work! "
                    "Check today's market prices with PRICE."
                )

            # Queue SMS
            await env.JOBS.send({
                "type": "send_sms",
                "payload": {
                    "to": farmer["phone"],
                    "farmer_id": farmer["id"],
                    "message": message,
                },
            })
            queued += 1

        except Exception as e:
            failed += 1
            log_error(f"Reminder failed for farmer {farmer['id']}: {str(e)}")

    log_event("sms_reminders_done", {
        "queued": queued,
        "failed": failed,
        "total": len(farmers),
    })