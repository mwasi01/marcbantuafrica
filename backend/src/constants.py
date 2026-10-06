"""
Marcbantu Africa — Application constants.
Centralized enums and lookup values.
"""

# ============================================================
# SUBSCRIPTION TIERS
# ============================================================
class Tier:
    STARTER = 'starter'
    PRO = 'pro'
    BUSINESS = 'business'
    ALL = [STARTER, PRO, BUSINESS]


TIER_LIMITS = {
    Tier.STARTER: {'farms': 1, 'records_per_month': 500, 'sms_per_month': 30},
    Tier.PRO:     {'farms': 5, 'records_per_month': 5000, 'sms_per_month': 300},
    Tier.BUSINESS: {'farms': 50, 'records_per_month': 50000, 'sms_per_month': 3000},
}


# ============================================================
# ENTERPRISE TYPES
# ============================================================
class EnterpriseType:
    CROP = 'crop'
    LIVESTOCK = 'livestock'
    POULTRY = 'poultry'
    HORTICULTURE = 'horticulture'
    AQUACULTURE = 'aquaculture'
    MIXED = 'mixed'
    OTHER = 'other'
    ALL = [CROP, LIVESTOCK, POULTRY, HORTICULTURE, AQUACULTURE, MIXED, OTHER]


# ============================================================
# RECORD TYPES
# ============================================================
class RecordType:
    CROP_ACTIVITY = 'crop_activity'
    LIVESTOCK = 'livestock'
    POULTRY = 'poultry'
    INPUT = 'input'
    HARVEST = 'harvest'
    SALE = 'sale'
    EXPENSE = 'expense'
    OBSERVATION = 'observation'
    OTHER = 'other'
    ALL = [CROP_ACTIVITY, LIVESTOCK, POULTRY, INPUT, HARVEST,
           SALE, EXPENSE, OBSERVATION, OTHER]


# ============================================================
# TRANSACTION TYPES
# ============================================================
class TransactionType:
    INCOME = 'income'
    EXPENSE = 'expense'
    ALL = [INCOME, EXPENSE]


# ============================================================
# TRANSACTION CATEGORIES
# ============================================================
class Category:
    # Income
    MILK_SALES = 'milk_sales'
    CROP_SALES = 'crop_sales'
    POULTRY_SALES = 'poultry_sales'
    LIVESTOCK_SALES = 'livestock_sales'
    VEGETABLE_SALES = 'vegetable_sales'
    OTHER_INCOME = 'other_income'

    # Expense
    SEEDS = 'seeds'
    FERTILIZER = 'fertilizer'
    CHEMICALS = 'chemicals'
    FEEDS = 'feeds'
    LABOUR = 'labour'
    VET = 'vet'
    TRANSPORT = 'transport'
    EQUIPMENT = 'equipment'
    FUEL = 'fuel'
    WATER = 'water'
    ELECTRICITY = 'electricity'
    RENT = 'rent'
    OTHER_EXPENSE = 'other_expense'


INCOME_CATEGORIES = [
    Category.MILK_SALES, Category.CROP_SALES, Category.POULTRY_SALES,
    Category.LIVESTOCK_SALES, Category.VEGETABLE_SALES, Category.OTHER_INCOME,
]

EXPENSE_CATEGORIES = [
    Category.SEEDS, Category.FERTILIZER, Category.CHEMICALS, Category.FEEDS,
    Category.LABOUR, Category.VET, Category.TRANSPORT, Category.EQUIPMENT,
    Category.FUEL, Category.WATER, Category.ELECTRICITY, Category.RENT,
    Category.OTHER_EXPENSE,
]


# ============================================================
# PAYMENT METHODS
# ============================================================
class PaymentMethod:
    CASH = 'cash'
    MPESA = 'mpesa'
    AIRTEL = 'airtel'
    BANK = 'bank'
    CHEQUE = 'cheque'
    CREDIT = 'credit'
    OTHER = 'other'
    ALL = [CASH, MPESA, AIRTEL, BANK, CHEQUE, CREDIT, OTHER]


