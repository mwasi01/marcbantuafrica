"""
Marcbantu Africa — Weekly scheduled jobs.
Monday 8am: weekly farm summaries.
"""
from utils import log_event, log_error
from db import DB


async def weekly_reports(env):
    """Generate and send weekly summaries to Pro+ farmers."""
    db = DB(env)
    log_event('weekly_reports_start')

    farmers = await db.query("""
        SELECT id, phone, full_name, email
        FROM farmers
        WHERE subscription_tier IN ('pro', 'business')
        AND verified = 1
    """)

    for farmer in farmers:
        try:
            # Calculate weekly summary
            summary = await get_weekly_summary(db, farmer['id'])
            if summary:
                await env.JOBS.send({
                    'type': 'send_sms',
                    'payload': {
                        'to': farmer['phone'],
                        'farmer_id': farmer['id'],
                        'template_code': 'WEEKLY_SUMMARY',
                        'variables': {
                            'name': farmer['full_name'].split()[0],
                            'income': summary['income'],
                            'expenses': summary['expenses'],
                            'profit': summary['profit'],
                        },
                    }
                })
        except Exception as e:
            log_error(f"Weekly report failed for farmer {farmer['id']}: {str(e)}")

    log_event('weekly_reports_done')


async def get_weekly_summary(db, farmer_id: int) -> dict | None:
    """Get last 7 days summary for a farmer."""
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

    income = row['income']
    expenses = row['expenses']
    return {
        'income': f"{income:,.0f}",
        'expenses': f"{expenses:,.0f}",
        'profit': f"{income - expenses:,.0f}",
    }