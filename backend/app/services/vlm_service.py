import base64
import json
import httpx
from pathlib import Path
from typing import Dict, Any, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import structlog
import asyncio

logger = structlog.get_logger()

# ── Anti-Anchoring Prompt (trimmed) ────────────────────────────────────────────
# Same anti-anchoring design as before (no copyable literal example values,
# ranges instead of single anchor points, explicit "don't reuse the previous
# frame's score" instruction) — but shortened. On this hardware, prompt
# processing alone (~1600-1700 tokens) was costing 200-400s per frame at
# 4-8 tok/s BEFORE generation even started, so trimming prose here has a
# direct, measurable effect on wall-clock time, not just token count.
# Placeholder syntax changed slightly (<int>, <bool>, <float ...> instead of
# full descriptive phrases) — _TEMPLATE_LEAK_MARKERS below was updated to
# match, so echoed-placeholder detection still works against this version.
BEHAVIOURAL_ANALYSIS_PROMPT = """Analyse this single video frame of a child interacting with a robot. Base every field ONLY on what THIS frame shows — do not reuse a value from a previous frame in this session.

This system has no audio/speech input — base every judgement on visible behaviour only.

Return ONLY valid JSON (no markdown, no extra text), replacing every <placeholder>:

{
  "eye_contact": {"ados_code": <int: 0=typical, 2=atypical>, "directed_at_robot": <bool>, "quality": "<short phrase>"},
  "directed_expression": {"ados_code": <int: 0=directed,1=some,2=none>, "directed_at_robot": <bool>},
  "gesture": {"descriptive_ados_code": <int: 0-3 or 8=N/A>, "gesture_present": <bool>},
  "hand_mannerisms": {"ados_code": <int: 0=none,1=occasional,2=frequent>, "present": <bool>},
  "joint_attention": {"score": <float 0.00-1.00>, "gaze_shift_to_object": <bool>, "gaze_shift_back_to_robot": <bool>},
  "postural_orientation": {"engagement_score": <float 0.00-1.00>, "facing_robot": <bool>},
  "frame_summary": "<one sentence, only what is visible>"
}

Score bands and consistency rules — place the value where the evidence puts it, do not default to a band's midpoint. Every MUST rule below is checked automatically after you respond — a violation is treated as an error, not a stylistic choice:
- eye_contact.ados_code: this is a strict two-way mapping to directed_at_robot. If directed_at_robot is true, ados_code MUST be 0. If directed_at_robot is false, ados_code MUST be 2. There is no other valid combination.
- directed_expression.ados_code: if directed_at_robot is true, ados_code MUST be 0. If directed_at_robot is false, ados_code MUST be 1 or 2 (never 0) — pick 1 if some directed affect was still visible, 2 if none was.
- hand_mannerisms.ados_code: if present is false, ados_code MUST be 0. If present is true, ados_code MUST be 1 or 2 (never 0) — pick 1 if occasional, 2 if frequent.
- joint_attention.score: confirmed gaze shift TO an object/away AND back to robot=0.80-1.00; sustained attention on robot with NO confirmed shift away (even if gaze briefly returns/re-settles on robot)=0.40-0.70; brief/ambiguous engagement=0.20-0.40; no engagement=0.00-0.20. If gaze_shift_to_object is false, the score MUST be ≤0.70 regardless of gaze_shift_back_to_robot. If gaze_shift_to_object is true AND gaze_shift_back_to_robot is true, the score MUST be ≥0.80.
- postural_orientation.engagement_score: body fully toward robot=0.80-1.00; partially angled=0.45-0.65; away/neutral=0.10-0.35. If facing_robot is false, the score MUST be ≤0.65. If facing_robot is true, the score MUST be ≥0.70.

ADOS codes: eye_contact(0/2), expression(0/1/2), gesture(0/1/2/3/8=N/A), mannerism(0/1/2)."""


