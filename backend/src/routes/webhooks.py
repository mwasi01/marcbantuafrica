"""
Marcbantu Africa — Webhook routes.
Inbound callbacks: M-Pesa, Africa's Talking delivery reports.
"""
from utils import success_response, log_event, now_iso
from db import DB


# ============================================================
# M-PESA CALLBACK
# ============================================================
async def mpesa_callback(request, env):
    """POST /api/webhooks/mpesa
    Receives M-Pesa STK push / C2B callbacks.
    """
    try:
        body = await request.json()
    except Exception:
        return Response('Invalid JSON', status=400)

    log_event('mpesa_callback', {'body': body})

    db = DB(env)

    # Handle STK push result
    stk = body.get('Body', {}).get('stkCallback', {})
    if stk:
        checkout_id = stk.get('CheckoutRequestID')
        result_code = stk.get('ResultCode')
        result_desc = stk.get('ResultDesc')
        callback_metadata = stk.get('CallbackMetadata', {}).get('Item', [])

        amount = None
        mpesa_receipt = None
        phone = None
        for item in callback_metadata:
            if item.get('Name') == 'Amount':
                amount = item.get('Value')
            elif item.get('Name') == 'MpesaReceiptNumber':
                mpesa_receipt = item.get('Value')
            elif item.get('Name') == 'PhoneNumber':
                phone = str(item.get('Value'))

        # Log the transaction in audit
        await db.insert('audit_log', {
            'action': 'mpesa_payment',
            'entity': 'payment',
            'details': f"CheckoutID={checkout_id} Amount={amount} Receipt={mpesa_receipt} Phone={phone} Result={result_code}",
        })

        # If successful, find farmer by phone and record income
        if result_code == 0 and phone:
            farmer = await db.query_one(
                "SELECT id FROM farmers WHERE phone LIKE ? LIMIT 1",
                [f"%{phone[-9:]}"]
            )
            if farmer:
                farm = await db.query_one(
                    "SELECT id FROM farms WHERE farmer_id = ? AND active = 1 LIMIT 1",
                    [farmer['id']]
                )
                if farm and amount:
                    await db.insert('transactions', {
                        'farm_id': farm['id'],
                        'type': 'income',
                        'category': 'other_income',
                        'description': f"M-Pesa payment — {mpesa_receipt or 'N/A'}",
                        'amount': float(amount),
                        'payment_method': 'mpesa',
                        'reference': mpesa_receipt,
                        'transaction_date': now_iso()[:10],
                    })

    # Handle C2B validation/confirmation
    c2b = body.get('TransID') or body.get('TransId')
    if c2b:
        log_event('mpesa_c2b', {'trans_id': c2b, 'body': body})

    return success_response({
        'ResultCode': 0,
        'ResultDesc': 'Accepted',
    })


# ============================================================
# AFRICA'S TALKING DELIVERY REPORT
# ============================================================
async def africastalking_callback(request, env):
    """POST /api/webhooks/africastalking
    Receives SMS delivery reports and voice call updates.
    """
    try:
        form = await request.formData()
        data = {k: form.get(k) for k in form.keys()}
    except Exception:
        data = {}

    log_event('at_callback', data)

    db = DB(env)

    # SMS delivery report
    if 'id' in data and 'status' in data:
        at_message_id = data.get('id')
        status = data.get('status', '').lower()
        phone = data.get('phoneNumber')

        # Map statuses
        status_map = {
            'success': 'delivered',
            'sent': 'sent',
            'failed': 'failed',
            'rejected': 'failed',
            'buffered': 'queued',
        }
        new_status = status_map.get(status, status)

        # Update comm log
        if phone:
            await db.execute("""
                UPDATE communication_log
                SET status = ?, external_id = ?
                WHERE phone = ? AND channel = 'sms' AND direction = 'outbound'
                AND status IN ('queued', 'sent')
            """, [new_status, at_message_id, phone])

    # Voice call status
    if 'callSessionState' in data or 'sessionId' in data:
        log_event('at_voice_callback', data)

    return Response('OK', status=200, headers={'Content-Type': 'text/plain'})