"""
Marcbantu Africa — SMS Service.
Africa's Talking integration with templates, bulk, delivery tracking.
"""
import json
from utils import now_iso, log_event, generate_reference


AT_PROD_URL = "https://api.africastalking.com"
AT_SANDBOX_URL = "https://api.sandbox.africastalking.com"


class SMSService:
    def __init__(self, env):
        self.env = env
        self.api_key = getattr(env, "AT_API_KEY", "") or ""
        self.username = getattr(env, "AT_USERNAME", "sandbox") or "sandbox"
        self.sender_id = getattr(env, "AT_SENDER_ID", "MARCBANTU") or "MARCBANTU"

    @property
    def base_url(self) -> str:
        return AT_SANDBOX_URL if self.username == "sandbox" else AT_PROD_URL

    async def send(self, to: str, message: str) -> dict:
        """Send a single SMS. Returns {'success': bool, ...}."""
        if not self.api_key:
            return {"success": False, "error": "Africa's Talking not configured"}

        if not to or not message:
            return {"success": False, "error": "Missing 'to' or 'message'"}

        body = (
            f"username={self.username}"
            f"&to={to}"
            f"&message={message}"
            f"&from={self.sender_id}"
        )

        try:
            response = await fetch(
                f"{self.base_url}/version1/messaging",
                method="POST",
                headers={
                    "apiKey": self.api_key,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                body=body,
            )
            data = await response.json()
            if response.status not in (200, 201):
                return {"success": False, "error": f"AT {response.status}", "raw": data}

            # Extract recipient status
            recipients = (
                data.get("SMSMessageData", {}).get("Recipients", [])
            )
            status = recipients[0].get("status") if recipients else "Unknown"
            message_id = recipients[0].get("messageId") if recipients else None

            return {
                "success": True,
                "message_id": message_id,
                "status": status,
                "provider_response": data,
            }
        except Exception as e:
            log_event("sms_send_failed", {"to": to, "error": str(e)})
            return {"success": False, "error": str(e)}

    async def send_bulk(self, recipients: list, message: str) -> dict:
        """Send to multiple recipients via AT's bulk API (comma-separated)."""
        if not self.api_key:
            return {"success": False, "error": "Africa's Talking not configured"}

        if not recipients:
            return {"success": False, "error": "No recipients"}

        # AT accepts comma-separated list up to ~1000
        to_list = ",".join(recipients[:1000])

        body = (
            f"username={self.username}"
            f"&to={to_list}"
            f"&message={message}"
            f"&from={self.sender_id}"
        )

        try:
            response = await fetch(
                f"{self.base_url}/version1/messaging",
                method="POST",
                headers={
                    "apiKey": self.api_key,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                body=body,
            )
            data = await response.json()
            recipients_data = (
                data.get("SMSMessageData", {}).get("Recipients", [])
            )
            return {
                "success": response.status in (200, 201),
                "sent_count": len(recipients_data),
                "provider_response": data,
            }
        except Exception as e:
            log_event("sms_bulk_failed", {"error": str(e), "count": len(recipients)})
            return {"success": False, "error": str(e)}

    async def send_from_template(self, to: str, template_code: str,
                                 variables: dict) -> dict:
        """Look up a template, fill variables, and send."""
        from db import DB
        db = DB(self.env)

        template = await db.query_one(
            "SELECT body FROM sms_templates WHERE code = ? AND active = 1",
            [template_code]
        )
        if not template:
            return {"success": False, "error": f"Template '{template_code}' not found"}

        message = template["body"]
        for k, v in (variables or {}).items():
            message = message.replace(f"{{{k}}}", str(v))

        return await self.send(to, message)

    async def queue(self, to: str, message: str, farmer_id: int = None) -> bool:
        """Queue an SMS via Cloudflare Queues."""
        try:
            await self.env.JOBS.send({
                "type": "send_sms",
                "payload": {
                    "to": to,
                    "message": message,
                    "farmer_id": farmer_id,
                },
            })
            return True
        except Exception as e:
            log_event("sms_queue_failed", {"error": str(e)})
            return False

    async def log(self, farmer_id, direction: str, phone: str,
                  message: str, status: str, error: str = None,
                  reference: str = None):
        """Persist to communication_log."""
        from db import DB
        db = DB(self.env)
        try:
            await db.insert("communication_log", {
                "farmer_id": farmer_id,
                "channel": "sms",
                "direction": direction,
                "phone": phone,
                "message": (message or "")[:1000],
                "status": status,
                "reference": reference or generate_reference("SMS"),
                "error_message": error,
            })
        except Exception:
            pass