def _validate_and_repair(result: Dict, timestamp: float) -> Dict:
    """Validate and repair VLM output."""
    defaults = {
        "eye_contact": {"ados_code": 0, "directed_at_robot": True},
        "directed_expression": {"ados_code": 0, "directed_at_robot": True},
        "gesture": {"descriptive_ados_code": 0},
        "hand_mannerisms": {"ados_code": 0},
        "joint_attention": {"score": 0.5},
        "postural_orientation": {"engagement_score": 0.5},
    }

    for key, default in defaults.items():
        if key not in result or not isinstance(result[key], dict):
            result[key] = default
        else:
            for subkey, subval in default.items():
                if subkey not in result[key]:
                    result[key][subkey] = subval

    # Repair joint attention — use boolean fields to derive score, don't blindly set 0.5
    # NOTE: uses strict `is True` checks (not bare truthiness). A malformed/non-boolean
    # value here — e.g. a leftover template placeholder string like "<true|false>" —
    # is truthy in Python and would otherwise be silently scored as a confirmed
    # bidirectional gaze shift (0.80), fabricating a confident signal from garbage.
    # This should be unreachable now that _parse_vlm_response rejects template-leaked
    # responses before they reach this function, but the strict check stays as a
    # second line of defence against any other source of malformed boolean fields.
    ja = result.get("joint_attention", {})
    ja_score = _to_float(ja.get("score"))
    if ja_score == 0.0:
        # Score is 0 — derive from booleans if present
        if ja.get("gaze_shift_to_object") is True and ja.get("gaze_shift_back_to_robot") is True:
            ja["score"] = 0.80   # full bidirectional gaze shift observed
        elif ja.get("gaze_shift_to_object") is True or ja.get("gaze_shift_back_to_robot") is True:
            ja["score"] = 0.45   # partial gaze shift
        elif result.get("eye_contact", {}).get("directed_at_robot") is True:
            ja["score"] = 0.50   # child looking at robot — proxy for JA
        else:
            ja["score"] = 0.25   # no evidence of joint attention
    # If score is already > 0 (model gave a real answer), keep it as-is

    # Repair postural orientation — use facing_robot boolean
    po = result.get("postural_orientation", {})
    po_score = _to_float(po.get("engagement_score"))
    if po_score == 0.0:
        if po.get("facing_robot") is True:
            po["engagement_score"] = 0.80   # facing robot confirmed — must satisfy facing=true MUST rule (>=0.70)
        elif result.get("directed_expression", {}).get("directed_at_robot") is True:
            po["engagement_score"] = 0.50   # expression directed → some orientation
        else:
            po["engagement_score"] = 0.30   # no orientation signal

    result["_consistency_flags"] = _check_consistency(result, timestamp)

    return result


