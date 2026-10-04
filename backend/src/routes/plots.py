"""
Marcbantu Africa — Plot routes.
Plots are fields/parcels inside a farm.
"""
from utils import (
    success_response, error_response, parse_json, require_auth,
    now_iso, to_int, to_float, log_event, require_fields,
)
from constants import HTTP, ErrorCode
from db import DB


# ============================================================
# HELPERS
# ============================================================
async def _get_owned_farm(db: DB, farm_id: int, farmer_id: int) -> dict | None:
    return await db.query_one(
        "SELECT id FROM farms WHERE id = ? AND farmer_id = ?",
        [farm_id, farmer_id]
    )


async def _get_owned_plot(db: DB, plot_id: int, farmer_id: int) -> dict | None:
    return await db.query_one("""
        SELECT p.* FROM plots p
        JOIN farms f ON p.farm_id = f.id
        WHERE p.id = ? AND f.farmer_id = ?
    """, [plot_id, farmer_id])


# ============================================================
# LIST PLOTS
# ============================================================
async def list_plots(request, env, farm_id: int):
    """GET /api/farms/:id/plots"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    farm = await _get_owned_farm(db, farm_id, user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    plots = await db.query("""
        SELECT p.*,
            (SELECT COUNT(*) FROM records WHERE plot_id = p.id) as record_count
        FROM plots p
        WHERE p.farm_id = ?
        ORDER BY p.active DESC, p.name
    """, [farm_id])

    return success_response(plots)


# ============================================================
# CREATE PLOT
# ============================================================
async def create_plot(request, env, farm_id: int):
    """POST /api/farms/:id/plots
    Body: {name, size_acres?, latitude?, longitude?, soil_type?, soil_ph?,
           irrigation_type?, current_crop?, notes?}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    farm = await _get_owned_farm(db, farm_id, user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    data = await parse_json(request)
    err_msg = require_fields(data, ['name'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    plot_id = await db.insert('plots', {
        'farm_id': farm_id,
        'name': str(data['name']).strip(),
        'size_acres': to_float(data.get('size_acres')) or None,
        'latitude': to_float(data.get('latitude')) or None,
        'longitude': to_float(data.get('longitude')) or None,
        'soil_type': data.get('soil_type'),
        'soil_ph': to_float(data.get('soil_ph')) or None,
        'irrigation_type': data.get('irrigation_type'),
        'current_crop': data.get('current_crop'),
        'notes': data.get('notes'),
        'active': 1,
    })

    plot = await db.query_one("SELECT * FROM plots WHERE id = ?", [plot_id])

    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': 'plot_created',
        'entity': 'plot',
        'entity_id': plot_id,
        'details': data['name'],
    })

    return success_response(plot, message="Plot created successfully", status=HTTP.CREATED)


# ============================================================
# GET PLOT
# ============================================================
async def get_plot(request, env, plot_id: int):
    """GET /api/plots/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    plot = await _get_owned_plot(db, plot_id, user['id'])
    if not plot:
        return error_response("Plot not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # Recent records for this plot
    plot['recent_records'] = await db.query("""
        SELECT id, record_type, activity, description, record_date
        FROM records WHERE plot_id = ?
        ORDER BY record_date DESC LIMIT 10
    """, [plot_id])

    # Pest scouting on this plot
    plot['pest_scouting'] = await db.query("""
        SELECT id, pest_name, severity, scout_date
        FROM pest_scouting WHERE plot_id = ?
        ORDER BY scout_date DESC LIMIT 5
    """, [plot_id])

    return success_response(plot)


# ============================================================
# UPDATE PLOT
# ============================================================
async def update_plot(request, env, plot_id: int):
    """PUT /api/plots/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    plot = await _get_owned_plot(db, plot_id, user['id'])
    if not plot:
        return error_response("Plot not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    data = await parse_json(request)

    allowed = ['name', 'size_acres', 'latitude', 'longitude', 'soil_type',
               'soil_ph', 'irrigation_type', 'current_crop', 'notes']
    updates = {}
    for k in allowed:
        if k in data:
            if k in ('size_acres', 'latitude', 'longitude', 'soil_ph'):
                updates[k] = to_float(data[k]) or None
            elif k == 'name':
                updates[k] = str(data[k]).strip()
            else:
                updates[k] = data[k]

    if 'active' in data:
        updates['active'] = 1 if data['active'] else 0

    if not updates:
        return error_response("No valid fields to update", status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    updates['updated_at'] = now_iso()
    await db.update('plots', updates, 'id = ?', [plot_id])

    updated = await db.query_one("SELECT * FROM plots WHERE id = ?", [plot_id])

    return success_response(updated, message="Plot updated")


# ============================================================
# DELETE PLOT
# ============================================================
async def delete_plot(request, env, plot_id: int):
    """DELETE /api/plots/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    plot = await _get_owned_plot(db, plot_id, user['id'])
    if not plot:
        return error_response("Plot not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    record_count = await db.count('records', 'plot_id = ?', [plot_id])

    if record_count > 0:
        await db.update('plots', {
            'active': 0,
            'updated_at': now_iso(),
        }, 'id = ?', [plot_id])
        message = f"Plot archived (has {record_count} records)"
    else:
        await db.delete('plots', 'id = ?', [plot_id])
        message = "Plot deleted"

    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': 'plot_deleted',
        'entity': 'plot',
        'entity_id': plot_id,
    })

    return success_response(None, message=message)