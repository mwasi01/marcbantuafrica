"""
Marcbantu Africa — Operations routes.
Tasks, workers, attendance, equipment, equipment maintenance.
"""
from utils import (
    success_response, error_response, parse_json, require_auth,
    now_iso, to_int, to_float, log_event, require_fields,
    paginated_response,
)
from validators import (
    ValidationError,
    validate_task, validate_worker, validate_attendance, validate_equipment,
)
from constants import HTTP, ErrorCode, Priority, TaskStatus
from db import DB


# ============================================================
# HELPERS
# ============================================================
async def _get_owned_farm(db: DB, farm_id: int, farmer_id: int):
    return await db.query_one(
        "SELECT id FROM farms WHERE id = ? AND farmer_id = ?",
        [farm_id, farmer_id]
    )


async def _get_owned_task(db: DB, task_id: int, farmer_id: int):
    return await db.query_one("""
        SELECT t.* FROM tasks t
        JOIN farms f ON t.farm_id = f.id
        WHERE t.id = ? AND f.farmer_id = ?
    """, [task_id, farmer_id])


async def _get_owned_worker(db: DB, worker_id: int, farmer_id: int):
    return await db.query_one("""
        SELECT w.* FROM workers w
        JOIN farms f ON w.farm_id = f.id
        WHERE w.id = ? AND f.farmer_id = ?
    """, [worker_id, farmer_id])


async def _get_owned_equipment(db: DB, equipment_id: int, farmer_id: int):
    return await db.query_one("""
        SELECT e.* FROM equipment e
        JOIN farms f ON e.farm_id = f.id
        WHERE e.id = ? AND f.farmer_id = ?
    """, [equipment_id, farmer_id])


