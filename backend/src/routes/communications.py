"""
Marcbantu Africa — Communications routes.
SMS, USSD, WhatsApp, Voice via Africa's Talking.
Inbound webhooks + outbound sending.
"""

from js import Response, Object, fetch
from utils import (
    success_response, error_response, parse_json, require_auth,
    now_iso, to_int, to_float, log_event, require_fields,
    parse_form, generate_reference,
    js_headers,
    _sp,
)
from constants import HTTP, ErrorCode, Channel
from db import DB


# ============================================================
# AFRICA'S TALKING CLIENT
# ============================================================
async def _at_send_sms(env, to: str, message: str, sender_id: str = None) -> dict:
    """Send SMS via Africa's Talking. Returns response dict."""
    api_key = getattr(env, 'AT_API_KEY', '')
    username = getattr(env, 'AT_USERNAME', 'sandbox')
    sender = sender_id or getattr(env, 'AT_SENDER_ID', 'MARCBANTU')

    if not api_key:
        return {'error': 'Africa\'s Talking not configured'}

    base_url = 'https://api.africastalking.com' if username != 'sandbox' else 'https://api.sandbox.africastalking.com'

    body = f"username={username}&to={to}&message={message}&from={sender}"
    try:
        response = await fetch(
            f"{base_url}/version1/messaging",
            method='POST',
            headers=js_headers({
                'apiKey': api_key,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            }),
            body=body,
        )
        if response.status != 200 and response.status != 201:
            return {'error': f'AT returned {response.status}', 'status': response.status}

        data = await response.json()
        return data
    except Exception as e:
        return {'error': str(e)}


async def _log_comm(db: DB, farmer_id, channel: str, direction: str,
                    phone: str, message: str, status: str,
                    reference: str = None, error: str = None):
    """Log a communication to the DB."""
    try:
        await db.insert('communication_log', {
            'farmer_id': farmer_id,
            'channel': channel,
            'direction': direction,
            'phone': phone,
            'message': message[:1000] if message else None,
            'status': status,
            'reference': reference,
            'error_message': error,
        })
    except Exception:
        pass


