"""
Marcbantu Africa — Cron dispatcher.
"""
from utils import log_event, log_error


# Cron expression -> list of job modules
CRON_JOBS = {
    "0 6 * * *":   ["daily_weather", "daily_prices"],
    "0 7 * * *":   ["sms_reminders"],
    "0 8 * * 1":   ["weekly_reports"],
    "0 0 1 * *":   ["cleanup"],
}


async def handle(event, env, ctx):
    """Handle a cron trigger."""
    cron = getattr(event, "cron", None)
    scheduled_time = getattr(event, "scheduledTime", None)

    log_event("cron_trigger", {"cron": cron, "scheduled": scheduled_time})

    if not cron:
        log_error("Cron event has no schedule")
        return

    jobs = CRON_JOBS.get(cron, [])
    if not jobs:
        log_error(f"No jobs mapped to cron: {cron}")
        return

    for job_name in jobs:
        try:
            await run_job(job_name, env)
        except Exception as e:
            log_error(f"Cron job '{job_name}' failed: {str(e)}")


async def run_job(name: str, env):
    """Run a scheduled job by name."""
    log_event("cron_job_start", {"job": name})

    import importlib
    module = importlib.import_module(f"jobs.{name}")
    if hasattr(module, "run"):
        await module.run({}, env)
    else:
        log_error(f"Job {name} has no run() function")

    log_event("cron_job_end", {"job": name})