# ============================================================
# TASKS — LIST
# ============================================================
async def list_tasks(request, env):
    """GET /api/tasks
    Query: farm_id?, status?, priority?, assigned_to?, overdue?, from?, to?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = request.url

    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("t.farm_id = ?")
        params.append(to_int(farm_id))

    status = url.search_params.get('status')
    if status:
        where.append("t.status = ?")
        params.append(status)

    priority = url.search_params.get('priority')
    if priority:
        where.append("t.priority = ?")
        params.append(priority)

    assigned_to = url.search_params.get('assigned_to')
    if assigned_to:
        where.append("t.assigned_to = ?")
        params.append(to_int(assigned_to))

    if url.search_params.get('overdue') == 'true':
        where.append("t.due_date < date('now') AND t.status NOT IN ('completed', 'cancelled')")

    date_from = url.search_params.get('from')
    if date_from:
        where.append("t.due_date >= ?")
        params.append(date_from)

    date_to = url.search_params.get('to')
    if date_to:
        where.append("t.due_date <= ?")
        params.append(date_to)

    where_sql = ' AND '.join(where)

    tasks = await db.query(f"""
        SELECT t.*,
               f.name as farm_name,
               e.name as enterprise_name,
               w.name as assigned_to_name
        FROM tasks t
        JOIN farms f ON t.farm_id = f.id
        LEFT JOIN enterprises e ON t.enterprise_id = e.id
        LEFT JOIN workers w ON t.assigned_to = w.id
        WHERE {where_sql}
        ORDER BY
            CASE t.status
                WHEN 'in_progress' THEN 1
                WHEN 'pending' THEN 2
                WHEN 'completed' THEN 3
                ELSE 4
            END,
            CASE t.priority
                WHEN 'urgent' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                ELSE 4
            END,
            t.due_date ASC NULLS LAST,
            t.id DESC
    """, params)

    return success_response(tasks)


# ============================================================
# TASKS — CREATE
# ============================================================
async def create_task(request, env):
    """POST /api/tasks"""
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    try:
        clean = validate_task(data)
    except ValidationError as e:
        return error_response(e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)
    farm = await _get_owned_farm(db, clean['farm_id'], user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # Validate worker belongs to same farm
    if clean.get('assigned_to'):
        worker = await db.query_one(
            "SELECT id FROM workers WHERE id = ? AND farm_id = ?",
            [clean['assigned_to'], clean['farm_id']]
        )
        if not worker:
            clean['assigned_to'] = None

    task_id = await db.insert('tasks', clean)

    task = await db.query_one("""
        SELECT t.*, f.name as farm_name, e.name as enterprise_name, w.name as assigned_to_name
        FROM tasks t
        JOIN farms f ON t.farm_id = f.id
        LEFT JOIN enterprises e ON t.enterprise_id = e.id
        LEFT JOIN workers w ON t.assigned_to = w.id
        WHERE t.id = ?
    """, [task_id])

    log_event('task_created', {'task_id': task_id, 'farmer_id': user['id']})

    return success_response(task, message="Task created", status=HTTP.CREATED)


# ============================================================
# TASKS — GET
# ============================================================
async def get_task(request, env, task_id: int):
    """GET /api/tasks/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    task = await db.query_one("""
        SELECT t.*,
               f.name as farm_name,
               e.name as enterprise_name,
               p.name as plot_name,
               w.name as assigned_to_name,
               w.phone as assigned_to_phone
        FROM tasks t
        JOIN farms f ON t.farm_id = f.id
        LEFT JOIN enterprises e ON t.enterprise_id = e.id
        LEFT JOIN plots p ON t.plot_id = p.id
        LEFT JOIN workers w ON t.assigned_to = w.id
        WHERE t.id = ? AND f.farmer_id = ?
    """, [task_id, user['id']])

    if not task:
        return error_response("Task not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    return success_response(task)


# ============================================================
# TASKS — UPDATE
# ============================================================
async def update_task(request, env, task_id: int):
    """PUT /api/tasks/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    task = await _get_owned_task(db, task_id, user['id'])
    if not task:
        return error_response("Task not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    data = await parse_json(request)
    updates = {}

    if 'title' in data:
        updates['title'] = str(data['title']).strip()
    if 'description' in data:
        updates['description'] = data['description']
    if 'priority' in data:
        if data['priority'] not in Priority.ALL:
            return error_response("Invalid priority", status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)
        updates['priority'] = data['priority']
    if 'status' in data:
        if data['status'] not in TaskStatus.ALL:
            return error_response("Invalid status", status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)
        updates['status'] = data['status']
        if data['status'] == 'completed':
            updates['completed_at'] = now_iso()
    if 'due_date' in data:
        updates['due_date'] = data['due_date']
    if 'assigned_to' in data:
        updates['assigned_to'] = to_int(data['assigned_to']) or None
    if 'enterprise_id' in data:
        updates['enterprise_id'] = to_int(data['enterprise_id']) or None
    if 'plot_id' in data:
        updates['plot_id'] = to_int(data['plot_id']) or None

    if not updates:
        return error_response("No valid fields to update",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    updates['updated_at'] = now_iso()
    await db.update('tasks', updates, 'id = ?', [task_id])

    updated = await db.query_one("""
        SELECT t.*, f.name as farm_name, w.name as assigned_to_name
        FROM tasks t
        JOIN farms f ON t.farm_id = f.id
        LEFT JOIN workers w ON t.assigned_to = w.id
        WHERE t.id = ?
    """, [task_id])

    return success_response(updated, message="Task updated")


# ============================================================
# TASKS — DELETE
# ============================================================
async def delete_task(request, env, task_id: int):
    """DELETE /api/tasks/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    task = await _get_owned_task(db, task_id, user['id'])
    if not task:
        return error_response("Task not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    await db.delete('tasks', 'id = ?', [task_id])

    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': 'task_deleted',
        'entity': 'task',
        'entity_id': task_id,
    })

    return success_response(None, message="Task deleted")


# ============================================================
# TASKS — COMPLETE
# ============================================================
async def complete_task(request, env, task_id: int):
    """POST /api/tasks/:id/complete"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    task = await _get_owned_task(db, task_id, user['id'])
    if not task:
        return error_response("Task not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    if task['status'] == 'completed':
        return error_response("Task is already completed",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.CONFLICT)

    await db.update('tasks', {
        'status': 'completed',
        'completed_at': now_iso(),
        'updated_at': now_iso(),
    }, 'id = ?', [task_id])

    return success_response(None, message="Task marked complete")


# ============================================================
# WORKERS — LIST
# ============================================================
async def list_workers(request, env):
    """GET /api/workers
    Query: farm_id?, active=1
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = request.url

    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("w.farm_id = ?")
        params.append(to_int(farm_id))

    if url.search_params.get('active', '1') == '1':
        where.append("w.active = 1")

    workers = await db.query(f"""
        SELECT w.*, f.name as farm_name,
            (SELECT COUNT(*) FROM attendance WHERE worker_id = w.id AND date = date('now')) as attended_today
        FROM workers w
        JOIN farms f ON w.farm_id = f.id
        WHERE {' AND '.join(where)}
        ORDER BY w.active DESC, w.name
    """, params)

    return success_response(workers)


