from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class AnalysisStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class PipelineStage(str, Enum):
    EXTRACTING_FRAMES = "Extracting video frames"
    SOM_MARKING = "Applying Set-of-Mark visual prompting"
    VLM_ANALYSIS = "Running VLM behavioural analysis"
    SCORING_ADOS = "Computing ADOS-grounded scores"
    COMPUTING_HRI = "Computing HRI extension metrics"
    PROFILE_SUMMARY = "Computing behavioural profile summary"
    PROFILE_RANKING = "Ranking profile indicators"
    GENERATING_REPORT = "Generating explainable report"


# ─── Video Upload ─────────────────────────────────────────────────────────────

class VideoUploadResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    file_size: int
    duration_seconds: Optional[float]
    fps: Optional[float]
    width: Optional[int]
    height: Optional[int]
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Analysis ─────────────────────────────────────────────────────────────────

class AnalysisJobCreate(BaseModel):
    video_id: str
    vlm_model: Optional[str] = "llava:13b"


class AnalysisJobResponse(BaseModel):
    id: str
    video_id: str
    video_filename: Optional[str] = None
    status: AnalysisStatus
    stage: Optional[str]
    progress: int
    error_message: Optional[str]
    vlm_model: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# ─── Behavioural Profile ──────────────────────────────────────────────────────

class ADOSCoreScores(BaseModel):
    """
    Items 3 (Linked Nonverbal Communication) and 5 (Emphatic/Emotional
    Gestures) removed — both required speech/audio co-occurrence data this
    system does not capture (no TTS or speech understanding).
    """
    eye_contact_score: Optional[int] = Field(None, description="ADOS Item 1: 0=typical, 2=atypical")
    directed_expression_score: Optional[int] = Field(None, description="ADOS Item 2: 0-2")
    descriptive_gesture_score: Optional[int] = Field(None, description="ADOS Item 4: 0,1,2,3,8")
    hand_mannerism_score: Optional[int] = Field(None, description="ADOS Item 6: 0,1,2")


class HRIExtensionScores(BaseModel):
    """Multimodal Sync Ratio removed — required speech co-occurrence data."""
    joint_attention_mean: Optional[float] = Field(None, ge=0, le=1)
    postural_orientation_mean: Optional[float] = Field(None, ge=0, le=1)


class ProfileSummary(BaseModel):
    """
    Replaces AQ10Prediction/SHAPAttribution. No published, validated formula
    exists for predicting AQ-10 from visual-only behavioural indicators
    (confirmed with supervisor) — this explains the ADOS/HRI profile itself
    instead, via a transparent deviation-from-typical ranking. See
    BehaviouralScoringEngine.compute_profile_summary() for the method.
    """
    profile_deviations: Optional[Dict[str, float]] = Field(
        None, description="feature -> 0-1 deviation from typical/neutral"
    )
    feature_importance: Optional[List[Dict[str, Any]]] = Field(
        None, description="profile indicators ranked by deviation, most notable first"
    )


class AnalysisResultResponse(BaseModel):
    id: str
    job_id: str
    video_filename: Optional[str] = None
    ados_scores: ADOSCoreScores
    hri_extensions: HRIExtensionScores
    profile_summary: ProfileSummary
    natural_language_explanation: Optional[str]
    segment_timeline: Optional[List[Dict[str, Any]]]
    frames_analysed: Optional[int]
    clinical_disclaimer: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Progress WebSocket ───────────────────────────────────────────────────────

class ProgressUpdate(BaseModel):
    job_id: str
    status: str
    stage: Optional[str]
    progress: int
    message: Optional[str]


# ─── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    ollama_available: bool
    ollama_model: str
    database_ok: bool


# ─── Frame Summaries (NEW) ────────────────────────────────────────────────────

class FrameSummaryResponse(BaseModel):
    """Single frame summary response from VLM."""
    frame_index: int = Field(..., description="Frame number in sequence (1-based)")
    timestamp: float = Field(..., description="Timestamp in seconds from start of video")
    summary: str = Field(..., description="VLM-generated description of what's happening in this frame")
    tokens: int = Field(..., description="Number of tokens in the VLM response")
    parse_error: bool = Field(..., description="Whether this frame had a parsing error")
    raw_response: Optional[str] = Field(None, description="Raw JSON response from VLM (truncated to 500 chars for API)")


class FrameSummariesResponse(BaseModel):
    """Complete frame summaries for a job with metadata."""
    job_id: str = Field(..., description="Unique identifier for the analysis job")
    video_id: Optional[str] = Field(None, description="ID of the video being analysed")
    vlm_model: Optional[str] = Field(None, description="VLM model used for analysis")
    frames_analysed: int = Field(..., description="Total number of frames analysed")
    natural_language_explanation: Optional[str] = Field(None, description="Full natural language explanation of results")
    frame_summaries: List[FrameSummaryResponse] = Field(default_factory=list, description="List of frame-by-frame summaries")

    model_config = ConfigDict(from_attributes=True)


class ExportResponse(BaseModel):
    """Response for export operations."""
    job_id: str = Field(..., description="Job ID that was exported")
    formats: List[str] = Field(..., description="List of formats exported")
    files: List[str] = Field(..., description="List of exported filenames")
    message: str = Field(..., description="Status message")