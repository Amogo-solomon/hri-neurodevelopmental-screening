import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
import structlog

logger = structlog.get_logger()

FEATURE_NAMES = [
    "eye_contact_score",
    "directed_expression_score",
    "descriptive_gesture_score",
    "hand_mannerism_score",
    "joint_attention_mean",
    "postural_orientation_mean",
]

FEATURE_LABELS = {
    "eye_contact_score":          "Eye Contact (ADOS Item 1)",
    "directed_expression_score":  "Directed Expressions (ADOS Item 2)",
    "descriptive_gesture_score":  "Descriptive Gestures (ADOS Item 4)",
    "hand_mannerism_score":       "Hand & Finger Mannerisms (ADOS Item 6)",
    "joint_attention_mean":       "Joint Attention (HRI Extension)",
    "postural_orientation_mean":  "Postural Orientation (HRI Extension)",
}


class BehaviouralScoringEngine:
    """
    Aggregates per-frame VLM outputs into a final behavioural profile.
    Implements ADOS Items 1, 2, 4, 6, HRI extension metrics (joint attention,
    postural orientation), and a profile-deviation explainability summary.

    Items 3 (Linked Nonverbal Communication) and 5 (Emphatic/Emotional
    Gestures), the Multimodal Sync Ratio HRI metric, and AQ-10 prediction
    have been removed: all three required speech/audio co-occurrence data
    this system does not capture (no TTS or speech understanding), and no
    published, validated formula exists for predicting AQ-10 from visual
    behavioural indicators alone.

    HRI metric derivation strategy (in priority order):
    1. Use explicit float score if > 0
    2. Derive from boolean fields (facing_robot, gaze_shift_*)
    3. Derive from ADOS boolean fields as proxy (directed_at_robot)
    4. Estimate from aggregate ADOS scores as last resort
    """

    def aggregate_frame_analyses(
        self, frame_analyses: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not frame_analyses:
            return self._empty_scores()

        all_frames   = frame_analyses
        valid        = [f for f in all_frames if not f.get("parse_error")]
        n_total      = len(all_frames)
        n_valid      = len(valid)

        logger.info(
            "aggregating_frames",
            total=n_total,
            valid=n_valid,
            parse_errors=n_total - n_valid,
        )

        # Use all frames for ADOS (parse_error fallbacks have neutral ADOS codes)
        # Use valid frames for HRI (parse_error fallbacks have 0.5 neutral HRI scores)
        ados_frames = all_frames   # ADOS codes from all frames
        hri_frames  = all_frames   # HRI from all frames including neutral fallbacks

        # ADOS Items - take the most common score across frames
        # ── ADOS Item 1: Eye Contact ──────────────────────────────────────────
        eye_codes = [
            self._safe_int(f.get("eye_contact", {}).get("ados_code"))
            for f in ados_frames
            if self._safe_int(f.get("eye_contact", {}).get("ados_code")) is not None
        ]
        # NOTE: previously used a code==2-only atypical_ratio threshold, which
        # silently discarded ados_code==1 (mild atypicality) frames and
        # defaulted them to "typical". Fixed to use the same modal aggregation
        # as every other ADOS item for consistency.
        eye_contact_score = self._modal(eye_codes, 0)

        # ── ADOS Item 2: Directed Expression ─────────────────────────────────
        expr_codes = [
            self._safe_int(f.get("directed_expression", {}).get("ados_code"))
            for f in ados_frames
            if self._safe_int(f.get("directed_expression", {}).get("ados_code")) is not None
        ]
        directed_expression_score = self._modal(expr_codes, 0)

        # ── ADOS Item 4: Descriptive Gestures ─────────────────────────────────
        desc_codes = [
            self._safe_int(f.get("gesture", {}).get("descriptive_ados_code"))
            for f in ados_frames
            if self._safe_int(f.get("gesture", {}).get("descriptive_ados_code")) is not None
        ]
        descriptive_gesture_score = self._modal(desc_codes, 0)

        # ── ADOS Item 6: Hand Mannerisms ──────────────────────────────────────
        mann_codes = [
            self._safe_int(f.get("hand_mannerisms", {}).get("ados_code"))
            for f in ados_frames
            if self._safe_int(f.get("hand_mannerisms", {}).get("ados_code")) is not None
        ]
        hand_mannerism_score = self._modal(mann_codes, 0)

        # HRI metrics - average across frames
        # ── HRI: Joint Attention ──────────────────────────────────────────────
        joint_attention_mean = self._compute_joint_attention(hri_frames, valid)

        # ── HRI: Postural Orientation ─────────────────────────────────────────
        postural_orientation_mean = self._compute_posture(hri_frames, valid)

        return {
            "eye_contact_score":          eye_contact_score,
            "directed_expression_score":  directed_expression_score,
            "descriptive_gesture_score":  descriptive_gesture_score,
            "hand_mannerism_score":       hand_mannerism_score,
            "joint_attention_mean":       self._safe_round(joint_attention_mean),
            "postural_orientation_mean":  self._safe_round(postural_orientation_mean),
        }

    # ── HRI Computation Helpers ───────────────────────────────────────────────

    def _compute_joint_attention(
        self, all_frames: List[Dict], valid: List[Dict]
    ) -> float:
        """
        Compute joint attention score using 4-tier fallback strategy.
        """
        scores = []

        for f in all_frames:
            ja    = f.get("joint_attention", {})
            score = self._safe_float(ja.get("score"))
            gsto  = ja.get("gaze_shift_to_object")
            gsbr  = ja.get("gaze_shift_back_to_robot")

            if score is not None and score > 0:
                # Priority 1: explicit non-zero float score
                scores.append(score)
            elif gsto is True and gsbr is True:
                # Priority 2: full bidirectional gaze shift
                scores.append(0.80)
            elif gsto is True:
                # Priority 3: partial gaze shift
                scores.append(0.45)
            elif gsbr is True:
                # Priority 4: gaze back to robot
                scores.append(0.55)
            # else: no signal, skip

        if scores:
            return float(np.mean(scores))

        # Tier 2 fallback: derive from eye_contact directed_at_robot
        robot_gaze_frames = [
            f for f in all_frames
            if f.get("eye_contact", {}).get("directed_at_robot") is True
        ]
        n = len(all_frames)
        if robot_gaze_frames and n > 0:
            ratio = len(robot_gaze_frames) / n
            # Scale: if child looks at robot >50% of time, that's good JA proxy
            return min(ratio * 1.2, 1.0)

        # Tier 3 fallback: estimate from ADOS eye contact — mark conservative
        ec_scores = [
            self._safe_int(f.get("eye_contact", {}).get("ados_code"), 0)
            for f in all_frames
        ]
        if ec_scores:
            typical_ratio = sum(1 for s in ec_scores if s == 0) / len(ec_scores)
            # Only return a value if most frames show typical eye contact
            # Otherwise fall through to None (genuinely insufficient data)
            if typical_ratio >= 0.5:
                return round(typical_ratio * 0.55, 4)  # very conservative ADOS-proxy

        return None  # Tier 4: genuinely no data — surface as N/A in UI

    def _compute_posture(
        self, all_frames: List[Dict], valid: List[Dict]
    ) -> float:
        """
        Compute postural orientation score using 3-tier fallback.
        """
        scores = []

        for f in all_frames:
            po    = f.get("postural_orientation", {})
            score = self._safe_float(po.get("engagement_score"))
            fr    = po.get("facing_robot")

            if score is not None and score > 0:
                scores.append(score)
            elif fr is True:
                scores.append(0.68)

        if scores:
            return float(np.mean(scores))

        # Fallback: estimate from expression directedness
        # If expressions are directed at robot, child is likely oriented toward it
        directed_expr = [
            f for f in all_frames
            if f.get("directed_expression", {}).get("directed_at_robot") is True
        ]
        n = len(all_frames)
        if directed_expr and n > 0:
            return min(len(directed_expr) / n * 0.85, 1.0)

        return None  # Tier 4: no posture signal — surface as N/A

    # ── ADOS/HRI Profile Explainability ────────────────────────────────────────

    def compute_profile_summary(
        self, scores: Dict[str, Any]
    ) -> Tuple[Dict[str, float], List[Dict]]:
        """
        Replaces the old AQ-10/SHAP explainability with a direct explanation
        of the ADOS-grounded behavioural profile itself, per supervisor
        guidance: no published, validated formula exists for predicting
        AQ-10 from visual-only behavioural indicators, so nothing should be
        predicted — only the profile itself should be explained.

        Method: each of the 6 retained indicators is normalised to a 0-1
        "deviation from typical/neutral" score, using each field's own
        known range and direction (ADOS codes: 0 = typical, higher = more
        atypical; HRI engagement scores: 1.0 = fully engaged/typical,
        so deviation = 1 - value). This is a transparent, deterministic
        rescaling — not a fitted or learned model, and it makes no claim
        about clinical risk or diagnostic category. Ranking these deviations
        shows which indicators contributed most to the overall profile,
        which is what "explainable" means here: explaining the ADOS/HRI
        profile itself, not a downstream prediction built on top of it.
        """
        def deviation(key: str) -> Optional[float]:
            val = scores.get(key)
            if val is None:
                return None
            if key in ("eye_contact_score",):
                return float(val) / 2.0            # codes 0-2
            if key in ("directed_expression_score", "hand_mannerism_score"):
                return float(val) / 2.0             # codes 0-2
            if key == "descriptive_gesture_score":
                if val == 8:                        # N/A — cannot assess, excluded from ranking
                    return None
                return float(val) / 3.0             # codes 0-3
            if key in ("joint_attention_mean", "postural_orientation_mean"):
                return max(0.0, 1.0 - float(val))   # higher engagement = lower deviation
            return None

        deviations: Dict[str, float] = {}
        for key in FEATURE_NAMES:
            d = deviation(key)
            if d is not None:
                deviations[key] = round(d, 4)

        def tier(d: float) -> str:
            # NOTE: previously split at 0.20/0.50, which meant any deviation
            # at or above the exact scale midpoint (0.50) landed in the most
            # severe tier — so a genuinely middling value (e.g. a 0.50 HRI
            # engagement score, or an ADOS code sitting at the mid-point of
            # its range) was labelled "notably atypical" rather than "mild".
            # Rebalanced to roughly equal thirds so the midpoint of any
            # feature's range reads as "mildly atypical", and only the top
            # third of the deviation range is "notably atypical".
            if d < 0.30:
                return "typical"
            if d < 0.60:
                return "mildly atypical"
            return "notably atypical"

        ranked = sorted(
            [{
                "feature":       feat,
                "label":         FEATURE_LABELS[feat],
                "raw_value":     scores.get(feat),
                "deviation":     dev,
                "tier":          tier(dev),
            } for feat, dev in deviations.items()],
            key=lambda x: x["deviation"],
            reverse=True,
        )
        return deviations, ranked

    # ── NL Explanation ────────────────────────────────────────────────────────

    def generate_explanation(
        self,
        scores: Dict,
        ranked_features: List[Dict],
    ) -> str:
        """
        Describes the ADOS-grounded behavioural profile directly, using the
        profile-deviation ranking from compute_profile_summary(). No AQ-10
        or other predictive score is generated or referenced — see
        compute_profile_summary()'s docstring for why.
        """
        top = ranked_features[:3]

        expl = (
            "The VLM behavioural analysis across the video session produced the following "
            "ADOS-grounded behavioural profile, based on visual indicators only.\n\n"
        )

        ec = int(scores.get("eye_contact_score") or 0)
        de = int(scores.get("directed_expression_score") or 0)
        expl += "**Social Communication:** "
        expl += (
            "Eye contact was flexible and socially modulated (ADOS Item 1: typical). "
            if ec == 0 else
            "Eye contact was poorly modulated or rigid (ADOS Item 1: atypical). "
        )
        expl += (
            "Facial expressions were appropriately directed at the robot. "
            if de == 0 else
            f"Directed emotional expression towards the robot was limited (score {de}). "
        )
        expl += "\n\n"

        dg = int(scores.get("descriptive_gesture_score") or 0)
        expl += "**Gesture:** "
        expl += (
            "Spontaneous descriptive gestures were present and varied. "
            if dg == 0 else "Spontaneous descriptive gestures were limited or absent. "
        )
        expl += "\n\n"

        ja = scores.get("joint_attention_mean")
        po = scores.get("postural_orientation_mean")

        def fmt(v):
            if v is None:
                return "not computed (insufficient VLM inference quality)"
            return f"{v:.2f}"

        expl += (
            f"**HRI Engagement Metrics:** Joint attention (gaze-shift-to-robot) scored "
            f"{fmt(ja)}/1.0; postural orientation towards the robot scored {fmt(po)}/1.0.\n\n"
        )

        expl += "**Most Notable Profile Indicators:**\n"
        for f in top:
            expl += (
                f"- {f['label']}: {f['tier']} (deviation from typical = {f['deviation']:.2f}, "
                f"raw value = {f['raw_value']})\n"
            )

        return expl

    # ── Timeline ──────────────────────────────────────────────────────────────

    def build_segment_timeline(
        self, frame_analyses: List[Dict[str, Any]]
    ) -> List[Dict]:
        events = []
        for frame in frame_analyses:
            ts = frame.get("timestamp", 0)
            if frame.get("eye_contact", {}).get("ados_code") == 2:
                events.append({
                    "time": ts, "event": "Atypical eye contact",
                    "type": "ados", "severity": "warning",
                })
            if frame.get("hand_mannerisms", {}).get("present"):
                events.append({
                    "time": ts, "event": "Hand mannerism detected",
                    "type": "ados", "severity": "info",
                })
            ja = frame.get("joint_attention", {})
            if ja.get("gaze_shift_to_object") and ja.get("gaze_shift_back_to_robot"):
                events.append({
                    "time": ts, "event": "Joint attention episode",
                    "type": "hri", "severity": "positive",
                })
        return events

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _modal(self, scores: List[int], default: int = 0) -> int:
        if not scores:
            return default
        return Counter(scores).most_common(1)[0][0]

    def _safe_int(self, val, default=None):
        if val is None:
            return default
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    def _safe_float(self, val, default=None):
        if val is None:
            return default
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    def _safe_round(self, val, ndigits=4):
        if val is None:
            return None
        try:
            return round(float(val), ndigits)
        except (TypeError, ValueError):
            return None

    def _empty_scores(self) -> Dict[str, Any]:
        return {k: None for k in FEATURE_NAMES}