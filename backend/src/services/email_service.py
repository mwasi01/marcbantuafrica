"""
Marcbantu Africa — Email Service.
Uses MailChannels (free for Cloudflare Workers) or Resend.
"""
import json
from utils import now_iso, log_event


class EmailService:
    def __init__(self, env):
        self.env = env
        self.from_email = getattr(env, "EMAIL_FROM", "noreply@marcbantu.africa") or "noreply@marcbantu.africa"
        self.from_name = getattr(env, "APP_NAME", "Marcbantu Africa") or "Marcbantu Africa"
        self.resend_key = getattr(env, "RESEND_API_KEY", "") or ""

    async def send(self, to: str, subject: str, html: str, text: str = None) -> dict:
        """Send an email via Resend or MailChannels."""
        if self.resend_key:
            return await self._send_resend(to, subject, html, text)
        return await self._send_mailchannels(to, subject, html, text)

    async def _send_resend(self, to: str, subject: str, html: str, text: str = None) -> dict:
        try:
            response = await fetch("https://api.resend.com/emails", method="POST", headers={
                "Authorization": f"Bearer {self.resend_key}",
                "Content-Type": "application/json",
            }, body=json.dumps({
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to],
                "subject": subject,
                "html": html,
                "text": text or "",
            }))
            data = await response.json()
            return {"success": response.status < 300, "raw": data}
        except Exception as e:
            log_event("email_resend_failed", {"error": str(e)})
            return {"success": False, "error": str(e)}

    async def _send_mailchannels(self, to: str, subject: str, html: str, text: str = None) -> dict:
        try:
            response = await fetch("https://api.mailchannels.net/tx/v1/send", method="POST", headers={
                "Content-Type": "application/json",
            }, body=json.dumps({
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": self.from_email, "name": self.from_name},
                "subject": subject,
                "content": [
                    {"type": "text/plain", "value": text or html},
                    {"type": "text/html", "value": html},
                ],
            }))
            return {"success": response.status < 300}
        except Exception as e:
            log_event("email_mailchannels_failed", {"error": str(e)})
            return {"success": False, "error": str(e)}

    # ---------------- TEMPLATES ----------------
    def template_welcome(self, name: str) -> tuple:
        subject = "Welcome to Marcbantu Africa"
        html = f"""
        <div style="font-family:sans-serif;max-width:600px;margin:auto;">
          <h2 style="color:#1a3c2e;">Welcome, {name}!</h2>
          <p>Your Marcbantu Africa account is ready. Start by adding your first farm.</p>
          <p><a href="https://marcbantu.africa/dashboard.html" style="background:#e6b422;color:#1a3c2e;padding:10px 20px;border-radius:20px;text-decoration:none;font-weight:bold;">Open your dashboard</a></p>
          <p style="color:#666;font-size:12px;margin-top:30px;">Marcbantu Africa — Smart farming starts with smart management.</p>
        </div>
        """
        return subject, html

    def template_weekly_summary(self, name: str, income: float,
                                expenses: float, profit: float) -> tuple:
        subject = f"Your weekly farm summary"
        html = f"""
        <div style="font-family:sans-serif;max-width:600px;margin:auto;">
          <h2 style="color:#1a3c2e;">Hi {name},</h2>
          <p>Here's your farm performance this week:</p>
          <table style="width:100%;border-collapse:collapse;">
            <tr><td style="padding:8px;border-bottom:1px solid #eee;">Income</td><td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">KES {income:,.0f}</td></tr>
            <tr><td style="padding:8px;border-bottom:1px solid #eee;">Expenses</td><td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">KES {expenses:,.0f}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Profit</td><td style="padding:8px;text-align:right;font-weight:bold;color:{'#2e7d32' if profit >= 0 else '#c0392b'};">KES {profit:,.0f}</td></tr>
          </table>
          <p style="margin-top:20px;"><a href="https://marcbantu.africa/finance.html" style="color:#e6b422;">View full report →</a></p>
        </div>
        """
        return subject, html

    def template_password_reset(self, otp: str) -> tuple:
        subject = "Your Marcbantu password reset code"
        html = f"""
        <div style="font-family:sans-serif;max-width:600px;margin:auto;">
          <h2 style="color:#1a3c2e;">Password reset</h2>
          <p>Your reset code is:</p>
          <p style="font-size:32px;font-weight:bold;letter-spacing:4px;color:#e6b422;">{otp}</p>
          <p>Valid for 10 minutes. If you didn't request this, ignore this email.</p>
        </div>
        """
        return subject, html