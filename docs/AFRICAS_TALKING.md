
---

## 18.6 `docs/AFRICAS_TALKING.md`

```markdown
# Marcbantu Africa — Africa's Talking Setup

Complete guide to SMS, USSD, Voice, WhatsApp, and Payments via Africa's Talking.

---

## Why Africa's Talking?

- **Pan-African** — direct telecom connections in 20+ countries
- **USSD native** — most providers can't do USSD properly
- **Cheaper** than Twilio/Vonage for African SMS
- **Local support** — Nairobi-based team
- **Mobile money** integration (M-Pesa etc.)
- **Airtime** API — reward farmers directly

---

## Sign Up

1. Go to https://africastalking.com
2. Create account (email + phone)
3. Verify email + phone
4. Choose **Sandbox** for testing
5. Later apply for **Production**

---

## Sandbox Setup (Free Testing)

### Get Credentials

1. Dashboard → Settings → API Key
2. Note your **username** (usually `sandbox`)
3. Copy API key

### Test Numbers

In sandbox, you can only send to verified numbers:

1. Dashboard → SMS → Test Numbers
2. Add your phone (+254...)
3. Receive verification code
4. Enter code

### Test USSD

Dashboard → USSD → Sandbox gives you a code like `*384*12345#`.

### Test from Code

```python
# From backend
api_key = env.AT_API_KEY         # sandbox key
username = env.AT_USERNAME        # "sandbox"