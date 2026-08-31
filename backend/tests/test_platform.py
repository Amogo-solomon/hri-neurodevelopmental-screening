"""
HRI Platform — Backend Test Suite
Tests: upload endpoint, analysis job creation, health check,
       scoring engine, VLM service mock, pipeline stages.
"""
import pytest
import asyncio
import os
import json
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

# ─── App bootstrap ────────────────────────────────────────────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_hri.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("UPLOAD_DIR", "/tmp/hri-test-uploads")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")

from app.main import app
from app.db.database import init_db, engine, Base
from app.services.scoring_engine import BehaviouralScoringEngine

# ── Auth fixture for platform tests ──────────────────────────────────────────
_PT_USER = {
    "email": "platform_tester@lincoln.ac.uk",
    "full_name": "Platform Test User",
    "password": "PlatformPass1@x",
    "role": "researcher",
}

@pytest.fixture
async def auth_client(client):
    """Register + login, return client with auth headers."""
    await client.post("/api/v1/auth/register", json=_PT_USER)
    resp = await client.post("/api/v1/auth/login", json={
        "email": _PT_USER["email"], "password": _PT_USER["password"]
    })
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


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
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c


# ─── Health endpoint ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Health endpoint should return 200 with required fields."""
    with patch("app.api.v1.endpoints.health.OllamaVLMService") as mock_vlm:
        mock_vlm.return_value.check_health = AsyncMock(return_value=False)
        resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "version" in data
    assert "database_ok" in data
    assert data["database_ok"] is True


