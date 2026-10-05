"""
Marcbantu Africa — WhatsApp Service.
Meta WhatsApp Cloud API integration.
"""

from js import fetch
import json
from utils import now_iso, log_event, generate_reference


GRAPH_URL = "https://graph.facebook.com/v18.0"


class WhatsAppService:
    def __init__(self, env):
        self.env = env
        self.token = getattr(env, "WHATSAPP_TOKEN", "") or ""
        self.phone_id = getattr(env, "WHATSAPP_PHONE_ID", "") or ""

    @property
    def configured(self) -> bool:
        return bool(self.token and self.phone_id)

    async def send_text(self, to: str, message: str) -> dict:
        if not self.configured:
            return {"success": False, "error": "WhatsApp not configured"}

        payload = {
            "messaging_product": "whatsapp",
            "to": to.lstrip("+"),
            "type": "text",
            "text": {"body": message},
        }

        try:
            response = await fetch(
                f"{GRAPH_URL}/{self.phone_id}/messages",
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                body=json.dumps(payload),
            )
            data = await response.json()
            return {"success": response.status < 300, "raw": data}
        except Exception as e:
            log_event("whatsapp_send_failed", {"error": str(e)})
            return {"success": False, "error": str(e)}

    async def send_template(self, to: str, template_name: str,
                            language: str = "en", variables: list = None) -> dict:
        if not self.configured:
            return {"success": False, "error": "WhatsApp not configured"}

        components = []
        if variables:
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": str(v)} for v in variables],
            })

        payload = {
            "messaging_product": "whatsapp",
            "to": to.lstrip("+"),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": components,
            },
        }

        try:
            response = await fetch(
                f"{GRAPH_URL}/{self.phone_id}/messages",
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                body=json.dumps(payload),
            )
            data = await response.json()
            return {"success": response.status < 300, "raw": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_image(self, to: str, image_url: str, caption: str = "") -> dict:
        if not self.configured:
            return {"success": False, "error": "WhatsApp not configured"}

        payload = {
            "messaging_product": "whatsapp",
            "to": to.lstrip("+"),
            "type": "image",
            "image": {"link": image_url, "caption": caption},
        }

        try:
            response = await fetch(
                f"{GRAPH_URL}/{self.phone_id}/messages",
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                body=json.dumps(payload),
            )
            data = await response.json()
            return {"success": response.status < 300, "raw": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def log(self, farmer_id, direction: str, phone: str,
                  message: str, status: str, error: str = None):
        from db import DB
        db = DB(self.env)
        try:
            await db.insert("communication_log", {
                "farmer_id": farmer_id,
                "channel": "whatsapp",
                "direction": direction,
                "phone": phone,
                "message": (message or "")[:1000],
                "status": status,
                "error_message": error,
            })
        except Exception:
            pass