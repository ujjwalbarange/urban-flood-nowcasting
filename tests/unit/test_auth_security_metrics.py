"""Unit tests for Authentication, Rate Limiting, and Prometheus Metrics (Phase 2I)."""

import pytest
from httpx import AsyncClient, ASGITransport

from services.api.main import app
from services.api.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hashing_and_verification():
    """Verify PBKDF2 password hashing and constant-time verification."""
    pwd = "mumbai_monsoon_secure_2026"
    hashed = hash_password(pwd)
    assert "$" in hashed
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_jwt_creation_and_decoding():
    """Verify HS256 JWT access token creation and decoding."""
    payload = {"sub": "operator", "role": "operator", "ward_id": "FN"}
    token = create_access_token(payload)
    assert isinstance(token, str)
    assert len(token) > 20

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "operator"
    assert decoded["role"] == "operator"
    assert decoded["ward_id"] == "FN"
    assert "exp" in decoded


@pytest.mark.asyncio
async def test_auth_login_and_me_profile():
    """Verify login returns Bearer token and /auth/me returns current user."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login with operator
        r = await client.post("/api/v1/auth/login", json={"username": "operator", "password": "operator123"})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "operator"
        token = data["access_token"]

        # 2. Access /auth/me with Bearer token
        r_me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r_me.status_code == 200
        user_info = r_me.json()
        assert user_info["username"] == "operator"
        assert user_info["role"] == "operator"
        assert user_info["ward_id"] == "FN"

        # 3. Invalid password login
        r_fail = await client.post("/api/v1/auth/login", json={"username": "operator", "password": "wrong"})
        assert r_fail.status_code == 401


@pytest.mark.asyncio
async def test_auth_role_restriction():
    """Verify admin-only endpoints reject non-admin users with 403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Citizen login
        r_cit = await client.post("/api/v1/auth/login", json={"username": "citizen", "password": "citizen123"})
        assert r_cit.status_code == 200
        cit_token = r_cit.json()["access_token"]

        # Citizen attempts to access /auth/users (admin only)
        r_forbidden = await client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {cit_token}"})
        assert r_forbidden.status_code == 403

        # Admin login
        r_adm = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "mumbai_admin_2026"})
        assert r_adm.status_code == 200
        adm_token = r_adm.json()["access_token"]

        # Admin accesses /auth/users
        r_allowed = await client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {adm_token}"})
        assert r_allowed.status_code == 200
        users_list = r_allowed.json()
        assert len(users_list) >= 4


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint():
    """Verify /metrics exposes valid Prometheus text format."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/metrics")
        assert r.status_code == 200
        assert "text/plain" in r.headers.get("content-type", "")
        text_body = r.text
        assert "mufns_uptime_seconds" in text_body
        assert "# HELP" in text_body
        assert "# TYPE" in text_body


@pytest.mark.asyncio
async def test_rate_limiting_headers():
    """Verify rate limiting headers are returned on requests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
        # Health check is exempt, so let's call an API route
        r_api = await client.get("/api/v1/geodata/wards")
        assert r_api.status_code == 200
        assert "x-ratelimit-limit" in r_api.headers
        assert "x-ratelimit-remaining" in r_api.headers
        assert "x-ratelimit-reset" in r_api.headers
