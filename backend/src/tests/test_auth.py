"""
Tests for routes/auth.py — register, login, logout, me, JWT flows.
"""
import json
import pytest

from routes import auth
from tests import (
    make_request, make_env, make_auth_header,
    seed_farmer, TEST_PHONE, TEST_PASSWORD, TEST_JWT_SECRET,
)


# ============================================================
# HELPER
# ============================================================
async def _parse(response):
    try:
        return json.loads(response.body)
    except Exception:
        return {}


# ============================================================
# REGISTER
# ============================================================
class TestRegister:
    @pytest.mark.asyncio
    async def test_success(self):
        env = make_env()
        request = make_request(method="POST", body={
            "phone": "+254799999999",
            "full_name": "New Farmer",
            "password": "securePass123",
        })
        response = await auth.register(request, env)
        assert response.status == 201
        body = await _parse(response)
        assert body["success"] is True
        assert "token" in body["data"]
        assert body["data"]["farmer"]["phone"] == "+254799999999"
        # Should be in DB
        assert len(env.DB.tables["farmers"]) == 1

    @pytest.mark.asyncio
    async def test_phone_already_exists(self):
        env = make_env()
        seed_farmer(env, phone=TEST_PHONE)
        request = make_request(method="POST", body={
            "phone": TEST_PHONE,
            "full_name": "Dup",
            "password": "whatever123",
        })
        response = await auth.register(request, env)
        assert response.status == 409
        body = await _parse(response)
        assert "already registered" in body["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_missing_required_field(self):
        env = make_env()
        request = make_request(method="POST", body={
            "phone": "+254799999999",
            # missing full_name and password
        })
        response = await auth.register(request, env)
        assert response.status == 400

    @pytest.mark.asyncio
    async def test_short_password(self):
        env = make_env()
        request = make_request(method="POST", body={
            "phone": "+254799999999",
            "full_name": "Test",
            "password": "123",
        })
        response = await auth.register(request, env)
        assert response.status == 400

    @pytest.mark.asyncio
    async def test_invalid_email(self):
        env = make_env()
        request = make_request(method="POST", body={
            "phone": "+254799999999",
            "full_name": "Test",
            "password": "securePass123",
            "email": "not-an-email",
        })
        response = await auth.register(request, env)
        assert response.status == 400

    @pytest.mark.asyncio
    async def test_phone_normalization(self):
        env = make_env()
        # Kenyan format 07... should normalize to +254...
        request = make_request(method="POST", body={
            "phone": "0799888777",
            "full_name": "Test",
            "password": "securePass123",
        })
        response = await auth.register(request, env)
        assert response.status == 201
        body = await _parse(response)
        assert body["data"]["farmer"]["phone"] == "+254799888777"


# ============================================================
# LOGIN
# ============================================================
class TestLogin:
    @pytest.mark.asyncio
    async def test_success(self):
        env = make_env()
        seed_farmer(env, farmer_id=1, phone=TEST_PHONE)
        request = make_request(method="POST", body={
            "phone": TEST_PHONE,
            "password": TEST_PASSWORD,
        })
        response = await auth.login(request, env)
        assert response.status == 200
        body = await _parse(response)
        assert body["success"] is True
        assert "token" in body["data"]
        assert body["data"]["farmer"]["phone"] == TEST_PHONE
        # password_hash should not be in response
        assert "password_hash" not in body["data"]["farmer"]

    @pytest.mark.asyncio
    async def test_wrong_password(self):
        env = make_env()
        seed_farmer(env, phone=TEST_PHONE)
        request = make_request(method="POST", body={
            "phone": TEST_PHONE,
            "password": "wrongPassword",
        })
        response = await auth.login(request, env)
        assert response.status == 401

    @pytest.mark.asyncio
    async def test_unknown_phone(self):
        env = make_env()
        request = make_request(method="POST", body={
            "phone": "+254700000000",
            "password": "anything",
        })
        response = await auth.login(request, env)
        assert response.status == 401

    @pytest.mark.asyncio
    async def test_missing_password(self):
        env = make_env()
        request = make_request(method="POST", body={"phone": TEST_PHONE})
        response = await auth.login(request, env)
        assert response.status == 400


# ============================================================
# ME
# ============================================================
class TestMe:
    @pytest.mark.asyncio
    async def test_authenticated(self):
        env = make_env()
        seed_farmer(env, farmer_id=1)
        request = make_request(headers=make_auth_header(user_id=1))
        response = await auth.me(request, env)
        assert response.status == 200
        body = await _parse(response)
        assert body["data"]["id"] == 1
        assert body["data"]["phone"] == TEST_PHONE
        assert body["data"]["farm_count"] == 0  # no farms seeded

    @pytest.mark.asyncio
    async def test_no_token(self):
        env = make_env()
        seed_farmer(env)
        request = make_request()
        response = await auth.me(request, env)
        assert response.status == 401

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        env = make_env()
        seed_farmer(env)
        request = make_request(headers={"Authorization": "Bearer bogus.token.x"})
        response = await auth.me(request, env)
        assert response.status == 401


# ============================================================
# LOGOUT
# ============================================================
class TestLogout:
    @pytest.mark.asyncio
    async def test_success(self):
        env = make_env()
        seed_farmer(env, farmer_id=1)
        request = make_request(method="POST", headers=make_auth_header(1))
        response = await auth.logout(request, env)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_unauthenticated(self):
        env = make_env()
        request = make_request(method="POST")
        response = await auth.logout(request, env)
        assert response.status == 401


# ============================================================
# REFRESH
# ============================================================
class TestRefresh:
    @pytest.mark.asyncio
    async def test_valid_token(self):
        env = make_env()
        seed_farmer(env, farmer_id=1)
        request = make_request(method="POST", headers=make_auth_header(1))
        response = await auth.refresh(request, env)
        assert response.status == 200
        body = await _parse(response)
        assert "token" in body["data"]
        assert body["data"]["token"] != make_auth_header(1)["Authorization"].replace("Bearer ", "")

    @pytest.mark.asyncio
    async def test_no_token(self):
        env = make_env()
        request = make_request(method="POST")
        response = await auth.refresh(request, env)
        assert response.status == 401


# ============================================================
# CHANGE PASSWORD
# ============================================================
class TestChangePassword:
    @pytest.mark.asyncio
    async def test_success(self):
        env = make_env()
        seed_farmer(env, farmer_id=1, phone=TEST_PHONE)
        request = make_request(
            method="POST",
            body={"current_password": TEST_PASSWORD, "new_password": "newPass456"},
            headers=make_auth_header(1),
        )
        response = await auth.change_password(request, env)
        assert response.status == 200

        # Verify login with new password works
        login_req = make_request(method="POST", body={
            "phone": TEST_PHONE, "password": "newPass456",
        })
        login_resp = await auth.login(login_req, env)
        assert login_resp.status == 200

    @pytest.mark.asyncio
    async def test_wrong_current_password(self):
        env = make_env()
        seed_farmer(env, farmer_id=1)
        request = make_request(
            method="POST",
            body={"current_password": "wrongPass", "new_password": "newPass456"},
            headers=make_auth_header(1),
        )
        response = await auth.change_password(request, env)
        assert response.status == 401

    @pytest.mark.asyncio
    async def test_short_new_password(self):
        env = make_env()
        seed_farmer(env, farmer_id=1)
        request = make_request(
            method="POST",
            body={"current_password": TEST_PASSWORD, "new_password": "abc"},
            headers=make_auth_header(1),
        )
        response = await auth.change_password(request, env)
        assert response.status == 400

    @pytest.mark.asyncio
    async def test_same_password(self):
        env = make_env()
        seed_farmer(env, farmer_id=1)
        request = make_request(
            method="POST",
            body={"current_password": TEST_PASSWORD, "new_password": TEST_PASSWORD},
            headers=make_auth_header(1),
        )
        response = await auth.change_password(request, env)
        assert response.status == 400

    @pytest.mark.asyncio
    async def test_missing_fields(self):
        env = make_env()
        seed_farmer(env, farmer_id=1)
        request = make_request(
            method="POST",
            body={"current_password": TEST_PASSWORD},
            headers=make_auth_header(1),
        )
        response = await auth.change_password(request, env)
        assert response.status == 400


# ============================================================
# FORGOT PASSWORD
# ============================================================
class TestForgotPassword:
    @pytest.mark.asyncio
    async def test_known_phone(self):
        env = make_env()
        seed_farmer(env, phone=TEST_PHONE)
        request = make_request(method="POST", body={"phone": TEST_PHONE})
        response = await auth.forgot_password(request, env)
        assert response.status == 200
        # OTP should be in KV
        otp = await env.CACHE.get(f"otp:{TEST_PHONE}")
        assert otp is not None
        assert len(otp) == 6
        # SMS should be queued
        assert len(env.JOBS.sent) == 1
        assert env.JOBS.sent[0]["type"] == "send_sms"

    @pytest.mark.asyncio
    async def test_unknown_phone(self):
        # Should return 200 anyway (don't leak which phones exist)
        env = make_env()
        request = make_request(method="POST", body={"phone": "+254700000001"})
        response = await auth.forgot_password(request, env)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_missing_phone(self):
        env = make_env()
        request = make_request(method="POST", body={})
        response = await auth.forgot_password(request, env)
        assert response.status == 400


# ============================================================
# RESET PASSWORD
# ============================================================
class TestResetPassword:
    @pytest.mark.asyncio
    async def test_success(self):
        env = make_env()
        seed_farmer(env, phone=TEST_PHONE)
        # Pre-set OTP
        await env.CACHE.put(f"otp:{TEST_PHONE}", "123456", expirationTtl=600)

        request = make_request(method="POST", body={
            "phone": TEST_PHONE,
            "otp": "123456",
            "new_password": "resetPass789",
        })
        response = await auth.reset_password(request, env)
        assert response.status == 200

        # OTP should be consumed
        assert await env.CACHE.get(f"otp:{TEST_PHONE}") is None

        # Login with new password
        login_req = make_request(method="POST", body={
            "phone": TEST_PHONE, "password": "resetPass789",
        })
        login_resp = await auth.login(login_req, env)
        assert login_resp.status == 200

    @pytest.mark.asyncio
    async def test_wrong_otp(self):
        env = make_env()
        seed_farmer(env, phone=TEST_PHONE)
        await env.CACHE.put(f"otp:{TEST_PHONE}", "123456", expirationTtl=600)

        request = make_request(method="POST", body={
            "phone": TEST_PHONE,
            "otp": "999999",
            "new_password": "resetPass789",
        })
        response = await auth.reset_password(request, env)
        assert response.status == 401

    @pytest.mark.asyncio
    async def test_expired_otp(self):
        env = make_env()
        seed_farmer(env, phone=TEST_PHONE)
        # No OTP in KV

        request = make_request(method="POST", body={
            "phone": TEST_PHONE,
            "otp": "123456",
            "new_password": "resetPass789",
        })
        response = await auth.reset_password(request, env)
        assert response.status == 400


# ============================================================
# FULL AUTH FLOW
# ============================================================
class TestFullAuthFlow:
    @pytest.mark.asyncio
    async def test_register_login_access(self):
        env = make_env()

        # 1. Register
        reg = await auth.register(
            make_request(method="POST", body={
                "phone": "0700111222",
                "full_name": "Flow Farmer",
                "password": "flowPass123",
            }),
            env,
        )
        assert reg.status == 201
        reg_body = await _parse(reg)
        token = reg_body["data"]["token"]
        assert token

        # 2. Access /me with the token
        me = await auth.me(
            make_request(headers={"Authorization": f"Bearer {token}"}),
            env,
        )
        assert me.status == 200
        me_body = await _parse(me)
        assert me_body["data"]["phone"] == "+254700111222"

        # 3. Login again
        login = await auth.login(
            make_request(method="POST", body={
                "phone": "+254700111222",
                "password": "flowPass123",
            }),
            env,
        )
        assert login.status == 200

        # 4. Logout
        logout = await auth.logout(
            make_request(method="POST", headers=make_auth_header(1)),
            env,
        )
        assert logout.status == 200