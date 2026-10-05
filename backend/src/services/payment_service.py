"""
Marcbantu Africa — Payment Service.
M-Pesa STK Push, C2B, and payment status.
"""

from js import fetch
import base64
import json
from datetime import datetime
from utils import now_iso, log_event


MPESA_PROD = "https://api.safaricom.co.ke"
MPESA_SANDBOX = "https://sandbox.safaricom.co.ke"


class PaymentService:
    def __init__(self, env):
        self.env = env
        self.consumer_key = getattr(env, "MPESA_CONSUMER_KEY", "") or ""
        self.consumer_secret = getattr(env, "MPESA_CONSUMER_SECRET", "") or ""
        self.shortcode = getattr(env, "MPESA_SHORTCODE", "") or ""
        self.passkey = getattr(env, "MPESA_PASSKEY", "") or ""
        self.callback_url = getattr(env, "MPESA_CALLBACK_URL", "") or ""
        self.environment = getattr(env, "MPESA_ENVIRONMENT", "sandbox") or "sandbox"

    @property
    def base_url(self) -> str:
        return MPESA_PROD if self.environment == "production" else MPESA_SANDBOX

    @property
    def configured(self) -> bool:
        return bool(self.consumer_key and self.consumer_secret and self.shortcode)

    async def get_access_token(self) -> str | None:
        """OAuth token from Safaricom."""
        if not self.configured:
            return None

        credentials = f"{self.consumer_key}:{self.consumer_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        try:
            response = await fetch(
                f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials",
                method="GET",
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Accept": "application/json",
                },
            )
            data = await response.json()
            return data.get("access_token")
        except Exception as e:
            log_event("mpesa_token_failed", {"error": str(e)})
            return None

    def _generate_password(self, timestamp: str) -> str:
        raw = f"{self.shortcode}{self.passkey}{timestamp}"
        return base64.b64encode(raw.encode()).decode()

    async def stk_push(self, phone: str, amount: float,
                       account_reference: str, description: str,
                       callback_url: str = None) -> dict:
        """Initiate an STK push (Lipa na M-Pesa)."""
        if not self.configured:
            return {"success": False, "error": "M-Pesa not configured"}

        token = await self.get_access_token()
        if not token:
            return {"success": False, "error": "Failed to get access token"}

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = self._generate_password(timestamp)
        callback = callback_url or self.callback_url

        # Normalize phone to 2547XXXXXXXX
        phone_norm = phone.replace("+", "").strip()
        if phone_norm.startswith("0"):
            phone_norm = "254" + phone_norm[1:]

        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone_norm,
            "PartyB": self.shortcode,
            "PhoneNumber": phone_norm,
            "CallBackURL": callback,
            "AccountReference": account_reference[:12],
            "TransactionDesc": description[:50],
        }

        try:
            response = await fetch(
                f"{self.base_url}/mpesa/stkpush/v1/processrequest",
                method="POST",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                body=json.dumps(payload),
            )
            data = await response.json()
            return {
                "success": response.status < 300,
                "checkout_request_id": data.get("CheckoutRequestID"),
                "merchant_request_id": data.get("MerchantRequestID"),
                "response_code": data.get("ResponseCode"),
                "response_description": data.get("ResponseDescription"),
                "raw": data,
            }
        except Exception as e:
            log_event("mpesa_stk_failed", {"error": str(e)})
            return {"success": False, "error": str(e)}

    async def stk_status(self, checkout_request_id: str) -> dict:
        """Query STK push status."""
        if not self.configured:
            return {"success": False, "error": "M-Pesa not configured"}

        token = await self.get_access_token()
        if not token:
            return {"success": False, "error": "Auth failed"}

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = self._generate_password(timestamp)

        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        }

        try:
            response = await fetch(
                f"{self.base_url}/mpesa/stkpushquery/v1/query",
                method="POST",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                body=json.dumps(payload),
            )
            data = await response.json()
            return {"success": response.status < 300, "raw": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def record_payment(self, farmer_id: int, farm_id: int, amount: float,
                             reference: str, method: str = "mpesa",
                             description: str = None) -> int | None:
        """Record a successful payment as an income transaction."""
        from db import DB
        db = DB(self.env)
        try:
            tx_id = await db.insert("transactions", {
                "farm_id": farm_id,
                "type": "income",
                "category": "other_income",
                "description": description or f"Payment received — {reference}",
                "amount": amount,
                "payment_method": method,
                "reference": reference,
                "transaction_date": now_iso()[:10],
            })
            return tx_id
        except Exception as e:
            log_event("payment_record_failed", {"error": str(e)})
            return None