@pytest.mark.asyncio
async def test_root_endpoint(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "docs" in resp.json()


# ─── Upload endpoint ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_invalid_extension(auth_client):
    client = auth_client
    """Reject non-video file extensions."""
    resp = await client.post(
        "/api/v1/upload/video",
        files={"file": ("test.pdf", b"fake content", "application/pdf")},
    )
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_valid_video(auth_client, tmp_path):
    client = auth_client
    """Valid video upload should return VideoUploadResponse."""
    # Minimal valid MP4 header bytes
    fake_mp4 = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 100

    with patch("app.api.v1.endpoints.upload.VideoProcessor") as MockProc:
        mock_proc = MockProc.return_value
        mock_proc.compute_sha256.return_value = "abc123"
        mock_proc.validate_video.return_value = {
            "fps": 25.0, "frame_count": 250,
            "width": 640, "height": 480, "duration_seconds": 10.0,
        }
        resp = await client.post(
            "/api/v1/upload/video",
            files={"file": ("session01.mp4", fake_mp4, "video/mp4")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["original_filename"] == "session01.mp4"
    assert data["status"] == "uploaded"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_videos(auth_client):
    client = auth_client
    resp = await client.get("/api/v1/upload/videos")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ─── Analysis endpoints ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_analysis_missing_video(auth_client):
    client = auth_client
    """Starting analysis for non-existent video should return 404."""
    resp = await client.post(
        "/api/v1/analysis/start",
        json={"video_id": "nonexistent-video-id"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_jobs(auth_client):
    client = auth_client
    resp = await client.get("/api/v1/analysis/jobs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ─── Scoring engine unit tests ────────────────────────────────────────────────
# NOTE: rewritten to match the current scoring engine API. ADOS Items 3 and 5
# (linked_nonverbal, emphatic_gesture) and the Multimodal Sync Ratio HRI metric
# were removed — all three required speech/audio data this system does not
# capture. AQ-10 prediction and SHAP attribution were also removed: no
# published, validated formula exists for predicting AQ-10 from visual-only
# indicators, and the AQ-10 labels available for this project's dataset were
# confirmed, in consultation with the supervisor, not to be valid ground
# truth. Both are replaced by compute_profile_summary(), a deviation-from-
# typical ranking across the 6 retained indicators.

class TestBehaviouralScoringEngine:
    def setup_method(self):
        self.engine = BehaviouralScoringEngine()

    def _make_frame(self, eye_code=0, expression_code=0, desc_ados=0,
                    mannerism_code=0, ja_score=0.8, posture=0.9,
                    directed_at_robot=True):
        return {
            "eye_contact": {"ados_code": eye_code, "directed_at_robot": directed_at_robot,
                           "quality": "sustained"},
            "directed_expression": {"ados_code": expression_code, "directed_at_robot": directed_at_robot},
            "gesture": {"gesture_present": True, "descriptive_ados_code": desc_ados},
            "hand_mannerisms": {"present": mannerism_code > 0, "ados_code": mannerism_code},
            "joint_attention": {"score": ja_score, "gaze_shift_to_object": True,
                               "gaze_shift_back_to_robot": True},
            "postural_orientation": {"engagement_score": posture, "facing_robot": True},
            "frame_summary": "Test frame",
        }

    def test_aggregate_typical_profile(self):
        frames = [self._make_frame() for _ in range(10)]
        scores = self.engine.aggregate_frame_analyses(frames)
        assert scores["eye_contact_score"] == 0
        assert scores["directed_expression_score"] == 0
        assert scores["hand_mannerism_score"] == 0
        assert scores["joint_attention_mean"] == pytest.approx(0.8, abs=0.01)
        assert scores["postural_orientation_mean"] == pytest.approx(0.9, abs=0.01)

    def test_aggregate_atypical_eye_contact(self):
        """Modal aggregation: majority code across frames should win."""
        frames = (
            [self._make_frame(eye_code=2)] * 6 +
            [self._make_frame(eye_code=0)] * 4
        )
        scores = self.engine.aggregate_frame_analyses(frames)
        assert scores["eye_contact_score"] == 2

    def test_profile_summary_typical_profile(self):
        """A fully typical/engaged profile should show low deviation on every field."""
        scores = {
            "eye_contact_score": 0, "directed_expression_score": 0,
            "descriptive_gesture_score": 0, "hand_mannerism_score": 0,
            "joint_attention_mean": 0.9, "postural_orientation_mean": 0.9,
        }
        deviations, ranked = self.engine.compute_profile_summary(scores)
        assert all(d < 0.30 for d in deviations.values())
        assert all(f["tier"] == "typical" for f in ranked)

    def test_profile_summary_atypical_profile(self):
        """A fully atypical/disengaged profile should show high deviation."""
        scores = {
            "eye_contact_score": 2, "directed_expression_score": 2,
            "descriptive_gesture_score": 3, "hand_mannerism_score": 2,
            "joint_attention_mean": 0.1, "postural_orientation_mean": 0.1,
        }
        deviations, ranked = self.engine.compute_profile_summary(scores)
        assert all(d >= 0.60 for d in deviations.values())
        assert all(f["tier"] == "notably atypical" for f in ranked)

    def test_profile_summary_midpoint_is_mild_not_severe(self):
        """Regression test for a real bug: a genuinely mid-range engagement
        score (0.50) must land in the 'mildly atypical' tier, not the most
        severe tier — the original 0.20/0.50 boundary put any value at or
        above the midpoint into the worst tier, which was wrong."""
        scores = {"joint_attention_mean": 0.50, "postural_orientation_mean": 0.50}
        deviations, ranked = self.engine.compute_profile_summary(scores)
        assert all(f["tier"] == "mildly atypical" for f in ranked)

    def test_profile_summary_ranked_by_deviation(self):
        scores = {
            "eye_contact_score": 0, "directed_expression_score": 2,
            "joint_attention_mean": 0.9,
        }
        deviations, ranked = self.engine.compute_profile_summary(scores)
        # Most deviant indicator (directed_expression, code 2) should rank first
        assert ranked[0]["feature"] == "directed_expression_score"

    def test_empty_frames(self):
        scores = self.engine.aggregate_frame_analyses([])
        assert scores["eye_contact_score"] is None

    def test_segment_timeline_events(self):
        frames = [
            self._make_frame(eye_code=2),
            self._make_frame(eye_code=0),
        ]
        frames[0]["timestamp"] = 0.0
        frames[1]["timestamp"] = 1.0
        events = self.engine.build_segment_timeline(frames)
        assert isinstance(events, list)

    def test_generate_explanation_returns_string(self):
        scores = {
            "eye_contact_score": 0, "directed_expression_score": 0,
            "descriptive_gesture_score": 0, "hand_mannerism_score": 0,
            "joint_attention_mean": 0.7, "postural_orientation_mean": 0.7,
        }
        _, ranked = self.engine.compute_profile_summary(scores)
        explanation = self.engine.generate_explanation(scores, ranked)
        assert isinstance(explanation, str)
        assert len(explanation) > 100
        assert "AQ-10" not in explanation  # AQ-10 is no longer part of the system