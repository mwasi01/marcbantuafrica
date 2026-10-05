"""
Marcbantu Africa — Voice Service.
Africa's Talking Voice API for outbound calls and IVR.
"""

from js import fetch
import json
from utils import now_iso, log_event, js_headers


AT_VOICE_PROD = "https://voice.africastalking.com"
AT_VOICE_SANDBOX = "https://voice.sandbox.africastalking.com"


class VoiceService:
    def __init__(self, env):
        self.env = env
        self.api_key = getattr(env, "AT_API_KEY", "") or ""
        self.username = getattr(env, "AT_USERNAME", "sandbox") or "sandbox"

    @property
    def base_url(self) -> str:
        return AT_VOICE_SANDBOX if self.username == "sandbox" else AT_VOICE_PROD

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def call(self, to: str, from_number: str = "") -> dict:
        """Initiate an outbound call."""
        if not self.configured:
            return {"success": False, "error": "Voice not configured"}

        try:
            response = await fetch(
                f"{self.base_url}/call",
                method="POST",
                headers=js_headers({
                    "apiKey": self.api_key,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                }),
                body=f"username={self.username}&to={to}&from={from_number}",
            )
            data = await response.json()

            if hasattr(data, 'to_py'):

                data = data.to_py()
            return {"success": response.status < 300, "raw": data}
        except Exception as e:
            log_event("voice_call_failed", {"error": str(e), "to": to})
            return {"success": False, "error": str(e)}

    async def call_with_audio(self, to: str, audio_url: str) -> dict:
        """Place a call that plays an audio file."""
        # Similar to call() but with a media URL. AT uses 'callFrom' + content in XML.
        # Placeholder for the actual AT Voice XML flow.
        return await self.call(to)

    async def log(self, farmer_id, direction: str, phone: str,
                  message: str, status: str, error: str = None):
        from db import DB
        db = DB(self.env)
        try:
            await db.insert("communication_log", {
                "farmer_id": farmer_id,
                "channel": "voice",
                "direction": direction,
                "phone": phone,
                "message": (message or "")[:1000],
                "status": status,
                "error_message": error,
            })
        except Exception:
            pass