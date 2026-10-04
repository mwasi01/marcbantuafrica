"""
Marcbantu Africa — Jobs package.
Dispatches Cloudflare Queue messages to the correct job handler.

Queue message format:
{
    "type": "send_sms" | "send_bulk_sms" | "send_whatsapp" | "send_push"
           | "daily_prices" | "daily_weather" | "sms_reminders"
           | "weekly_reports" | "cleanup" | "sync_records",
    "payload": {...},
    "attempt": 1,
    "created_at": "2025-01-01T00:00:00Z"
}
"""
import importlib
from utils import log_event, log_error


# ============================================================
# JOB REGISTRY
# ============================================================
JOB_REGISTRY = {
    # Communication jobs
    "send_sms":        "jobs.send_sms",
    "send_bulk_sms":   "jobs.send_bulk_sms",
    "send_whatsapp":   "jobs.send_whatsapp",
    "send_push":       "jobs.send_push",

    # Scheduled jobs
    "daily_prices":    "jobs.daily_prices",
    "daily_weather":   "jobs.daily_weather",
    "sms_reminders":   "jobs.sms_reminders",
    "weekly_reports":  "jobs.weekly_reports",
    "cleanup":         "jobs.cleanup",

    # Data jobs
    "sync_records":    "jobs.sync_records",
}


# ============================================================
# BATCH PROCESSING
# ============================================================
async def process_batch(batch, env):
    """Process a Cloudflare Queues batch."""
    processed = 0
    failed = 0
    total = len(batch.messages)

    for message in batch.messages:
        try:
            body = message.body if hasattr(message, "body") else message
            await process_message(body, env)
            if hasattr(message, "ack"):
                message.ack()
            processed += 1
        except Exception as e:
            failed += 1
            log_error(f"Job failed: {str(e)}", {
                "message": str(message)[:300],
            })
            if hasattr(message, "retry"):
                message.retry()

    log_event("queue_batch_processed", {
        "processed": processed,
        "failed": failed,
        "total": total,
    })


# ============================================================
# SINGLE MESSAGE DISPATCHER
# ============================================================
async def process_message(data, env):
    """Route a single message to its handler."""
    if not isinstance(data, dict):
        raise ValueError("Message body must be a dict")

    job_type = data.get("type")
    payload = data.get("payload", {}) or {}

    if not job_type:
        raise ValueError("Job message missing 'type'")

    module_name = JOB_REGISTRY.get(job_type)
    if not module_name:
        raise ValueError(f"Unknown job type: {job_type}")

    log_event("job_start", {"type": job_type})

    # Dynamic import — works with Cloudflare Workers' Python runtime
    module = importlib.import_module(module_name)

    if not hasattr(module, "run"):
        raise AttributeError(f"Job module {module_name} has no 'run' function")

    await module.run(payload, env)

    log_event("job_done", {"type": job_type})