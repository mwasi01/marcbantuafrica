"""
Marcbantu Africa — Notification routes.
In-app notifications, device tokens for push, mark read, unread counts.
"""
from utils import (
    success_response, error_response, parse_json, require_auth,
    now_iso, to_int, log_event, require_fields,
)
from constants import HTTP, ErrorCode, NotificationType
from db import DB


# ============================================================
# LIST NOTIFICATIONS
# ============================================================
async def list_notifications(request, env):
    """GET /api/notifications
    Query: unread=true?, type?, limit=50
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = request.url

    where = ["farmer_id = ?"]
    params = [user['id']]

    if url.search_params.get('unread') == 'true':
        where.append("read = 0")

    n_type = url.search_params.get('type')
    if n_type:
        where.append("type = ?")
        params.append(n_type)

    limit = min(to_int(url.search_params.get('limit', 50), 50), 200)

    notifications = await db.query(f"""
        SELECT * FROM notifications
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC
        LIMIT ?
    """, params + [limit])

    # Unread count
    unread_count = await db.count('notifications', 'farmer_id = ? AND read = 0', [user['id']])

    return success_response({
        'notifications': notifications,
        'unread_count': unread_count,
    })


# ============================================================
# MARK READ
# ============================================================
async def mark_read(request, env, notification_id: int):
    """POST /api/notifications/:id/read"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    notification = await db.query_one(
        "SELECT id FROM notifications WHERE id = ? AND farmer_id = ?",
        [notification_id, user['id']]
    )
    if not notification:
        return error_response("Notification not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    await db.update('notifications', {
        'read': 1,
        'read_at': now_iso(),
    }, 'id = ?', [notification_id])

    return success_response(None, message="Marked as read")


async def mark_all_read(request, env):
    """POST /api/notifications/read-all"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    await db.execute("""
        UPDATE notifications SET read = 1, read_at = datetime('now')
        WHERE farmer_id = ? AND read = 0
    """, [user['id']])

    return success_response(None, message="All notifications marked as read")


# ============================================================
# DELETE NOTIFICATION
# ============================================================
async def delete_notification(request, env, notification_id: int):
    """DELETE /api/notifications/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    notification = await db.query_one(
        "SELECT id FROM notifications WHERE id = ? AND farmer_id = ?",
        [notification_id, user['id']]
    )
    if not notification:
        return error_response("Notification not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    await db.delete('notifications', 'id = ?', [notification_id])
    return success_response(None, message="Notification deleted")


# ============================================================
# REGISTER DEVICE (for push)
# ============================================================
async def register_device(request, env):
    """POST /api/notifications/register-device
    Body: {token, platform: 'web'|'android'|'ios'}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ['token'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    platform = data.get('platform', 'web')
    if platform not in ('web', 'android', 'ios'):
        return error_response("Invalid platform",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)

    existing = await db.query_one(
        "SELECT id FROM device_tokens WHERE token = ?",
        [data['token']]
    )

    if existing:
        await db.update('device_tokens', {
            'farmer_id': user['id'],
            'platform': platform,
            'user_agent': request.headers.get('User-Agent', '')[:200],
            'active': 1,
            'last_used_at': now_iso(),
        }, 'id = ?', [existing['id']])
        device_id = existing['id']
        message = "Device updated"
    else:
        device_id = await db.insert('device_tokens', {
            'farmer_id': user['id'],
            'token': data['token'],
            'platform': platform,
            'user_agent': request.headers.get('User-Agent', '')[:200],
            'active': 1,
            'last_used_at': now_iso(),
        })
        message = "Device registered"

    return success_response({'device_id': device_id}, message=message, status=HTTP.CREATED)


# ============================================================
# SEND PUSH NOTIFICATION
# ============================================================
async def send_push(request, env):
    """POST /api/notifications/push
    Body: {farmer_ids: [], title, message, url?}
    Admin-only in production.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ['title', 'message'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    farmer_ids = data.get('farmer_ids') or [user['id']]

    db = DB(env)
    sent = 0

    for fid in farmer_ids:
        # Create in-app notification
        await db.insert('notifications', {
            'farmer_id': fid,
            'type': data.get('type', 'system'),
            'title': data['title'],
            'message': data['message'],
            'action_url': data.get('url'),
            'priority': data.get('priority', 'normal'),
        })
        sent += 1

        # Queue push send to devices
        tokens = await db.query(
            "SELECT token, platform FROM device_tokens WHERE farmer_id = ? AND active = 1",
            [fid]
        )
        for t in tokens:
            try:
                await env.JOBS.send({
                    'type': 'send_push',
                    'payload': {
                        'token': t['token'],
                        'platform': t['platform'],
                        'title': data['title'],
                        'body': data['message'],
                        'url': data.get('url'),
                    },
                })
            except Exception:
                pass

    return success_response({'sent': sent}, message=f"Notification sent to {sent} farmers")


# ============================================================
# UNREAD COUNT
# ============================================================
async def unread_count(request, env):
    """GET /api/notifications/unread-count"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    count = await db.count('notifications', 'farmer_id = ? AND read = 0', [user['id']])

    # Breakdown by type
    by_type = await db.query("""
        SELECT type, COUNT(*) as count FROM notifications
        WHERE farmer_id = ? AND read = 0
        GROUP BY type
    """, [user['id']])

    return success_response({
        'unread_count': count,
        'by_type': by_type,
    })