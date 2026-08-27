// ─── Video ───────────────────────────────────────────────────────────────────

export interface VideoUpload {
  id: string;
  filename: string;
  original_filename: string;
  file_size: number;
  duration_seconds: number | null;
  fps: number | null;
  width: number | null;
  height: number | null;
  status: 'uploaded' | 'processing' | 'complete' | 'error';
  created_at: string;
}

// ─── Analysis ────────────────────────────────────────────────────────────────

export type AnalysisStatus = 'queued' | 'running' | 'complete' | 'failed';

export interface AnalysisJob {
  id: string;
  video_id: string;
  video_filename: string | null;
  status: AnalysisStatus;
  stage: string | null;
  progress: number;
  error_message: string | null;
  vlm_model: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

// ─── Results ─────────────────────────────────────────────────────────────────

export interface ADOSCoreScores {
  eye_contact_score: number | null;
  directed_expression_score: number | null;
  descriptive_gesture_score: number | null;
  hand_mannerism_score: number | null;
}

export interface HRIExtensionScores {
  joint_attention_mean: number | null;
  postural_orientation_mean: number | null;
}

export interface ProfileFeature {
  feature: string;
  label: string;
  raw_value: number | null;
  deviation: number;
  tier: 'typical' | 'mildly atypical' | 'notably atypical';
}

export interface ProfileSummary {
  profile_deviations: Record<string, number> | null;
  feature_importance: ProfileFeature[] | null;
}

export interface SegmentEvent {
  time: number;
  event: string;
  type: 'ados' | 'hri';
  severity: 'warning' | 'info' | 'positive';
}

export interface AnalysisResult {
  id: string;
  job_id: string;
  video_filename: string | null;
  ados_scores: ADOSCoreScores;
  hri_extensions: HRIExtensionScores;
  profile_summary: ProfileSummary;
  natural_language_explanation: string | null;
  segment_timeline: SegmentEvent[] | null;
  frames_analysed: number | null;
  clinical_disclaimer: string;
  created_at: string;
}

// ─── Frame Summaries (new endpoint: GET /results/{job_id}/frame-summaries) ───

export interface FrameSummary {
  frame_index: number;
  timestamp: number;
  summary: string;
  tokens: number;
  parse_error: boolean;
  raw_response: string;
}

export interface FrameSummariesResponse {
  job_id: string;
  video_id: string | null;
  vlm_model: string | null;
  frames_analysed: number;
  natural_language_explanation: string | null;
  frame_summaries: FrameSummary[];
}

// ─── Progress ────────────────────────────────────────────────────────────────

export interface ProgressUpdate {
  job_id: string;
  status: string;
  stage: string | null;
  progress: number;
  message: string | null;
}

// ─── Health ──────────────────────────────────────────────────────────────────

export interface HealthStatus {
  status: string;
  version: string;
  ollama_available: boolean;
  ollama_model: string;
  database_ok: boolean;
}