def _check_consistency(result: Dict, timestamp: float) -> List[str]:
    """
    Cross-field consistency checks on an already-parsed, already-repaired
    response. This is a different failure class from the repair logic
    above: a well-formed response can still have a high numeric score with
    no supporting boolean evidence anywhere in the same response — e.g.
    joint_attention.score = 0.9 while gaze_shift_to_object is False. That's
    not malformed data, it's the model's own judgements disagreeing with
    each other. We don't silently overwrite either field —
    we don't know which one is right — we just flag it, so it shows up in
    logs and in the stored frame data (under "_consistency_flags") instead
    of only being spottable by manually cross-referencing a spreadsheet.
    """
    flags: List[str] = []

    ja = result.get("joint_attention", {})
    ja_score = _to_float(ja.get("score"))
    gsto = ja.get("gaze_shift_to_object")
    gsbr = ja.get("gaze_shift_back_to_robot")
    if ja_score > 0.70 and not (gsto is True and gsbr is True):
        flags.append("joint_attention_high_without_gaze_shift")
    if ja_score < 0.80 and gsto is True and gsbr is True:
        flags.append("joint_attention_low_despite_full_gaze_shift")

    po = result.get("postural_orientation", {})
    po_score = _to_float(po.get("engagement_score"))
    facing = po.get("facing_robot")
    if po_score > 0.65 and facing is not True:
        flags.append("postural_engagement_high_without_facing_robot")
    if po_score < 0.70 and facing is True:
        flags.append("postural_engagement_low_despite_facing_robot")

    # NOTE: added after a real case where eye_contact.ados_code and
    # directed_expression.ados_code both read "0" (typical) in 100% of a
    # session's frames while their own directed_at_robot boolean was False
    # in 85% of those same frames — the model's categorical judgement and
    # its own supporting evidence disagreed throughout, and nothing was
    # flagging it. Same pattern as the joint_attention/postural checks
    # above, applied to the two ADOS items that carry a directed_at_robot
    # field. ados_code == 0 is "typical/directed" for both these fields.
    ec = result.get("eye_contact", {})
    ec_code = ec.get("ados_code")
    ec_dir = ec.get("directed_at_robot")
    if ec_code == 0 and ec_dir is not True:
        flags.append("eye_contact_typical_without_directed_at_robot")
    # NOTE: added after the prompt was tightened to a strict two-way mapping
    # (directed_at_robot=True -> code MUST be 0) — this is the mirror check,
    # catching the opposite violation: code=2 despite directed_at_robot=True.
    # Found via a real result where this fired on 19/20 frames while the
    # original-direction check above found zero — without this check the
    # model could satisfy "never code=0 without support" by simply always
    # coding 2, which is not the same as actually following the rule.
    if ec_code == 2 and ec_dir is True:
        flags.append("eye_contact_atypical_despite_directed_at_robot")

    de = result.get("directed_expression", {})
    de_code = de.get("ados_code")
    de_dir = de.get("directed_at_robot")
    if de_code == 0 and de_dir is not True:
        flags.append("directed_expression_typical_without_directed_at_robot")
    if de_code in (1, 2) and de_dir is True:
        flags.append("directed_expression_atypical_despite_directed_at_robot")

    # Same pattern again: hand_mannerisms.ados_code == 0 means "none/typical"
    # (no repetitive mannerisms observed), which should correspond to
    # present == False. Found via a real result where ados_code was 0 in
    # 100% of frames while present was True in 81% of those same frames.
    hm = result.get("hand_mannerisms", {})
    hm_code = hm.get("ados_code")
    hm_present = hm.get("present")
    if hm_code == 0 and hm_present is True:
        flags.append("hand_mannerism_typical_despite_present")
    if hm_code in (1, 2) and hm_present is False:
        flags.append("hand_mannerism_atypical_despite_absent")

    if flags:
        logger.warning("vlm_internal_inconsistency", timestamp=timestamp, flags=flags)

    return flags


