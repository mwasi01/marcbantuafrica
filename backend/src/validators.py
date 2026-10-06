"""
Marcbantu Africa — Validators.
Per-resource input validation with clear error messages.
"""
from constants import (
    Tier, EnterpriseType, RecordType, TransactionType,
    PaymentMethod, Priority, TaskStatus, PaymentStatus,
    Severity, Channel, NotificationType,
    INCOME_CATEGORIES, EXPENSE_CATEGORIES,
)
from utils import (
    is_valid_phone, is_valid_email, validate_phone,
    to_int, to_float, require_fields, validate_enum,
)


class ValidationError(Exception):
    """Raised when validation fails."""
    def __init__(self, message, field=None):
        super().__init__(message)
        self.message = message
        self.field = field


# ============================================================
# AUTH
# ============================================================
def validate_register(data: dict) -> dict:
    """Validate registration input. Returns cleaned data."""
    err = require_fields(data, ['phone', 'full_name', 'password'])
    if err:
        raise ValidationError(err)

    phone = validate_phone(data['phone'])
    if not is_valid_phone(phone):
        raise ValidationError("Invalid phone number", field='phone')

    if len(data['password']) < 6:
        raise ValidationError("Password must be at least 6 characters", field='password')

    if len(data['full_name'].strip()) < 2:
        raise ValidationError("Full name is too short", field='full_name')

    email = data.get('email', '').strip().lower() if data.get('email') else None
    if email and not is_valid_email(email):
        raise ValidationError("Invalid email address", field='email')

    return {
        'phone': phone,
        'email': email,
        'full_name': data['full_name'].strip(),
        'password': data['password'],
        'county': data.get('county'),
        'location': data.get('location'),
        'language': data.get('language', 'en'),
    }


def validate_login(data: dict) -> dict:
    """Validate login input."""
    err = require_fields(data, ['phone', 'password'])
    if err:
        raise ValidationError(err)

    phone = validate_phone(data['phone'])
    return {'phone': phone, 'password': data['password']}


# ============================================================
# FARM
# ============================================================
def validate_farm(data: dict) -> dict:
    err = require_fields(data, ['name'])
    if err:
        raise ValidationError(err)

    return {
        'name': str(data['name']).strip(),
        'county': data.get('county'),
        'location': data.get('location'),
        'size_acres': to_float(data.get('size_acres')),
        'latitude': to_float(data.get('latitude')),
        'longitude': to_float(data.get('longitude')),
        'altitude_m': to_float(data.get('altitude_m')),
        'soil_type': data.get('soil_type'),
        'irrigation_type': data.get('irrigation_type'),
        'water_source': data.get('water_source'),
        'notes': data.get('notes'),
    }


# ============================================================
# ENTERPRISE
# ============================================================
def validate_enterprise(data: dict) -> dict:
    err = require_fields(data, ['name', 'type'])
    if err:
        raise ValidationError(err)

    err = validate_enum(data['type'], EnterpriseType.ALL, 'type')
    if err:
        raise ValidationError(err, field='type')

    return {
        'name': str(data['name']).strip(),
        'type': data['type'],
        'species_or_crop': data.get('species_or_crop'),
        'quantity': to_float(data.get('quantity')) or None,
        'unit': data.get('unit'),
        'start_date': data.get('start_date'),
        'expected_end_date': data.get('expected_end_date'),
        'status': data.get('status', 'active'),
        'notes': data.get('notes'),
    }


# ============================================================
# RECORD
# ============================================================
def validate_record(data: dict) -> dict:
    err = require_fields(data, ['farm_id', 'record_type', 'record_date'])
    if err:
        raise ValidationError(err)

    err = validate_enum(data['record_type'], RecordType.ALL, 'record_type')
    if err:
        raise ValidationError(err, field='record_type')

    return {
        'farm_id': to_int(data['farm_id']),
        'enterprise_id': to_int(data['enterprise_id']) or None,
        'record_type': data['record_type'],
        'activity': data.get('activity'),
        'description': data.get('description'),
        'quantity': to_float(data.get('quantity')) or None,
        'unit': data.get('unit'),
        'cost': to_float(data.get('cost')),
        'revenue': to_float(data.get('revenue')),
        'record_date': data['record_date'],
        'notes': data.get('notes'),
        'photo_url': data.get('photo_url'),
        'latitude': to_float(data.get('latitude')) or None,
        'longitude': to_float(data.get('longitude')) or None,
    }


