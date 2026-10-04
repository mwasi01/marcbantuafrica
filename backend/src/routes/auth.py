"""
Marcbantu Africa — Authentication routes.
Register, login, logout, password management, session handling.
"""
from utils import (
    success_response, error_response, json_response, no_content,
    parse_json, validate_phone, is_valid_phone,
    hash_password, verify_password, create_token, verify_token,
    get_bearer_token, get_auth_user, require_auth,
    generate_reference, now_iso, log_event,
    to_int,
)
from validators import (
    ValidationError,
    validate_register, validate_login,
)
from constants import HTTP, ErrorCode, Tier
from db import DB


# ============================================================
# REGISTER
# ============================================================
async def register(request, env):
    """POST /api/auth/register
    Body: {phone, full_name, password, email?, county?, location?, language?}
    """
    data = await parse_json(request)

    try:
        clean = validate_register(data)
    except ValidationError as e:
        return error_response(e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)

    # Check if phone already exists
    existing = await db.query_one("SELECT id FROM farmers WHERE phone = ?", [clean['phone']])
    if existing:
        return error_response(
            "This phone number is already registered",
            status=HTTP.CONFLICT,
            code=ErrorCode.PHONE_EXISTS,
        )

    # Check if email exists (if provided)
    if clean.get('email'):
        email_exists = await db.query_one("SELECT id FROM farmers WHERE email = ?", [clean['email']])
        if email_exists:
            return error_response(
                "This email is already registered",
                status=HTTP.CONFLICT,
                code=ErrorCode.EMAIL_EXISTS,
            )

    # Hash password
    password_hash = hash_password(clean['password'])

    # Insert farmer
    farmer_id = await db.insert('farmers', {
        'phone': clean['phone'],
        'email': clean.get('email'),
        'full_name': clean['full_name'],
        'password_hash': password_hash,
        'county': clean.get('county'),
        'location': clean.get('location'),
        'language': clean.get('language', 'en'),
        'subscription_tier': Tier.STARTER,
        'verified': 0,
    })

    if not farmer_id:
        return error_response(
            "Failed to create account. Please try again.",
            status=HTTP.INTERNAL_ERROR,
            code=ErrorCode.INTERNAL_ERROR,
        )

    # Log the event
    await db.insert('audit_log', {
        'farmer_id': farmer_id,
        'action': 'register',
        'entity': 'farmer',
        'entity_id': farmer_id,
        'details': f"New registration from {clean['phone']}",
    })

    # Create welcome notification
    await db.insert('notifications', {
        'farmer_id': farmer_id,
        'type': 'system',
        'title': 'Welcome to Marcbantu Africa!',
        'message': 'Your account is ready. Start by adding your first farm.',
        'priority': 'normal',
    })

    # Issue token
    token = create_token(
        {'id': farmer_id, 'phone': clean['phone']},
        env.JWT_SECRET,
        expires_in=86400 * 7,
    )

    # Fetch full farmer record
    farmer = await db.query_one(
        "SELECT id, phone, email, full_name, county, location, language, subscription_tier, verified, created_at FROM farmers WHERE id = ?",
        [farmer_id]
    )

    log_event('register_success', {'farmer_id': farmer_id, 'phone': clean['phone']})

    return success_response(
        {
            'token': token,
            'token_type': 'Bearer',
            'expires_in': 86400 * 7,
            'farmer': farmer,
        },
        message="Account created successfully. Welcome to Marcbantu!",
        status=HTTP.CREATED,
    )


# ============================================================
# LOGIN
# ============================================================
async def login(request, env):
    """POST /api/auth/login
    Body: {phone, password}
    """
    data = await parse_json(request)

    try:
        clean = validate_login(data)
    except ValidationError as e:
        return error_response(e.message, status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)

    farmer = await db.query_one(
        "SELECT * FROM farmers WHERE phone = ?",
        [clean['phone']]
    )

    if not farmer:
        return error_response(
            "Invalid phone number or password",
            status=HTTP.UNAUTHORIZED,
            code=ErrorCode.INVALID_CREDENTIALS,
        )

    if not verify_password(clean['password'], farmer['password_hash']):
        # Log failed attempt
        await db.insert('audit_log', {
            'farmer_id': farmer['id'],
            'action': 'login_failed',
            'entity': 'farmer',
            'entity_id': farmer['id'],
            'details': 'Invalid password',
        })
        return error_response(
            "Invalid phone number or password",
            status=HTTP.UNAUTHORIZED,
            code=ErrorCode.INVALID_CREDENTIALS,
        )

    # Update last login
    await db.update('farmers', {'last_login_at': now_iso()}, 'id = ?', [farmer['id']])

    # Create session record
    session_id = generate_reference('SESS')
    await db.insert('sessions', {
        'id': session_id,
        'farmer_id': farmer['id'],
        'expires_at': now_iso(),  # placeholder, real expiry handled by JWT
        'channel': 'web',
    })

    # Issue token
    token = create_token(
        {'id': farmer['id'], 'phone': farmer['phone']},
        env.JWT_SECRET,
        expires_in=86400 * 7,
    )

    # Remove sensitive fields
    farmer.pop('password_hash', None)

    # Log success
    await db.insert('audit_log', {
        'farmer_id': farmer['id'],
        'action': 'login',
        'entity': 'farmer',
        'entity_id': farmer['id'],
    })

    log_event('login_success', {'farmer_id': farmer['id']})

    return success_response(
        {
            'token': token,
            'token_type': 'Bearer',
            'expires_in': 86400 * 7,
            'farmer': farmer,
        },
        message="Login successful"
    )


