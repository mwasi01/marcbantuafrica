"""
Marcbantu Africa — Pest & Disease routes.
Field scouting, chemical treatments, inventory, IPM practices,
pest library reference, AI-powered photo diagnosis, outbreak alerts.
"""
from utils import (
    success_response, error_response, parse_json, require_auth,
    now_iso, to_int, to_float, log_event, require_fields, paginated_response,
    _sp,
)
from validators import (
    ValidationError,
    validate_scouting, validate_treatment,
)
from constants import HTTP, ErrorCode, Severity
from db import DB


# ============================================================
# HELPERS
# ============================================================
async def _get_owned_farm(db: DB, farm_id: int, farmer_id: int):
    return await db.query_one(
        "SELECT id, latitude, longitude, county FROM farms WHERE id = ? AND farmer_id = ?",
        [farm_id, farmer_id]
    )


async def _get_owned_scouting(db: DB, scouting_id: int, farmer_id: int):
    return await db.query_one("""
        SELECT ps.* FROM pest_scouting ps
        JOIN farms f ON ps.farm_id = f.id
        WHERE ps.id = ? AND f.farmer_id = ?
    """, [scouting_id, farmer_id])


async def _get_owned_treatment(db: DB, treatment_id: int, farmer_id: int):
    return await db.query_one("""
        SELECT t.* FROM treatments t
        JOIN farms f ON t.farm_id = f.id
        WHERE t.id = ? AND f.farmer_id = ?
    """, [treatment_id, farmer_id])