# ============================================================
# WORKERS — CREATE
# ============================================================
async def create_worker(request, env):
    """POST /api/workers"""
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    try:
        clean = validate_worker(data)
    except ValidationError as e:
        return error_response(e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)
    farm = await _get_owned_farm(db, clean['farm_id'], user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    clean['active'] = 1
    worker_id = await db.insert('workers', clean)

    worker = await db.query_one("SELECT * FROM workers WHERE id = ?", [worker_id])

    log_event('worker_created', {'worker_id': worker_id, 'farmer_id': user['id']})

    return success_response(worker, message="Worker added", status=HTTP.CREATED)


# ============================================================
# WORKERS — UPDATE
# ============================================================
async def update_worker(request, env, worker_id: int):
    """PUT /api/workers/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    worker = await _get_owned_worker(db, worker_id, user['id'])
    if not worker:
        return error_response("Worker not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    data = await parse_json(request)
    allowed = ['name', 'phone', 'role', 'wage_type', 'wage_amount', 'active', 'notes']
    updates = {}
    for k in allowed:
        if k in data:
            if k == 'wage_amount':
                updates[k] = to_float(data[k]) or None
            elif k == 'active':
                updates[k] = 1 if data[k] else 0
            elif k == 'name':
                updates[k] = str(data[k]).strip()
            else:
                updates[k] = data[k]

    if not updates:
        return error_response("No valid fields to update",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    updates['updated_at'] = now_iso()
    await db.update('workers', updates, 'id = ?', [worker_id])

    updated = await db.query_one("SELECT * FROM workers WHERE id = ?", [worker_id])

    return success_response(updated, message="Worker updated")


# ============================================================
# WORKERS — DELETE
# ============================================================
async def delete_worker(request, env, worker_id: int):
    """DELETE /api/workers/:id — soft delete"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    worker = await _get_owned_worker(db, worker_id, user['id'])
    if not worker:
        return error_response("Worker not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # Soft delete: mark inactive (preserves attendance history)
    await db.update('workers', {
        'active': 0,
        'end_date': now_iso()[:10],
        'updated_at': now_iso(),
    }, 'id = ?', [worker_id])

    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': 'worker_deactivated',
        'entity': 'worker',
        'entity_id': worker_id,
    })

    return success_response(None, message="Worker deactivated")


