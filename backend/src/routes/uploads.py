"""
Marcbantu Africa — Upload routes.
File uploads to R2 (photos, documents, PDFs).
"""

from js import Response, Object
from utils import (
    success_response, error_response, require_auth,
    now_iso, to_int, log_event, generate_reference,
    js_headers,
)
from constants import HTTP, ErrorCode
from db import DB


# ============================================================
# FILE SIZE LIMITS (bytes)
# ============================================================
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_TYPES = {
    'image/jpeg', 'image/png', 'image/webp', 'image/gif',
    'application/pdf',
    'text/csv',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}


# ============================================================
# UPLOAD FILE
# ============================================================
async def upload_file(request, env):
    """POST /api/uploads
    Form data: file (required), entity?, entity_id?, farm_id?
    Returns: {id, file_key, url}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    try:
        form = await request.formData()
    except Exception:
        return error_response("Invalid form data", status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    file = form.get('file')
    if not file:
        return error_response("'file' is required", status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    # Get file info
    file_name = getattr(file, 'name', 'file')
    file_size = getattr(file, 'size', 0)
    content_type = getattr(file, 'type', 'application/octet-stream')

    if file_size > MAX_FILE_SIZE:
        return error_response(f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    if content_type not in ALLOWED_TYPES:
        return error_response(f"File type not allowed: {content_type}",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    # Read content
    try:
        content = await file.arrayBuffer()
    except Exception:
        return error_response("Failed to read file", status=HTTP.BAD_REQUEST, code=ErrorCode.INTERNAL_ERROR)

    # Generate R2 key
    ext = file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else 'bin'
    ref = generate_reference('F')
    file_key = f"uploads/{user['id']}/{ref}.{ext}"

    # Upload to R2
    try:
        await env.FILES.put(file_key, content, {
            'httpMetadata': {'contentType': content_type},
            'customMetadata': {
                'farmer_id': str(user['id']),
                'original_name': file_name[:200],
            },
        })
    except Exception as e:
        log_event('r2_upload_failed', {'error': str(e), 'key': file_key})
        return error_response("Upload failed", status=HTTP.INTERNAL_ERROR, code=ErrorCode.INTERNAL_ERROR)

    # Build public URL (in production, use a signed URL or public bucket)
    url = f"https://files.marcbantuafrica.com/{file_key}"

    # Save metadata
    db = DB(env)
    upload_id = await db.insert('uploads', {
        'farmer_id': user['id'],
        'farm_id': to_int(form.get('farm_id')) or None,
        'entity': form.get('entity'),
        'entity_id': to_int(form.get('entity_id')) or None,
        'file_key': file_key,
        'file_name': file_name,
        'file_type': content_type.split('/')[0],
        'file_size': file_size,
        'mime_type': content_type,
        'url': url,
    })

    log_event('file_uploaded', {
        'upload_id': upload_id,
        'farmer_id': user['id'],
        'size': file_size,
    })

    return success_response({
        'id': upload_id,
        'file_key': file_key,
        'url': url,
        'file_name': file_name,
        'file_size': file_size,
        'mime_type': content_type,
    }, message="File uploaded", status=HTTP.CREATED)


# ============================================================
# GET UPLOAD
# ============================================================
async def get_upload(request, env, upload_id: int):
    """GET /api/uploads/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    upload = await db.query_one(
        "SELECT * FROM uploads WHERE id = ? AND farmer_id = ?",
        [upload_id, user['id']]
    )
    if not upload:
        return error_response("Upload not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    return success_response(upload)


# ============================================================
# DELETE UPLOAD
# ============================================================
async def delete_upload(request, env, upload_id: int):
    """DELETE /api/uploads/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    upload = await db.query_one(
        "SELECT * FROM uploads WHERE id = ? AND farmer_id = ?",
        [upload_id, user['id']]
    )
    if not upload:
        return error_response("Upload not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # Delete from R2
    try:
        await env.FILES.delete(upload['file_key'])
    except Exception as e:
        log_event('r2_delete_failed', {'error': str(e), 'key': upload['file_key']})

    # Delete metadata
    await db.delete('uploads', 'id = ?', [upload_id])

    return success_response(None, message="File deleted")


# ============================================================
# SERVE FILE (proxy from R2)
# ============================================================
async def serve_file(request, env, file_key: str):
    """GET /files/* — proxy from R2. Public read for now."""
    try:
        obj = await env.FILES.get(file_key)
        if not obj:
            return error_response("File not found", status=HTTP.NOT_FOUND)

        return Response.new(obj.body, headers=js_headers({
            'Content-Type': obj.httpMetadata.get('contentType', 'application/octet-stream') if obj.httpMetadata else 'application/octet-stream',
            'Cache-Control': 'public, max-age=31536000',
            'Access-Control-Allow-Origin': '*',
        }))
    except Exception:
        return error_response("File fetch failed", status=HTTP.INTERNAL_ERROR)