# ============================================================
# SCOUTING — LIST
# ============================================================
async def list_scouting(request, env):
    """GET /api/pest/scouting
    Query: farm_id?, plot_id?, severity?, pest?, from?, to?, page, page_size
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("ps.farm_id = ?")
        params.append(to_int(farm_id))

    plot_id = url.search_params.get('plot_id')
    if plot_id:
        where.append("ps.plot_id = ?")
        params.append(to_int(plot_id))

    severity = url.search_params.get('severity')
    if severity:
        where.append("ps.severity = ?")
        params.append(severity)

    pest = url.search_params.get('pest')
    if pest:
        where.append("ps.pest_name LIKE ?")
        params.append(f"%{pest}%")

    date_from = url.search_params.get('from')
    if date_from:
        where.append("ps.scout_date >= ?")
        params.append(date_from)

    date_to = url.search_params.get('to')
    if date_to:
        where.append("ps.scout_date <= ?")
        params.append(date_to)

    page = to_int(url.search_params.get('page', 1), 1)
    page_size = to_int(url.search_params.get('page_size', 50), 50)

    sql = f"""
        SELECT ps.*,
               f.name as farm_name,
               p.name as plot_name,
               e.name as enterprise_name
        FROM pest_scouting ps
        JOIN farms f ON ps.farm_id = f.id
        LEFT JOIN plots p ON ps.plot_id = p.id
        LEFT JOIN enterprises e ON ps.enterprise_id = e.id
        WHERE {' AND '.join(where)}
        ORDER BY ps.scout_date DESC, ps.id DESC
    """

    result = await db.paginate(sql, params, page=page, page_size=page_size)
    return paginated_response(result, message="Scouting records retrieved")


# ============================================================
# SCOUTING — CREATE
# ============================================================
async def create_scouting(request, env):
    """POST /api/pest/scouting"""
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    try:
        clean = validate_scouting(data)
    except ValidationError as e:
        return error_response(e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)
    farm = await _get_owned_farm(db, clean['farm_id'], user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    scouting_id = await db.insert('pest_scouting', clean)

    scouting = await db.query_one("""
        SELECT ps.*, f.name as farm_name, p.name as plot_name
        FROM pest_scouting ps
        JOIN farms f ON ps.farm_id = f.id
        LEFT JOIN plots p ON ps.plot_id = p.id
        WHERE ps.id = ?
    """, [scouting_id])

    # If severity is high or critical, queue an SMS warning to this farmer
    if clean['severity'] in ('high', 'critical'):
        try:
            farmer = await db.query_one(
                "SELECT phone, full_name FROM farmers WHERE id = ?",
                [user['id']]
            )
            if farmer:
                await env.JOBS.send({
                    'type': 'send_sms',
                    'payload': {
                        'to': farmer['phone'],
                        'farmer_id': user['id'],
                        'body': (
                            f"PEST ALERT: {clean['pest_name']} recorded at {clean['severity']} severity. "
                            f"Take action now. Log treatment in Marcbantu."
                        ),
                    }
                })
        except Exception:
            pass

    log_event('scouting_created', {
        'scouting_id': scouting_id,
        'farmer_id': user['id'],
        'severity': clean['severity'],
    })

    return success_response(scouting, message="Scouting recorded", status=HTTP.CREATED)


# ============================================================
# SCOUTING — UPDATE
# ============================================================
async def update_scouting(request, env, scouting_id: int):
    """PUT /api/pest/scouting/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    s = await _get_owned_scouting(db, scouting_id, user['id'])
    if not s:
        return error_response("Scouting record not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    data = await parse_json(request)
    allowed = ['pest_name', 'pest_type', 'severity', 'affected_area_pct',
               'photo_url', 'symptoms', 'scout_date', 'notes']
    updates = {}
    for k in allowed:
        if k in data:
            if k == 'affected_area_pct':
                updates[k] = to_float(data[k]) or None
            elif k == 'severity':
                if data[k] not in Severity.ALL:
                    return error_response("Invalid severity",
                                         status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)
                updates[k] = data[k]
            else:
                updates[k] = data[k]

    if not updates:
        return error_response("No valid fields to update",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    await db.update('pest_scouting', updates, 'id = ?', [scouting_id])

    updated = await db.query_one("SELECT * FROM pest_scouting WHERE id = ?", [scouting_id])
    return success_response(updated, message="Scouting updated")


# ============================================================
# SCOUTING — DELETE
# ============================================================
async def delete_scouting(request, env, scouting_id: int):
    """DELETE /api/pest/scouting/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    s = await _get_owned_scouting(db, scouting_id, user['id'])
    if not s:
        return error_response("Scouting record not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    await db.delete('pest_scouting', 'id = ?', [scouting_id])
    return success_response(None, message="Scouting deleted")


# ============================================================
# TREATMENTS — LIST
# ============================================================
async def list_treatments(request, env):
    """GET /api/pest/treatments
    Query: farm_id?, plot_id?, product?, from?, to?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("t.farm_id = ?")
        params.append(to_int(farm_id))

    plot_id = url.search_params.get('plot_id')
    if plot_id:
        where.append("t.plot_id = ?")
        params.append(to_int(plot_id))

    product = url.search_params.get('product')
    if product:
        where.append("t.product LIKE ?")
        params.append(f"%{product}%")

    date_from = url.search_params.get('from')
    if date_from:
        where.append("t.application_date >= ?")
        params.append(date_from)

    date_to = url.search_params.get('to')
    if date_to:
        where.append("t.application_date <= ?")
        params.append(date_to)

    treatments = await db.query(f"""
        SELECT t.*,
               f.name as farm_name,
               p.name as plot_name,
               e.name as enterprise_name
        FROM treatments t
        JOIN farms f ON t.farm_id = f.id
        LEFT JOIN plots p ON t.plot_id = p.id
        LEFT JOIN enterprises e ON t.enterprise_id = e.id
        WHERE {' AND '.join(where)}
        ORDER BY t.application_date DESC, t.id DESC
        LIMIT 500
    """, params)

    return success_response(treatments)


# ============================================================
# TREATMENTS — CREATE
# ============================================================
async def create_treatment(request, env):
    """POST /api/pest/treatments"""
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    try:
        clean = validate_treatment(data)
    except ValidationError as e:
        return error_response(e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)
    farm = await _get_owned_farm(db, clean['farm_id'], user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    treatment_id = await db.insert('treatments', clean)

    # Auto-record as expense if cost provided
    total_cost = to_float(data.get('total_cost'))
    if total_cost > 0:
        await db.insert('transactions', {
            'farm_id': clean['farm_id'],
            'enterprise_id': clean.get('enterprise_id'),
            'type': 'expense',
            'category': 'chemicals',
            'description': f"{clean['product']} applied to {clean.get('target_pest', 'pest')}",
            'amount': total_cost,
            'transaction_date': clean['application_date'],
        })

    treatment = await db.query_one("""
        SELECT t.*, f.name as farm_name, p.name as plot_name
        FROM treatments t
        JOIN farms f ON t.farm_id = f.id
        LEFT JOIN plots p ON t.plot_id = p.id
        WHERE t.id = ?
    """, [treatment_id])

    log_event('treatment_created', {
        'treatment_id': treatment_id,
        'farmer_id': user['id'],
        'product': clean['product'],
    })

    return success_response(treatment, message="Treatment recorded", status=HTTP.CREATED)


# ============================================================
# PEST LIBRARY — LIST
# ============================================================
async def library(request, env):
    """GET /api/pest/library
    Query: type?, crop?, q?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["1=1"]
    params = []

    pest_type = url.search_params.get('type')
    if pest_type:
        where.append("type = ?")
        params.append(pest_type)

    crop = url.search_params.get('crop')
    if crop:
        where.append("affected_crops LIKE ?")
        params.append(f"%{crop}%")

    search = url.search_params.get('q')
    if search:
        where.append("(name LIKE ? OR scientific_name LIKE ? OR symptoms LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])

    items = await db.query(f"""
        SELECT * FROM pest_library
        WHERE {' AND '.join(where)}
        ORDER BY name
        LIMIT 200
    """, params)

    return success_response(items)


# ============================================================
# PEST LIBRARY — SINGLE
# ============================================================
async def library_item(request, env, item_id: int):
    """GET /api/pest/library/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    item = await db.query_one("SELECT * FROM pest_library WHERE id = ?", [item_id])
    if not item:
        return error_response("Pest not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    return success_response(item)


# ============================================================
# AI DIAGNOSIS (placeholder — production uses Workers AI)
# ============================================================
async def diagnose(request, env):
    """POST /api/pest/diagnose
    Body: {farm_id?, photo_url?, crop?, symptoms?}
    In production: calls Workers AI vision model with the photo.
    For now: uses crop + symptoms to match against pest_library.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    photo_url = data.get('photo_url')
    crop = data.get('crop')
    symptoms = (data.get('symptoms') or '').lower()

    db = DB(env)

    # Search pest_library by crop + symptom keywords
    candidates = []
    if crop:
        candidates = await db.query(
            "SELECT * FROM pest_library WHERE affected_crops LIKE ? LIMIT 10",
            [f"%{crop}%"]
        )
    else:
        candidates = await db.query("SELECT * FROM pest_library LIMIT 20")

    # Score by symptom overlap
    scored = []
    symptom_words = [w.strip() for w in symptoms.split() if len(w) > 3]
    for pest in candidates:
        pest_symptoms = (pest.get('symptoms') or '').lower()
        score = sum(1 for w in symptom_words if w in pest_symptoms)
        if score > 0 or not symptom_words:
            scored.append((score, pest))

    scored.sort(key=lambda x: -x[0])
    top = scored[:3]

    if not top:
        return success_response({
            'diagnosis': None,
            'message': 'No matching pests found. Try adding more symptoms or a clearer photo.',
            'confidence': 0,
        })

    matches = []
    for score, pest in top:
        confidence = min(round(50 + score * 12, 1), 95)
        matches.append({
            'pest_name': pest['name'],
            'scientific_name': pest.get('scientific_name'),
            'type': pest.get('type'),
            'symptoms': pest.get('symptoms'),
            'treatment_organic': pest.get('treatment_organic'),
            'treatment_chemical': pest.get('treatment_chemical'),
            'prevention': pest.get('prevention'),
            'confidence': confidence,
        })

    log_event('pest_diagnosis', {
        'farmer_id': user['id'],
        'crop': crop,
        'top_match': matches[0]['pest_name'] if matches else None,
    })

    return success_response({
        'diagnosis': matches[0] if matches else None,
        'alternatives': matches[1:] if len(matches) > 1 else [],
        'disclaimer': 'AI-assisted diagnosis. Confirm with your local extension officer for severe cases.',
    })


# ============================================================
# OUTBREAK ALERTS (regional)
# ============================================================
async def alerts(request, env):
    """GET /api/pest/alerts
    Query: farm_id?
    Returns pests reported nearby in the last 30 days.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    farm_id = url.search_params.get('farm_id')
    if not farm_id:
        return error_response("'farm_id' is required",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    farm = await db.query_one("""
        SELECT county FROM farms WHERE id = ? AND farmer_id = ?
    """, [to_int(farm_id), user['id']])

    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    county = farm.get('county')
    if not county:
        return success_response({
            'county': None,
            'alerts': [],
            'message': 'Set your farm county to receive regional pest alerts.',
        })

    # Aggregate scouting by pest in same county over last 30 days
    alerts = await db.query("""
        SELECT ps.pest_name,
               COUNT(*) as report_count,
               MAX(ps.severity) as max_severity,
               MAX(ps.scout_date) as last_seen,
               GROUP_CONCAT(DISTINCT ps.pest_type) as types
        FROM pest_scouting ps
        JOIN farms f ON ps.farm_id = f.id
        WHERE f.county = ?
        AND ps.scout_date >= date('now', '-30 days')
        GROUP BY ps.pest_name
        ORDER BY report_count DESC
        LIMIT 10
    """, [county])

    return success_response({
        'county': county,
        'period_days': 30,
        'alerts': alerts,
        'count': len(alerts),
    })


# ============================================================
# CHEMICAL INVENTORY
# ============================================================
async def inventory(request, env):
    """GET /api/pest/inventory
    Query: farm_id?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)
    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("ci.farm_id = ?")
        params.append(to_int(farm_id))

    items = await db.query(f"""
        SELECT ci.*, f.name as farm_name,
            CASE
                WHEN ci.expiry_date < date('now') THEN 'expired'
                WHEN ci.expiry_date < date('now', '+60 days') THEN 'expiring_soon'
                ELSE 'ok'
            END as expiry_status
        FROM chemical_inventory ci
        JOIN farms f ON ci.farm_id = f.id
        WHERE {' AND '.join(where)}
        ORDER BY ci.expiry_date NULLS LAST, ci.product_name
    """, params)

    return success_response(items)


async def add_inventory(request, env):
    """POST /api/pest/inventory"""
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ['farm_id', 'product_name'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    db = DB(env)
    farm = await _get_owned_farm(db, to_int(data['farm_id']), user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    inv_id = await db.insert('chemical_inventory', {
        'farm_id': to_int(data['farm_id']),
        'product_name': data['product_name'],
        'active_ingredient': data.get('active_ingredient'),
        'category': data.get('category'),
        'quantity_in_stock': to_float(data.get('quantity_in_stock')) or None,
        'unit': data.get('unit'),
        'purchase_date': data.get('purchase_date'),
        'purchase_cost': to_float(data.get('purchase_cost')) or None,
        'expiry_date': data.get('expiry_date'),
        'storage_location': data.get('storage_location'),
        'safety_notes': data.get('safety_notes'),
    })

    item = await db.query_one("SELECT * FROM chemical_inventory WHERE id = ?", [inv_id])
    return success_response(item, message="Chemical added to inventory", status=HTTP.CREATED)


# ============================================================
# IPM PRACTICES
# ============================================================
async def list_ipm(request, env):
    """GET /api/pest/ipm
    Query: farm_id?, plot_id?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)
    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("i.farm_id = ?")
        params.append(to_int(farm_id))

    plot_id = url.search_params.get('plot_id')
    if plot_id:
        where.append("i.plot_id = ?")
        params.append(to_int(plot_id))

    practices = await db.query(f"""
        SELECT i.*, f.name as farm_name, p.name as plot_name
        FROM ipm_practices i
        JOIN farms f ON i.farm_id = f.id
        LEFT JOIN plots p ON i.plot_id = p.id
        WHERE {' AND '.join(where)}
        ORDER BY i.applied_date DESC
        LIMIT 200
    """, params)

    return success_response(practices)


async def add_ipm(request, env):
    """POST /api/pest/ipm"""
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ['farm_id', 'practice_type', 'applied_date'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    db = DB(env)
    farm = await _get_owned_farm(db, to_int(data['farm_id']), user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    ipm_id = await db.insert('ipm_practices', {
        'farm_id': to_int(data['farm_id']),
        'plot_id': to_int(data.get('plot_id')) or None,
        'practice_type': data['practice_type'],
        'description': data.get('description'),
        'applied_date': data['applied_date'],
        'effectiveness': data.get('effectiveness'),
        'notes': data.get('notes'),
    })

    practice = await db.query_one("SELECT * FROM ipm_practices WHERE id = ?", [ipm_id])
    return success_response(practice, message="IPM practice logged", status=HTTP.CREATED)


# ============================================================
# PEST DASHBOARD
# ============================================================
async def pest_dashboard(request, env):
    """GET /api/pest/dashboard
    Query: farm_id?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("ps.farm_id = ?")
        params.append(to_int(farm_id))

    where_sql = ' AND '.join(where)

    # Scouting stats
    scouting_stats = await db.query_one(f"""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN ps.severity IN ('high','critical') THEN 1 END) as severe,
            COUNT(CASE WHEN ps.scout_date >= date('now', '-30 days') THEN 1 END) as last_30_days
        FROM pest_scouting ps
        JOIN farms f ON ps.farm_id = f.id
        WHERE {where_sql}
    """, params)

    # Top pests
    top_pests = await db.query(f"""
        SELECT ps.pest_name, COUNT(*) as count, MAX(ps.severity) as max_severity
        FROM pest_scouting ps
        JOIN farms f ON ps.farm_id = f.id
        WHERE {where_sql}
        GROUP BY ps.pest_name
        ORDER BY count DESC
        LIMIT 5
    """, params)

    # Recent treatments
    recent_treatments = await db.query(f"""
        SELECT t.id, t.product, t.application_date, t.target_pest, t.total_cost
        FROM treatments t
        JOIN farms f ON t.farm_id = f.id
        WHERE f.farmer_id = ?
        ORDER BY t.application_date DESC
        LIMIT 5
    """, [user['id']])

    # Chemical inventory expiring soon
    expiring = await db.query(f"""
        SELECT ci.product_name, ci.expiry_date, ci.quantity_in_stock, ci.unit
        FROM chemical_inventory ci
        JOIN farms f ON ci.farm_id = f.id
        WHERE f.farmer_id = ?
        AND ci.expiry_date IS NOT NULL
        AND ci.expiry_date < date('now', '+60 days')
        ORDER BY ci.expiry_date ASC
        LIMIT 5
    """, [user['id']])

    return success_response({
        'scouting': scouting_stats,
        'top_pests': top_pests,
        'recent_treatments': recent_treatments,
        'expiring_chemicals': expiring,
    })