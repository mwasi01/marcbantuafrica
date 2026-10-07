"""
Marcbantu Africa — Main API Router.
Entry point for Cloudflare Workers (Python).
"""

from js import fetch
import re
from utils import json_response, error_response, log_event, log_error, now_iso
from constants import HTTP, ErrorCode
from middleware import handle_options, wrap

# Import route handlers
from routes import (
    auth,
    farmers,
    farms,
    plots,
    enterprises,
    records,
    finance,
    planning,
    decisions,
    operations,
    market,
    weather,
    pest,
    learning,
    notifications,
    communications,
    uploads,
    reports,
    partners,
    webhooks,
    feed,
    messages,
)


# ============================================================
# ROUTE TABLE
# ============================================================
# Format: (METHOD, REGEX_PATTERN, HANDLER)
ROUTES = [
    # ---------------- AUTH ----------------
    ("POST", r"^/api/auth/register$", auth.register),
    ("POST", r"^/api/auth/login$", auth.login),
    ("POST", r"^/api/auth/logout$", auth.logout),
    ("GET", r"^/api/auth/me$", auth.me),
    ("POST", r"^/api/auth/refresh$", auth.refresh),
    ("POST", r"^/api/auth/change-password$", auth.change_password),
    ("POST", r"^/api/auth/forgot-password$", auth.forgot_password),
    # ---------------- FARMERS ----------------
    ("GET", r"^/api/farmers/me$", farmers.get_profile),
    ("PUT", r"^/api/farmers/me$", farmers.update_profile),
    ("GET", r"^/api/farmers/stats$", farmers.get_stats),
    ("POST", r"^/api/farmers/verify$", farmers.verify_account),
    ("GET", r"^/api/farmers/dashboard$", farmers.dashboard),
    ("GET", r"^/api/farmers/subscription$", farmers.subscription_info),
    ("POST", r"^/api/farmers/upgrade$", farmers.upgrade_subscription),
    ("GET", r"^/api/farmers/preferences$", farmers.get_preferences),
    ("PUT", r"^/api/farmers/preferences$", farmers.update_preferences),
    ("GET", r"^/api/farmers/activity$", farmers.activity_log),
    # ---------------- FARMS ----------------
    ("GET", r"^/api/farms$", farms.list_farms),
    ("POST", r"^/api/farms$", farms.create_farm),
    ("GET", r"^/api/farms/(\d+)$", farms.get_farm),
    ("PUT", r"^/api/farms/(\d+)$", farms.update_farm),
    ("DELETE", r"^/api/farms/(\d+)$", farms.delete_farm),
    ("GET", r"^/api/farms/(\d+)/summary$", farms.get_summary),
    # ---------------- PLOTS ----------------
    ("GET", r"^/api/farms/(\d+)/plots$", plots.list_plots),
    ("POST", r"^/api/farms/(\d+)/plots$", plots.create_plot),
    ("GET", r"^/api/plots/(\d+)$", plots.get_plot),
    ("PUT", r"^/api/plots/(\d+)$", plots.update_plot),
    ("DELETE", r"^/api/plots/(\d+)$", plots.delete_plot),
    # ---------------- ENTERPRISES ----------------
    ("GET", r"^/api/farms/(\d+)/enterprises$", enterprises.list_enterprises),
    ("POST", r"^/api/farms/(\d+)/enterprises$", enterprises.create_enterprise),
    ("GET", r"^/api/enterprises/(\d+)$", enterprises.get_enterprise),
    ("PUT", r"^/api/enterprises/(\d+)$", enterprises.update_enterprise),
    ("DELETE", r"^/api/enterprises/(\d+)$", enterprises.delete_enterprise),
    ("GET", r"^/api/enterprises/(\d+)/performance$", enterprises.get_performance),
    # ---------------- RECORDS ----------------
    ("GET", r"^/api/records$", records.list_records),
    ("POST", r"^/api/records$", records.create_record),
    ("GET", r"^/api/records/(\d+)$", records.get_record),
    ("PUT", r"^/api/records/(\d+)$", records.update_record),
    ("DELETE", r"^/api/records/(\d+)$", records.delete_record),
    ("GET", r"^/api/records/summary$", records.get_summary),
    ("POST", r"^/api/records/sync$", records.sync_offline),
    # ---------------- FINANCE ----------------
    ("GET", r"^/api/finance/transactions$", finance.list_transactions),
    ("POST", r"^/api/finance/transactions$", finance.create_transaction),
    ("PUT", r"^/api/finance/transactions/(\d+)$", finance.update_transaction),
    ("DELETE", r"^/api/finance/transactions/(\d+)$", finance.delete_transaction),
    ("GET", r"^/api/finance/profit-loss$", finance.profit_loss),
    ("GET", r"^/api/finance/dashboard$", finance.dashboard_summary),
    ("GET", r"^/api/finance/cash-flow$", finance.cash_flow),
    ("GET", r"^/api/finance/expense-breakdown$", finance.expense_breakdown),
    ("GET", r"^/api/finance/enterprise-performance$", finance.enterprise_performance),
    # ---------------- PLANNING ----------------
    ("GET", r"^/api/planning/budgets$", planning.list_budgets),
    ("POST", r"^/api/planning/budgets$", planning.create_budget),
    ("GET", r"^/api/planning/budgets/(\d+)$", planning.get_budget),
    ("PUT", r"^/api/planning/budgets/(\d+)$", planning.update_budget),
    ("DELETE", r"^/api/planning/budgets/(\d+)$", planning.delete_budget),
    ("POST", r"^/api/planning/budgets/(\d+)/items$", planning.add_budget_item),
    ("PUT", r"^/api/planning/budgets/(\d+)/items/(\d+)$", planning.update_budget_item),
    (
        "DELETE",
        r"^/api/planning/budgets/(\d+)/items/(\d+)$",
        planning.delete_budget_item,
    ),
    ("GET", r"^/api/planning/cash-flow-forecast$", planning.cash_flow_forecast),
    ("GET", r"^/api/planning/seasonal-plan$", planning.seasonal_plan),
    # ---------------- DECISIONS ----------------
    ("POST", r"^/api/decisions/breakeven$", decisions.breakeven),
    ("POST", r"^/api/decisions/gross-margin$", decisions.gross_margin),
    ("POST", r"^/api/decisions/marginal$", decisions.marginal_analysis),
    ("POST", r"^/api/decisions/loan$", decisions.loan_affordability),
    ("POST", r"^/api/decisions/payback$", decisions.payback_period),
    ("POST", r"^/api/decisions/what-if$", decisions.what_if),
    ("POST", r"^/api/decisions/risk$", decisions.risk_assessment),
    ("GET", r"^/api/decisions/compare$", decisions.enterprise_comparison),
    ("GET", r"^/api/decisions/history$", decisions.decision_history),
    # ---------------- OPERATIONS ----------------
    ("GET", r"^/api/tasks$", operations.list_tasks),
    ("POST", r"^/api/tasks$", operations.create_task),
    ("GET", r"^/api/tasks/(\d+)$", operations.get_task),
    ("PUT", r"^/api/tasks/(\d+)$", operations.update_task),
    ("DELETE", r"^/api/tasks/(\d+)$", operations.delete_task),
    ("POST", r"^/api/tasks/(\d+)/complete$", operations.complete_task),
    ("GET", r"^/api/workers$", operations.list_workers),
    ("POST", r"^/api/workers$", operations.create_worker),
    ("PUT", r"^/api/workers/(\d+)$", operations.update_worker),
    ("DELETE", r"^/api/workers/(\d+)$", operations.delete_worker),
    ("POST", r"^/api/attendance$", operations.record_attendance),
    ("GET", r"^/api/attendance$", operations.list_attendance),
    ("GET", r"^/api/equipment$", operations.list_equipment),
    ("POST", r"^/api/equipment$", operations.create_equipment),
    ("PUT", r"^/api/equipment/(\d+)$", operations.update_equipment),
    ("POST", r"^/api/equipment/(\d+)/maintenance$", operations.log_maintenance),
    ("GET", r"^/api/operations/dashboard$", operations.operations_dashboard),
    # ---------------- MARKET ----------------
    # NOTE: more specific routes must come BEFORE the generic /prices route
    ("GET", r"^/api/market/prices/near-me$", market.prices_near_me),
    ("POST", r"^/api/market/prices/ingest$", market.trigger_ingest),
    ("GET", r"^/api/market/prices$", market.prices),
    ("GET", r"^/api/market/prices/history$", market.price_history),
    ("POST", r"^/api/market/prices$", market.add_price),
    ("GET", r"^/api/market/sales$", market.list_sales),
    ("POST", r"^/api/market/sales$", market.create_sale),
    ("PUT", r"^/api/market/sales/(\d+)$", market.update_sale),
    ("DELETE", r"^/api/market/sales/(\d+)$", market.delete_sale),
    ("GET", r"^/api/market/sales/summary$", market.sales_summary),
    ("GET", r"^/api/market/buyers$", market.list_buyers),
    ("POST", r"^/api/market/buyers$", market.create_buyer),
    ("PUT", r"^/api/market/buyers/(\d+)$", market.update_buyer),
    ("GET", r"^/api/market/contracts$", market.list_contracts),
    ("POST", r"^/api/market/contracts$", market.create_contract),
    ("GET", r"^/api/market/alerts$", market.list_alerts),
    ("POST", r"^/api/market/alerts$", market.create_alert),
    ("DELETE", r"^/api/market/alerts/(\d+)$", market.delete_alert),
    # ---------------- WEATHER ----------------
    ("GET", r"^/api/weather$", weather.get_weather),
    ("GET", r"^/api/weather/rainfall$", weather.rainfall_tracking),
    ("GET", r"^/api/weather/alerts$", weather.alerts),
    ("GET", r"^/api/weather/historical$", weather.historical),
    # ---------------- PEST ----------------
    ("GET", r"^/api/pest/scouting$", pest.list_scouting),
    ("POST", r"^/api/pest/scouting$", pest.create_scouting),
    ("PUT", r"^/api/pest/scouting/(\d+)$", pest.update_scouting),
    ("DELETE", r"^/api/pest/scouting/(\d+)$", pest.delete_scouting),
    ("GET", r"^/api/pest/treatments$", pest.list_treatments),
    ("POST", r"^/api/pest/treatments$", pest.create_treatment),
    ("POST", r"^/api/pest/diagnose$", pest.diagnose),
    ("GET", r"^/api/pest/library$", pest.library),
    ("GET", r"^/api/pest/library/(\d+)$", pest.library_item),
    ("GET", r"^/api/pest/alerts$", pest.alerts),
    ("GET", r"^/api/pest/inventory$", pest.inventory),
    ("POST", r"^/api/pest/inventory$", pest.add_inventory),
    ("GET", r"^/api/pest/ipm$", pest.list_ipm),
    ("POST", r"^/api/pest/ipm$", pest.add_ipm),
    ("GET", r"^/api/pest/dashboard$", pest.pest_dashboard),
    # ---------------- LEARNING ----------------
    ("GET", r"^/api/learning/courses$", learning.list_courses),
    ("GET", r"^/api/learning/courses/(\d+)$", learning.get_course),
    ("GET", r"^/api/learning/courses/(\d+)/lessons$", learning.list_lessons),
    ("POST", r"^/api/learning/enroll$", learning.enroll),
    ("GET", r"^/api/learning/my-courses$", learning.my_courses),
    ("POST", r"^/api/learning/progress$", learning.update_progress),
    ("GET", r"^/api/learning/videos$", learning.list_videos),
    ("POST", r"^/api/learning/chat$", learning.chat),
    ("GET", r"^/api/learning/chat/history$", learning.chat_history),
    ("GET", r"^/api/learning/forum/topics$", learning.list_forum_topics),
    ("POST", r"^/api/learning/forum/topics$", learning.create_forum_topic),
    ("GET", r"^/api/learning/forum/topics/(\d+)$", learning.get_forum_topic),
    ("POST", r"^/api/learning/forum/topics/(\d+)/replies$", learning.create_reply),
    ("GET", r"^/api/learning/experts$", learning.list_experts),
    ("POST", r"^/api/learning/consultations$", learning.book_consultation),
    ("GET", r"^/api/learning/consultations$", learning.my_consultations),
    ("GET", r"^/api/learning/dashboard$", learning.learning_dashboard),
    # ---------------- DIRECT MESSAGES ----------------
    ("GET",    r"^/api/messages/conversations$",                    messages.list_conversations),
    ("POST",   r"^/api/messages/conversations$",                    messages.start_conversation),
    ("GET",    r"^/api/messages/conversations/(\d+)$",              messages.get_conversation),
    ("GET",    r"^/api/messages/conversations/(\d+)/messages$",     messages.list_messages),
    ("POST",   r"^/api/messages/conversations/(\d+)/messages$",     messages.send_message),
    ("POST",   r"^/api/messages/conversations/(\d+)/read$",         messages.mark_read),
    ("GET",    r"^/api/messages/unread-count$",                     messages.unread_total),
    ("DELETE", r"^/api/messages/(\d+)$",                            messages.delete_message),
    ("GET",    r"^/api/messages/search-farmers$",                   messages.search_farmers),
    # ---------------- FARMER FEED ----------------
    ("GET",    r"^/api/feed$",                                   feed.list_feed),
    ("POST",   r"^/api/feed/posts$",                             feed.create_post),
    ("GET",    r"^/api/feed/posts/(\d+)$",                       feed.get_post),
    ("DELETE", r"^/api/feed/posts/(\d+)$",                       feed.delete_post),
    ("POST",   r"^/api/feed/posts/(\d+)/like$",                  feed.like_post),
    ("DELETE", r"^/api/feed/posts/(\d+)/like$",                  feed.unlike_post),
    ("POST",   r"^/api/feed/posts/(\d+)/comments$",              feed.create_comment),
    ("DELETE", r"^/api/feed/comments/(\d+)$",                    feed.delete_comment),
    ("POST",   r"^/api/feed/follow/(\d+)$",                      feed.follow_farmer),
    ("DELETE", r"^/api/feed/follow/(\d+)$",                      feed.unfollow_farmer),
    ("GET",    r"^/api/feed/followers/(\d+)$",                   feed.list_followers),
    ("GET",    r"^/api/feed/following/(\d+)$",                   feed.list_following),
    ("GET",    r"^/api/feed/suggested$",                          feed.suggested_farmers),
    ("GET",    r"^/api/feed/farmer/(\d+)$",                      feed.farmer_profile),
    ("GET",    r"^/api/feed/farmer/(\d+)/posts$",                feed.farmer_posts),
    # ---------------- NOTIFICATIONS ----------------
    ("GET", r"^/api/notifications$", notifications.list_notifications),
    ("GET", r"^/api/notifications/unread-count$", notifications.unread_count),
    ("POST", r"^/api/notifications/(\d+)/read$", notifications.mark_read),
    ("POST", r"^/api/notifications/read-all$", notifications.mark_all_read),
    ("DELETE", r"^/api/notifications/(\d+)$", notifications.delete_notification),
    ("POST", r"^/api/notifications/register-device$", notifications.register_device),
    ("POST", r"^/api/notifications/push$", notifications.send_push),
    # ---------------- COMMUNICATIONS ----------------
    ("POST", r"^/api/comms/sms$", communications.send_sms),
    ("POST", r"^/api/comms/sms/bulk$", communications.send_bulk_sms),
    ("POST", r"^/api/comms/sms/webhook$", communications.sms_webhook),
    ("POST", r"^/api/comms/ussd$", communications.ussd_handler),
    ("POST", r"^/api/comms/whatsapp$", communications.send_whatsapp),
    ("POST", r"^/api/comms/whatsapp/webhook$", communications.whatsapp_webhook),
    ("POST", r"^/api/comms/voice$", communications.send_voice),
    ("GET", r"^/api/comms/log$", communications.log),
    # ---------------- UPLOADS ----------------
    ("POST", r"^/api/uploads$", uploads.upload_file),
    ("GET", r"^/api/uploads/(\d+)$", uploads.get_upload),
    ("DELETE", r"^/api/uploads/(\d+)$", uploads.delete_upload),
    ("GET", r"^/files/(.+)$", uploads.serve_file),
    # ---------------- REPORTS ----------------
    ("GET", r"^/api/reports/profit-loss$", reports.profit_loss_report),
    ("GET", r"^/api/reports/enterprise-performance$", reports.enterprise_report),
    ("GET", r"^/api/reports/cash-flow$", reports.cash_flow_report),
    ("GET", r"^/api/reports/credit-score$", reports.credit_score),
    # ---------------- PARTNERS ----------------
    ("GET", r"^/api/partners$", partners.list_partners),
    ("POST", r"^/api/partners/apply$", partners.apply),
    # ---------------- WEBHOOKS ----------------
    ("POST", r"^/api/webhooks/mpesa$", webhooks.mpesa_callback),
    ("POST", r"^/api/webhooks/africastalking$", webhooks.africastalking_callback),
]


