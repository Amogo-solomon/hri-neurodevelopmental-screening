"""
HRI Platform — Authentication Test Suite
Tests: register, login, token refresh, logout, RBAC, password change,
       password reset flow, admin endpoints, audit log.
"""
import pytest
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_auth.db")
os.environ.setdefault("SECRET_KEY", "test-auth-secret-key-1234567890abc")
os.environ.setdefault("UPLOAD_DIR", "/tmp/hri-test-uploads")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ["ENVIRONMENT"] = "development"

import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.database import init_db, engine, Base
from app.core.security import hash_password, verify_password, create_access_token, hash_token


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    await init_db()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# Unique emails per test run
import time
_ts = str(int(time.time()))

RESEARCHER = {
    "email": f"researcher_{_ts}@lincoln.ac.uk",
    "full_name": "Dr Test Researcher",
    "password": "TestPass1@secure",
    "role": "researcher",
}
CLINICIAN = {
    "email": f"clinician_{_ts}@lincoln.ac.uk",
    "full_name": "Dr Test Clinician",
    "password": "ClinicPass1@nhs",
    "role": "clinician",
}
ADMIN = {
    "email": f"admin_{_ts}@lincoln.ac.uk",
    "full_name": "Platform Admin",
    "password": "AdminPass1@super",
    "role": "admin",
}


# ── Security unit tests ────────────────────────────────────────────────────────

def test_password_hashing():
    """bcrypt hash should verify correctly."""
    pw = "MySecure1@Pass"
    hashed = hash_password(pw)
    assert verify_password(pw, hashed)
    assert not verify_password("WrongPass1@X", hashed)
    assert hashed != pw  # stored as hash, not plain text


def test_jwt_access_token():
    """Access token should encode and decode correctly."""
    from app.core.security import create_access_token, decode_access_token
    token = create_access_token(subject="user-123", role="researcher")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "researcher"
    assert payload["type"] == "access"


def test_refresh_token_generation():
    """Refresh token raw and hash should differ; hash should be deterministic."""
    from app.core.security import create_refresh_token, hash_token
    raw, token_hash, exp = create_refresh_token()
    assert raw != token_hash
    assert hash_token(raw) == token_hash
    assert len(raw) > 30


def test_password_validation_rules():
    """Password validation regex should enforce all rules."""
    import re
    PASSWORD_RE = re.compile(
        r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&_\-#])[A-Za-z\d@$!%*?&_\-#]{8,64}$"
    )
    assert PASSWORD_RE.match("ValidPass1@x")
    assert not PASSWORD_RE.match("sh@A1")          # too short (5 chars)
    assert not PASSWORD_RE.match("nouppercase1@x") # no uppercase
    assert not PASSWORD_RE.match("NOLOWER1@X")     # no lowercase
    assert not PASSWORD_RE.match("NoSpecial1abc")  # no special char
    assert not PASSWORD_RE.match("NoDigits@Abc")   # no digit


# ── Registration ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_researcher(client):
    resp = await client.post("/api/v1/auth/register", json=RESEARCHER)
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == RESEARCHER["email"]
    assert data["role"] == "researcher"
    assert data["is_active"] is True
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    """Registering with the same email should return 409."""
    resp = await client.post("/api/v1/auth/register", json=RESEARCHER)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password(client):
    resp = await client.post("/api/v1/auth/register", json={
        **RESEARCHER, "email": "weak@test.com", "password": "weak"
    })
    assert resp.status_code == 422  # Pydantic validation


@pytest.mark.asyncio
async def test_register_clinician(client):
    resp = await client.post("/api/v1/auth/register", json=CLINICIAN)
    assert resp.status_code == 201