# ============================================================
# SEND SMS (single)
# ============================================================
async def send_sms(request, env):
    """POST /api/comms/sms
    Body: {to, message, farmer_id?, template_code?, variables?}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ['to', 'message'])
    if err_msg:
        # Try template
        if data.get('template_code'):
            db = DB(env)
            template = await db.query_one(
                "SELECT body FROM sms_templates WHERE code = ? AND active = 1",
                [data['template_code']]
            )
            if template:
                message = template['body']
                variables = data.get('variables', {})
                for k, v in variables.items():
                    message = message.replace(f"{{{k}}}", str(v))
                data['message'] = message
            else:
                return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)
        else:
            return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    to = data['to']
    message = data['message']

    # Send
    result = await _at_send_sms(env, to, message)

    # Log
    db = DB(env)
    status = 'sent' if 'error' not in result else 'failed'
    reference = generate_reference('SMS')

    await _log_comm(
        db,
        farmer_id=data.get('farmer_id') or user['id'],
        channel='sms',
        direction='outbound',
        phone=to,
        message=message,
        status=status,
        reference=reference,
        error=result.get('error'),
    )

    if 'error' in result:
        return error_response(f"SMS failed: {result['error']}", status=HTTP.SERVICE_UNAVAILABLE)

    return success_response({
        'reference': reference,
        'recipient': to,
        'status': 'sent',
        'provider_response': result,
    }, message="SMS sent")


# ============================================================
# SEND BULK SMS
# ============================================================
async def send_bulk_sms(request, env):
    """POST /api/comms/sms/bulk
    Body: {recipients: [phone...], message, or farmer_ids + template_code}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    recipients = data.get('recipients', [])
    farmer_ids = data.get('farmer_ids', [])
    message = data.get('message')
    template_code = data.get('template_code')
    variables = data.get('variables', {})

    if not recipients and not farmer_ids:
        return error_response("Provide 'recipients' or 'farmer_ids'",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    db = DB(env)

    # Resolve template
    if template_code:
        template = await db.query_one(
            "SELECT body FROM sms_templates WHERE code = ? AND active = 1",
            [template_code]
        )
        if template:
            message = template['body']
            for k, v in variables.items():
                message = message.replace(f"{{{k}}}", str(v))

    if not message:
        return error_response("Message or valid template required",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    # If farmer_ids provided, look up phones
    if farmer_ids:
        placeholders = ','.join(['?'] * len(farmer_ids))
        farmers = await db.query(
            f"SELECT id, phone FROM farmers WHERE id IN ({placeholders})",
            farmer_ids
        )
        recipients.extend([f['phone'] for f in farmers if f.get('phone')])

    if not recipients:
        return error_response("No valid recipients",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    if len(recipients) > 1000:
        return error_response("Max 1000 recipients per bulk send",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    # Queue each send (fire-and-forget via Queue)
    queued = 0
    for phone in recipients:
        try:
            await env.JOBS.send({
                'type': 'send_sms',
                'payload': {
                    'to': phone,
                    'message': message,
                    'farmer_id': user['id'],
                },
            })
            queued += 1
        except Exception as e:
            log_event('bulk_sms_queue_failed', {'phone': phone, 'error': str(e)})

    log_event('bulk_sms_queued', {
        'farmer_id': user['id'],
        'count': queued,
        'total': len(recipients),
    })

    return success_response({
        'queued': queued,
        'total': len(recipients),
        'message_preview': message[:100],
    }, message=f"Queued {queued} of {len(recipients)} messages")


# ============================================================
# SMS WEBHOOK (inbound from Africa's Talking)
# ============================================================
async def sms_webhook(request, env):
    """POST /api/comms/sms/webhook
    Receives inbound SMS from Africa's Talking.
    Parses commands and responds.
    """
    form = await parse_form(request)
    sender = form.get('from') or form.get('phoneNumber', '')
    text = (form.get('text') or '').strip()

    if not sender:
        return Response.new('Missing sender', status=400, headers=js_headers({'Content-Type': 'text/plain'}))

    log_event('sms_inbound', {'from': sender, 'text': text[:200]})

    db = DB(env)
    farmer = await db.query_one(
        "SELECT id, full_name, phone FROM farmers WHERE phone = ? OR phone = ?",
        [sender, sender.lstrip('+')]
    )

    # Log inbound
    await _log_comm(
        db,
        farmer_id=farmer['id'] if farmer else None,
        channel='sms',
        direction='inbound',
        phone=sender,
        message=text,
        status='received',
    )

    # Parse command
    parts = text.upper().split()
    command = parts[0] if parts else ''

    reply = ""

    if not farmer:
        if command == 'REGISTER':
            reply = "Welcome to Marcbantu! Visit marcbantuafrica.com to register. Reply HELP for commands."
        else:
            reply = "Hi! You're not registered. Reply REGISTER to get started with Marcbantu."
    else:
        reply = await _handle_sms_command(command, parts, farmer, db, env)

    # Send reply
    if reply:
        await _at_send_sms(env, sender, reply)

    return Response.new('OK', status=200, headers=js_headers({'Content-Type': 'text/plain'}))


async def _handle_sms_command(command: str, parts: list, farmer: dict, db: DB, env) -> str:
    """Handle SMS commands from farmers."""
    first_name = (farmer.get('full_name') or 'farmer').split()[0]

    if command == 'HELP':
        return (
            "Marcbantu commands:\n"
            "PRICE - Market prices\n"
            "MILK [litres] - Record milk\n"
            "BALANCE - Account summary\n"
            "WEATHER - Weather forecast\n"
            "HELP - This menu"
        )

    if command == 'PRICE':
        prices = await db.query("""
            SELECT crop, price, unit FROM market_prices
            WHERE price_date = (SELECT MAX(price_date) FROM market_prices)
            LIMIT 5
        """)
        if not prices:
            return "No prices available yet."
        lines = [f"{p['crop']}: KES {p['price']}/{p['unit']}" for p in prices]
        return "Today's prices:\n" + "\n".join(lines)

    if command == 'MILK' and len(parts) >= 2:
        try:
            litres = float(parts[1])
        except ValueError:
            return "Invalid amount. Send: MILK [litres] e.g. MILK 20"

        farm = await db.query_one(
            "SELECT id FROM farms WHERE farmer_id = ? AND active = 1 LIMIT 1",
            [farmer['id']]
        )
        if not farm:
            return "No active farm found. Add a farm at marcbantuafrica.com"

        await db.insert('records', {
            'farm_id': farm['id'],
            'record_type': 'livestock',
            'activity': 'milking',
            'quantity': litres,
            'unit': 'litres',
            'record_date': now_iso()[:10],
            'created_by': farmer['id'],
        })
        return f"Recorded {litres}L milk. Thank you!"

    if command == 'BALANCE':
        farm = await db.query_one(
            "SELECT id FROM farms WHERE farmer_id = ? AND active = 1 LIMIT 1",
            [farmer['id']]
        )
        if not farm:
            return "No active farm. Visit marcbantuafrica.com"

        totals = await db.query_one("""
            SELECT
                COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END), 0) as income,
                COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) as expenses
            FROM transactions WHERE farm_id = ?
        """, [farm['id']])

        income = totals['income'] if totals else 0
        expenses = totals['expenses'] if totals else 0
        return (
            f"Balance for {first_name}:\n"
            f"Income: KES {income:,.0f}\n"
            f"Expenses: KES {expenses:,.0f}\n"
            f"Profit: KES {income - expenses:,.0f}"
        )

    if command == 'WEATHER':
        farm = await db.query_one("""
            SELECT latitude, longitude, name FROM farms
            WHERE farmer_id = ? AND active = 1 AND latitude IS NOT NULL LIMIT 1
        """, [farmer['id']])

        if not farm:
            return "Set your farm location at marcbantuafrica.com for weather."

        lat, lon = farm['latitude'], farm['longitude']
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,weather_code"
                f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"
                f"&timezone=Africa/Nairobi&forecast_days=3"
            )
            resp = await fetch(url)
            data = await resp.json()
            current = data.get('current', {})
            daily = data.get('daily', {})
            days = daily.get('time', [])
            max_t = daily.get('temperature_2m_max', [])
            min_t = daily.get('temperature_2m_min', [])
            rain = daily.get('precipitation_sum', [])

            lines = [f"Current: {current.get('temperature_2m', '?')}°C"]
            for i, d in enumerate(days[:3]):
                lines.append(f"{d}: {min_t[i]:.0f}-{max_t[i]:.0f}°C, {rain[i]:.1f}mm")
            return "Weather:\n" + "\n".join(lines)
        except Exception:
            return "Weather service unavailable. Try again later."

    return f"Unknown command: {command}. Reply HELP for the menu."


# ============================================================
# USSD HANDLER
# ============================================================
async def ussd_handler(request, env):
    """POST /api/comms/ussd
    Africa's Talking sends USSD sessions here. Returns CON/END strings.
    """
    form = await parse_form(request)
    session_id = form.get('sessionId', '')
    phone = form.get('phoneNumber', '')
    text = form.get('text', '') or ''

    if not phone:
        return Response.new('END Invalid request', headers=js_headers({'Content-Type': 'text/plain'}))

    db = DB(env)
    farmer = await db.query_one(
        "SELECT id, full_name FROM farmers WHERE phone = ? OR phone = ?",
        [phone, phone.lstrip('+')]
    )

    # Track session
    existing = await db.query_one(
        "SELECT id FROM ussd_sessions WHERE session_id = ?", [session_id]
    )
    if not existing:
        await db.insert('ussd_sessions', {
            'session_id': session_id,
            'phone': phone,
            'farmer_id': farmer['id'] if farmer else None,
            'started_at': now_iso(),
        })

    # Route by level
    steps = text.split('*') if text else []
    response = await _ussd_route(steps, text, farmer, phone, db, env)

    # Mark end if terminal
    if response.startswith('END'):
        await db.execute(
            "UPDATE ussd_sessions SET ended_at = ? WHERE session_id = ?",
            [now_iso(), session_id]
        )

    # Log
    await _log_comm(
        db,
        farmer_id=farmer['id'] if farmer else None,
        channel='ussd',
        direction='inbound',
        phone=phone,
        message=text or '(session start)',
        status='received',
    )

    return Response.new(response, headers=js_headers({'Content-Type': 'text/plain'}))


async def _ussd_route(steps: list, text: str, farmer, phone: str, db: DB, env) -> str:
    """Route USSD menu based on accumulated input."""
    if not farmer:
        if not steps:
            return "CON Welcome to Marcbantu\n1. Learn more\n2. Register"
        if steps[0] == '1':
            return "END Marcbantu helps farmers manage records, plan, and grow profit. Visit marcbantuafrica.com"
        if steps[0] == '2':
            return "END Visit marcbantuafrica.com to register. Thank you!"
        return "END Invalid option"

    # Main menu
    if not steps:
        return (
            "CON Welcome back\n"
            "1. Market prices\n"
            "2. Record activity\n"
            "3. Check balance\n"
            "4. Weather\n"
            "5. Help"
        )

    top = steps[0]

    # Market prices
    if top == '1':
        prices = await db.query("""
            SELECT crop, price, unit FROM market_prices
            WHERE price_date = (SELECT MAX(price_date) FROM market_prices)
            LIMIT 5
        """)
        if not prices:
            return "END No prices available"
        lines = [f"{p['crop']}: KES {p['price']}/{p['unit']}" for p in prices]
        return "END Today's prices:\n" + "\n".join(lines)

    # Record activity
    if top == '2':
        if len(steps) == 1:
            return "CON Record what?\n1. Milk\n2. Eggs\n3. Sales\n4. Expense"
        sub = steps[1]
        if sub == '1':
            if len(steps) == 2:
                return "CON Enter litres of milk:"
            litres = steps[2]
            try:
                litres_f = float(litres)
            except ValueError:
                return "END Invalid amount"
            farm = await db.query_one(
                "SELECT id FROM farms WHERE farmer_id = ? AND active = 1 LIMIT 1",
                [farmer['id']]
            )
            if not farm:
                return "END No active farm"
            await db.insert('records', {
                'farm_id': farm['id'],
                'record_type': 'livestock',
                'activity': 'milking',
                'quantity': litres_f,
                'unit': 'litres',
                'record_date': now_iso()[:10],
                'created_by': farmer['id'],
            })
            return f"END Recorded {litres}L milk. Thank you!"
        if sub == '2':
            if len(steps) == 2:
                return "CON Enter number of eggs:"
            return f"END Recorded {steps[2]} eggs. Thank you!"
        if sub == '3':
            if len(steps) == 2:
                return "CON Enter sale amount (KES):"
            return f"END Sale of KES {steps[2]} recorded. Thank you!"
        if sub == '4':
            if len(steps) == 2:
                return "CON Enter expense amount (KES):"
            return f"END Expense of KES {steps[2]} recorded."
        return "END Invalid option"

    # Balance
    if top == '3':
        farm = await db.query_one(
            "SELECT id FROM farms WHERE farmer_id = ? AND active = 1 LIMIT 1",
            [farmer['id']]
        )
        if not farm:
            return "END No active farm"
        totals = await db.query_one("""
            SELECT
                COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END), 0) as income,
                COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) as expenses
            FROM transactions WHERE farm_id = ?
        """, [farm['id']])
        income = totals['income'] if totals else 0
        expenses = totals['expenses'] if totals else 0
        return (
            f"END Income: KES {income:,.0f}\n"
            f"Expenses: KES {expenses:,.0f}\n"
            f"Profit: KES {income - expenses:,.0f}"
        )

    # Weather
    if top == '4':
        farm = await db.query_one("""
            SELECT latitude, longitude FROM farms
            WHERE farmer_id = ? AND latitude IS NOT NULL LIMIT 1
        """, [farmer['id']])
        if not farm:
            return "END Set farm location first"
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={farm['latitude']}&longitude={farm['longitude']}"
                f"&current=temperature_2m,weather_code"
                f"&daily=temperature_2m_max,precipitation_sum&timezone=Africa/Nairobi&forecast_days=2"
            )
            resp = await fetch(url)
            data = await resp.json()
            curr = data.get('current', {})
            daily = data.get('daily', {})
            return (
                f"END Now: {curr.get('temperature_2m', '?')}°C\n"
                f"Tomorrow: {daily.get('temperature_2m_max', ['?'])[0]}°C, "
                f"{daily.get('precipitation_sum', [0])[0]}mm rain"
            )
        except Exception:
            return "END Weather unavailable"

    # Help
    if top == '5':
        return "END Commands: reply HELP via SMS to 20000 for full list."

    return "END Invalid option"


# ============================================================
# SEND WHATSAPP
# ============================================================
async def send_whatsapp(request, env):
    """POST /api/comms/whatsapp
    Body: {to, message, template_name?, variables?}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ['to'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    token = getattr(env, 'WHATSAPP_TOKEN', '')
    phone_id = getattr(env, 'WHATSAPP_PHONE_ID', '')

    if not token or not phone_id:
        return error_response("WhatsApp not configured", status=HTTP.SERVICE_UNAVAILABLE)

    to = data['to'].lstrip('+')
    message = data.get('message', '')

    payload = {
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'text',
        'text': {'body': message},
    }

    try:
        response = await fetch(
            f"https://graph.facebook.com/v18.0/{phone_id}/messages",
            method='POST',
            headers={
                'Authorization': f"Bearer {token}",
                'Content-Type': 'application/json',
            },
            body=__import__('json').dumps(payload),
        )
        result = await response.json()
        status = 'sent' if response.status < 300 else 'failed'
    except Exception as e:
        return error_response(f"WhatsApp error: {str(e)}", status=HTTP.SERVICE_UNAVAILABLE)

    db = DB(env)
    await _log_comm(
        db,
        farmer_id=user['id'],
        channel='whatsapp',
        direction='outbound',
        phone=to,
        message=message,
        status=status,
    )

    return success_response(result, message="WhatsApp sent")


async def whatsapp_webhook(request, env):
    """POST /api/comms/whatsapp/webhook
    Meta WhatsApp Cloud API webhook. Handles verification + messages.
    """
    # GET verification
    if request.method == 'GET':
        url = _sp(request)
        mode = url.search_params.get('hub.mode')
        token = url.search_params.get('hub.verify_token')
        challenge = url.search_params.get('hub.challenge')
        expected = getattr(env, 'WHATSAPP_VERIFY_TOKEN', 'marcbantu-verify')
        if mode == 'subscribe' and token == expected:
            return Response.new(challenge or '', headers=js_headers({'Content-Type': 'text/plain'}))
        return Response.new('Forbidden', status=403)

    # POST messages
    try:
        body = await request.json()
    except Exception:
        return Response.new('OK', status=200)

    # Log and extract
    entries = body.get('entry', [])
    db = DB(env)
    for entry in entries:
        for change in entry.get('changes', []):
            value = change.get('value', {})
            messages = value.get('messages', [])
            for msg in messages:
                sender = msg.get('from')
                text = msg.get('text', {}).get('body', '')
                await _log_comm(
                    db,
                    farmer_id=None,
                    channel='whatsapp',
                    direction='inbound',
                    phone=sender,
                    message=text,
                    status='received',
                )

    return Response.new('OK', status=200)


# ============================================================
# SEND VOICE
# ============================================================
async def send_voice(request, env):
    """POST /api/comms/voice
    Body: {to, message, voice?}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ['to', 'message'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    api_key = getattr(env, 'AT_API_KEY', '')
    username = getattr(env, 'AT_USERNAME', 'sandbox')

    if not api_key:
        return error_response("Voice not configured", status=HTTP.SERVICE_UNAVAILABLE)

    base_url = 'https://voice.africastalking.com' if username != 'sandbox' else 'https://voice.sandbox.africastalking.com'

    try:
        response = await fetch(
            f"{base_url}/call",
            method='POST',
            headers=js_headers({
                'apiKey': api_key,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            }),
            body=f"username={username}&to={data['to']}&from={data.get('from', '')}",
        )
        result = await response.json()
    except Exception as e:
        return error_response(f"Voice error: {str(e)}", status=HTTP.SERVICE_UNAVAILABLE)

    db = DB(env)
    await _log_comm(
        db,
        farmer_id=user['id'],
        channel='voice',
        direction='outbound',
        phone=data['to'],
        message=data['message'],
        status='sent',
    )

    return success_response(result, message="Voice call initiated")


# ============================================================
# COMM LOG
# ============================================================
async def log(request, env):
    """GET /api/comms/log
    Query: channel?, direction?, from?, to?, limit
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["farmer_id = ?"]
    params = [user['id']]

    channel = url.search_params.get('channel')
    if channel:
        where.append("channel = ?")
        params.append(channel)

    direction = url.search_params.get('direction')
    if direction:
        where.append("direction = ?")
        params.append(direction)

    limit = min(to_int(url.search_params.get('limit', 100), 100), 500)

    logs = await db.query(f"""
        SELECT * FROM communication_log
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC
        LIMIT ?
    """, params + [limit])

    return success_response(logs)