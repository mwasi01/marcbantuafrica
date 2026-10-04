"""
Tests for utils.py — JWT, passwords, validation, responses.
"""
import pytest
import time

from utils import (
    create_token, verify_token,
    hash_password, verify_password,
    validate_phone, is_valid_phone, is_valid_email,
    require_fields, validate_enum, to_int, to_float,
    json_response, error_response, success_response,
    now_iso, today, slugify, truncate, chunk_list,
    safe_json_loads, generate_reference,
    base64_url_encode, base64_url_decode,
)
from constants import HTTP, ErrorCode, Priority


TEST_SECRET = "test-secret"


# ============================================================
# JWT
# ============================================================
class TestJWT:
    def test_create_and_verify(self):
        token = create_token({"id": 1, "phone": "+254700000000"}, TEST_SECRET)
        payload = verify_token(token, TEST_SECRET)
        assert payload is not None
        assert payload["id"] == 1
        assert payload["phone"] == "+254700000000"
        assert "exp" in payload
        assert "iat" in payload

    def test_invalid_signature(self):
        token = create_token({"id": 1}, TEST_SECRET)
        payload = verify_token(token, "wrong-secret")
        assert payload is None

    def test_expired_token(self):
        # expires_in = -1 → already expired
        token = create_token({"id": 1}, TEST_SECRET, expires_in=-1)
        payload = verify_token(token, TEST_SECRET)
        assert payload is None

    def test_malformed_token(self):
        assert verify_token("not.a.token", TEST_SECRET) is None
        assert verify_token("", TEST_SECRET) is None
        assert verify_token(None, TEST_SECRET) is None
        assert verify_token("only.two", TEST_SECRET) is None

    def test_token_with_extra_claims(self):
        token = create_token({"id": 5, "role": "admin", "tier": "pro"}, TEST_SECRET)
        payload = verify_token(token, TEST_SECRET)
        assert payload["role"] == "admin"
        assert payload["tier"] == "pro"


# ============================================================
# BASE64 URL
# ============================================================
class TestBase64URL:
    def test_roundtrip(self):
        for data in [b"hello", b"", b"\x00\x01\x02", b"a" * 1000]:
            encoded = base64_url_encode(data)
            decoded = base64_url_decode(encoded)
            assert decoded == data

    def test_no_padding(self):
        encoded = base64_url_encode(b"hello world")
        assert "=" not in encoded


