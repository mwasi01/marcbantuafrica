"""
Job: send_whatsapp
Payload: {to, message?, template_name?, language?, variables?, image_url?}
"""
from services.whatsapp_service import WhatsAppService
from utils import log_event, log_error


async def run(payload: dict, env):
    """Send a WhatsApp message."""
    to = payload.get("to")
    if not to:
        log_error("send_whatsapp: missing 'to'")
        return

    svc = WhatsAppService(env)
    if not svc.configured:
        log_error("send_whatsapp: not configured")
        return

    message = payload.get("message")
    template_name = payload.get("template_name")
    variables = payload.get("variables", [])
    image_url = payload.get("image_url")
    language = payload.get("language", "en")
    farmer_id = payload.get("farmer_id")

    result = {"success": False}

    if image_url:
        result = await svc.send_image(to, image_url, caption=message or "")
    elif template_name:
        result = await svc.send_template(to, template_name, language, variables)
    elif message:
        result = await svc.send_text(to, message)
    else:
        log_error("send_whatsapp: no message, template, or image")
        return

    # Log
    await svc.log(
        farmer_id=farmer_id,
        direction="outbound",
        phone=to,
        message=message or f"(template: {template_name})" if template_name else "(image)",
        status="sent" if result.get("success") else "failed",
        error=result.get("error"),
    )

    log_event("whatsapp_job_done", {"to": to, "success": result.get("success")})