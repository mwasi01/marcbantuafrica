"""
Job: send_sms
Payload: {to, message, farmer_id?, template_code?, variables?}
"""
from services.sms_service import SMSService
from utils import log_event, log_error


async def run(payload: dict, env):
    """Send a single SMS."""
    to = payload.get("to")
    message = payload.get("message")
    farmer_id = payload.get("farmer_id")
    template_code = payload.get("template_code")
    variables = payload.get("variables", {})

    if not to:
        log_error("send_sms: missing 'to'", {"payload": payload})
        return

    svc = SMSService(env)

    # If template, resolve it first
    if template_code and not message:
        result = await svc.send_from_template(to, template_code, variables)
    else:
        if not message:
            log_error("send_sms: no message or template", {"payload": payload})
            return
        result = await svc.send(to, message)

    # Log
    status = "sent" if result.get("success") else "failed"
    await svc.log(
        farmer_id=farmer_id,
        direction="outbound",
        phone=to,
        message=message or f"(template: {template_code})",
        status=status,
        error=result.get("error"),
    )

    log_event("sms_job_done", {
        "to": to,
        "success": result.get("success"),
        "status": result.get("status"),
    })