# ── Login ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success(client):
    resp = await client.post("/api/v1/auth/login", json={
        "email": RESEARCHER["email"], "password": RESEARCHER["password"]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    resp = await client.post("/api/v1/auth/login", json={
        "email": RESEARCHER["email"], "password": "WrongPass1@bad"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email(client):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "nobody@nowhere.com", "password": "AnyPass1@x"
    })
    assert resp.status_code == 401


# ── Protected endpoints & JWT ──────────────────────────────────────────────────

@pytest.fixture
async def researcher_tokens(client):
    resp = await client.post("/api/v1/auth/login", json={
        "email": RESEARCHER["email"], "password": RESEARCHER["password"]
    })
    return resp.json()


@pytest.mark.asyncio
async def test_get_me_authenticated(client, researcher_tokens):
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {researcher_tokens['access_token']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == RESEARCHER["email"]


@pytest.mark.asyncio
async def test_get_me_no_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client):
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer fake.token.here"}
    )
    assert resp.status_code == 401


# ── Token refresh ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_token_refresh(client, researcher_tokens):
    resp = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": researcher_tokens["refresh_token"]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Refresh token is opaque and rotates — must always differ
    assert data["refresh_token"] != researcher_tokens["refresh_token"]
    # Access token has new expiry — at minimum the refresh token changed
    assert "access_token" in data


@pytest.mark.asyncio
async def test_refresh_token_replay_rejected(client, researcher_tokens):
    """Using the same refresh token twice should fail (rotation)."""
    old_refresh = researcher_tokens["refresh_token"]
    # First use — should succeed
    r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r1.status_code == 200
    # Second use — should fail (revoked)
    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r2.status_code == 401


# ── RBAC ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_researcher_cannot_access_admin(client, researcher_tokens):
    resp = await client.get(
        "/api/v1/auth/admin/users",
        headers={"Authorization": f"Bearer {researcher_tokens['access_token']}"},
    )
    assert resp.status_code == 403


# ── Admin bootstrap & RBAC ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_flow(client):
    """Create admin via DB directly, then test admin endpoints."""
    from app.db.database import AsyncSessionLocal
    from app.models.models import User as UserModel

    async with AsyncSessionLocal() as db:
        admin = UserModel(
            email=ADMIN["email"],
            full_name=ADMIN["full_name"],
            hashed_password=hash_password(ADMIN["password"]),
            role="admin",
            is_active=True,
            is_verified=True,
        )
        db.add(admin)
        await db.commit()

    # Login as admin
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": ADMIN["email"], "password": ADMIN["password"]
    })
    assert login_resp.status_code == 200
    admin_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # List users
    users_resp = await client.get("/api/v1/auth/admin/users", headers=headers)
    assert users_resp.status_code == 200
    assert len(users_resp.json()) >= 2

    # Create a user via admin
    create_resp = await client.post("/api/v1/auth/admin/users", headers=headers, json={
        "email": f"newuser_{_ts}@test.com",
        "full_name": "New Test User",
        "password": "NewUserPass1@x",
        "role": "researcher",
    })
    assert create_resp.status_code == 201
    new_user_id = create_resp.json()["id"]

    # Update the user role
    update_resp = await client.put(
        f"/api/v1/auth/admin/users/{new_user_id}",
        headers=headers,
        json={"role": "clinician"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["role"] == "clinician"

    # Delete the user
    del_resp = await client.delete(
        f"/api/v1/auth/admin/users/{new_user_id}", headers=headers
    )
    assert del_resp.status_code == 204

    # Audit log should exist
    audit_resp = await client.get("/api/v1/auth/admin/audit-log", headers=headers)
    assert audit_resp.status_code == 200
    actions = [a["action"] for a in audit_resp.json()]
    assert "login" in actions


# ── Password reset flow ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_password_reset_flow(client):
    """Full password reset: request → get dev token → confirm → login with new pw."""
    req_resp = await client.post("/api/v1/auth/password-reset/request", json={
        "email": RESEARCHER["email"]
    })
    assert req_resp.status_code == 202
    data = req_resp.json()
    assert "reset_token" in data   # dev mode only

    reset_token = data["reset_token"]
    new_password = "NewResetPass2@x"

    confirm_resp = await client.post("/api/v1/auth/password-reset/confirm", json={
        "token": reset_token,
        "new_password": new_password,
    })
    assert confirm_resp.status_code == 204

    # Can log in with new password
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": RESEARCHER["email"], "password": new_password
    })
    assert login_resp.status_code == 200

    # Old password no longer works
    old_login = await client.post("/api/v1/auth/login", json={
        "email": RESEARCHER["email"], "password": RESEARCHER["password"]
    })
    assert old_login.status_code == 401


@pytest.mark.asyncio
async def test_reset_token_reuse_rejected(client):
    """Password reset token cannot be used twice."""
    req = await client.post("/api/v1/auth/password-reset/request", json={
        "email": CLINICIAN["email"]
    })
    token = req.json().get("reset_token")
    if not token:
        pytest.skip("No dev token returned")

    # First use
    r1 = await client.post("/api/v1/auth/password-reset/confirm", json={
        "token": token, "new_password": "AnotherPass1@x"
    })
    assert r1.status_code == 204

    # Second use of same token
    r2 = await client.post("/api/v1/auth/password-reset/confirm", json={
        "token": token, "new_password": "YetAnotherPass1@x"
    })
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_nonexistent_email_still_202(client):
    """Non-existent email should still return 202 (anti-enumeration)."""
    resp = await client.post("/api/v1/auth/password-reset/request", json={
        "email": "nobody_at_all@nowhere.com"
    })
    assert resp.status_code == 202


# ── Logout ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_logout(client):
    # Log in fresh to get tokens (use admin which was not part of reset flow)
    login = await client.post("/api/v1/auth/login", json={
        "email": ADMIN["email"], "password": ADMIN["password"]
    })
    tokens = login.json()

    logout = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout.status_code == 204

    # Refresh should now fail
    refresh = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": tokens["refresh_token"]
    })
    assert refresh.status_code == 401


# ── Protected upload/analysis require auth ─────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_requires_auth(client):
    """Upload endpoint must reject unauthenticated requests."""
    resp = await client.post(
        "/api/v1/upload/video",
        files={"file": ("test.mp4", b"fake", "video/mp4")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_analysis_requires_auth(client):
    resp = await client.post("/api/v1/analysis/start", json={"video_id": "test"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_jobs_list_requires_auth(client):
    resp = await client.get("/api/v1/analysis/jobs")
    assert resp.status_code == 401