# ============================================================
# ATTENDANCE — RECORD
# ============================================================
async def record_attendance(request, env):
    """POST /api/attendance"""
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    try:
        clean = validate_attendance(data)
    except ValidationError as e:
        return error_response(e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)
    farm = await _get_owned_farm(db, clean['farm_id'], user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # Validate worker belongs to farm
    worker = await db.query_one(
        "SELECT id FROM workers WHERE id = ? AND farm_id = ?",
        [clean['worker_id'], clean['farm_id']]
    )
    if not worker:
        return error_response("Worker does not belong to this farm",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    # Upsert: unique constraint on (worker_id, date)
    existing = await db.query_one(
        "SELECT id FROM attendance WHERE worker_id = ? AND date = ?",
        [clean['worker_id'], clean['date']]
    )

    if existing:
        await db.update('attendance', {
            'status': clean['status'],
            'hours': clean.get('hours'),
            'notes': clean.get('notes'),
        }, 'id = ?', [existing['id']])
        att_id = existing['id']
        message = "Attendance updated"
    else:
        att_id = await db.insert('attendance', clean)
        message = "Attendance recorded"

    att = await db.query_one("""
        SELECT a.*, w.name as worker_name
        FROM attendance a
        JOIN workers w ON a.worker_id = w.id
        WHERE a.id = ?
    """, [att_id])

    return success_response(att, message=message, status=HTTP.CREATED if not existing else HTTP.OK)


# ============================================================
# ATTENDANCE — LIST
# ============================================================
async def list_attendance(request, env):
    """GET /api/attendance
    Query: farm_id?, worker_id?, from?, to?, date?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = request.url

    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("a.farm_id = ?")
        params.append(to_int(farm_id))

    worker_id = url.search_params.get('worker_id')
    if worker_id:
        where.append("a.worker_id = ?")
        params.append(to_int(worker_id))

    date_filter = url.search_params.get('date')
    if date_filter:
        where.append("a.date = ?")
        params.append(date_filter)

    date_from = url.search_params.get('from')
    if date_from:
        where.append("a.date >= ?")
        params.append(date_from)

    date_to = url.search_params.get('to')
    if date_to:
        where.append("a.date <= ?")
        params.append(date_to)

    records = await db.query(f"""
        SELECT a.*, w.name as worker_name, w.role as worker_role
        FROM attendance a
        JOIN workers w ON a.worker_id = w.id
        JOIN farms f ON a.farm_id = f.id
        WHERE {' AND '.join(where)}
        ORDER BY a.date DESC, w.name
        LIMIT 500
    """, params)

    return success_response(records)


# ============================================================
# EQUIPMENT — LIST
# ============================================================
async def list_equipment(request, env):
    """GET /api/equipment
    Query: farm_id?, status?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = request.url

    where = ["f.farmer_id = ?"]
    params = [user['id']]

    farm_id = url.search_params.get('farm_id')
    if farm_id:
        where.append("e.farm_id = ?")
        params.append(to_int(farm_id))

    status = url.search_params.get('status')
    if status:
        where.append("e.status = ?")
        params.append(status)

    equipment = await db.query(f"""
        SELECT e.*, f.name as farm_name,
            CASE
                WHEN e.next_service_date < date('now') THEN 'overdue'
                WHEN e.next_service_date < date('now', '+30 days') THEN 'due_soon'
                ELSE 'ok'
            END as service_urgency
        FROM equipment e
        JOIN farms f ON e.farm_id = f.id
        WHERE {' AND '.join(where)}
        ORDER BY
            CASE
                WHEN e.next_service_date < date('now') THEN 1
                WHEN e.next_service_date < date('now', '+30 days') THEN 2
                ELSE 3
            END,
            e.name
    """, params)

    return success_response(equipment)


# ============================================================
# EQUIPMENT — CREATE
# ============================================================
async def create_equipment(request, env):
    """POST /api/equipment"""
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    try:
        clean = validate_equipment(data)
    except ValidationError as e:
        return error_response(e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)
    farm = await _get_owned_farm(db, clean['farm_id'], user['id'])
    if not farm:
        return error_response("Farm not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    equipment_id = await db.insert('equipment', clean)
    eq = await db.query_one("SELECT * FROM equipment WHERE id = ?", [equipment_id])

    log_event('equipment_created', {'equipment_id': equipment_id, 'farmer_id': user['id']})

    return success_response(eq, message="Equipment added", status=HTTP.CREATED)


# ============================================================
# EQUIPMENT — UPDATE
# ============================================================
async def update_equipment(request, env, equipment_id: int):
    """PUT /api/equipment/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    eq = await _get_owned_equipment(db, equipment_id, user['id'])
    if not eq:
        return error_response("Equipment not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    data = await parse_json(request)
    allowed = ['name', 'type', 'make', 'model', 'serial_number', 'purchase_date',
               'purchase_cost', 'current_value', 'last_service_date', 'next_service_date',
               'service_interval_days', 'hours_used', 'fuel_type', 'status', 'notes']
    updates = {}
    for k in allowed:
        if k in data:
            if k in ('purchase_cost', 'current_value', 'hours_used'):
                updates[k] = to_float(data[k]) or None
            elif k == 'service_interval_days':
                updates[k] = to_int(data[k]) or None
            elif k == 'name':
                updates[k] = str(data[k]).strip()
            else:
                updates[k] = data[k]

    if not updates:
        return error_response("No valid fields to update",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    updates['updated_at'] = now_iso()
    await db.update('equipment', updates, 'id = ?', [equipment_id])

    updated = await db.query_one("SELECT * FROM equipment WHERE id = ?", [equipment_id])
    return success_response(updated, message="Equipment updated")


# ============================================================
# EQUIPMENT — LOG MAINTENANCE
# ============================================================
async def log_maintenance(request, env, equipment_id: int):
    """POST /api/equipment/:id/maintenance"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    eq = await _get_owned_equipment(db, equipment_id, user['id'])
    if not eq:
        return error_response("Equipment not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    data = await parse_json(request)
    err_msg = require_fields(data, ['maintenance_date'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    maintenance_id = await db.insert('equipment_maintenance', {
        'equipment_id': equipment_id,
        'maintenance_type': data.get('maintenance_type'),
        'description': data.get('description'),
        'cost': to_float(data.get('cost')),
        'maintenance_date': data['maintenance_date'],
        'performed_by': data.get('performed_by'),
        'next_service_date': data.get('next_service_date'),
        'notes': data.get('notes'),
    })

    # Update equipment last_service_date and status
    updates = {
        'last_service_date': data['maintenance_date'],
        'updated_at': now_iso(),
    }
    if data.get('next_service_date'):
        updates['next_service_date'] = data['next_service_date']
    if eq['status'] in ('needs_service', 'broken'):
        updates['status'] = 'good'
    await db.update('equipment', updates, 'id = ?', [equipment_id])

    # If a cost was recorded, create an expense transaction
    if to_float(data.get('cost')) > 0:
        await db.insert('transactions', {
            'farm_id': eq['farm_id'],
            'type': 'expense',
            'category': 'equipment',
            'description': f"Maintenance: {eq['name']} — {data.get('description', 'service')}",
            'amount': to_float(data['cost']),
            'transaction_date': data['maintenance_date'],
            'created_by': user['id'],
        })

    maintenance = await db.query_one(
        "SELECT * FROM equipment_maintenance WHERE id = ?",
        [maintenance_id]
    )

    log_event('maintenance_logged', {
        'equipment_id': equipment_id,
        'maintenance_id': maintenance_id,
        'farmer_id': user['id'],
    })

    return success_response(maintenance, message="Maintenance logged", status=HTTP.CREATED)


# ============================================================
# OPERATIONS DASHBOARD
# ============================================================
async def operations_dashboard(request, env):
    """GET /api/operations/dashboard
    Query: farm_id?
    Returns tasks, workers, equipment summary.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = request.url
    farm_id = url.search_params.get('farm_id')

    farm_filter = ""
    params = [user['id']]
    if farm_id:
        farm_filter = " AND t.farm_id = ?"
        params.append(to_int(farm_id))

    # Task summary
    task_stats = await db.query_one(f"""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN t.status = 'pending' THEN 1 END) as pending,
            COUNT(CASE WHEN t.status = 'in_progress' THEN 1 END) as in_progress,
            COUNT(CASE WHEN t.status = 'completed' THEN 1 END) as completed,
            COUNT(CASE WHEN t.due_date < date('now') AND t.status NOT IN ('completed','cancelled') THEN 1 END) as overdue
        FROM tasks t
        JOIN farms f ON t.farm_id = f.id
        WHERE f.farmer_id = ? {farm_filter}
    """, params)

    # Worker summary
    worker_params = [user['id']]
    worker_filter = ""
    if farm_id:
        worker_filter = " AND w.farm_id = ?"
        worker_params.append(to_int(farm_id))

    worker_stats = await db.query_one(f"""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN w.active = 1 THEN 1 END) as active
        FROM workers w
        JOIN farms f ON w.farm_id = f.id
        WHERE f.farmer_id = ? {worker_filter}
    """, worker_params)

    # Today's attendance
    att_params = [user['id']]
    att_filter = ""
    if farm_id:
        att_filter = " AND a.farm_id = ?"
        att_params.append(to_int(farm_id))

    today_attendance = await db.query_one(f"""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN a.status = 'present' THEN 1 END) as present,
            COUNT(CASE WHEN a.status = 'absent' THEN 1 END) as absent
        FROM attendance a
        JOIN farms f ON a.farm_id = f.id
        WHERE f.farmer_id = ? AND a.date = date('now') {att_filter}
    """, att_params)

    # Equipment summary
    eq_params = [user['id']]
    eq_filter = ""
    if farm_id:
        eq_filter = " AND e.farm_id = ?"
        eq_params.append(to_int(farm_id))

    equipment_stats = await db.query_one(f"""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN e.status = 'good' THEN 1 END) as good,
            COUNT(CASE WHEN e.status = 'needs_service' THEN 1 END) as needs_service,
            COUNT(CASE WHEN e.status = 'broken' THEN 1 END) as broken,
            COUNT(CASE WHEN e.next_service_date < date('now') THEN 1 END) as overdue_service
        FROM equipment e
        JOIN farms f ON e.farm_id = f.id
        WHERE f.farmer_id = ? {eq_filter}
    """, eq_params)

    # Today's tasks (top 5)
    today_params = [user['id']]
    today_filter = ""
    if farm_id:
        today_filter = " AND t.farm_id = ?"
        today_params.append(to_int(farm_id))

    today_tasks = await db.query(f"""
        SELECT t.id, t.title, t.priority, t.status, t.due_date, w.name as assigned_to_name
        FROM tasks t
        JOIN farms f ON t.farm_id = f.id
        LEFT JOIN workers w ON t.assigned_to = w.id
        WHERE f.farmer_id = ? {today_filter}
        AND t.status NOT IN ('completed', 'cancelled')
        AND t.due_date <= date('now', '+1 day')
        ORDER BY t.priority DESC, t.due_date ASC
        LIMIT 5
    """, today_params)

    return success_response({
        'tasks': task_stats,
        'workers': worker_stats,
        'attendance_today': today_attendance,
        'equipment': equipment_stats,
        'today_tasks': today_tasks,
    })