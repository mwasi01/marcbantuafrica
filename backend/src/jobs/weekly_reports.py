"""
Job: weekly_reports
Generates and sends weekly farm summaries to Pro+ farmers.
Runs every Monday at 8am via cron.
"""
from utils import now_iso, log_event, log_error
from db import DB


async def run(payload: dict, env):
    """Send weekly summaries."""
    log_event("weekly_reports_start")

    db = DB(env)

    farmers = await db.query("""
        SELECT id, phone, email, full_name
        FROM farmers
        WHERE subscription_tier IN ('pro', 'business')
        AND verified = 1
        LIMIT 1000
    """)

    sent_sms = 0
    sent_email = 0
    failed = 0

    for farmer in farmers:
        try:
            summary = await _get_weekly_summary(db, farmer["id"])
            if not summary:
                continue

            first_name = (farmer["full_name"] or "farmer").split()[0]

            # SMS
            if farmer.get("phone"):
                await env.JOBS.send({
                    "type": "send_sms",
                    "payload": {
                        "to": farmer["phone"],
                        "farmer_id": farmer["id"],
                        "template_code": "WEEKLY_SUMMARY",
                        "variables": {
                            "name": first_name,
                            "income": f"{summary['income']:,.0f}",
                            "expenses": f"{summary['expenses']:,.0f}",
                            "profit": f"{summary['profit']:,.0f}",
                        },
                    },
                })
                sent_sms += 1

            # Email (if subscribed)
            if farmer.get("email") and summary["income"] > 0:
                await _send_weekly_email(env, farmer, summary)
                sent_email += 1

        except Exception as e:
            failed += 1
            log_error(f"Weekly report failed for farmer {farmer['id']}: {str(e)}")

    log_event("weekly_reports_done", {
        "sms": sent_sms,
        "email": sent_email,
        "failed": failed,
        "total": len(farmers),
    })


async def _get_weekly_summary(db: DB, farmer_id: int) -> dict | None:
    """Compute 7-day summary for a farmer."""
    row = await db.query_one("""
        SELECT
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as expenses
        FROM transactions t
        JOIN farms f ON t.farm_id = f.id
        WHERE f.farmer_id = ?
        AND t.transaction_date >= date('now', '-7 days')
    """, [farmer_id])

    if not row:
        return None

    income = row["income"]
    expenses = row["expenses"]

    # Skip if no activity at all
    if income == 0 and expenses == 0:
        return None

    return {
        "income": income,
        "expenses": expenses,
        "profit": income - expenses,
    }


async def _send_weekly_email(env, farmer: dict, summary: dict):
    """Send a nicely formatted weekly email."""
    from services.email_service import EmailService
    svc = EmailService(env)

    first_name = (farmer["full_name"] or "farmer").split()[0]
    subject, html = svc.template_weekly_summary(
        first_name,
        summary["income"],
        summary["expenses"],
        summary["profit"],
    )

    await svc.send(farmer["email"], subject, html)