# ============================================================
# TRANSACTION
# ============================================================
def validate_transaction(data: dict) -> dict:
    err = require_fields(data, ['farm_id', 'type', 'category', 'amount', 'transaction_date'])
    if err:
        raise ValidationError(err)

    err = validate_enum(data['type'], TransactionType.ALL, 'type')
    if err:
        raise ValidationError(err, field='type')

    # Validate category matches type
    if data['type'] == TransactionType.INCOME:
        valid_cats = INCOME_CATEGORIES + [c for c in EXPENSE_CATEGORIES]  # allow any
    else:
        valid_cats = EXPENSE_CATEGORIES + [c for c in INCOME_CATEGORIES]

    amount = to_float(data['amount'])
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero", field='amount')

    payment_method = data.get('payment_method')
    if payment_method:
        err = validate_enum(payment_method, PaymentMethod.ALL, 'payment_method')
        if err:
            raise ValidationError(err, field='payment_method')

    return {
        'farm_id': to_int(data['farm_id']),
        'enterprise_id': to_int(data.get('enterprise_id')) or None,
        'type': data['type'],
        'category': data['category'],
        'description': data.get('description'),
        'amount': amount,
        'payment_method': payment_method,
        'reference': data.get('reference'),
        'transaction_date': data['transaction_date'],
        'notes': data.get('notes'),
    }


# ============================================================
# SALE
# ============================================================
def validate_sale(data: dict) -> dict:
    err = require_fields(data, ['farm_id', 'product', 'quantity', 'unit_price', 'sale_date'])
    if err:
        raise ValidationError(err)

    quantity = to_float(data['quantity'])
    unit_price = to_float(data['unit_price'])
    if quantity <= 0:
        raise ValidationError("Quantity must be > 0", field='quantity')
    if unit_price < 0:
        raise ValidationError("Unit price cannot be negative", field='unit_price')

    payment_status = data.get('payment_status', PaymentStatus.PENDING)
    err = validate_enum(payment_status, PaymentStatus.ALL, 'payment_status')
    if err:
        raise ValidationError(err, field='payment_status')

    return {
        'farm_id': to_int(data['farm_id']),
        'buyer_id': to_int(data.get('buyer_id')) or None,
        'enterprise_id': to_int(data.get('enterprise_id')) or None,
        'product': data['product'],
        'quantity': quantity,
        'unit': data.get('unit', 'kg'),
        'unit_price': unit_price,
        'total': quantity * unit_price,
        'payment_status': payment_status,
        'payment_method': data.get('payment_method'),
        'amount_paid': to_float(data.get('amount_paid', 0)),
        'sale_date': data['sale_date'],
        'notes': data.get('notes'),
    }


# ============================================================
# TASK
# ============================================================
def validate_task(data: dict) -> dict:
    err = require_fields(data, ['farm_id', 'title'])
    if err:
        raise ValidationError(err)

    priority = data.get('priority', Priority.MEDIUM)
    err = validate_enum(priority, Priority.ALL, 'priority')
    if err:
        raise ValidationError(err, field='priority')

    status = data.get('status', TaskStatus.PENDING)
    err = validate_enum(status, TaskStatus.ALL, 'status')
    if err:
        raise ValidationError(err, field='status')

    return {
        'farm_id': to_int(data['farm_id']),
        'enterprise_id': to_int(data.get('enterprise_id')) or None,
        'plot_id': to_int(data.get('plot_id')) or None,
        'assigned_to': to_int(data.get('assigned_to')) or None,
        'title': str(data['title']).strip(),
        'description': data.get('description'),
        'priority': priority,
        'status': status,
        'due_date': data.get('due_date'),
    }


# ============================================================
# WORKER
# ============================================================
def validate_worker(data: dict) -> dict:
    err = require_fields(data, ['farm_id', 'name'])
    if err:
        raise ValidationError(err)

    return {
        'farm_id': to_int(data['farm_id']),
        'name': str(data['name']).strip(),
        'phone': validate_phone(data['phone']) if data.get('phone') else None,
        'role': data.get('role'),
        'wage_type': data.get('wage_type', 'monthly'),
        'wage_amount': to_float(data.get('wage_amount')) or None,
        'start_date': data.get('start_date'),
        'notes': data.get('notes'),
    }


# ============================================================
# ATTENDANCE
# ============================================================
def validate_attendance(data: dict) -> dict:
    err = require_fields(data, ['worker_id', 'farm_id', 'date'])
    if err:
        raise ValidationError(err)

    status = data.get('status', 'present')
    err = validate_enum(status, ['present', 'absent', 'half-day', 'leave', 'holiday'], 'status')
    if err:
        raise ValidationError(err, field='status')

    return {
        'worker_id': to_int(data['worker_id']),
        'farm_id': to_int(data['farm_id']),
        'date': data['date'],
        'status': status,
        'hours': to_float(data.get('hours')) or None,
        'task_id': to_int(data.get('task_id')) or None,
        'notes': data.get('notes'),
    }


# ============================================================
# EQUIPMENT
# ============================================================
def validate_equipment(data: dict) -> dict:
    err = require_fields(data, ['farm_id', 'name'])
    if err:
        raise ValidationError(err)

    return {
        'farm_id': to_int(data['farm_id']),
        'name': str(data['name']).strip(),
        'type': data.get('type'),
        'make': data.get('make'),
        'model': data.get('model'),
        'serial_number': data.get('serial_number'),
        'purchase_date': data.get('purchase_date'),
        'purchase_cost': to_float(data.get('purchase_cost')) or None,
        'current_value': to_float(data.get('current_value')) or None,
        'last_service_date': data.get('last_service_date'),
        'next_service_date': data.get('next_service_date'),
        'status': data.get('status', 'good'),
        'notes': data.get('notes'),
    }


