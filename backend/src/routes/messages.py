"""
Marcbantu Africa — Direct Messages routes.
Farmer-to-farmer messaging.
"""
from utils import (
    success_response, error_response, parse_json, require_auth,
    now_iso, to_int, log_event, require_fields,
    paginated_response, _sp,
)
from constants import HTTP, ErrorCode
from db import DB


# ============================================================
# HELPERS
# ============================================================
def _normalize_pair(x: int, y: int):
    """Return (smaller, larger) so conversation pairs are unique."""
    return (x, y) if x < y else (y, x)


async def _get_or_create_conversation(db: DB, me: int, other: int):
    """Find or create the conversation between two farmers."""
    a, b = _normalize_pair(me, other)
    convo = await db.query_one(
        "SELECT * FROM conversations WHERE farmer_a = ? AND farmer_b = ?",
        [a, b]
    )
    if convo:
        return convo
    convo_id = await db.insert('conversations', {
        'farmer_a': a,
        'farmer_b': b,
    })
    return await db.query_one("SELECT * FROM conversations WHERE id = ?", [convo_id])


def _unread_for(convo: dict, me: int) -> int:
    """Return unread count for the current user."""
    if convo['farmer_a'] == me:
        return convo.get('unread_count_a') or 0
    return convo.get('unread_count_b') or 0


def _other_id(convo: dict, me: int) -> int:
    return convo['farmer_b'] if convo['farmer_a'] == me else convo['farmer_a']