def _to_float(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


_TEMPLATE_LEAK_MARKERS = (
    "<int", "<bool>", "<float 0.00", "<short phrase>",
    "<one sentence, only what is visible>",
)


def _contains_template_leak(obj: Any) -> bool:
    """
    Detect cases where the model echoed the prompt's placeholder text back
    verbatim instead of filling it in, e.g. returning the literal string
    "<float 0.00-1.00, see scale below...>" as a field value. This is
    syntactically valid JSON — it will parse successfully — so without this
    check it silently passes through as "real" data and, worse, its truthy
    non-empty strings can trigger downstream repair logic meant for actual
    booleans (see the joint_attention repair fix above).

    Model-agnostic by design: this doesn't check which model or prompt
    version produced the response, only whether known placeholder tokens
    leaked into the output. Update _TEMPLATE_LEAK_MARKERS if the prompt
    wording changes.
    """
    if isinstance(obj, str):
        return any(marker in obj for marker in _TEMPLATE_LEAK_MARKERS)
    if isinstance(obj, dict):
        return any(_contains_template_leak(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_template_leak(v) for v in obj)
    return False


def _parse_vlm_response(raw_text: str, timestamp: float) -> Optional[Dict[str, Any]]:
    """Parse VLM response and extract JSON."""
    if not raw_text or len(raw_text.strip()) < 5:
        logger.warning("vlm_empty_response", timestamp=timestamp)
        return None

    clean = raw_text.strip()

    # Try to find JSON object
    start = clean.find("{")
    end = clean.rfind("}") + 1
    if start < 0 or end <= start:
        logger.warning("vlm_no_json_found", timestamp=timestamp, raw=raw_text[:200])
        return None

    clean = clean[start:end]

    try:
        result = json.loads(clean)
    except json.JSONDecodeError as e:
        logger.warning("vlm_json_decode_error", timestamp=timestamp, error=str(e))
        return None

    if _contains_template_leak(result):
        # Treated exactly like a parse failure: falls through to
        # _make_fallback() in the caller, and is correctly counted in the
        # job's parse_error rate instead of contaminating the aggregate.
        logger.warning("vlm_template_echo_detected", timestamp=timestamp, raw=raw_text[:200])
        return None

    return _validate_and_repair(result, timestamp)


def _make_fallback(timestamp: float) -> Dict[str, Any]:
    """Fallback when VLM fails."""
    return {
        "eye_contact": {"ados_code": 0, "directed_at_robot": True},
        "directed_expression": {"ados_code": 0, "directed_at_robot": True},
        "gesture": {"descriptive_ados_code": 0},
        "hand_mannerisms": {"ados_code": 0},
        "joint_attention": {"score": 0.5},
        "postural_orientation": {"engagement_score": 0.5},
        "parse_error": True,
        "timestamp": timestamp,
        "raw_response": "",
        "summary": "Fallback response (VLM failed)",
    }


def _extract_summary(result: Dict) -> str:
    """Extract a meaningful summary from the VLM response."""
    # Try to get the frame_summary field
    if "frame_summary" in result:
        return result["frame_summary"]
    
    # Or build a summary from key observations
    observations = []
    
    # Eye contact observation
    if "eye_contact" in result and "observation" in result["eye_contact"]:
        observations.append(f"Eye contact: {result['eye_contact']['observation']}")
    
    # Gesture observation
    if "gesture" in result and "observation" in result["gesture"]:
        observations.append(f"Gesture: {result['gesture']['observation']}")
    
    # Joint attention observation
    if "joint_attention" in result and "observation" in result["joint_attention"]:
        observations.append(f"Joint attention: {result['joint_attention']['observation']}")
    
    # Postural orientation observation
    if "postural_orientation" in result and "observation" in result["postural_orientation"]:
        observations.append(f"Posture: {result['postural_orientation']['observation']}")
    
    if observations:
        return " | ".join(observations)
    
    # Fallback: create a simple summary from scores
    ec = result.get("eye_contact", {}).get("ados_code", 0)
    ja = result.get("joint_attention", {}).get("score", 0.5)
    return f"Frame analysis: Eye contact score {ec}, Joint attention score {ja:.2f}"


class OllamaVLMService:
    """
    Calls local Ollama VLM for per-frame behavioural analysis.
    All inference runs locally — no data leaves the system (UK GDPR Art.44).
    """

    def __init__(
        self,
        base_url: str,
        model: str = "llava:13b",
        timeout: int = 600,
        num_ctx: int = 3072,
        num_predict: int = 550,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.timeout = httpx.Timeout(
            connect=30.0,
            read=float(timeout),
            write=60.0,
            pool=10.0,
        )

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(min=2, max=8),
        retry=retry_if_exception_type(httpx.ReadTimeout),
    )
    async def analyse_frame(
        self,
        frame_path: str,
        som_frame_path: str,
        timestamp: float,
        session_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a frame to Ollama and return validated behavioural scores."""
        prompt = BEHAVIOURAL_ANALYSIS_PROMPT
        if session_context:
            prompt = f"{session_context}\n\n{prompt}"

        # Read and encode image to base64
        try:
            image_b64 = self._encode_image(som_frame_path)
        except Exception as e:
            logger.error("image_encode_error", error=str(e), frame=frame_path)
            return _make_fallback(timestamp)

        # Build payload for Ollama API
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": self.num_predict,
                "num_ctx": self.num_ctx,
            },
        }

        # Send to Ollama API
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

        except httpx.ConnectError:
            logger.error("ollama_connect_error", url=self.base_url)
            return _make_fallback(timestamp)
        except httpx.ReadTimeout:
            logger.warning("ollama_read_timeout", timestamp=timestamp, model=self.model)
            raise
        except Exception as e:
            logger.error("ollama_unexpected_error", error=str(e), timestamp=timestamp)
            return _make_fallback(timestamp)

        # Parse the response
        raw_text = data.get("response", "")
        eval_count = data.get("eval_count", 0)

        # ⭐ NEW: Log the actual response content (first 200 chars)
        if raw_text:
            logger.debug(f"vlm_response_content: {raw_text[:200]}...")
        else:
            logger.warning("vlm_response_empty", timestamp=timestamp)

        logger.debug(
            "vlm_response_received",
            timestamp=timestamp,
            response_tokens=eval_count,
            response_length=len(raw_text),
        )

        # Check for suspiciously short responses
        if eval_count < 10:
            logger.warning(
                "vlm_suspiciously_short_response",
                timestamp=timestamp,
                eval_count=eval_count,
                raw=raw_text[:100],
            )
            # Try one more time with a simpler prompt
            return await self._retry_with_simpler_prompt(som_frame_path, timestamp)

        result = _parse_vlm_response(raw_text, timestamp)
        if result is None:
            return _make_fallback(timestamp)

        # ⭐ NEW: Save the raw response and a summary
        result["raw_response"] = raw_text
        result["summary"] = _extract_summary(result)
        result["timestamp"] = timestamp
        result["frame_path"] = frame_path
        result["eval_count"] = eval_count

        return result

    async def _retry_with_simpler_prompt(self, image_path: str, timestamp: float) -> Dict[str, Any]:
        """Retry with a very simple prompt if the model failed.

        NOTE: kept deliberately minimal (this is a last-resort retry after the
        main prompt produced a suspiciously short response), but still avoids
        embedding literal example numbers the model could copy verbatim.
        """
        simple_prompt = (
            "Look at this image of a child and a robot. Return ONLY valid JSON, "
            "based on what you actually see in THIS image: "
            '{"eye_contact": {"ados_code": <0 or 2, based on the image>}, '
            '"joint_attention": {"score": <float 0.0-1.0, based on the image>}}'
        )
        
        try:
            image_b64 = self._encode_image(image_path)
            payload = {
                "model": self.model,
                "prompt": simple_prompt,
                "images": [image_b64],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 100}
            }
            
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                data = response.json()
                raw = data.get("response", "")
                
            result = _parse_vlm_response(raw, timestamp)
            if result:
                result["raw_response"] = raw
                result["summary"] = _extract_summary(result)
                result["timestamp"] = timestamp
                result["eval_count"] = data.get("eval_count", 0)
                return result
        except Exception:
            pass
        
        return _make_fallback(timestamp)

    async def check_health(self) -> bool:
        """Check if Ollama is running and the configured model is available."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                if r.status_code == 200:
                    models = r.json().get("models", [])
                    names = [m.get("name", "") for m in models]
                    return any(self.model.split(":")[0] in n for n in names)
        except Exception:
            pass
        return False

    async def list_available_models(self) -> list:
        """Return list of pulled model names."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                if r.status_code == 200:
                    return [m.get("name", "") for m in r.json().get("models", [])]
        except Exception:
            pass
        return []