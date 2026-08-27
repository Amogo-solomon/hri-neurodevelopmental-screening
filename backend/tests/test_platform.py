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

class TestBehaviouralScoringEngine:
    def setup_method(self):
        self.engine = BehaviouralScoringEngine()

    def _make_frame(self, eye_code=0, expression_code=0, desc_ados=0, emph_ados=0,
                    mannerism_code=0, ja_score=0.8, sync_score=0.7, posture=0.9,
                    directed_at_robot=True, sync_with_speech=True):
        return {
            "eye_contact": {"ados_code": eye_code, "directed_at_robot": directed_at_robot,
                           "quality": "sustained", "confidence": 0.9, "observation": "test"},
            "directed_expression": {"ados_code": expression_code, "directed_at_robot": directed_at_robot,
                                   "confidence": 0.8, "observation": "test"},
            "gesture": {"gesture_present": True, "descriptive_ados_code": desc_ados,
                       "emphatic_ados_code": emph_ados, "synchronized_with_speech": sync_with_speech,
                       "confidence": 0.8, "observation": "test"},
            "hand_mannerisms": {"present": False, "ados_code": mannerism_code,
                               "confidence": 0.9, "observation": "none"},
            "joint_attention": {"score": ja_score, "gaze_shift_to_object": True,
                               "gaze_shift_back_to_robot": True, "observation": "test"},
            "postural_orientation": {"engagement_score": posture, "facing_robot": True,
                                    "forward_lean": False, "observation": "test"},
            "multimodal_sync": {"sync_score": sync_score, "gaze_gesture_speech_cooccur": True},
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
        """If >40% of frames show atypical eye contact, score should be 2."""
        frames = (
            [self._make_frame(eye_code=2)] * 6 +
            [self._make_frame(eye_code=0)] * 4
        )
        scores = self.engine.aggregate_frame_analyses(frames)
        assert scores["eye_contact_score"] == 2

    def test_cascade_rule_linked_nonverbal(self):
        """When eye contact score=2, linked_nonverbal should be coded 8 (N/A)."""
        frames = [self._make_frame(eye_code=2)] * 10
        scores = self.engine.aggregate_frame_analyses(frames)
        assert scores["linked_nonverbal_score"] == 8

    def test_aq10_prediction_low_risk(self):
        scores = {
            "eye_contact_score": 0, "directed_expression_score": 0,
            "linked_nonverbal_score": 0, "descriptive_gesture_score": 0,
            "emphatic_gesture_score": 0, "hand_mannerism_score": 0,
            "joint_attention_mean": 0.9, "multimodal_sync_ratio": 0.85,
            "postural_orientation_mean": 0.9,
        }
        pred, lo, hi, risk = self.engine.predict_aq10(scores)
        assert 0 <= pred <= 10
        assert lo <= pred <= hi
        assert risk in {"low", "borderline", "elevated"}

    def test_aq10_prediction_elevated_risk(self):
        scores = {
            "eye_contact_score": 2, "directed_expression_score": 2,
            "linked_nonverbal_score": 8, "descriptive_gesture_score": 3,
            "emphatic_gesture_score": 3, "hand_mannerism_score": 2,
            "joint_attention_mean": 0.1, "multimodal_sync_ratio": 0.1,
            "postural_orientation_mean": 0.1,
        }
        pred, lo, hi, risk = self.engine.predict_aq10(scores)
        assert pred >= 5  # elevated profile should score higher

    def test_shap_values_shape(self):
        scores = {
            "eye_contact_score": 0, "directed_expression_score": 0,
            "linked_nonverbal_score": 0, "descriptive_gesture_score": 0,
            "emphatic_gesture_score": 0, "hand_mannerism_score": 0,
            "joint_attention_mean": 0.7, "multimodal_sync_ratio": 0.7,
            "postural_orientation_mean": 0.7,
        }
        shap_vals, ranked = self.engine.compute_shap_values(scores)
        assert len(shap_vals) == 9
        assert len(ranked) == 9
        assert all("label" in f and "shap_value" in f for f in ranked)

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
        assert any("eye contact" in e["event"].lower() for e in events)

    def test_generate_explanation_returns_string(self):
        scores = {
            "eye_contact_score": 0, "directed_expression_score": 0,
            "linked_nonverbal_score": 0, "descriptive_gesture_score": 0,
            "emphatic_gesture_score": 0, "hand_mannerism_score": 0,
            "joint_attention_mean": 0.7, "multimodal_sync_ratio": 0.7,
            "postural_orientation_mean": 0.7,
        }
        _, ranked = self.engine.compute_shap_values(scores)
        explanation = self.engine.generate_explanation(scores, 3.2, "low", ranked)
        assert isinstance(explanation, str)
        assert len(explanation) > 100
        assert "AQ-10" in explanation
