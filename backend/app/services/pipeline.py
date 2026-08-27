import asyncio
from datetime import datetime, timezone
from typing import Callable, Optional
import structlog

from app.services.video_processor import VideoProcessor
from app.services.vlm_service import OllamaVLMService
from app.services.scoring_engine import BehaviouralScoringEngine
from app.core.config import get_settings

logger   = structlog.get_logger()
settings = get_settings()


def _adaptive_frame_count(duration_seconds: float) -> int:
    """
    Returns the number of frames to sample based on video duration.
    Minimum 20, maximum 80.
    """
    if duration_seconds <= 0:
        return 30
    return max(20, min(80, int(duration_seconds / 10)))


class AnalysisPipeline:
    """
    7-stage HRI behavioural analysis pipeline.
    Includes VLM quality detection — warns when model is not processing images.
    """

    STAGES = [
        (10, "Extracting video frames"),
        (22, "Applying Set-of-Mark visual prompting"),
        (65, "Running VLM behavioural analysis"),
        (75, "Computing ADOS-grounded scores"),
        (82, "Computing HRI extension metrics"),
        (88, "Computing behavioural profile summary"),
        (94, "Ranking profile indicators"),
        (99, "Generating explainable report"),
    ]

    def __init__(self, vlm_model: str = None):
        # vlm_model lets the caller override the container's configured
        # default per job (e.g. the model the user actually selected in the
        # UI). Previously this constructor took no arguments, so every job
        # silently used settings.vlm_model regardless of what was selected
        # or displayed — the model dropdown had no real effect.
        self.video_processor = VideoProcessor(settings.upload_dir)
        self.vlm_service     = OllamaVLMService(
            settings.ollama_base_url,
            vlm_model or settings.vlm_model,
            settings.vlm_timeout_seconds,
            settings.vlm_num_ctx,
            settings.vlm_num_predict,
        )
        self.scoring_engine = BehaviouralScoringEngine()

    async def run(
        self,
        video_path: str,
        job_id:     str,
        progress_callback: Optional[Callable] = None,
    ) -> dict:

        async def notify(stage: str, progress: int, message: str = ""):
            if progress_callback:
                await progress_callback(stage, progress, message)
            logger.info("pipeline_progress", job_id=job_id, stage=stage, pct=progress)

        try:
            # ── Pre-check: Ollama reachable + model loaded ────────────────────
            ollama_ok = await self.vlm_service.check_health()
            if not ollama_ok:
                available = await self.vlm_service.list_available_models()
                requested_model = self.vlm_service.model
                if not available:
                    raise RuntimeError(
                        f"Ollama has no models loaded. "
                        f"Run: docker exec hri_ollama ollama pull {requested_model}"
                    )
                model_list = ", ".join(available)
                raise RuntimeError(
                    f"Model '{requested_model}' not found. "
                    f"Available: {model_list}. "
                    f"Pull it: docker exec hri_ollama ollama pull {requested_model}"
                )

            # ── Stage 1: Extract frames ───────────────────────────────────────
            await notify(self.STAGES[0][1], self.STAGES[0][0],
                         "Validating video and extracting frames")

            meta = await asyncio.get_event_loop().run_in_executor(
                None, self.video_processor.validate_video, video_path
            )
            duration   = meta.get("duration_seconds", 0) or 0
            max_frames = _adaptive_frame_count(duration)

            logger.info("adaptive_sampling", duration_s=round(duration, 1),
                        max_frames=max_frames)

            await notify(
                self.STAGES[0][1], self.STAGES[0][0],
                f"Video: {round(duration/60, 1)} min — sampling {max_frames} frames"
            )

            frames = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.video_processor.extract_frames(
                    video_path, target_fps=1.0, max_frames=max_frames
                ),
            )
            if not frames:
                raise RuntimeError(
                    "No frames extracted. Check video file integrity."
                )

            # ── Stage 2: SoM annotation ───────────────────────────────────────
            await notify(self.STAGES[1][1], self.STAGES[1][0],
                         f"Annotating {len(frames)} frames with Set-of-Mark regions")

            som_frames = []
            for i, (ts, fp) in enumerate(frames):
                som_fp, region_map = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda fp=fp, i=i: self.video_processor.apply_som_marks(fp, i)
                )
                som_frames.append((ts, fp, som_fp, region_map))

            # ── Stage 3: VLM inference ────────────────────────────────────────
            await notify(self.STAGES[2][1], self.STAGES[2][0],
                         f"Sending {len(som_frames)} frames to {self.vlm_service.model}")

            frame_analyses = []
            total          = len(som_frames)
            parse_errors   = 0
            fast_responses = 0  # responses < 30 tokens — model not processing image

            for idx, (ts, fp, som_fp, _) in enumerate(som_frames):
                try:
                    analysis = await self.vlm_service.analyse_frame(fp, som_fp, ts)

                    # Track quality signals
                    if analysis.get("parse_error"):
                        parse_errors += 1
                    eval_count = analysis.get("eval_count", 999)
                    if eval_count < 30:
                        fast_responses += 1

                    frame_analyses.append(analysis)

                except Exception as e:
                    logger.warning("frame_analysis_error", idx=idx, ts=ts, error=str(e))
                    parse_errors += 1
                    # Use conservative fallback instead of crashing
                    from app.services.vlm_service import _make_fallback
                    fb = _make_fallback(ts)
                    fb["frame_path"] = fp
                    frame_analyses.append(fb)

                # Progress: 22% → 65%
                within = 22 + int((idx + 1) / total * 43)
                status_note = ""
                if fast_responses > idx // 2:
                    status_note = " ⚠ Model may not be processing images"
                await notify(
                    self.STAGES[2][1],
                    within,
                    f"Frame {idx+1}/{total} (t={ts:.1f}s){status_note}",
                )

            # ── Quality check ─────────────────────────────────────────────────
            fast_ratio  = fast_responses / max(total, 1)
            error_ratio = parse_errors   / max(total, 1)

            if fast_ratio > 0.5:
                logger.warning(
                    "vlm_quality_warning",
                    fast_responses=fast_responses,
                    total=total,
                    model=self.vlm_service.model,
                    hint=(
                        "More than 50% of responses were under 30 tokens. "
                        "The model may not be processing images. "
                        f"Try: docker exec hri_ollama ollama pull {self.vlm_service.model}"
                    ),
                )

            if len(frame_analyses) == 0:
                raise RuntimeError("All frame analyses failed.")

            # ── Stage 4: ADOS scoring ─────────────────────────────────────────
            await notify(self.STAGES[3][1], self.STAGES[3][0],
                         "Aggregating ADOS items 1–6")
            scores = self.scoring_engine.aggregate_frame_analyses(frame_analyses)

            # ── Stage 5: HRI metrics (already computed in stage 4) ────────────
            await notify(self.STAGES[4][1], self.STAGES[4][0])

            # ── Stage 6: Profile deviation summary ────────────────────────────
            await notify(self.STAGES[5][1], self.STAGES[5][0])
            profile_deviations, ranked_features = (
                self.scoring_engine.compute_profile_summary(scores)
            )

            # ── Stage 7: (ranking already computed above) ─────────────────────
            await notify(self.STAGES[6][1], self.STAGES[6][0])

            # ── Stage 8: Generate report ──────────────────────────────────────
            await notify(self.STAGES[7][1], self.STAGES[7][0])
            explanation = self.scoring_engine.generate_explanation(
                scores, ranked_features
            )
            timeline = self.scoring_engine.build_segment_timeline(frame_analyses)

            # Add quality note to explanation if model quality was poor
            if fast_ratio > 0.5:
                explanation += (
                    "\n\n**⚠ Analysis Quality Warning:** "
                    f"The VLM model ({settings.vlm_model}) returned unusually short responses "
                    f"for {fast_responses}/{total} frames, suggesting it may not have fully "
                    "processed the video frames. HRI metrics may be based on conservative "
                    "defaults rather than observed behaviour. "
                    "Consider re-running with llama3.2-vision:11b or qwen2.5vl:7b for better results."
                )

            # Cleanup extracted frames
            from pathlib import Path as _P
            self.video_processor.cleanup_frames(_P(video_path).stem)

            await notify("Complete", 100, "Analysis complete")

            # ⭐ NEW: Extract frame summaries for the frontend
            frame_summaries = []
            for f in frame_analyses:
                frame_summaries.append({
                    "timestamp": f.get("timestamp", 0),
                    "summary": f.get("summary", "No summary available"),
                    "eval_count": f.get("eval_count", 0),
                    "parse_error": f.get("parse_error", False),
                    "raw_response": f.get("raw_response", ""), # Full 
                # "raw_response": f.get("raw_response", "")[:500],  # Limit for storage
                    "consistency_flags": f.get("_consistency_flags", []),
                })

            return {
                "scores":                     scores,
                "profile_deviations":         profile_deviations,
                "feature_importance":         ranked_features,
                "natural_language_explanation": explanation,
                "segment_timeline":           timeline,
                "frames_analysed":            len(frame_analyses),
                "frames_failed":              parse_errors,
                "vlm_quality_ok":             fast_ratio < 0.5,
                "frame_summaries":            frame_summaries,  # ⭐ NEW field
                "vlm_frame_analyses": [
                    {
                        "timestamp":    f.get("timestamp"),
                        "summary":      f.get("summary", "No summary"),
                        "eval_count":   f.get("eval_count", 0),
                        "parse_error":  f.get("parse_error", False),
                        "raw_response": f.get("raw_response", ""), # Full response
                       # "raw_response": f.get("raw_response", "")[:200], # response truncation
                        "consistency_flags": f.get("_consistency_flags", []),
                    }
                    for f in frame_analyses
                ],
                "clinical_disclaimer": settings.nice_esf_disclaimer,
            }

        except Exception as e:
            logger.error("pipeline_error", job_id=job_id, error=str(e))
            raise