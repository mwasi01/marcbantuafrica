"""
Job: sync_records
Processes bulk offline record uploads from farmer devices.
Handles deduplication via client_id, conflict resolution, and notifications.

Payload:
{
    "farmer_id": 1,
    "records": [
        {"client_id": "off-abc123", "farm_id": 1, "record_type": "livestock",
         "activity": "milking", "quantity": 20, "unit": "litres",
         "record_date": "2025-10-04"},
        ...
    ],
    "source": "pwa" | "sms" | "ussd"
}
"""
import json
from utils import now_iso, log_event, log_error, generate_reference
from db import DB


# ============================================================
# MAIN JOB
# ============================================================
async def run(payload: dict, env):
    """Process a batch of offline records."""
    farmer_id = payload.get("farmer_id")
    records = payload.get("records", [])
    source = payload.get("source", "pwa")

    if not farmer_id:
        log_error("sync_records: missing farmer_id")
        return

    if not records:
        log_event("sync_records_empty", {"farmer_id": farmer_id})
        return

    log_event("sync_records_start", {
        "farmer_id": farmer_id,
        "count": len(records),
        "source": source,
    })

    db = DB(env)

    # Verify farmer exists
    farmer = await db.query_one(
        "SELECT id, phone, full_name FROM farmers WHERE id = ?",
        [farmer_id]
    )
    if not farmer:
        log_error("sync_records: farmer not found", {"farmer_id": farmer_id})
        return

    # Get farmer's active farms for ownership check
    farms = await db.query(
        "SELECT id FROM farms WHERE farmer_id = ? AND active = 1",
        [farmer_id]
    )
    farm_ids = {f["id"] for f in farms}

    if not farm_ids:
        log_error("sync_records: no active farms", {"farmer_id": farmer_id})
        return

    # Process records
    succeeded = []
    failed = []
    duplicates = []

    for record in records:
        try:
            result = await _sync_one(db, record, farm_ids, farmer_id, source, env)
            if result["status"] == "created":
                succeeded.append(result)
            elif result["status"] == "duplicate":
                duplicates.append(result)
            else:
                failed.append(result)
        except Exception as e:
            log_error(f"sync_record_failed: {str(e)}", {"record": record})
            failed.append({
                "client_id": record.get("client_id"),
                "status": "error",
                "error": str(e),
            })

    # Auto-create transactions for sale/expense records
    tx_created = 0
    for success in succeeded:
        try:
            record_id = success.get("server_id")
            if record_id:
                created = await _auto_create_transaction(db, record_id, farmer_id)
                if created:
                    tx_created += 1
        except Exception as e:
            log_error(f"Auto-transaction failed: {str(e)}")

    # Notify farmer
    if succeeded or failed:
        await _notify_farmer(db, env, farmer, succeeded, failed, source)

    log_event("sync_records_done", {
        "farmer_id": farmer_id,
        "created": len(succeeded),
        "duplicates": len(duplicates),
        "failed": len(failed),
        "transactions": tx_created,
    })


# ============================================================
# SYNC SINGLE RECORD
# ============================================================
async def _sync_one(db: DB, record: dict, farm_ids: set,
                    farmer_id: int, source: str, env) -> dict:
    """Sync one offline record. Returns {status, server_id?, client_id, ...}."""
    client_id = record.get("client_id") or generate_reference("OFF")

    # Validate farm ownership
    farm_id = record.get("farm_id")
    if not farm_id or farm_id not in farm_ids:
        return {
            "client_id": client_id,
            "status": "failed",
            "error": "Farm not owned or inactive",
        }

    # Dedupe by client_id if provided
    if record.get("client_id"):
        existing = await db.query_one(
            "SELECT id FROM records WHERE client_id = ?",
            [record["client_id"]]
        )
        if existing:
            return {
                "client_id": client_id,
                "server_id": existing["id"],
                "status": "duplicate",
            }

    # Validate required fields
    if not record.get("record_type"):
        return {
            "client_id": client_id,
            "status": "failed",
            "error": "Missing record_type",
        }

    if not record.get("record_date"):
        record["record_date"] = now_iso()[:10]

    # Validate enterprise belongs to farm if provided
    enterprise_id = record.get("enterprise_id")
    if enterprise_id:
        ent = await db.query_one(
            "SELECT id FROM enterprises WHERE id = ? AND farm_id = ?",
            [enterprise_id, farm_id]
        )
        if not ent:
            enterprise_id = None

    # Validate plot
    plot_id = record.get("plot_id")
    if plot_id:
        plot = await db.query_one(
            "SELECT id FROM plots WHERE id = ? AND farm_id = ?",
            [plot_id, farm_id]
        )
        if not plot:
            plot_id = None

    # Insert
    record_id = await db.insert("records", {
        "farm_id": farm_id,
        "enterprise_id": enterprise_id,
        "plot_id": plot_id,
        "record_type": record.get("record_type"),
        "activity": record.get("activity"),
        "description": record.get("description"),
        "quantity": _safe_float(record.get("quantity")),
        "unit": record.get("unit"),
        "cost": _safe_float(record.get("cost")) or 0,
        "revenue": _safe_float(record.get("revenue")) or 0,
        "record_date": record["record_date"],
        "notes": record.get("notes"),
        "photo_url": record.get("photo_url"),
        "latitude": _safe_float(record.get("latitude")),
        "longitude": _safe_float(record.get("longitude")),
        "client_id": record.get("client_id"),
        "sync_source": source,
        "created_by": farmer_id,
    })

    return {
        "client_id": client_id,
        "server_id": record_id,
        "status": "created",
    }