# ============================================================
# ROUTE MATCHER
# ============================================================
def match_route(method: str, path: str):
    """Find matching route handler. Returns (handler, params) or (None, None)."""
    for route_method, pattern, handler in ROUTES:
        if route_method != method:
            continue
        match = re.match(pattern, path)
        if match:
            return handler, match.groups()
    return None, None


# ============================================================
# MAIN FETCH HANDLER
# ============================================================
async def on_fetch(request, env, ctx):
    """Main entry point for all API requests."""
    method = request.method

    # CORS preflight
    if method == "OPTIONS":
        return handle_options(request)

    # Extract path
    try:
        from urllib.parse import urlparse

        parsed = urlparse(str(request.url))
        path = parsed.path.rstrip("/") or "/"
    except Exception:
        path = "/"

    # Health check
    if path in ("/api/health", "/health", "/api"):
        return json_response(
            {
                "status": "ok",
                "service": "Marcbantu Africa API",
                "version": getattr(env, "API_VERSION", "1.0.0"),
                "timestamp": now_iso(),
                "environment": getattr(env, "ENVIRONMENT", "production"),
            }
        )

    # Root
    if path == "/":
        return json_response(
            {
                "name": "Marcbantu Africa API",
                "version": "1.0.0",
                "docs": "/api/docs",
                "health": "/api/health",
                "endpoints": [
                    "/api/auth/*",
                    "/api/farms/*",
                    "/api/records/*",
                    "/api/finance/*",
                    "/api/decisions/*",
                    "/api/market/*",
                    "/api/weather/*",
                    "/api/pest/*",
                    "/api/learning/*",
                    "/api/operations/*",
                    "/api/notifications/*",
                    "/api/comms/*",
                    "/api/uploads/*",
                    "/api/reports/*",
                ],
            }
        )

    # API docs (simple JSON listing)
    if path == "/api/docs":
        return json_response(
            {
                "routes": [
                    {"method": m, "path": p, "handler": h.__name__}
                    for m, p, h in ROUTES
                ]
            }
        )

    # Match route
    handler, params = match_route(method, path)
    if not handler:
        return error_response(
            f"Route not found: {method} {path}",
            status=HTTP.NOT_FOUND,
            code=ErrorCode.NOT_FOUND,
        )

    # Convert params to ints where possible
    converted = []
    for p in params or []:
        try:
            converted.append(int(p))
        except (ValueError, TypeError):
            converted.append(p)

    # Wrap handler with middleware
    wrapped = wrap(handler)

    try:
        if converted:
            return await wrapped(request, env, *converted)
        return await wrapped(request, env)
    except Exception as e:
        log_error(str(e), {"path": path, "method": method})
        return error_response(
            "Internal server error",
            status=HTTP.INTERNAL_ERROR,
            code=ErrorCode.INTERNAL_ERROR,
        )


# ============================================================
# SCHEDULED HANDLER (Cron)
# ============================================================
async def on_scheduled(event, env, ctx):
    """Handle cron triggers."""
    from scheduled import cron

    try:
        await cron.handle(event, env, ctx)
    except Exception as e:
        log_error(f"Cron error: {str(e)}", {"cron": getattr(event, "cron", "unknown")})


# ============================================================
# QUEUE HANDLER
# ============================================================
async def on_queue(batch, env, ctx):
    """Handle queued messages."""
    from jobs import process_batch

    try:
        await process_batch(batch, env)
    except Exception as e:
        log_error(f"Queue error: {str(e)}")


# ============================================================
# PYTHON WORKERS ENTRYPOINT
# ============================================================
# Cloudflare Workers Python uses a class-based entrypoint.
# The runtime auto-discovers a class named `Default` and calls:
#   - fetch()     for HTTP requests
#   - scheduled() for cron triggers
#   - queue()     for Queue messages
# ============================================================


class Default:
    async def fetch(self, request, env, ctx):
        return await on_fetch(request, env, ctx)

    async def scheduled(self, event, env, ctx):
        return await on_scheduled(event, env, ctx)

    async def queue(self, batch, env, ctx):
        return await on_queue(batch, env, ctx)
