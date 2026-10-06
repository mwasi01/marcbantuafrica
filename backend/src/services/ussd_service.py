"""
Marcbantu Africa — USSD Service.
Menu engine for USSD flows.
"""
from utils import now_iso, log_event


class USSDService:
    def __init__(self, env):
        self.env = env

    async def load_menu(self, code: str) -> dict:
        """Load a menu definition from DB."""
        from db import DB
        db = DB(self.env)
        return await db.query_one(
            "SELECT * FROM ussd_menus WHERE code = ?", [code]
        )

    def format_response(self, menu: dict, extra: dict = None,
                        terminal: bool = False) -> str:
        """Format menu body with variables, prefix CON or END."""
        body = menu.get("body", "") if menu else ""
        if extra:
            for k, v in extra.items():
                body = body.replace(f"{{{k}}}", str(v))
        prefix = "END" if terminal or (menu and menu.get("is_terminal")) else "CON"
        return f"{prefix} {body}"

    async def track_session(self, session_id: str, phone: str,
                            farmer_id, current_menu: str = None):
        """Create or update a USSD session record."""
        from db import DB
        db = DB(self.env)
        try:
            existing = await db.query_one(
                "SELECT id FROM ussd_sessions WHERE session_id = ?",
                [session_id]
            )
            if existing:
                await db.update("ussd_sessions", {
                    "current_menu": current_menu,
                }, "id = ?", [existing["id"]])
            else:
                await db.insert("ussd_sessions", {
                    "session_id": session_id,
                    "phone": phone,
                    "farmer_id": farmer_id,
                    "current_menu": current_menu,
                    "started_at": now_iso(),
                })
        except Exception as e:
            log_event("ussd_session_failed", {"error": str(e)})

    async def end_session(self, session_id: str):
        from db import DB
        db = DB(self.env)
        try:
            await db.execute(
                "UPDATE ussd_sessions SET ended_at = ? WHERE session_id = ?",
                [now_iso(), session_id]
            )
        except Exception:
            pass

    async def find_farmer(self, phone: str):
        """Look up a farmer by phone."""
        from db import DB
        db = DB(self.env)
        return await db.query_one(
            "SELECT id, full_name FROM farmers WHERE phone = ? OR phone = ?",
            [phone, phone.lstrip("+")]
        )