# ============================================================
# AUTO TRANSACTION
# ============================================================
async def _auto_create_transaction(db: DB, record_id: int, farmer_id: int) -> bool:
    """Create a transaction for sale/expense records."""
    record = await db.query_one("SELECT * FROM records WHERE id = ?", [record_id])
    if not record:
        return False

    # Skip if transaction already exists
    existing = await db.query_one(
        "SELECT id FROM transactions WHERE record_id = ?",
        [record_id]
    )
    if existing:
        return False

    rtype = record.get("record_type")
    revenue = record.get("revenue") or 0
    cost = record.get("cost") or 0

    if rtype == "sale" and revenue > 0:
        await db.insert("transactions", {
            "farm_id": record["farm_id"],
            "enterprise_id": record.get("enterprise_id"),
            "record_id": record_id,
            "type": "income",
            "category": "crop_sales",
            "description": record.get("description") or "Sale",
            "amount": revenue,
            "transaction_date": record["record_date"],
            "created_by": farmer_id,
        })
        return True

    if rtype == "expense" and cost > 0:
        await db.insert("transactions", {
            "farm_id": record["farm_id"],
            "enterprise_id": record.get("enterprise_id"),
            "record_id": record_id,
            "type": "expense",
            "category": "other_expense",
            "description": record.get("description") or "Expense",
            "amount": cost,
            "transaction_date": record["record_date"],
            "created_by": farmer_id,
        })
        return True

    return False


# ============================================================
# NOTIFY FARMER
# ============================================================
async def _notify_farmer(db: DB, env, farmer: dict,
                         succeeded: list, failed: list, source: str):
    """Create in-app notification + optional SMS confirming sync."""
    total = len(succeeded) + len(failed)
    if total == 0:
        return

    # In-app notification
    title = f"{len(succeeded)} records synced"
    if failed:
        title += f" · {len(failed)} failed"

    message = f"Your offline records are now on the server."
    if failed:
        message += f" {len(failed)} could not be synced — check the app for details."

    try:
        await db.insert("notifications", {
            "farmer_id": farmer["id"],
            "type": "system",
            "title": title,
            "message": message,
            "priority": "high" if failed else "normal",
            "action_url": "/records.html",
        })
    except Exception:
        pass

    # SMS confirmation for large syncs (>20 records)
    if len(succeeded) >= 20 and farmer.get("phone"):
        try:
            await env.JOBS.send({
                "type": "send_sms",
                "payload": {
                    "to": farmer["phone"],
                    "farmer_id": farmer["id"],
                    "message": (
                        f"Marcbantu: {len(succeeded)} offline records synced successfully."
                        + (f" {len(failed)} failed." if failed else "")
                    ),
                },
            })
        except Exception:
            pass

    # Log failure details for support
    if failed:
        log_event("sync_records_failed_details", {
            "farmer_id": farmer["id"],
            "failures": failed[:10],
        })


# ============================================================
# HELPERS
# ============================================================
def _safe_float(value):
    """Convert to float or None."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ============================================================
# LEGACY HELPER (used by routes/records.py sync_offline)
# ============================================================
async def sync_offline_batch(farmer_id: int, records: list, source: str, env) -> dict:
    """
    Called directly from routes when sync happens synchronously.
    Same logic as run(), but returns a result instead of using queues.
    """
    await run({
        "farmer_id": farmer_id,
        "records": records,
        "source": source,
    }, env)

    return {
        "status": "processed",
        "count": len(records),
    }