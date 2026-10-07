#!/usr/bin/env bash
# Fix D1 "Type 'undefined' not supported" errors by filtering None values
# out of INSERT/UPDATE statements (letting SQL DEFAULTs apply).
set -euo pipefail

DB_FILE="backend/src/db.py"
VAL_FILE="backend/src/validators.py"

[[ -f "$DB_FILE"  ]] || { echo "Missing $DB_FILE"; exit 1; }
[[ -f "$VAL_FILE" ]] || { echo "Missing $VAL_FILE"; exit 1; }

STAMP="$(date +%Y%m%d-%H%M%S)"
cp "$DB_FILE"  "$DB_FILE.bak-$STAMP"
cp "$VAL_FILE" "$VAL_FILE.bak-$STAMP"
echo "Backups:"
echo "  $DB_FILE.bak-$STAMP"
echo "  $VAL_FILE.bak-$STAMP"

python3 - <<'PY'
import re, pathlib

# ============================================================
# 1. Patch db.py insert() and update()
# ============================================================
p = pathlib.Path("backend/src/db.py")
src = p.read_text(encoding="utf-8")

# --- insert() --------------------------------------------------
old_insert = '''    async def insert(self, table: str, data: dict) -> int | None:
        """Insert a row and return the new ID."""
        keys = list(data.keys())
        values = list(data.values())
        placeholders = ", ".join(["?"] * len(keys))
        columns = ", ".join(keys)
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        result = await self.execute(sql, values)
        if result and hasattr(result, 'meta') and result.meta:
            return result.meta.last_row_id
        return None'''

new_insert = '''    async def insert(self, table: str, data: dict) -> int | None:
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
        return None'''

if old_insert in src:
    src = src.replace(old_insert, new_insert, 1)
    print("  ✓ Patched db.insert()")
else:
    print("  ⚠ db.insert() pattern not found — attempting regex fallback")
    # regex fallback
    m = re.search(r"(async def insert\(self.*?return None)\n", src, re.DOTALL)
    if m:
        src = src[:m.start(1)] + new_insert.split("\n", 1)[1].lstrip() + src[m.end(1):]
        print("  ✓ Patched db.insert() via regex")
    else:
        print("  ✗ Could not patch db.insert()")

# --- update() --------------------------------------------------
old_update = '''    async def update(self, table: str, data: dict, where: str, params: list):
        """Update rows matching `where`."""
        if not data:
            return None
        sets = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values()) + list(params)
        sql = f"UPDATE {table} SET {sets} WHERE {where}"
        return await self.execute(sql, values)'''

new_update = '''    async def update(self, table: str, data: dict, where: str, params: list):
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
        return await self.execute(sql, values)'''

if old_update in src:
    src = src.replace(old_update, new_update, 1)
    print("  ✓ Patched db.update()")
else:
    print("  ⚠ db.update() pattern not found")

p.write_text(src, encoding="utf-8")

# ============================================================
# 2. Patch validators.validate_farm to include county
# ============================================================
v = pathlib.Path("backend/src/validators.py")
vs = v.read_text(encoding="utf-8")

old_vf = '''    return {
        'name': str(data['name']).strip(),
        'size_acres': to_float(data.get('size_acres')) or None,
        'latitude': to_float(data.get('latitude')) or None,
        'longitude': to_float(data.get('longitude')) or None,
        'altitude_m': to_float(data.get('altitude_m')) or None,
        'soil_type': data.get('soil_type'),
        'irrigation_type': data.get('irrigation_type'),
        'water_source': data.get('water_source'),
        'notes': data.get('notes'),
    }'''

new_vf = '''    return {
        'name': str(data['name']).strip(),
        'county': data.get('county'),
        'location': data.get('location'),
        'size_acres': to_float(data.get('size_acres')),
        'latitude': to_float(data.get('latitude')),
        'longitude': to_float(data.get('longitude')),
        'altitude_m': to_float(data.get('altitude_m')),
        'soil_type': data.get('soil_type'),
        'irrigation_type': data.get('irrigation_type'),
        'water_source': data.get('water_source'),
        'notes': data.get('notes'),
    }'''

if old_vf in vs:
    vs = vs.replace(old_vf, new_vf, 1)
    print("  ✓ Patched validate_farm() (added county, location; removed 'or None')")
else:
    print("  ⚠ validate_farm() return block not found")
    # Try a looser regex
    m = re.search(
        r"(def validate_farm\(data: dict\) -> dict:.*?return \{)(.*?)(\})",
        vs, re.DOTALL,
    )
    if m:
        vs = vs[:m.start(2)] + "\n" + new_vf.split("return {", 1)[1].split("}", 1)[0].rstrip() + "\n    " + vs[m.end(2):]
        print("  ✓ Patched validate_farm() via regex")
    else:
        print("  ✗ Could not patch validate_farm()")

v.write_text(vs, encoding="utf-8")
PY

echo ""
echo "Verifying db.py changes:"
grep -n "Drop None values\|filters None values" "$DB_FILE" || echo "  (not found)"

echo ""
echo "Verifying validators.py changes:"
grep -n "'county': data.get('county')" "$VAL_FILE" || echo "  (not found)"

echo ""
echo "Next steps:"
echo "  1. Verify the diff:  git diff backend/src/db.py backend/src/validators.py"
echo "  2. Deploy:           npx wrangler deploy --env=\"\""
echo "  3. Test creating a farm from the browser."
