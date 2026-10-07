"""
Marcbantu Africa — Idempotent D1 migration runner.

Why this exists
---------------
SQLite has no `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. Running a
migration file twice throws `duplicate column name` and aborts the rest
of the file. This runner:

  1. Splits each .sql file into individual statements.
  2. For ALTER TABLE ... ADD COLUMN, checks PRAGMA table_info first.
  3. For CREATE TABLE / CREATE INDEX, uses IF NOT EXISTS.
  4. Splits multi-row INSERTs into chunks (of 50 rows) so no single
     statement exceeds the OS command-line arg limit.
  5. Switches to `--file` mode for statements > 4 KB, translating the
     path from WSL (`/mnt/c/...`) to Windows (`C:\\...`) so the Windows
     wrangler binary can find it.
  6. Records applied migrations in a `_migrations` ledger table.

Usage
-----
    python3 backend/migrations/migration_runner.py --local
    python3 backend/migrations/migration_runner.py --remote
    python3 backend/migrations/migration_runner.py --remote --file 010_market_intelligence.sql
    python3 backend/migrations/migration_runner.py --remote --dry-run
    python3 backend/migrations/migration_runner.py --remote --force

Requirements
------------
  - Node.js + npx (wrangler is invoked via `npx wrangler`)
  - wrangler.toml at the project root with a `marcbantu-db` D1 binding
  - Python 3.10+
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ============================================================
# Config
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # backend/migrations/ → project root
MIGRATIONS_DIR = SCRIPT_DIR
DB_NAME = "marcbantu-db"
LEDGER_TABLE = "_migrations"
CMD_LIMIT = 4000  # statements longer than this go through --file


# ============================================================
# Logging
# ============================================================
_USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def info(msg: str) -> None:
    print(_c("36", f"[INFO] {msg}"))


def ok(msg: str) -> None:
    print(_c("32", f"[ OK ] {msg}"))


def warn(msg: str) -> None:
    print(_c("33", f"[WARN] {msg}"))


def fail(msg: str) -> None:
    print(_c("31", f"[FAIL] {msg}"), file=sys.stderr)


def debug(msg: str) -> None:
    print(_c("90", f"[DBG ] {msg}"))


# ============================================================
# WSL → Windows path translation
# ============================================================
def _to_windows_path(p: Path) -> str:
    """
    Convert a WSL path like /mnt/c/Users/hp/foo to a Windows path like
    C:\\Users\\hp\\foo so Windows-native binaries (wrangler via npx)
    can find the file.

    No-op on non-WSL systems where the path is already native.
    """
    s = str(p)
    m = re.match(r"^/mnt/([a-zA-Z])/(.*)$", s)
    if m:
        drive = m.group(1).upper()
        rest = m.group(2).replace("/", "\\")
        return f"{drive}:\\{rest}"
    return s


# ============================================================
# SQL parsing
# ============================================================
@dataclass
class Statement:
    sql: str
    line: int
    kind: (
        str  # 'alter-add', 'create-table', 'create-index', 'insert', 'pragma', 'other'
    )
    alter_table: str = ""
    alter_column: str = ""

    def is_noop_if_exists(self) -> bool:
        if self.kind in ("create-table", "create-index"):
            return "IF NOT EXISTS" in self.sql.upper()
        return False


def _classify(sql: str, line: int) -> Statement:
    stripped = sql.strip()
    upper = stripped.upper()
    stmt = Statement(sql=stripped, line=line, kind="other")

    if upper.startswith("CREATE TABLE"):
        stmt.kind = "create-table"
    elif upper.startswith("CREATE UNIQUE INDEX") or upper.startswith("CREATE INDEX"):
        stmt.kind = "create-index"
    elif upper.startswith("ALTER TABLE") and "ADD COLUMN" in upper:
        stmt.kind = "alter-add"
        m = re.match(
            r"ALTER\s+TABLE\s+([\w.]+)\s+ADD\s+COLUMN\s+([\w]+)",
            stripped,
            re.IGNORECASE,
        )
        if m:
            stmt.alter_table = m.group(1)
            stmt.alter_column = m.group(2)
    elif upper.startswith("INSERT"):
        stmt.kind = "insert"
    elif upper.startswith("PRAGMA"):
        stmt.kind = "pragma"

    return stmt


def split_sql_statements(text: str) -> list[Statement]:
    """
    Split a .sql file into individual statements.

    Handles:
      - Semicolon-separated statements
      - Single-line `--` comments
      - `/* ... */` block comments
      - Single-quoted string literals (with '' escapes)
    """
    statements: list[Statement] = []
    buf: list[str] = []
    in_single = False
    in_line_comment = False
    in_block_comment = False
    start_line = 1
    line_no = 1

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if ch == "\n":
            line_no += 1

        if in_single:
            buf.append(ch)
            if ch == "'" and nxt == "'":
                buf.append(nxt)
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                buf.append(ch)
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if ch == "-" and nxt == "-":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue

        if ch == "'":
            in_single = True
            if not buf:
                start_line = line_no
            buf.append(ch)
            i += 1
            continue

        if ch == ";":
            stmt_text = "".join(buf).strip()
            if stmt_text:
                statements.append(_classify(stmt_text, start_line))
            buf = []
            i += 1
            continue

        if not buf and not ch.isspace():
            start_line = line_no

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(_classify(tail, start_line))

    return statements


# ============================================================
# Long-INSERT chunking
# ============================================================
def chunk_insert_statement(stmt: Statement, chunk_size: int = 50) -> list[Statement]:
    """
    Split a multi-row INSERT ... VALUES (...), (...), (...) statement
    into smaller INSERTs of `chunk_size` rows each.

    Only handles the simple pattern:
        INSERT [OR IGNORE|OR REPLACE] INTO t (col1, col2, ...) VALUES (...), (...), ...
    """
    if stmt.kind != "insert":
        return [stmt]

    sql = stmt.sql.strip()
    upper = sql.upper()
    vpos = upper.find(" VALUES ")
    if vpos == -1:
        return [stmt]

    prefix = sql[:vpos].rstrip()
    values_part = sql[vpos + len(" VALUES ") :].strip()

    # Split values on top-level commas (respect parentheses and quotes)
    groups: list[str] = []
    depth = 0
    in_single = False
    buf: list[str] = []
    i = 0
    n = len(values_part)
    while i < n:
        ch = values_part[i]
        nxt = values_part[i + 1] if i + 1 < n else ""

        if in_single:
            buf.append(ch)
            if ch == "'" and nxt == "'":
                buf.append(nxt)
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue

        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch == ")":
            depth -= 1
            buf.append(ch)
            i += 1
            continue
        if ch == "," and depth == 0:
            groups.append("".join(buf).strip())
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    if buf:
        groups.append("".join(buf).strip())

    if len(groups) <= chunk_size:
        return [stmt]

    chunks: list[Statement] = []
    for start in range(0, len(groups), chunk_size):
        group_slice = groups[start : start + chunk_size]
        new_sql = f"{prefix} VALUES " + ", ".join(group_slice)
        chunks.append(Statement(sql=new_sql, line=stmt.line, kind="insert"))
    return chunks


# ============================================================
# Wrangler CLI
# ============================================================
def _wrangler_base(remote: bool) -> list[str]:
    cmd = ["npx", "wrangler", "d1", "execute", DB_NAME, "--json"]
    cmd.append("--remote" if remote else "--local")
    return cmd


def _cleanup(tmp_path: Optional[Path]) -> None:
    """Remove a temp SQL file if it was written."""
    if tmp_path and tmp_path.exists():
        try:
            tmp_path.unlink()
        except OSError:
            pass


def run_sql(sql: str, remote: bool, dry_run: bool = False) -> tuple[bool, str]:
    """
    Execute one SQL statement via wrangler. Returns (success, output).

    Wrangler has two ways to receive SQL:
      - `--command '<sql>'` — for short statements
      - `--file <path>`     — for long statements

    The OS command-line arg limit caps `--command` at roughly 128 KB in
    practice (much less through bash). Statements longer than CMD_LIMIT
    go via a temp file and `--file` instead.

    On WSL, the temp file path must be translated to its Windows
    equivalent because wrangler is a Windows binary.
    """
    if dry_run:
        return True, "(dry-run)"

    # Flatten: replace any run of whitespace with a single space.
    flat_sql = " ".join(sql.split())

    # Wrangler adds its own terminator; a trailing `;` sometimes confuses it.
    while flat_sql.endswith(";"):
        flat_sql = flat_sql[:-1].rstrip()

    if not flat_sql:
        return True, "(empty)"

    tmp_path: Optional[Path] = None

    if len(flat_sql) <= CMD_LIMIT:
        cmd = _wrangler_base(remote) + ["--command", flat_sql]
    else:
        tmp_dir = MIGRATIONS_DIR / ".tmp"
        tmp_dir.mkdir(exist_ok=True)
        tmp_path = tmp_dir / f"stmt_{os.getpid()}_{len(flat_sql)}.sql"

        # Explicit LF endings so D1 parses cleanly regardless of host OS.
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(flat_sql + ";\n")

        # Translate to a Windows path so npx wrangler can find the file.
        win_path = _to_windows_path(tmp_path)
        cmd = _wrangler_base(remote) + ["--file", win_path]

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        _cleanup(tmp_path)
        return False, "timeout after 180s"
    except FileNotFoundError:
        _cleanup(tmp_path)
        return False, "npx not found — install Node.js"

    _cleanup(tmp_path)

    out = (proc.stdout or "") + (proc.stderr or "")

    if proc.returncode != 0:
        return False, out.strip()

    # Wrangler may wrap D1 errors inside a JSON envelope even on exit 0.
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else []
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", proc.stdout or "", re.DOTALL)
        if m:
            try:
                payload = json.loads(m.group(0))
            except json.JSONDecodeError:
                payload = []
        else:
            payload = []

    if isinstance(payload, list):
        for entry in payload:
            if isinstance(entry, dict):
                if entry.get("success") is False:
                    err = entry.get("error") or entry.get("errors") or entry
                    return False, str(err)
                if "error" in entry and entry["error"]:
                    return False, str(entry["error"])

    return True, out.strip()


# ============================================================
# Ledger
# ============================================================
def ledger_bootstrap(remote: bool) -> bool:
    sql = textwrap.dedent(
        f"""
        CREATE TABLE IF NOT EXISTS {LEDGER_TABLE} (
            filename     TEXT PRIMARY KEY,
            checksum     TEXT NOT NULL,
            applied_at   TEXT NOT NULL DEFAULT (datetime('now')),
            statements   INTEGER DEFAULT 0
        )
        """
    ).strip()
    success, out = run_sql(sql, remote)
    if not success:
        fail(f"Could not create ledger table: {out}")
    return success


def ledger_applied(remote: bool) -> dict[str, str]:
    sql = f"SELECT filename, checksum FROM {LEDGER_TABLE}"
    success, out = run_sql(sql, remote)
    if not success:
        warn(f"Could not read ledger: {out}")
        return {}

    m = re.search(r"\[.*\]", out, re.DOTALL)
    if not m:
        warn("Ledger output unparseable — assuming empty ledger")
        return {}
    try:
        payload = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}

    results: dict[str, str] = {}
    for entry in payload if isinstance(payload, list) else [payload]:
        rows = entry.get("results") or entry.get("data") or []
        if isinstance(rows, list):
            for row in rows:
                if "filename" in row:
                    results[row["filename"]] = row.get("checksum", "")
    return results


def ledger_record(filename: str, checksum: str, count: int, remote: bool) -> None:
    safe_name = filename.replace("'", "''")
    sql = (
        f"INSERT INTO {LEDGER_TABLE} (filename, checksum, statements) "
        f"VALUES ('{safe_name}', '{checksum}', {int(count)}) "
        f"ON CONFLICT(filename) DO UPDATE SET "
        f"checksum = excluded.checksum, "
        f"applied_at = datetime('now'), "
        f"statements = excluded.statements"
    )
    success, out = run_sql(sql, remote)
    if not success:
        warn(f"Could not record {filename} in ledger: {out}")


# ============================================================
# Introspection
# ============================================================
_table_columns_cache: dict[tuple[str, bool], set[str]] = {}


def table_columns(table: str, remote: bool) -> set[str]:
    key = (table, remote)
    if key in _table_columns_cache:
        return _table_columns_cache[key]

    sql = f"PRAGMA table_info({table})"
    success, out = run_sql(sql, remote)
    cols: set[str] = set()

    if success:
        m = re.search(r"\[.*\]", out, re.DOTALL)
        if m:
            try:
                payload = json.loads(m.group(0))
                for entry in payload if isinstance(payload, list) else [payload]:
                    rows = entry.get("results") or entry.get("data") or []
                    for row in rows:
                        if "name" in row:
                            cols.add(row["name"])
            except json.JSONDecodeError:
                pass

    _table_columns_cache[key] = cols
    return cols


# ============================================================
# Checksums
# ============================================================
def file_checksum(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:16]


# ============================================================
# Apply one file
# ============================================================
@dataclass
class FileResult:
    filename: str
    total: int = 0
    executed: int = 0
    skipped: int = 0
    errors: int = 0
    applied: bool = False
    error_messages: list[str] = field(default_factory=list)


def apply_file(path: Path, remote: bool, dry_run: bool, force: bool) -> FileResult:
    result = FileResult(filename=path.name)
    text = path.read_text(encoding="utf-8")
    statements = split_sql_statements(text)

    # Expand long multi-row INSERTs into chunked statements
    expanded: list[Statement] = []
    for stmt in statements:
        if stmt.kind == "insert" and stmt.sql.count("),(") > 30:
            expanded.extend(chunk_insert_statement(stmt, chunk_size=50))
        else:
            expanded.append(stmt)
    statements = expanded
    result.total = len(statements)

    info(f"── {path.name}  ({len(statements)} statements)")

    for stmt in statements:
        if stmt.kind == "pragma":
            continue

        # CREATE ... IF NOT EXISTS — safe to run every time
        if stmt.is_noop_if_exists() and not force:
            success, out = run_sql(stmt.sql, remote, dry_run)
            if success:
                result.executed += 1
            else:
                low = out.lower()
                if "already exists" in low:
                    result.skipped += 1
                else:
                    result.errors += 1
                    result.error_messages.append(f"L{stmt.line}: {out[:200]}")
            continue

        # ALTER TABLE ADD COLUMN — check existence first
        if stmt.kind == "alter-add" and not force:
            existing = table_columns(stmt.alter_table, remote)
            if stmt.alter_column in existing:
                result.skipped += 1
                debug(f"  L{stmt.line}: skip ADD COLUMN {stmt.alter_column} (exists)")
                continue

        # Everything else
        success, out = run_sql(stmt.sql, remote, dry_run)
        if success:
            result.executed += 1
        else:
            low = out.lower()
            if "duplicate column name" in low or "already exists" in low:
                result.skipped += 1
                continue
            result.errors += 1
            result.error_messages.append(f"L{stmt.line}: {out[:300]}")

    result.applied = result.errors == 0
    return result


# ============================================================
# Main
# ============================================================
def discover_migrations(only: Optional[str]) -> list[Path]:
    files = sorted(p for p in MIGRATIONS_DIR.glob("*.sql") if p.name != "schema.sql")
    if only:
        files = [p for p in files if p.name == only]
        if not files:
            fail(f"No migration file named {only}")
            sys.exit(1)
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description="Marcbantu D1 migration runner")
    group = ap.add_mutually_exclusive_group()
    group.add_argument(
        "--local", action="store_true", help="target the local D1 (default)"
    )
    group.add_argument("--remote", action="store_true", help="target the production D1")
    ap.add_argument("--file", help="run only this migration file")
    ap.add_argument(
        "--dry-run", action="store_true", help="show what would run, don't execute"
    )
    ap.add_argument(
        "--force", action="store_true", help="re-run even if ledger says applied"
    )
    args = ap.parse_args()

    remote = args.remote

    if shutil.which("npx") is None:
        fail("`npx` not found. Install Node.js first.")
        return 2

    info(f"Target: {'REMOTE (production)' if remote else 'LOCAL'}")
    info(f"Project root: {PROJECT_ROOT}")
    info(f"Migrations:   {MIGRATIONS_DIR}")
    print()

    if not ledger_bootstrap(remote):
        return 3

    applied = {} if args.force else ledger_applied(remote)
    files = discover_migrations(args.file)
    if not files:
        warn("No migration files found")
        return 0

    total_exec = total_skip = total_err = 0
    applied_files = 0

    for path in files:
        checksum = file_checksum(path)
        recorded = applied.get(path.name)

        if recorded and recorded != checksum and not args.force:
            warn(f"{path.name}  checksum changed since last apply")
            warn(f"   recorded={recorded}  current={checksum}")

        result = apply_file(path, remote=remote, dry_run=args.dry_run, force=args.force)
        total_exec += result.executed
        total_skip += result.skipped
        total_err += result.errors

        if result.applied:
            ok(f"{path.name}  {result.executed} run, {result.skipped} skipped")
            applied_files += 1
            if not args.dry_run:
                ledger_record(path.name, checksum, result.executed, remote)
        else:
            fail(
                f"{path.name}  {result.errors} error(s), "
                f"{result.executed} run, {result.skipped} skipped"
            )
            for msg in result.error_messages[:5]:
                print(f"     {msg}")
            if len(result.error_messages) > 5:
                print(f"     ... and {len(result.error_messages) - 5} more")
        print()

    print("=" * 60)
    if total_err == 0:
        ok(
            f"All migrations applied.  {applied_files} file(s), "
            f"{total_exec} statements, {total_skip} skipped."
        )
    else:
        fail(f"Migration run finished with {total_err} error(s).")
    print("=" * 60)
    return 0 if total_err == 0 else 4


if __name__ == "__main__":
    sys.exit(main())