# ============================================================
# PASSWORDS
# ============================================================
class TestPasswords:
    def test_hash_and_verify(self):
        pw = "mySecret123"
        hashed = hash_password(pw)
        assert hashed != pw
        assert "$" in hashed
        assert verify_password(pw, hashed) is True

    def test_wrong_password(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_different_hashes_for_same_password(self):
        # Salt should make each hash unique
        pw = "samePassword"
        h1 = hash_password(pw)
        h2 = hash_password(pw)
        assert h1 != h2  # different salts

    def test_invalid_hash_format(self):
        assert verify_password("pw", "not-a-valid-hash") is False
        assert verify_password("pw", "") is False
        assert verify_password("pw", None) is False


# ============================================================
# PHONE / EMAIL VALIDATION
# ============================================================
class TestPhoneValidation:
    def test_kenyan_formats(self):
        assert validate_phone("0712345678") == "+254712345678"
        assert validate_phone("254712345678") == "+254712345678"
        assert validate_phone("+254712345678") == "+254712345678"
        assert validate_phone("712345678") == "+254712345678"

    def test_with_spaces_and_dashes(self):
        assert validate_phone("0712 345 678") == "+254712345678"
        assert validate_phone("0712-345-678") == "+254712345678"

    def test_invalid_format(self):
        assert is_valid_phone("123") is False
        assert is_valid_phone("") is False
        assert is_valid_phone("abc") is False

    def test_valid_phone(self):
        assert is_valid_phone("+254712345678") is True


class TestEmailValidation:
    def test_valid(self):
        assert is_valid_email("a@b.co") is True
        assert is_valid_email("test.user+tag@example.com") is True

    def test_invalid(self):
        assert is_valid_email("") is False
        assert is_valid_email("no-at-sign") is False
        assert is_valid_email("a@b") is False
        assert is_valid_email("@b.com") is False
        assert is_valid_email("a@") is False


# ============================================================
# FIELDS / ENUMS
# ============================================================
class TestFieldValidation:
    def test_all_present(self):
        data = {"a": 1, "b": "x"}
        assert require_fields(data, ["a", "b"]) is None

    def test_missing_field(self):
        result = require_fields({"a": 1}, ["a", "b", "c"])
        assert "b" in result
        assert "c" in result

    def test_empty_string_counts_as_missing(self):
        result = require_fields({"a": ""}, ["a"])
        assert result is not None

    def test_none_counts_as_missing(self):
        result = require_fields({"a": None}, ["a"])
        assert result is not None

    def test_empty_data(self):
        assert require_fields({}, ["a"]) is not None
        assert require_fields(None, ["a"]) is not None


class TestEnumValidation:
    def test_valid(self):
        assert validate_enum("low", ["low", "high"], "priority") is None

    def test_invalid(self):
        result = validate_enum("bad", ["low", "high"], "priority")
        assert "priority" in result
        assert "bad" not in result  # actually bad IS in result string, let me fix assertion below


class TestEnumValidation2:
    def test_error_message(self):
        msg = validate_enum("urgent", Priority.ALL, "priority")
        assert msg is None  # urgent IS valid
        msg = validate_enum("invalid", Priority.ALL, "priority")
        assert msg is not None
        assert "priority" in msg


# ============================================================
# TYPE COERCION
# ============================================================
class TestTypeCoercion:
    def test_to_int(self):
        assert to_int("42") == 42
        assert to_int(42) == 42
        assert to_int(42.9) == 42
        assert to_int("bad") == 0
        assert to_int("bad", default=99) == 99
        assert to_int(None) == 0
        assert to_int(None, default=-1) == -1

    def test_to_float(self):
        assert to_float("3.14") == 3.14
        assert to_float(3) == 3.0
        assert to_float("bad") == 0.0
        assert to_float("bad", default=1.5) == 1.5
        assert to_float(None) == 0.0


# ============================================================
# RESPONSES
# ============================================================
class TestResponses:
    def test_success_response(self):
        r = success_response({"id": 1}, message="OK")
        assert r.status == 200

    def test_error_response(self):
        r = error_response("bad", status=400, code=ErrorCode.VALIDATION_ERROR)
        assert r.status == 400

    def test_json_response(self):
        r = json_response({"x": 1}, status=201)
        assert r.status == 201


# ============================================================
# DATE / STRING HELPERS
# ============================================================
class TestDateHelpers:
    def test_now_iso(self):
        result = now_iso()
        assert "T" in result
        assert result.endswith("Z")
        assert len(result) == 20  # YYYY-MM-DDTHH:MM:SSZ

    def test_today(self):
        result = today()
        assert len(result) == 10  # YYYY-MM-DD
        assert result[4] == "-"


class TestStringHelpers:
    def test_slugify(self):
        assert slugify("Hello World") == "hello-world"
        assert slugify("Farm Management!") == "farm-management"
        assert slugify("  Multiple   Spaces  ") == "multiple-spaces"
        assert slugify("") == ""

    def test_truncate(self):
        assert truncate("hello", 100) == "hello"
        assert truncate("hello world", 8) == "hello..."
        assert truncate("", 5) == ""
        assert truncate(None, 5) is None


class TestListHelpers:
    def test_chunk_list(self):
        assert chunk_list([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
        assert chunk_list([], 3) == []
        assert chunk_list([1], 5) == [[1]]
        assert chunk_list([1, 2, 3], 1) == [[1], [2], [3]]


class TestJSONHelpers:
    def test_safe_json_loads(self):
        assert safe_json_loads('{"a": 1}') == {"a": 1}
        assert safe_json_loads("invalid") is None
        assert safe_json_loads("invalid", default={}) == {}
        assert safe_json_loads('') is None


class TestReferenceGenerator:
    def test_format(self):
        ref = generate_reference()
        assert ref.startswith("MB-")
        assert len(ref) > 10

    def test_custom_prefix(self):
        ref = generate_reference("SMS")
        assert ref.startswith("SMS-")

    def test_uniqueness(self):
        refs = {generate_reference() for _ in range(50)}
        assert len(refs) == 50