"""
Marcbantu Africa — Partner routes.
Partner directory and applications.
"""
from utils import (
    success_response, error_response, parse_json, require_auth,
    now_iso, to_int, log_event, require_fields,
    _sp,
)
from constants import HTTP, ErrorCode
from db import DB


# ============================================================
# LIST PARTNERS
# ============================================================
async def list_partners(request, env):
    """GET /api/partners
    Query: type?, county?
    Partners are stored in buyers table with type in
    ('cooperative', 'processor', 'institution') plus system_config for formal partners.
    """
    db = DB(env)
    url = _sp(request)

    # In production, this would query a dedicated partners table.
    # For now, use system_config to store partner info.
    rows = await db.query("""
        SELECT key, value FROM system_config
        WHERE category = 'partner' AND public = 1
    """)

    import json
    partners = []
    for r in rows:
        try:
            partners.append(json.loads(r['value']))
        except Exception:
            pass

    return success_response(partners)


# ============================================================
# APPLY TO BECOME A PARTNER
# ============================================================
async def apply(request, env):
    """POST /api/partners/apply
    Body: {organization_name, contact_name, email, phone, type, message}
    """
    data = await parse_json(request)
    err_msg = require_fields(data, ['organization_name', 'contact_name', 'email', 'type'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    db = DB(env)

    # Log application
    await db.insert('audit_log', {
        'action': 'partner_application',
        'entity': 'partner',
        'details': f"{data['organization_name']} ({data['type']}) — {data['email']}",
    })

    # Notify admin
    admin = await db.query_one(
        "SELECT id FROM farmers WHERE phone = '+254700000001' LIMIT 1"
    )
    if admin:
        await db.insert('notifications', {
            'farmer_id': admin['id'],
            'type': 'system',
            'title': 'New partner application',
            'message': f"{data['organization_name']} applied as a {data['type']} partner.",
            'priority': 'normal',
        })

    log_event('partner_application', {
        'org': data['organization_name'],
        'type': data['type'],
    })

    return success_response(None, message="Application submitted. Our team will contact you shortly.")