# ============================================================
# LOGOUT
# ============================================================
async def logout(request, env):
    """POST /api/auth/logout
    Invalidates the current session.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)

    # Log the event
    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': 'logout',
        'entity': 'farmer',
        'entity_id': user['id'],
    })

    # Delete sessions for this farmer
    await db.delete('sessions', 'farmer_id = ?', [user['id']])

    log_event('logout_success', {'farmer_id': user['id']})

    return success_response(None, message="Logged out successfully")


# ============================================================
# ME — GET current user
# ============================================================
async def me(request, env):
    """GET /api/auth/me
    Returns the current authenticated farmer.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    farmer = await db.query_one(
        """SELECT id, phone, email, full_name, country, county, location,
                  language, profile_photo_url, subscription_tier,
                  subscription_expires_at, verified, verified_at,
                  last_login_at, created_at, updated_at
           FROM farmers WHERE id = ?""",
        [user['id']]
    )

    if not farmer:
        return error_response("User not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # Get farm count
    farm_count = await db.count('farms', 'farmer_id = ?', [user['id']])
    farmer['farm_count'] = farm_count

    # Get unread notifications
    unread = await db.count('notifications', 'farmer_id = ? AND read = 0', [user['id']])
    farmer['unread_notifications'] = unread

    return success_response(farmer)


# ============================================================
# REFRESH TOKEN
# ============================================================
async def refresh(request, env):
    """POST /api/auth/refresh
    Issues a new token if the current one is still valid.
    """
    token = get_bearer_token(request)
    if not token:
        return error_response("No token provided", status=HTTP.UNAUTHORIZED, code=ErrorCode.UNAUTHORIZED)

    payload = verify_token(token, env.JWT_SECRET)
    if not payload:
        return error_response(
            "Token is invalid or expired",
            status=HTTP.UNAUTHORIZED,
            code=ErrorCode.TOKEN_EXPIRED,
        )

    # Check user still exists
    db = DB(env)
    farmer = await db.query_one("SELECT id, phone FROM farmers WHERE id = ?", [payload['id']])
    if not farmer:
        return error_response("User no longer exists", status=HTTP.UNAUTHORIZED, code=ErrorCode.UNAUTHORIZED)

    # Issue new token
    new_token = create_token(
        {'id': farmer['id'], 'phone': farmer['phone']},
        env.JWT_SECRET,
        expires_in=86400 * 7,
    )

    return success_response({
        'token': new_token,
        'token_type': 'Bearer',
        'expires_in': 86400 * 7,
    }, message="Token refreshed")


# ============================================================
# CHANGE PASSWORD
# ============================================================
async def change_password(request, env):
    """POST /api/auth/change-password
    Body: {current_password, new_password}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)

    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not current_password or not new_password:
        return error_response(
            "Both current_password and new_password are required",
            status=HTTP.BAD_REQUEST,
            code=ErrorCode.MISSING_FIELD,
        )

    if len(new_password) < 6:
        return error_response(
            "New password must be at least 6 characters",
            status=HTTP.BAD_REQUEST,
            code=ErrorCode.VALIDATION_ERROR,
        )

    if current_password == new_password:
        return error_response(
            "New password must be different from current password",
            status=HTTP.BAD_REQUEST,
            code=ErrorCode.VALIDATION_ERROR,
        )

    db = DB(env)
    farmer = await db.query_one("SELECT password_hash FROM farmers WHERE id = ?", [user['id']])
    if not farmer:
        return error_response("User not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    if not verify_password(current_password, farmer['password_hash']):
        return error_response(
            "Current password is incorrect",
            status=HTTP.UNAUTHORIZED,
            code=ErrorCode.INVALID_CREDENTIALS,
        )

    # Update password
    new_hash = hash_password(new_password)
    await db.update('farmers', {
        'password_hash': new_hash,
        'updated_at': now_iso(),
    }, 'id = ?', [user['id']])

    # Invalidate all sessions
    await db.delete('sessions', 'farmer_id = ?', [user['id']])

    # Audit log
    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': 'password_changed',
        'entity': 'farmer',
        'entity_id': user['id'],
    })

    # Notification
    await db.insert('notifications', {
        'farmer_id': user['id'],
        'type': 'system',
        'title': 'Password changed',
        'message': 'Your password was changed successfully. If this was not you, contact support immediately.',
        'priority': 'high',
    })

    log_event('password_changed', {'farmer_id': user['id']})

    return success_response(None, message="Password changed successfully")


# ============================================================
# FORGOT PASSWORD
# ============================================================
async def forgot_password(request, env):
    """POST /api/auth/forgot-password
    Body: {phone}
    Sends an OTP via SMS.
    """
    data = await parse_json(request)
    phone_raw = data.get('phone')
    if not phone_raw:
        return error_response("Phone number is required", status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    phone = validate_phone(phone_raw)
    if not is_valid_phone(phone):
        return error_response("Invalid phone number", status=HTTP.BAD_REQUEST, code=ErrorCode.INVALID_FORMAT)

    db = DB(env)
    farmer = await db.query_one("SELECT id, phone, full_name FROM farmers WHERE phone = ?", [phone])

    # Always return success (don't reveal if user exists)
    generic_msg = "If this phone number is registered, you will receive an OTP shortly."

    if not farmer:
        return success_response(None, message=generic_msg)

    # Generate 6-digit OTP
    import random
    otp = f"{random.randint(100000, 999999)}"
    expires_at = now_iso()

    # Store OTP in KV with 10-minute TTL
    try:
        await env.CACHE.put(
            f"otp:{phone}",
            otp,
            expirationTtl=600,  # 10 minutes
        )
    except Exception as e:
        log_event('otp_store_failed', {'phone': phone, 'error': str(e)})
        return error_response("Failed to generate OTP. Please try again.", status=HTTP.INTERNAL_ERROR)

    # Queue SMS
    await env.JOBS.send({
        'type': 'send_sms',
        'payload': {
            'to': phone,
            'farmer_id': farmer['id'],
            'body': f"Your Marcbantu password reset code is: {otp}. Valid for 10 minutes. Do not share this code.",
        }
    })

    # Audit log
    await db.insert('audit_log', {
        'farmer_id': farmer['id'],
        'action': 'password_reset_requested',
        'entity': 'farmer',
        'entity_id': farmer['id'],
    })

    log_event('otp_sent', {'farmer_id': farmer['id'], 'phone': phone})

    return success_response(None, message=generic_msg)


# ============================================================
# RESET PASSWORD (with OTP)
# ============================================================
async def reset_password(request, env):
    """POST /api/auth/reset-password
    Body: {phone, otp, new_password}
    """
    data = await parse_json(request)

    phone_raw = data.get('phone')
    otp = data.get('otp')
    new_password = data.get('new_password')

    if not phone_raw or not otp or not new_password:
        return error_response(
            "phone, otp, and new_password are required",
            status=HTTP.BAD_REQUEST,
            code=ErrorCode.MISSING_FIELD,
        )

    if len(new_password) < 6:
        return error_response(
            "Password must be at least 6 characters",
            status=HTTP.BAD_REQUEST,
            code=ErrorCode.VALIDATION_ERROR,
        )

    phone = validate_phone(phone_raw)

    # Verify OTP from KV
    try:
        stored_otp = await env.CACHE.get(f"otp:{phone}")
    except Exception as e:
        log_event('otp_fetch_failed', {'phone': phone, 'error': str(e)})
        return error_response("Failed to verify OTP. Please try again.", status=HTTP.INTERNAL_ERROR)

    if not stored_otp:
        return error_response(
            "OTP has expired or was never requested",
            status=HTTP.BAD_REQUEST,
            code=ErrorCode.TOKEN_EXPIRED,
        )

    if stored_otp != str(otp).strip():
        return error_response(
            "Invalid OTP",
            status=HTTP.UNAUTHORIZED,
            code=ErrorCode.INVALID_CREDENTIALS,
        )

    db = DB(env)
    farmer = await db.query_one("SELECT id FROM farmers WHERE phone = ?", [phone])
    if not farmer:
        return error_response("User not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # Update password
    new_hash = hash_password(new_password)
    await db.update('farmers', {
        'password_hash': new_hash,
        'updated_at': now_iso(),
    }, 'id = ?', [farmer['id']])

    # Delete OTP from KV
    try:
        await env.CACHE.delete(f"otp:{phone}")
    except Exception:
        pass

    # Invalidate sessions
    await db.delete('sessions', 'farmer_id = ?', [farmer['id']])

    # Audit
    await db.insert('audit_log', {
        'farmer_id': farmer['id'],
        'action': 'password_reset',
        'entity': 'farmer',
        'entity_id': farmer['id'],
    })

    log_event('password_reset_success', {'farmer_id': farmer['id']})

    return success_response(None, message="Password reset successfully. Please log in.")


# ============================================================
# VERIFY PHONE (send OTP for account verification)
# ============================================================
async def verify_phone(request, env):
    """POST /api/auth/verify-phone
    Sends an OTP to verify the phone number of the logged-in user.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    farmer = await db.query_one("SELECT id, phone, verified FROM farmers WHERE id = ?", [user['id']])
    if not farmer:
        return error_response("User not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    if farmer['verified']:
        return success_response(None, message="Phone already verified")

    import random
    otp = f"{random.randint(100000, 999999)}"

    try:
        await env.CACHE.put(f"verify:{farmer['phone']}", otp, expirationTtl=600)
    except Exception:
        return error_response("Failed to generate OTP", status=HTTP.INTERNAL_ERROR)

    # Queue SMS
    await env.JOBS.send({
        'type': 'send_sms',
        'payload': {
            'to': farmer['phone'],
            'farmer_id': farmer['id'],
            'body': f"Your Marcbantu verification code is: {otp}. Valid for 10 minutes.",
        }
    })

    return success_response(None, message="Verification code sent")


# ============================================================
# CONFIRM PHONE VERIFICATION
# ============================================================
async def confirm_verification(request, env):
    """POST /api/auth/confirm-verification
    Body: {otp}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    otp = data.get('otp')
    if not otp:
        return error_response("OTP is required", status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    db = DB(env)
    farmer = await db.query_one("SELECT id, phone FROM farmers WHERE id = ?", [user['id']])
    if not farmer:
        return error_response("User not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    try:
        stored_otp = await env.CACHE.get(f"verify:{farmer['phone']}")
    except Exception:
        return error_response("Failed to verify OTP", status=HTTP.INTERNAL_ERROR)

    if not stored_otp:
        return error_response("OTP expired or not requested", status=HTTP.BAD_REQUEST, code=ErrorCode.TOKEN_EXPIRED)

    if str(otp).strip() != stored_otp:
        return error_response("Invalid OTP", status=HTTP.UNAUTHORIZED, code=ErrorCode.INVALID_CREDENTIALS)

    # Mark verified
    await db.update('farmers', {
        'verified': 1,
        'verified_at': now_iso(),
        'updated_at': now_iso(),
    }, 'id = ?', [farmer['id']])

    # Delete OTP
    try:
        await env.CACHE.delete(f"verify:{farmer['phone']}")
    except Exception:
        pass

    await db.insert('audit_log', {
        'farmer_id': farmer['id'],
        'action': 'phone_verified',
        'entity': 'farmer',
        'entity_id': farmer['id'],
    })

    log_event('phone_verified', {'farmer_id': farmer['id']})

    return success_response(None, message="Phone verified successfully")


# ============================================================
# DELETE ACCOUNT
# ============================================================
async def delete_account(request, env):
    """POST /api/auth/delete-account
    Body: {password, confirm: true}
    Permanently deletes the account and all associated data.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    password = data.get('password')
    confirm = data.get('confirm')

    if not password:
        return error_response("Password is required", status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    if not confirm:
        return error_response(
            "Account deletion must be confirmed",
            status=HTTP.BAD_REQUEST,
            code=ErrorCode.VALIDATION_ERROR,
        )

    db = DB(env)
    farmer = await db.query_one("SELECT password_hash FROM farmers WHERE id = ?", [user['id']])
    if not farmer:
        return error_response("User not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    if not verify_password(password, farmer['password_hash']):
        return error_response("Invalid password", status=HTTP.UNAUTHORIZED, code=ErrorCode.INVALID_CREDENTIALS)

    # Log before deletion
    await db.insert('audit_log', {
        'farmer_id': user['id'],
        'action': 'account_deleted',
        'entity': 'farmer',
        'entity_id': user['id'],
    })

    # Delete the farmer (cascades to farms, records, transactions, etc.)
    await db.delete('farmers', 'id = ?', [user['id']])

    log_event('account_deleted', {'farmer_id': user['id']})

    return success_response(None, message="Account deleted. We're sorry to see you go.")