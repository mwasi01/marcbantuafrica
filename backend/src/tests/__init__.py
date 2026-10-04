"""
Marcbantu Africa — Test package.
Shared fixtures, mocks, and helpers for the test suite.
"""
import json
import time
import hmac
import hashlib
import base64


# ============================================================
# SHARED CONSTANTS
# ============================================================
TEST_JWT_SECRET = "test-secret-do-not-use-in-prod"
TEST_PHONE = "+254712345678"
TEST_PASSWORD = "test123456"
TEST_FULL_NAME = "Test Farmer"


# ============================================================
# MOCK CLASSES
# ============================================================
class MockRequest:
    """Minimal Request mock."""

    def __init__(self, method="GET", url="http://localhost/api/test",
                 headers=None, body=None, form_data=None):
        self.method = method
        self.url = MockURL(url)
        self.headers = headers or {}
        self._body = body or {}
        self._form = form_data or {}

    async def json(self):
        return self._body

    async def formData(self):
        return self._form


class MockURL:
    def __init__(self, url: str):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        self.scheme = parsed.scheme
        self.netloc = parsed.netloc
        self.path = parsed.path
        self.query = parsed.query
        self.search_params = MockSearchParams(parse_qs(parsed.query))


class MockSearchParams:
    def __init__(self, params: dict):
        # parse_qs returns lists; flatten
        self._params = {k: (v[0] if isinstance(v, list) and v else v)
                        for k, v in (params or {}).items()}

    def get(self, key, default=None):
        return self._params.get(key, default)


class MockEnv:
    """Env mock — bindings and secrets."""

    def __init__(self, **overrides):
        self.ENVIRONMENT = overrides.get("ENVIRONMENT", "test")
        self.APP_NAME = overrides.get("APP_NAME", "Marcbantu Africa")
        self.API_VERSION = overrides.get("API_VERSION", "1.0.0")
        self.FRONTEND_URL = overrides.get("FRONTEND_URL", "http://localhost:8788")
        self.JWT_SECRET = overrides.get("JWT_SECRET", TEST_JWT_SECRET)
        self.AT_API_KEY = overrides.get("AT_API_KEY", "")
        self.AT_USERNAME = overrides.get("AT_USERNAME", "sandbox")
        self.AT_SENDER_ID = overrides.get("AT_SENDER_ID", "MARCBANTU")
        self.WHATSAPP_TOKEN = overrides.get("WHATSAPP_TOKEN", "")
        self.WHATSAPP_PHONE_ID = overrides.get("WHATSAPP_PHONE_ID", "")
        self.CACHE = MockKV()
        self.SESSIONS = MockKV()
        self.DB = MockDB()
        self.JOBS = MockQueue()
        self.FILES = MockR2()


class MockKV:
    """In-memory KV mock."""

    def __init__(self):
        self._data = {}

    async def get(self, key):
        entry = self._data.get(key)
        if not entry:
            return None
        value, expires_at = entry
        if expires_at and expires_at < time.time():
            del self._data[key]
            return None
        return value

    async def put(self, key, value, expirationTtl=None):
        expires_at = time.time() + expirationTtl if expirationTtl else None
        self._data[key] = (value, expires_at)

    async def delete(self, key):
        self._data.pop(key, None)


class MockQueue:
    """Queue mock — records sent messages."""

    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)
        return {"success": True}


class MockR2:
    """R2 mock — in-memory object store."""

    def __init__(self):
        self._objects = {}

    async def put(self, key, value, options=None):
        self._objects[key] = {"value": value, "options": options}

    async def get(self, key):
        return self._objects.get(key)

    async def delete(self, key):
        self._objects.pop(key, None)