# ============================================================
# LIST CONVERSATIONS (INBOX)
# ============================================================
async def list_conversations(request, env):
    """GET /api/messages/conversations
    Returns inbox sorted by last_message_at DESC.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    me = user['id']

    convos = await db.query("""
        SELECT * FROM conversations
        WHERE farmer_a = ? OR farmer_b = ?
        ORDER BY COALESCE(last_message_at, created_at) DESC
        LIMIT 100
    """, [me, me])

    if not convos:
        return success_response([])

    # Fetch the other farmers' info + last message bodies
    other_ids = list({_other_id(c, me) for c in convos})
    last_msg_ids = [c['last_message_id'] for c in convos if c.get('last_message_id')]

    placeholders_u = ','.join(['?'] * len(other_ids))
    users = await db.query(
        f"SELECT id, full_name, county, location FROM farmers WHERE id IN ({placeholders_u})",
        other_ids
    )
    users_map = {u['id']: u for u in users}

    last_map = {}
    if last_msg_ids:
        placeholders_m = ','.join(['?'] * len(last_msg_ids))
        msgs = await db.query(
            f"SELECT id, body, message_type, sender_id, created_at FROM messages WHERE id IN ({placeholders_m})",
            last_msg_ids
        )
        last_map = {m['id']: m for m in msgs}

    result = []
    for c in convos:
        other = users_map.get(_other_id(c, me), {})
        last = last_map.get(c.get('last_message_id'))
        result.append({
            'id': c['id'],
            'other_user': {
                'id': other.get('id'),
                'full_name': other.get('full_name', 'Farmer'),
                'county': other.get('county'),
                'location': other.get('location'),
            },
            'last_message': last,
            'unread_count': _unread_for(c, me),
            'last_message_at': c.get('last_message_at') or c.get('created_at'),
        })

    return success_response(result)


# ============================================================
# START A CONVERSATION WITH A FARMER
# ============================================================
async def start_conversation(request, env):
    """POST /api/messages/conversations
    Body: {farmer_id}
    Returns the existing or newly created conversation with that farmer.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ['farmer_id'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    other_id = to_int(data['farmer_id'])
    if other_id == user['id']:
        return error_response("Cannot message yourself",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)
    other = await db.query_one(
        "SELECT id, full_name, county, location FROM farmers WHERE id = ?",
        [other_id]
    )
    if not other:
        return error_response("Farmer not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    convo = await _get_or_create_conversation(db, user['id'], other_id)

    return success_response({
        'id': convo['id'],
        'other_user': {
            'id': other['id'],
            'full_name': other.get('full_name', 'Farmer'),
            'county': other.get('county'),
            'location': other.get('location'),
        },
        'unread_count': _unread_for(convo, user['id']),
    })


# ============================================================
# GET ONE CONVERSATION
# ============================================================
async def get_conversation(request, env, convo_id: int):
    """GET /api/messages/conversations/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    me = user['id']
    convo = await db.query_one("SELECT * FROM conversations WHERE id = ?", [convo_id])
    if not convo:
        return error_response("Conversation not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)
    if convo['farmer_a'] != me and convo['farmer_b'] != me:
        return error_response("Not authorized", status=HTTP.FORBIDDEN, code=ErrorCode.FORBIDDEN)

    other_id = _other_id(convo, me)
    other = await db.query_one(
        "SELECT id, full_name, county, location FROM farmers WHERE id = ?",
        [other_id]
    )

    return success_response({
        'id': convo['id'],
        'other_user': {
            'id': other['id'],
            'full_name': other.get('full_name', 'Farmer'),
            'county': other.get('county'),
            'location': other.get('location'),
        },
        'unread_count': _unread_for(convo, me),
    })


# ============================================================
# LIST MESSAGES IN A CONVERSATION (and mark as read)
# ============================================================
async def list_messages(request, env, convo_id: int):
    """GET /api/messages/conversations/:id/messages?page=1&page_size=50
    Marks all unread messages as read (for the current user).
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    me = user['id']
    convo = await db.query_one("SELECT * FROM conversations WHERE id = ?", [convo_id])
    if not convo:
        return error_response("Conversation not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)
    if convo['farmer_a'] != me and convo['farmer_b'] != me:
        return error_response("Not authorized", status=HTTP.FORBIDDEN, code=ErrorCode.FORBIDDEN)

    url = _sp(request)
    page = to_int(url.search_params.get('page', 1), 1)
    page_size = min(to_int(url.search_params.get('page_size', 50), 50), 100)

    # Fetch messages (paginated)
    sql = """
        SELECT m.id, m.sender_id, m.body, m.message_type, m.media_url,
               m.read_at, m.created_at,
               f.full_name as sender_name
        FROM messages m
        JOIN farmers f ON m.sender_id = f.id
        WHERE m.conversation_id = ?
        ORDER BY m.created_at DESC
    """
    result = await db.paginate(sql, [convo_id], page=page, page_size=page_size)
    # Reverse to show oldest first
    result['items'] = list(reversed(result.get('items', [])))

    # Mark all unread messages from the OTHER user as read
    await db.execute("""
        UPDATE messages
        SET read_at = ?
        WHERE conversation_id = ?
          AND sender_id != ?
          AND read_at IS NULL
    """, [now_iso(), convo_id, me])

    # Reset unread counter for me
    if convo['farmer_a'] == me:
        await db.update('conversations', {'unread_count_a': 0}, 'id = ?', [convo_id])
    else:
        await db.update('conversations', {'unread_count_b': 0}, 'id = ?', [convo_id])

    return paginated_response(result, message="Messages retrieved")


# ============================================================
# SEND A MESSAGE
# ============================================================
async def send_message(request, env, convo_id: int):
    """POST /api/messages/conversations/:id/messages
    Body: {body, message_type?, media_url?}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    me = user['id']
    convo = await db.query_one("SELECT * FROM conversations WHERE id = ?", [convo_id])
    if not convo:
        return error_response("Conversation not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)
    if convo['farmer_a'] != me and convo['farmer_b'] != me:
        return error_response("Not authorized", status=HTTP.FORBIDDEN, code=ErrorCode.FORBIDDEN)

    data = await parse_json(request)
    err_msg = require_fields(data, ['body'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    body = str(data['body']).strip()
    if not body or len(body) > 5000:
        return error_response("Message must be 1-5000 chars",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    message_type = data.get('message_type', 'text')
    if message_type not in ('text', 'image', 'file'):
        message_type = 'text'

    msg_id = await db.insert('messages', {
        'conversation_id': convo_id,
        'sender_id': me,
        'body': body,
        'message_type': message_type,
        'media_url': data.get('media_url'),
    })

    # Update conversation's last message + increment unread for the OTHER user
    other = _other_id(convo, me)
    is_a_me = (convo['farmer_a'] == me)

    updates = {
        'last_message_id': msg_id,
        'last_message_at': now_iso(),
    }
    if is_a_me:
        updates['unread_count_b'] = (convo.get('unread_count_b') or 0) + 1
    else:
        updates['unread_count_a'] = (convo.get('unread_count_a') or 0) + 1

    await db.update('conversations', updates, 'id = ?', [convo_id])

    # Notify the recipient (in-app)
    me_info = await db.query_one("SELECT full_name FROM farmers WHERE id = ?", [me])
    await db.insert('notifications', {
        'farmer_id': other,
        'type': 'message',
        'title': 'New message',
        'message': f"{(me_info['full_name'] if me_info else 'Someone')}: {body[:80]}",
        'action_url': f'/messages.html?c={convo_id}',
    })

    # Return the saved message
    msg = await db.query_one("""
        SELECT m.id, m.sender_id, m.body, m.message_type, m.media_url,
               m.read_at, m.created_at,
               f.full_name as sender_name
        FROM messages m
        JOIN farmers f ON m.sender_id = f.id
        WHERE m.id = ?
    """, [msg_id])

    return success_response(msg, message="Message sent", status=HTTP.CREATED)


# ============================================================
# MARK CONVERSATION AS READ
# ============================================================
async def mark_read(request, env, convo_id: int):
    """POST /api/messages/conversations/:id/read"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    me = user['id']
    convo = await db.query_one("SELECT * FROM conversations WHERE id = ?", [convo_id])
    if not convo:
        return error_response("Conversation not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)
    if convo['farmer_a'] != me and convo['farmer_b'] != me:
        return error_response("Not authorized", status=HTTP.FORBIDDEN, code=ErrorCode.FORBIDDEN)

    await db.execute("""
        UPDATE messages
        SET read_at = ?
        WHERE conversation_id = ? AND sender_id != ? AND read_at IS NULL
    """, [now_iso(), convo_id, me])

    if convo['farmer_a'] == me:
        await db.update('conversations', {'unread_count_a': 0}, 'id = ?', [convo_id])
    else:
        await db.update('conversations', {'unread_count_b': 0}, 'id = ?', [convo_id])

    return success_response({'marked_read': True})


# ============================================================
# TOTAL UNREAD COUNT (for sidebar badge)
# ============================================================
async def unread_total(request, env):
    """GET /api/messages/unread-count
    Sum of unread messages across all conversations.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    me = user['id']

    row = await db.query_one("""
        SELECT
            COALESCE(SUM(CASE WHEN farmer_a = ? THEN unread_count_a ELSE 0 END), 0) +
            COALESCE(SUM(CASE WHEN farmer_b = ? THEN unread_count_b ELSE 0 END), 0) as total
        FROM conversations
        WHERE farmer_a = ? OR farmer_b = ?
    """, [me, me, me, me])

    return success_response({'unread_count': row['total'] if row else 0})


# ============================================================
# DELETE MESSAGE (own messages only)
# ============================================================
async def delete_message(request, env, message_id: int):
    """DELETE /api/messages/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    msg = await db.query_one("SELECT id, sender_id FROM messages WHERE id = ?", [message_id])
    if not msg:
        return error_response("Message not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)
    if msg['sender_id'] != user['id']:
        return error_response("Not authorized", status=HTTP.FORBIDDEN, code=ErrorCode.FORBIDDEN)

    await db.delete('messages', 'id = ?', [message_id])
    return success_response(None, message="Message deleted")


# ============================================================
# SEARCH FARMERS TO MESSAGE (for "New Chat" modal)
# ============================================================
async def search_farmers(request, env):
    """GET /api/messages/search-farmers?q=name
    Returns farmers matching the query (excludes self).
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)
    q = (url.search_params.get('q') or '').strip()

    if not q:
        # Return recent suggested farmers
        farmers = await db.query("""
            SELECT id, full_name, county, location
            FROM farmers
            WHERE id != ?
            ORDER BY id DESC
            LIMIT 20
        """, [user['id']])
    else:
        like = f"%{q}%"
        farmers = await db.query("""
            SELECT id, full_name, county, location
            FROM farmers
            WHERE id != ? AND full_name LIKE ?
            ORDER BY full_name
            LIMIT 20
        """, [user['id'], like])

    return success_response(farmers)
