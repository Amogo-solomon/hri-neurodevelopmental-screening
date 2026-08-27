import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.db.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class VideoUpload(Base):
    __tablename__ = "video_uploads"

    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    duration_seconds = Column(Float, nullable=True)
    fps = Column(Float, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    mime_type = Column(String, nullable=False)
    upload_path = Column(String, nullable=False)
    checksum_sha256 = Column(String, nullable=True)  # data integrity
    status = Column(String, default="uploaded")  # uploaded|processing|complete|error
    created_at = Column(DateTime, default=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    updated_at = Column(DateTime, default=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    child_id = Column(String, nullable=True)  # optional subject identifier

    analyses = relationship("AnalysisJob", back_populates="video", cascade="all, delete-orphan")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    video_id = Column(String, ForeignKey("video_uploads.id"), nullable=False)
    status = Column(String, default="queued")  # queued|running|complete|failed
    stage = Column(String, nullable=True)  # current pipeline stage
    progress = Column(Integer, default=0)  # 0-100
    error_message = Column(Text, nullable=True)
    vlm_model = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    video = relationship("VideoUpload", back_populates="analyses")
    result = relationship("AnalysisResult", back_populates="job", uselist=False, cascade="all, delete-orphan")
    segments = relationship("BehaviourSegment", back_populates="job", cascade="all, delete-orphan")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("analysis_jobs.id"), nullable=False, unique=True)

    # ─── ADOS-grounded core items ─────────────────────────────────────────────
    # Items 3 (Linked Nonverbal Communication) and 5 (Emphatic/Emotional
    # Gestures) removed — both required speech/audio co-occurrence data this
    # system does not capture.
    eye_contact_score = Column(Integer, nullable=True)          # 0 or 2
    directed_expression_score = Column(Integer, nullable=True)  # 0,1,2
    descriptive_gesture_score = Column(Integer, nullable=True)  # 0,1,2,3,8
    hand_mannerism_score = Column(Integer, nullable=True)       # 0,1,2

    # ─── HRI extensions ───────────────────────────────────────────────────────
    # Multimodal Sync Ratio removed — required speech co-occurrence.
    joint_attention_mean = Column(Float, nullable=True)         # 0–1
    postural_orientation_mean = Column(Float, nullable=True)    # 0–1

    # ─── Profile explainability ────────────────────────────────────────────────
    # AQ-10 prediction and SHAP attribution removed — no published, validated
    # formula exists for predicting AQ-10 from visual-only behavioural
    # indicators (confirmed with supervisor). Replaced with a direct
    # deviation-from-typical summary of the ADOS/HRI profile itself.
    profile_deviations = Column(JSON, nullable=True)            # {feature: deviation 0-1}
    feature_importance = Column(JSON, nullable=True)            # ranked profile indicators
    natural_language_explanation = Column(Text, nullable=True)

    # ─── Raw VLM outputs ──────────────────────────────────────────────────────
    vlm_frame_analyses = Column(JSON, nullable=True)            # per-frame VLM responses
    segment_timeline = Column(JSON, nullable=True)              # timestamped events

    # ⭐ NEW: Frame summaries for easy display
    frame_summaries = Column(JSON, nullable=True)               # List of summaries

    # ─── Metadata ─────────────────────────────────────────────────────────────
    frames_analysed = Column(Integer, nullable=True)
    clinical_disclaimer = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc))

    job = relationship("AnalysisJob", back_populates="result")


class BehaviourSegment(Base):
    __tablename__ = "behaviour_segments"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("analysis_jobs.id"), nullable=False)
    start_time = Column(Float, nullable=False)   # seconds
    end_time = Column(Float, nullable=False)
    behaviour_type = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    frame_index = Column(Integer, nullable=True)
    extra_data = Column(JSON, nullable=True)

    job = relationship("AnalysisJob", back_populates="segments")


class User(Base):
    """Platform user — supports researcher, clinician, admin roles."""
    __tablename__ = "users"

    id            = Column(String,  primary_key=True, default=generate_uuid)
    email         = Column(String,  unique=True, nullable=False, index=True)
    full_name     = Column(String,  nullable=False)
    hashed_password = Column(String, nullable=False)
    role          = Column(String,  default="researcher")   # researcher|clinician|admin
    is_active     = Column(Boolean, default=True)
    is_verified   = Column(Boolean, default=False)
    institution   = Column(String,  nullable=True)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime, nullable=True)

    # Refresh tokens (allows multi-device logout)
    refresh_tokens = relationship("RefreshToken", back_populates="user",
                                  cascade="all, delete-orphan")
    # Audit log entries
    audit_logs     = relationship("AuditLog", back_populates="user",
                                  cascade="all, delete-orphan")


class RefreshToken(Base):
    """Stored refresh token — enables secure token rotation & revocation."""
    __tablename__ = "refresh_tokens"

    id         = Column(String,  primary_key=True, default=generate_uuid)
    user_id    = Column(String,  ForeignKey("users.id"), nullable=False)
    token_hash = Column(String,  nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked    = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_agent = Column(String,  nullable=True)   # device context
    ip_address = Column(String,  nullable=True)

    user = relationship("User", back_populates="refresh_tokens")


class AuditLog(Base):
    """NHS DSP / UK GDPR Article 30 — record of processing activities."""
    __tablename__ = "audit_logs"

    id         = Column(String,  primary_key=True, default=generate_uuid)
    user_id    = Column(String,  ForeignKey("users.id"), nullable=True)
    action     = Column(String,  nullable=False)   # login|logout|upload|analyse|delete|…
    resource   = Column(String,  nullable=True)    # e.g. video_id or job_id
    ip_address = Column(String,  nullable=True)
    user_agent = Column(String,  nullable=True)
    detail     = Column(JSON,    nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="audit_logs")


class PasswordResetToken(Base):
    """Single-use password reset token — expires in 1 hour."""
    __tablename__ = "password_reset_tokens"

    id         = Column(String,  primary_key=True, default=generate_uuid)
    user_id    = Column(String,  ForeignKey("users.id"), nullable=False)
    token_hash = Column(String,  nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used       = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))