class MockDB:
    """In-memory D1 mock with prepare/bind/all/first/run."""

    def __init__(self):
        self.tables = {
            "farmers": [],
            "farms": [],
            "plots": [],
            "enterprises": [],
            "records": [],
            "transactions": [],
            "tasks": [],
            "workers": [],
            "attendance": [],
            "equipment": [],
            "equipment_maintenance": [],
            "market_prices": [],
            "buyers": [],
            "sales": [],
            "contracts": [],
            "price_alerts": [],
            "pest_scouting": [],
            "pest_library": [],
            "treatments": [],
            "chemical_inventory": [],
            "ipm_practices": [],
            "courses": [],
            "lessons": [],
            "enrollments": [],
            "lesson_progress": [],
            "videos": [],
            "chatbot_conversations": [],
            "chatbot_messages": [],
            "forum_topics": [],
            "forum_replies": [],
            "experts": [],
            "consultations": [],
            "communication_log": [],
            "sms_templates": [],
            "ussd_sessions": [],
            "ussd_menus": [],
            "notifications": [],
            "device_tokens": [],
            "message_queue": [],
            "whatsapp_templates": [],
            "budgets": [],
            "budget_items": [],
            "audit_log": [],
            "sessions": [],
            "weather_cache": [],
            "system_config": [],
            "uploads": [],
            "api_keys": [],
            "rate_limit_log": [],
            "system_metrics": [],
            "schema_migrations": [],
        }
        self._auto_id = {t: 1 for t in self.tables}
        self._next_stmt_id = 1

    def prepare(self, sql):
        return MockStatement(self, sql)

    async def batch(self, statements):
        return [await s.run() for s in statements]


class MockStatement:
    """Represents a prepared statement."""

    def __init__(self, db: MockDB, sql: str):
        self.db = db
        self.sql = sql
        self.params = []

    def bind(self, *params):
        self.params = list(params)
        return self

    async def all(self):
        rows = self._execute()
        return MockResult(results=rows)

    async def first(self):
        rows = self._execute()
        return rows[0] if rows else None

    async def run(self):
        rows = self._execute()
        last_id = self.db._auto_id.get(self._table(), 0)
        return MockRunResult(
            results=rows,
            meta=MockMeta(
                last_row_id=last_id - 1 if self._is_insert() else None,
                changes=len(rows),
            ),
        )

    # ---------- internal ----------
    def _is_insert(self):
        return self.sql.strip().upper().startswith("INSERT")

    def _is_update(self):
        return self.sql.strip().upper().startswith("UPDATE")

    def _is_delete(self):
        return self.sql.strip().upper().startswith("DELETE")

    def _table(self):
        import re
        s = self.sql.strip().upper()
        for pattern in (r"INSERT\s+INTO\s+(\w+)",
                        r"UPDATE\s+(\w+)",
                        r"FROM\s+(\w+)"):
            m = re.search(pattern, s)
            if m:
                return m.group(1).lower()
        return None

    def _execute(self):
        """Super-simple SQL emulation for tests.
        Supports:
        - SELECT * FROM table
        - SELECT * FROM table WHERE col = ? [AND col = ?]
        - INSERT INTO table (...)
        - UPDATE table SET ...
        - DELETE FROM table WHERE ...
        """
        import re
        sql_up = self.sql.strip().upper()
        table = self._table()
        if not table or table not in self.db.tables:
            return []

        if self._is_insert():
            return self._do_insert(table)
        if self._is_update():
            return self._do_update(table)
        if self._is_delete():
            return self._do_delete(table)
        return self._do_select(table)

    def _do_select(self, table):
        rows = list(self.db.tables[table])
        where_col, where_val = self._parse_simple_where()
        if where_col:
            rows = [r for r in rows if str(r.get(where_col)) == str(where_val)]
        return rows

    def _do_insert(self, table):
        import re
        m = re.search(r"\(([^)]+)\)\s*VALUES", self.sql)
        if not m:
            return []
        cols = [c.strip() for c in m.group(1).split(",")]
        row = {}
        for i, col in enumerate(cols):
            if i < len(self.params):
                row[col] = self.params[i]
        # auto id
        new_id = self.db._auto_id.get(table, 1)
        row["id"] = new_id
        self.db._auto_id[table] = new_id + 1
        self.db.tables[table].append(row)
        return [row]

    def _do_update(self, table):
        import re
        m = re.search(r"SET\s+(.+?)\s+WHERE", self.sql, re.IGNORECASE)
        if not m:
            return []
        sets = [s.strip() for s in m.group(1).split(",")]
        keys = [s.split("=")[0].strip() for s in sets]
        # Last params is where value; earlier are set values
        set_values = self.params[:len(keys)]
        where_val = self.params[-1] if len(self.params) > len(keys) else None
        where_col = self._where_col()

        updated = []
        for row in self.db.tables[table]:
            if where_col and str(row.get(where_col)) != str(where_val):
                continue
            for k, v in zip(keys, set_values):
                row[k] = v
            updated.append(row)
        return updated

    def _do_delete(self, table):
        where_col, where_val = self._parse_simple_where()
        before = len(self.db.tables[table])
        if where_col:
            self.db.tables[table] = [
                r for r in self.db.tables[table]
                if str(r.get(where_col)) != str(where_val)
            ]
        else:
            self.db.tables[table] = []
        return [{"deleted": before - len(self.db.tables[table])}]

    def _parse_simple_where(self):
        import re
        m = re.search(r"WHERE\s+(\w+)\s*=\s*\?", self.sql, re.IGNORECASE)
        if m and self.params:
            return m.group(1), self.params[-1]
        return None, None

    def _where_col(self):
        import re
        m = re.search(r"WHERE\s+(\w+)\s*=", self.sql, re.IGNORECASE)
        return m.group(1) if m else None