# ============================================================
# PRIORITIES
# ============================================================
class Priority:
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    URGENT = 'urgent'
    ALL = [LOW, MEDIUM, HIGH, URGENT]


# ============================================================
# TASK / STATUS
# ============================================================
class TaskStatus:
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    ALL = [PENDING, IN_PROGRESS, COMPLETED, CANCELLED]


class PaymentStatus:
    PENDING = 'pending'
    PARTIAL = 'partial'
    PAID = 'paid'
    CANCELLED = 'cancelled'
    ALL = [PENDING, PARTIAL, PAID, CANCELLED]


# ============================================================
# PEST SEVERITY
# ============================================================
class Severity:
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'
    ALL = [LOW, MEDIUM, HIGH, CRITICAL]


# ============================================================
# COMMUNICATION CHANNELS
# ============================================================
class Channel:
    SMS = 'sms'
    USSD = 'ussd'
    WHATSAPP = 'whatsapp'
    VOICE = 'voice'
    EMAIL = 'email'
    PUSH = 'push'
    ALL = [SMS, USSD, WHATSAPP, VOICE, EMAIL, PUSH]


# ============================================================
# NOTIFICATION TYPES
# ============================================================
class NotificationType:
    WEATHER = 'weather'
    MARKET = 'market'
    REMINDER = 'reminder'
    ALERT = 'alert'
    SYSTEM = 'system'
    FINANCE = 'finance'
    PEST = 'pest'
    LEARNING = 'learning'
    ALL = [WEATHER, MARKET, REMINDER, ALERT, SYSTEM, FINANCE, PEST, LEARNING]


# ============================================================
# ERROR CODES
# ============================================================
class ErrorCode:
    # Auth
    UNAUTHORIZED = 'UNAUTHORIZED'
    FORBIDDEN = 'FORBIDDEN'
    INVALID_CREDENTIALS = 'INVALID_CREDENTIALS'
    TOKEN_EXPIRED = 'TOKEN_EXPIRED'
    PHONE_EXISTS = 'PHONE_EXISTS'
    EMAIL_EXISTS = 'EMAIL_EXISTS'

    # Validation
    VALIDATION_ERROR = 'VALIDATION_ERROR'
    MISSING_FIELD = 'MISSING_FIELD'
    INVALID_FORMAT = 'INVALID_FORMAT'

    # Resource
    NOT_FOUND = 'NOT_FOUND'
    ALREADY_EXISTS = 'ALREADY_EXISTS'
    CONFLICT = 'CONFLICT'

    # Rate limit
    RATE_LIMITED = 'RATE_LIMITED'

    # Server
    INTERNAL_ERROR = 'INTERNAL_ERROR'
    EXTERNAL_API_ERROR = 'EXTERNAL_API_ERROR'

    # Business
    TIER_LIMIT_EXCEEDED = 'TIER_LIMIT_EXCEEDED'
    INSUFFICIENT_FUNDS = 'INSUFFICIENT_FUNDS'


# ============================================================
# HTTP STATUS
# ============================================================
class HTTP:
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    UNPROCESSABLE = 422
    TOO_MANY_REQUESTS = 429
    INTERNAL_ERROR = 500
    SERVICE_UNAVAILABLE = 503


# ============================================================
# LANGUAGES
# ============================================================
class Language:
    ENGLISH = 'en'
    SWAHILI = 'sw'
    FRENCH = 'fr'
    AMHARIC = 'am'
    ALL = [ENGLISH, SWAHILI, FRENCH, AMHARIC]


# ============================================================
# PAGINATION
# ============================================================
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


# ============================================================
# DATE FORMATS
# ============================================================
DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
ISO_FORMAT = '%Y-%m-%dT%H:%M:%SZ'