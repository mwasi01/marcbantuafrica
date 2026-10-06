"""
Marcbantu Africa — Database layer.
Wraps Cloudflare D1 for clean, safe access.
"""


class DB:
    """D1 database helper. All queries go through here."""

    def __init__(self, env):
        self.db = env.DB

    # ========================================================
    # CORE QUERIES
    # ========================================================
    async def query(self, sql: str, params: list = None) -> list:
        """Run a SELECT and return all rows as list of Python dicts."""
        stmt = self.db.prepare(sql)
        if params:
            stmt = stmt.bind(*params)
        result = await stmt.all()
        if not result or not result.results:
            return []
        rows = result.results
        if hasattr(rows, "to_py"):
            rows = rows.to_py()
        return list(rows)


    async def query_one(self, sql: str, params: list = None) -> dict | None:
        """Run a SELECT and return first row as a Python dict or None."""
        stmt = self.db.prepare(sql)
        if params:
            stmt = stmt.bind(*params)
        result = await stmt.first()
        if not result:
            return None
        if hasattr(result, "to_py"):
            return result.to_py()
        return result


    async def execute(self, sql: str, params: list = None):
        """Run INSERT/UPDATE/DELETE. Returns result meta."""
        stmt = self.db.prepare(sql)
        if params:
            stmt = stmt.bind(*params)
        return await stmt.run()

    async def execute_many(self, statements: list):
        """Execute multiple statements in a batch (transaction)."""
        prepared = []
        for sql, params in statements:
            stmt = self.db.prepare(sql)
            if params:
                stmt = stmt.bind(*params)
            prepared.append(stmt)
        return await self.db.batch(prepared)

    # ========================================================
    # CRUD SHORTCUTS
    # ========================================================
    async def insert(self, table: str, data: dict) -> int | None:
        """Insert a row and return the new ID.

        Filters out keys whose value is None so that D1 can use the column
        default (or NULL) instead of erroring on 'undefined'. D1 does not
        accept JS undefined values — Python None becomes undefined when
        crossing the Pyodide bridge.
        """
        # Drop None values (D1 rejects undefined; SQL defaults handle rest)
        clean = {k: v for k, v in data.items() if v is not None}
        if not clean:
            raise ValueError(f"insert({table}) called with no non-None values")

        keys = list(clean.keys())
        values = list(clean.values())
        placeholders = ", ".join(["?"] * len(keys))
        columns = ", ".join(keys)
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        result = await self.execute(sql, values)
        if result and hasattr(result, 'meta') and result.meta:
            return result.meta.last_row_id
        return None

    async def update(self, table: str, data: dict, where: str, params: list):
        """Update rows matching `where`.

        Like insert(), this filters None values to avoid D1 undefined errors.
        If callers genuinely want to NULL a column, they should pass an
        explicit empty string or use a dedicated null-out helper.
        """
        clean = {k: v for k, v in data.items() if v is not None}
        if not clean:
            return None
        sets = ", ".join([f"{k} = ?" for k in clean.keys()])
        values = list(clean.values()) + list(params)
        sql = f"UPDATE {table} SET {sets} WHERE {where}"
        return await self.execute(sql, values)

    async def delete(self, table: str, where: str, params: list):
        """Delete rows matching `where`."""
        sql = f"DELETE FROM {table} WHERE {where}"
        return await self.execute(sql, params)

    async def exists(self, table: str, where: str, params: list) -> bool:
        """Check if any row matches."""
        row = await self.query_one(f"SELECT 1 as x FROM {table} WHERE {where} LIMIT 1", params)
        return row is not None

    async def count(self, table: str, where: str = "1=1", params: list = None) -> int:
        """Count rows matching `where`."""
        row = await self.query_one(f"SELECT COUNT(*) as total FROM {table} WHERE {where}", params)
        return row['total'] if row else 0

    # ========================================================
    # PAGINATION
    # ========================================================
    async def paginate(self, sql: str, params: list = None, page: int = 1, page_size: int = 50):
        """Run a paginated query. Returns {items, total, page, page_size, pages}."""
        from constants import MAX_PAGE_SIZE
        page = max(1, page)
        page_size = min(max(1, page_size), MAX_PAGE_SIZE)
        offset = (page - 1) * page_size

        # Count
        count_sql = f"SELECT COUNT(*) as total FROM ({sql}) as sub"
        count_row = await self.query_one(count_sql, params)
        total = count_row['total'] if count_row else 0

        # Items
        paged_sql = f"{sql} LIMIT ? OFFSET ?"
        paged_params = list(params or []) + [page_size, offset]
        items = await self.query(paged_sql, paged_params)

        pages = (total + page_size - 1) // page_size if page_size else 0
        return {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'pages': pages,
        }

    # ========================================================
    # TRANSACTIONS
    # ========================================================
    async def transaction(self, statements: list):
        """Execute multiple statements atomically.
        statements: list of (sql, params) tuples.
        """
        return await self.execute_many(statements)

    # ========================================================
    # HELPERS
    # ========================================================
    async def get_by_id(self, table: str, id: int, columns: str = "*") -> dict | None:
        """Get a row by ID."""
        return await self.query_one(f"SELECT {columns} FROM {table} WHERE id = ?", [id])

    async def get_by_field(self, table: str, field: str, value, columns: str = "*") -> dict | None:
        """Get a row by any field."""
        return await self.query_one(
            f"SELECT {columns} FROM {table} WHERE {field} = ? LIMIT 1",
            [value]
        )

    async def list_by_field(self, table: str, field: str, value,
                            columns: str = "*", order: str = "id DESC",
                            limit: int = None) -> list:
        """List rows by field."""
        sql = f"SELECT {columns} FROM {table} WHERE {field} = ? ORDER BY {order}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return await self.query(sql, [value])

    async def upsert(self, table: str, data: dict, unique_field: str) -> int | None:
        """Insert or update based on a unique field."""
        existing = await self.query_one(
            f"SELECT id FROM {table} WHERE {unique_field} = ?",
            [data[unique_field]]
        )
        if existing:
            await self.update(table, data, 'id = ?', [existing['id']])
            return existing['id']
        return await self.insert(table, data)