class MockResult:
    def __init__(self, results=None):
        self.results = results or []


class MockRunResult:
    def __init__(self, results=None, meta=None):
        self.results = results or []
        self.meta = meta or MockMeta()


class MockMeta:
    def __init__(self, last_row_id=None, changes=0):
        self.last_row_id = last_row_id
        self.changes = changes


# ============================================================
# HELPERS
# ============================================================
def make_auth_header(user_id: int = 1, phone: str = TEST_PHONE,
                     secret: str = TEST_JWT_SECRET) -> dict:
    """Build an Authorization header with a valid JWT."""
    from utils import create_token
    token = create_token({"id": user_id, "phone": phone}, secret, expires_in=3600)
    return {"Authorization": f"Bearer {token}"}


def make_request(method="GET", url="http://localhost/api/test",
                 body=None, headers=None, form_data=None) -> MockRequest:
    return MockRequest(method, url, headers, body, form_data)


def make_env(**overrides) -> MockEnv:
    return MockEnv(**overrides)


def seed_farmer(env: MockEnv, farmer_id: int = 1,
                phone: str = TEST_PHONE, verified: int = 1) -> dict:
    """Insert a farmer into the mock DB."""
    from utils import hash_password
    farmer = {
        "id": farmer_id,
        "phone": phone,
        "email": f"farmer{farmer_id}@test.local",
        "full_name": f"Test Farmer {farmer_id}",
        "password_hash": hash_password(TEST_PASSWORD),
        "country": "Kenya",
        "county": "Kiambu",
        "location": "Limuru",
        "language": "en",
        "subscription_tier": "pro",
        "subscription_expires_at": "2099-12-31T00:00:00Z",
        "verified": verified,
        "verified_at": "2025-01-01T00:00:00Z" if verified else None,
        "last_login_at": None,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }
    env.DB.tables["farmers"].append(farmer)
    if farmer_id >= env.DB._auto_id["farmers"]:
        env.DB._auto_id["farmers"] = farmer_id + 1
    return farmer


def seed_farm(env: MockEnv, farm_id: int = 1, farmer_id: int = 1) -> dict:
    farm = {
        "id": farm_id,
        "farmer_id": farmer_id,
        "name": f"Test Farm {farm_id}",
        "size_acres": 2.5,
        "latitude": -1.1167,
        "longitude": 36.65,
        "county": "Kiambu",
        "active": 1,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }
    env.DB.tables["farms"].append(farm)
    if farm_id >= env.DB._auto_id["farms"]:
        env.DB._auto_id["farms"] = farm_id + 1
    return farm