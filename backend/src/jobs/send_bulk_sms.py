"""
Job: send_bulk_sms
Payload: {recipients: [phone...], message?, template_code?, variables?}
"""
from services.sms_service import SMSService
from utils import log_event, log_error


CHUNK_SIZE = 100  # AT accepts ~1000 per request; keep smaller for reliability


async def run(payload: dict, env):
    """Send SMS to many recipients."""
    recipients = payload.get("recipients", [])
    message = payload.get("message")
    template_code = payload.get("template_code")
    variables = payload.get("variables", {})

    if not recipients:
        log_error("send_bulk_sms: no recipients")
        return

    svc = SMSService(env)

    # Resolve template if provided
    if template_code and not message:
        from db import DB
        db = DB(env)
        template = await db.query_one(
            "SELECT body FROM sms_templates WHERE code = ? AND active = 1",
            [template_code]
        )
        if not template:
            log_error("send_bulk_sms: template not found", {"code": template_code})
            return
        message = template["body"]
        for k, v in variables.items():
            message = message.replace(f"{{{k}}}", str(v))

    if not message:
        log_error("send_bulk_sms: no message")
        return

    sent = 0
    failed = 0

    # Chunk
    for i in range(0, len(recipients), CHUNK_SIZE):
        chunk = recipients[i:i + CHUNK_SIZE]
        result = await svc.send_bulk(chunk, message)

        if result.get("success"):
            sent += len(chunk)
        else:
            failed += len(chunk)
            log_error("bulk_chunk_failed", {
                "chunk_start": i,
                "chunk_size": len(chunk),
                "error": result.get("error"),
            })

        # Log per-recipient (bulk)
        for phone in chunk:
            await svc.log(
                farmer_id=None,
                direction="outbound",
                phone=phone,
                message=message,
                status="sent" if result.get("success") else "failed",
                error=result.get("error"),
            )

    log_event("bulk_sms_done", {
        "sent": sent,
        "failed": failed,
        "total": len(recipients),
    })