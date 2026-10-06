"""
Marcbantu Africa — Configuration.
Loads environment variables and provides typed access.
"""
import os


class Config:
    """Application configuration."""

    def __init__(self, env):
        # Environment
        self.ENVIRONMENT = getattr(env, 'ENVIRONMENT', 'development')
        self.APP_NAME = getattr(env, 'APP_NAME', 'Marcbantu Africa')
        self.API_VERSION = getattr(env, 'API_VERSION', '1.0.0')
        self.FRONTEND_URL = getattr(env, 'FRONTEND_URL', 'http://localhost:8788')
        self.DEFAULT_LANGUAGE = getattr(env, 'DEFAULT_LANGUAGE', 'en')
        self.DEFAULT_COUNTRY = getattr(env, 'DEFAULT_COUNTRY', 'Kenya')

        # Secrets
        self.JWT_SECRET = getattr(env, 'JWT_SECRET', 'dev-secret-change-me')
        self.JWT_EXPIRY_HOURS = int(getattr(env, 'JWT_EXPIRY_HOURS', 24 * 7))

        # Africa's Talking
        self.AT_API_KEY = getattr(env, 'AT_API_KEY', '')
        self.AT_USERNAME = getattr(env, 'AT_USERNAME', 'sandbox')
        self.AT_SENDER_ID = getattr(env, 'AT_SENDER_ID', 'MARCBANTU')
        self.AT_USSD_CODE = getattr(env, 'AT_USSD_CODE', '')

        # WhatsApp
        self.WHATSAPP_TOKEN = getattr(env, 'WHATSAPP_TOKEN', '')
        self.WHATSAPP_PHONE_ID = getattr(env, 'WHATSAPP_PHONE_ID', '')

        # M-Pesa / Payments
        self.MPESA_CONSUMER_KEY = getattr(env, 'MPESA_CONSUMER_KEY', '')
        self.MPESA_CONSUMER_SECRET = getattr(env, 'MPESA_CONSUMER_SECRET', '')
        self.MPESA_SHORTCODE = getattr(env, 'MPESA_SHORTCODE', '')
        self.MPESA_PASSKEY = getattr(env, 'MPESA_PASSKEY', '')
        self.MPESA_CALLBACK_URL = getattr(env, 'MPESA_CALLBACK_URL', '')

        # External APIs
        self.OPEN_METEO_URL = getattr(env, 'OPEN_METEO_URL', 'https://api.open-meteo.com/v1')
        self.AMIS_API_URL = getattr(env, 'AMIS_API_URL', 'https://amis.co.ke/api')

        # Email
        self.EMAIL_FROM = getattr(env, 'EMAIL_FROM', 'noreply@marcbantuafrica.com')
        self.SUPPORT_EMAIL = getattr(env, 'SUPPORT_EMAIL', 'support@marcbantuafrica.com')

        # Feature flags
        self.FEATURE_SMS = getattr(env, 'FEATURE_SMS', 'true') == 'true'
        self.FEATURE_USSD = getattr(env, 'FEATURE_USSD', 'true') == 'true'
        self.FEATURE_WHATSAPP = getattr(env, 'FEATURE_WHATSAPP', 'true') == 'true'
        self.FEATURE_AI = getattr(env, 'FEATURE_AI', 'true') == 'true'

        # Rate limits
        self.RATE_LIMIT_PER_MINUTE = int(getattr(env, 'RATE_LIMIT_PER_MINUTE', 60))
        self.RATE_LIMIT_PER_DAY = int(getattr(env, 'RATE_LIMIT_PER_DAY', 5000))

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == 'production'

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT in ('development', 'dev', 'local')

    @property
    def is_staging(self) -> bool:
        return self.ENVIRONMENT == 'staging'