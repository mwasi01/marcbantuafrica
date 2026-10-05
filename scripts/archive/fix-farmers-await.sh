#!/usr/bin/env bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

python3 << 'PYEOF'
import re

def patch(path, replacements):
    with open(path) as fh:
        src = fh.read()
    changed = False
    for old, new in replacements:
        if old in src:
            src = src.replace(old, new)
            changed = True
        else:
            print(f"  WARN: pattern not found in {path}:")
            print(f"        {old[:80]}...")
    if changed:
        with open(path, "w") as fh:
            fh.write(src)
        print(f"  patched: {path}")

# ---------- farmers.py ----------
patch("backend/src/routes/farmers.py", [
    # 1. record_count in get_profile
    (
        """    farmer['record_count'] = await db.query_one(\"\"\"
        SELECT COUNT(*) as total FROM records r
        JOIN farms f ON r.farm_id = f.id
        WHERE f.farmer_id = ?
    \"\"\", [user['id']])['total']""",
        """    _rc = await db.query_one(\"\"\"
        SELECT COUNT(*) as total FROM records r
        JOIN farms f ON r.farm_id = f.id
        WHERE f.farmer_id = ?
    \"\"\", [user['id']])
    farmer['record_count'] = _rc['total'] if _rc else 0"""
    ),
    # 2. enterprise_count in get_profile
    (
        """    farmer['enterprise_count'] = await db.query_one(\"\"\"
        SELECT COUNT(*) as total FROM enterprises e
        JOIN farms f ON e.farm_id = f.id
        WHERE f.farmer_id = ? AND e.status = 'active'
    \"\"\", [user['id']])['total']""",
        """    _ec = await db.query_one(\"\"\"
        SELECT COUNT(*) as total FROM enterprises e
        JOIN farms f ON e.farm_id = f.id
        WHERE f.farmer_id = ? AND e.status = 'active'
    \"\"\", [user['id']])
    farmer['enterprise_count'] = _ec['total'] if _ec else 0"""
    ),
    # 3. record_count_month in subscription_info
    (
        """    record_count_month = await db.query_one(\"\"\"
        SELECT COUNT(*) as total FROM records r
        JOIN farms f ON r.farm_id = f.id
        WHERE f.farmer_id = ? AND r.record_date >= date('now', 'start of month')
    \"\"\", [user['id']])['total']""",
        """    _rcm = await db.query_one(\"\"\"
        SELECT COUNT(*) as total FROM records r
        JOIN farms f ON r.farm_id = f.id
        WHERE f.farmer_id = ? AND r.record_date >= date('now', 'start of month')
    \"\"\", [user['id']])
    record_count_month = _rcm['total'] if _rcm else 0"""
    ),
])

# ---------- learning.py ----------
patch("backend/src/routes/learning.py", [
    (
        """    completed_lessons = await db.query_one(\"\"\"
        SELECT COUNT(*) as total FROM lesson_progress
        WHERE enrollment_id = ? AND completed = 1
    \"\"\", [enrollment['id']])['total']""",
        """    _cl = await db.query_one(\"\"\"
        SELECT COUNT(*) as total FROM lesson_progress
        WHERE enrollment_id = ? AND completed = 1
    \"\"\", [enrollment['id']])
    completed_lessons = _cl['total'] if _cl else 0"""
    ),
])

print()
print("Verify:")
PYEOF

echo ""
grep -n "_rc = await\|_ec = await\|_rcm = await\|_cl = await" backend/src/routes/farmers.py backend/src/routes/learning.py 2>/dev/null || echo "  (no matches — check files manually)"