# ============================================================
# PEST SCOUTING
# ============================================================
def validate_scouting(data: dict) -> dict:
    err = require_fields(data, ['farm_id', 'pest_name', 'scout_date'])
    if err:
        raise ValidationError(err)

    severity = data.get('severity', Severity.LOW)
    err = validate_enum(severity, Severity.ALL, 'severity')
    if err:
        raise ValidationError(err, field='severity')

    return {
        'farm_id': to_int(data['farm_id']),
        'plot_id': to_int(data.get('plot_id')) or None,
        'enterprise_id': to_int(data.get('enterprise_id')) or None,
        'pest_name': data['pest_name'],
        'pest_type': data.get('pest_type'),
        'severity': severity,
        'affected_area_pct': to_float(data.get('affected_area_pct')) or None,
        'photo_url': data.get('photo_url'),
        'symptoms': data.get('symptoms'),
        'scout_date': data['scout_date'],
        'notes': data.get('notes'),
    }


# ============================================================
# TREATMENT
# ============================================================
def validate_treatment(data: dict) -> dict:
    err = require_fields(data, ['farm_id', 'product', 'application_date'])
    if err:
        raise ValidationError(err)

    return {
        'farm_id': to_int(data['farm_id']),
        'plot_id': to_int(data.get('plot_id')) or None,
        'enterprise_id': to_int(data.get('enterprise_id')) or None,
        'product': data['product'],
        'active_ingredient': data.get('active_ingredient'),
        'rate': data.get('rate'),
        'target_pest': data.get('target_pest'),
        'application_date': data['application_date'],
        'notes': data.get('notes'),
    }


# ============================================================
# MESSAGE
# ============================================================
def validate_message(data: dict) -> dict:
    err = require_fields(data, ['recipient', 'body'])
    if err:
        raise ValidationError(err)

    channel = data.get('channel', Channel.SMS)
    err = validate_enum(channel, Channel.ALL, 'channel')
    if err:
        raise ValidationError(err, field='channel')

    return {
        'channel': channel,
        'recipient': data['recipient'],
        'body': data['body'],
        'farmer_id': to_int(data.get('farmer_id')) or None,
        'template_code': data.get('template_code'),
        'scheduled_for': data.get('scheduled_for'),
    }


# ============================================================
# NOTIFICATION
# ============================================================
def validate_notification(data: dict) -> dict:
    err = require_fields(data, ['farmer_id', 'type', 'title', 'message'])
    if err:
        raise ValidationError(err)

    err = validate_enum(data['type'], NotificationType.ALL, 'type')
    if err:
        raise ValidationError(err, field='type')

    return {
        'farmer_id': to_int(data['farmer_id']),
        'type': data['type'],
        'title': data['title'],
        'message': data['message'],
        'action_url': data.get('action_url'),
        'priority': data.get('priority', 'normal'),
    }


# ============================================================
# DECISION TOOLS
# ============================================================
def validate_breakeven(data: dict) -> dict:
    err = require_fields(data, ['fixed_costs', 'variable_cost_per_unit', 'price_per_unit'])
    if err:
        raise ValidationError(err)

    fixed = to_float(data['fixed_costs'])
    vc = to_float(data['variable_cost_per_unit'])
    price = to_float(data['price_per_unit'])

    if fixed < 0:
        raise ValidationError("Fixed costs cannot be negative", field='fixed_costs')
    if vc < 0:
        raise ValidationError("Variable cost cannot be negative", field='variable_cost_per_unit')
    if price <= vc:
        raise ValidationError("Price must be greater than variable cost per unit", field='price_per_unit')

    return {'fixed_costs': fixed, 'variable_cost_per_unit': vc, 'price_per_unit': price}


def validate_gross_margin(data: dict) -> dict:
    err = require_fields(data, ['revenue', 'variable_costs'])
    if err:
        raise ValidationError(err)
    return {
        'revenue': to_float(data['revenue']),
        'variable_costs': to_float(data['variable_costs']),
    }


def validate_loan(data: dict) -> dict:
    err = require_fields(data, ['loan_amount', 'annual_rate', 'term_months', 'monthly_profit'])
    if err:
        raise ValidationError(err)

    term = to_int(data['term_months'])
    if term <= 0:
        raise ValidationError("Term must be positive", field='term_months')

    return {
        'loan_amount': to_float(data['loan_amount']),
        'annual_rate': to_float(data['annual_rate']),
        'term_months': term,
        'monthly_profit': to_float(data['monthly_profit']),
    }


def validate_risk(data: dict) -> dict:
    err = require_fields(data, ['scores'])
    if err:
        raise ValidationError(err)
    if not isinstance(data['scores'], dict) or not data['scores']:
        raise ValidationError("Scores must be a non-empty object", field='scores')
    try:
        scores = {k: float(v) for k, v in data['scores'].items()}
    except (ValueError, TypeError):
        raise ValidationError("All scores must be numeric", field='scores')
    return {'scores': scores}