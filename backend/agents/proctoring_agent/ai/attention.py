from __future__ import annotations

import hashlib
import math
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any, Iterable

import cv2
import numpy as np


VIOLATION_STATES = {"eye_only_look_away", "head_only_look_away", "combined_look_away"}


@dataclass
class AttentionFilterState:
    pose: np.ndarray | None = None
    gaze: np.ndarray | None = None
    pose_direction: str = "center"
    gaze_direction: str = "center"
    eyes_closed: bool = False


@dataclass
class PendingAttention:
    state: str | None = None
    direction: str | None = None
    since_ms: int = 0
    last_ms: int = 0
    count: int = 0
    confidence_sum: float = 0.0


@dataclass
class ActiveAttention:
    state: str
    direction: str
    since_ms: int
    last_ms: int
    confidence_sum: float
    count: int
    event_id: str | None = None
    recovery_since_ms: int | None = None


@dataclass
class AttentionTransition:
    action: str = "none"  # none/open/update/close
    state: str = "screen_focused"
    direction: str = "center"
    start_ms: int = 0
    end_ms: int = 0
    duration_ms: int = 0
    confidence: float = 0.0
    event_id: str | None = None
    count: int = 0


class AttentionTemporalTracker:
    """Client-timestamp based confirmer with active-event extension and recovery.

    Low-confidence and technical states neither confirm new fraud events nor close an
    existing one immediately. This avoids converting one dropped/blurred frame into
    repeated event churn.
    """

    def __init__(self) -> None:
        self._pending: dict[str, PendingAttention] = {}
        self._active: dict[str, ActiveAttention] = {}
        self._lock = threading.Lock()

    def update(
        self,
        session_id: str,
        *,
        combined_state: str,
        direction: str,
        confidence: float,
        relative_ms: int,
        confirm_ms: int,
        confirm_count: int,
        recovery_ms: int,
    ) -> AttentionTransition:
        now = max(0, int(relative_ms))
        confidence = float(np.clip(confidence, 0.0, 1.0))
        technical = combined_state in {"low_confidence", "landmark_unavailable", "eyes_closed"}
        violation = combined_state in VIOLATION_STATES
        key = session_id
        with self._lock:
            active = self._active.get(key)
            pending = self._pending.get(key, PendingAttention())

            if active is not None:
                if violation and self._correlated(active, combined_state, direction):
                    active.last_ms = max(active.last_ms, now)
                    active.count += 1
                    active.confidence_sum += confidence
                    # Upgrade an eye-only/head-only event to one combined event when
                    # the second detector corroborates the same direction.
                    if combined_state == "combined_look_away":
                        active.state = combined_state
                    active.recovery_since_ms = None
                    return AttentionTransition(
                        action="update",
                        state=active.state,
                        direction=active.direction,
                        start_ms=active.since_ms,
                        end_ms=active.last_ms,
                        duration_ms=max(0, active.last_ms - active.since_ms),
                        confidence=active.confidence_sum / max(active.count, 1),
                        event_id=active.event_id,
                        count=active.count,
                    )
                if technical:
                    return AttentionTransition(
                        action="none",
                        state=active.state,
                        direction=active.direction,
                        start_ms=active.since_ms,
                        end_ms=active.last_ms,
                        duration_ms=max(0, active.last_ms - active.since_ms),
                        confidence=active.confidence_sum / max(active.count, 1),
                        event_id=active.event_id,
                        count=active.count,
                    )
                if active.recovery_since_ms is None:
                    active.recovery_since_ms = now
                if now - active.recovery_since_ms >= recovery_ms:
                    transition = AttentionTransition(
                        action="close",
                        state=active.state,
                        direction=active.direction,
                        start_ms=active.since_ms,
                        end_ms=now,
                        duration_ms=max(0, now - active.since_ms),
                        confidence=active.confidence_sum / max(active.count, 1),
                        event_id=active.event_id,
                        count=active.count,
                    )
                    self._active.pop(key, None)
                    self._pending.pop(key, None)
                    return transition
                return AttentionTransition(action="none", state=combined_state, direction=direction)

            if not violation or technical:
                self._pending.pop(key, None)
                return AttentionTransition(action="none", state=combined_state, direction=direction)

            same_pending = pending.state == combined_state and pending.direction == direction and now - pending.last_ms <= max(confirm_ms * 2, 4000)
            if not same_pending:
                pending = PendingAttention(combined_state, direction, now, now, 1, confidence)
            else:
                pending.last_ms = now
                pending.count += 1
                pending.confidence_sum += confidence
            self._pending[key] = pending
            elapsed = max(0, pending.last_ms - pending.since_ms)
            if pending.count >= max(1, confirm_count) and elapsed >= max(0, confirm_ms):
                active = ActiveAttention(
                    state=combined_state,
                    direction=direction,
                    since_ms=pending.since_ms,
                    last_ms=now,
                    confidence_sum=pending.confidence_sum,
                    count=pending.count,
                )
                self._active[key] = active
                self._pending.pop(key, None)
                return AttentionTransition(
                    action="open",
                    state=combined_state,
                    direction=direction,
                    start_ms=active.since_ms,
                    end_ms=active.last_ms,
                    duration_ms=max(0, active.last_ms - active.since_ms),
                    confidence=active.confidence_sum / max(active.count, 1),
                    count=active.count,
                )
            return AttentionTransition(action="none", state=combined_state, direction=direction, start_ms=pending.since_ms, end_ms=now, duration_ms=elapsed, confidence=pending.confidence_sum / max(pending.count, 1), count=pending.count)

    @staticmethod
    def _correlated(active: ActiveAttention, state: str, direction: str) -> bool:
        # Gaze-only/head-only may become combined without opening a duplicate event.
        return direction == active.direction and ({active.state, state} <= VIOLATION_STATES)

    def bind_event(self, session_id: str, event_id: str) -> None:
        with self._lock:
            active = self._active.get(session_id)
            if active is not None:
                active.event_id = event_id

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._pending.pop(session_id, None)
            self._active.pop(session_id, None)


class MediaPipeLandmarkProvider:
    """Lazy CPU MediaPipe Tasks Face Landmarker provider.

    The model is downloaded by ``prepare_models.py`` and checksum-verified from
    the project model manifest. Missing or invalid assets fail closed instead of
    silently falling back to a weaker five-landmark or dark-pixel heuristic.
    """

    package_version = "0.10.35"
    model_name = "MediaPipe Face Landmarker float16 task"
    model_asset = "face_landmarker.task"
    model_sha256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
    model_size_bytes = 3_758_596
    license_name = "Apache-2.0"
    windows_amd64_wheel_sha256 = "b08f001cf3c3cd0d88d9ed68f3368dc8a4913f568281a93117f083115aa672ba"

    def __init__(self, model_path: Path | None = None) -> None:
        if model_path is None:
            from ..config import get_settings

            model_path = get_settings().models_dir / self.model_asset
        self.model_path = Path(model_path)
        self._landmarker: Any = None
        self._lock = threading.Lock()
        self._load_error: str | None = None

    @property
    def available(self) -> bool:
        if not self.model_path.exists():
            self._load_error = f"Missing model asset: {self.model_path}"
            return False
        installed = self.installed_asset_checksum()
        if installed != self.model_sha256:
            self._load_error = (
                f"Invalid model checksum for {self.model_path.name}: "
                f"expected {self.model_sha256}, got {installed or 'unreadable'}"
            )
            return False
        try:
            import mediapipe  # noqa: F401
            return True
        except Exception as exc:
            self._load_error = f"MediaPipe {self.package_version} is unavailable: {exc}"
            return False

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def _load(self) -> None:
        if self._landmarker is not None:
            return
        if not self.available:
            raise RuntimeError(self._load_error or "MediaPipe Face Landmarker is unavailable")
        try:
            import mediapipe as mp

            base_options = mp.tasks.BaseOptions(
                model_asset_path=str(self.model_path),
                delegate=mp.tasks.BaseOptions.Delegate.CPU,
            )
            options = mp.tasks.vision.FaceLandmarkerOptions(
                base_options=base_options,
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                num_faces=1,
                min_face_detection_confidence=0.50,
                min_face_presence_confidence=0.50,
                min_tracking_confidence=0.50,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=True,
            )
            self._landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        except Exception as exc:  # pragma: no cover - native package failure
            self._load_error = str(exc)
            raise RuntimeError(f"MediaPipe Face Landmarker could not load: {exc}") from exc

    def detect(self, image_bgr: np.ndarray) -> np.ndarray | None:
        self._load()
        import mediapipe as mp

        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        with self._lock:
            result = self._landmarker.detect(mp_image)
        if not result.face_landmarks:
            return None
        landmarks = result.face_landmarks[0]
        return np.asarray([[p.x, p.y, p.z] for p in landmarks], dtype=np.float64)

    def installed_asset_checksum(self) -> str | None:
        try:
            if not self.model_path.exists():
                return None
            digest = hashlib.sha256()
            with self.model_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except OSError:
            return None


def _point(landmarks: np.ndarray, index: int, width: int, height: int) -> np.ndarray:
    value = landmarks[index]
    return np.asarray([value[0] * width, value[1] * height], dtype=np.float64)


def _mean_point(landmarks: np.ndarray, indices: Iterable[int], width: int, height: int) -> np.ndarray:
    return np.mean([_point(landmarks, index, width, height) for index in indices], axis=0)


def _projection_ratio(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> float:
    vector = end - start
    denom = float(np.dot(vector, vector))
    if denom <= 1e-8:
        return 0.5
    return float(np.dot(point - start, vector) / denom)


def _median(values: Iterable[float], default: float = 0.0) -> float:
    items = [float(v) for v in values if math.isfinite(float(v))]
    return float(median(items)) if items else default


def _mad(values: Iterable[float], centre: float, default: float = 0.0) -> float:
    items = [abs(float(v) - centre) for v in values if math.isfinite(float(v))]
    return float(median(items)) if items else default


def automatic_baseline_sample(
    raw: dict[str, Any],
    *,
    relative_ms: int,
    minimum_confidence: float,
    max_abs_yaw: float,
    max_abs_pitch: float,
    max_abs_roll: float,
) -> tuple[dict[str, Any] | None, str | None]:
    """Return a compact passive-baseline sample or a technical rejection reason.

    Only naturally screen-facing, high-quality pose frames are accepted. Gaze is
    optional: a reliable centre-gaze value is stored when available, otherwise
    head-pose baseline establishment can still complete safely.
    """

    if raw.get("status") != "valid":
        return None, str(raw.get("failure_reason") or raw.get("status") or "invalid_attention_frame")
    if raw.get("pose_status") != "valid":
        return None, str(raw.get("pose_failure_reason") or "pose_low_confidence")
    if bool(raw.get("eyes_closed")):
        return None, "eyes_closed"
    landmark_confidence = float(raw.get("landmark_confidence", 0.0))
    pose_confidence = float(raw.get("pose_confidence", 0.0))
    if min(landmark_confidence, pose_confidence) < minimum_confidence:
        return None, "baseline_confidence_below_threshold"
    yaw = float(raw.get("raw_yaw", 0.0))
    pitch = float(raw.get("raw_pitch", 0.0))
    roll = float(raw.get("raw_roll", 0.0))
    if abs(yaw) > max_abs_yaw or abs(pitch) > max_abs_pitch or abs(roll) > max_abs_roll:
        return None, "pose_not_neutral_enough_for_passive_baseline"
    sample: dict[str, Any] = {
        "relative_ms": max(0, int(relative_ms)),
        "raw_yaw": yaw,
        "raw_pitch": pitch,
        "raw_roll": roll,
        "landmark_confidence": landmark_confidence,
        "pose_confidence": pose_confidence,
    }
    gaze_confidence = float(raw.get("gaze_confidence", 0.0))
    if raw.get("gaze_status") == "valid" and gaze_confidence >= minimum_confidence:
        gaze_x = float(raw.get("gaze_x_ratio", 0.5))
        gaze_y = float(raw.get("gaze_y_ratio", 0.5))
        # Very large offsets are not treated as a neutral centre-gaze sample.
        if 0.30 <= gaze_x <= 0.70 and 0.28 <= gaze_y <= 0.72:
            sample.update({
                "gaze_x_ratio": gaze_x,
                "gaze_y_ratio": gaze_y,
                "gaze_confidence": gaze_confidence,
            })
    return sample, None


def finalize_automatic_baseline(
    samples: list[dict[str, Any]],
    *,
    minimum_samples: int,
    minimum_span_ms: int,
    max_mad_yaw: float,
    max_mad_pitch: float,
    max_mad_roll: float,
    minimum_confidence: float,
) -> dict[str, Any]:
    """Evaluate passive samples and derive a stable neutral pose.

    The result is deterministic and contains no random fallback values. Directional
    gaze boundaries remain conservative offsets around the observed centre gaze.
    """

    ordered = sorted(samples, key=lambda item: int(item.get("relative_ms", 0)))
    count = len(ordered)
    span_ms = 0 if count < 2 else int(ordered[-1]["relative_ms"]) - int(ordered[0]["relative_ms"])
    yaw = _median(item.get("raw_yaw", 0.0) for item in ordered)
    pitch = _median(item.get("raw_pitch", 0.0) for item in ordered)
    roll = _median(item.get("raw_roll", 0.0) for item in ordered)
    yaw_mad = _mad((item.get("raw_yaw", 0.0) for item in ordered), yaw, 99.0)
    pitch_mad = _mad((item.get("raw_pitch", 0.0) for item in ordered), pitch, 99.0)
    roll_mad = _mad((item.get("raw_roll", 0.0) for item in ordered), roll, 99.0)
    landmark_confidence = _median(item.get("landmark_confidence", 0.0) for item in ordered)
    pose_confidence = _median(item.get("pose_confidence", 0.0) for item in ordered)
    gaze_samples = [item for item in ordered if "gaze_x_ratio" in item and "gaze_y_ratio" in item]
    neutral_gaze_x = _median((item["gaze_x_ratio"] for item in gaze_samples), 0.5)
    neutral_gaze_y = _median((item["gaze_y_ratio"] for item in gaze_samples), 0.5)
    gaze_confidence = _median((item.get("gaze_confidence", 0.0) for item in gaze_samples), 0.0)
    stable = yaw_mad <= max_mad_yaw and pitch_mad <= max_mad_pitch and roll_mad <= max_mad_roll
    enough = count >= max(1, minimum_samples) and span_ms >= max(0, minimum_span_ms)
    confident = min(landmark_confidence, pose_confidence) >= minimum_confidence
    ready = bool(enough and stable and confident)
    stability_quality = float(np.clip(1.0 - max(
        yaw_mad / max(max_mad_yaw, 1e-6),
        pitch_mad / max(max_mad_pitch, 1e-6),
        roll_mad / max(max_mad_roll, 1e-6),
    ) * 0.5, 0.0, 1.0)) if ordered else 0.0
    baseline_confidence = float(np.clip(min(landmark_confidence, pose_confidence) * stability_quality, 0.0, 1.0))
    warning = None
    if not enough:
        warning = "collecting_additional_valid_neutral_frames"
    elif not stable:
        warning = "neutral_pose_samples_are_not_yet_stable"
    elif not confident:
        warning = "neutral_pose_confidence_is_below_threshold"
    return {
        "mode": "automatic_passive",
        "status": "ready" if ready else "collecting",
        "ready": ready,
        "accepted_samples": count,
        "sample_span_ms": max(0, span_ms),
        "neutral_pose": {"yaw": yaw, "pitch": pitch, "roll": roll},
        "natural_pose_range": {
            "yaw": max(4.0, 3.0 * yaw_mad),
            "pitch": max(4.0, 3.0 * pitch_mad),
            "roll": max(3.0, 3.0 * roll_mad),
        },
        "neutral_gaze": {"x_ratio": neutral_gaze_x, "y_ratio": neutral_gaze_y},
        "gaze_center_ready": len(gaze_samples) >= max(3, minimum_samples // 2),
        "baseline_confidence": round(baseline_confidence, 4),
        "uncertainty": "low" if ready and baseline_confidence >= 0.70 else "moderate",
        "technical_warning": warning,
        "quality": {
            "yaw_mad": round(yaw_mad, 4),
            "pitch_mad": round(pitch_mad, 4),
            "roll_mad": round(roll_mad, 4),
            "median_landmark_confidence": round(landmark_confidence, 4),
            "median_pose_confidence": round(pose_confidence, 4),
            "median_gaze_confidence": round(gaze_confidence, 4),
            "gaze_sample_count": len(gaze_samples),
            "stability_quality": round(stability_quality, 4),
        },
    }


def conservative_fallback_baseline(default_thresholds: dict[str, Any], multiplier: float) -> dict[str, Any]:
    multiplier = float(np.clip(multiplier, 1.0, 2.0))
    thresholds = dict(default_thresholds)
    for key in ("yaw_enter_degrees", "pitch_enter_degrees", "roll_enter_degrees", "gaze_horizontal_offset", "gaze_vertical_offset"):
        thresholds[key] = float(thresholds.get(key, 0.0)) * multiplier
    return {
        "mode": "automatic_passive",
        "status": "fallback",
        "ready": False,
        "neutral_pose": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
        "natural_pose_range": {"yaw": 6.0, "pitch": 6.0, "roll": 5.0},
        "neutral_gaze": {"x_ratio": 0.5, "y_ratio": 0.5},
        "detector_thresholds": thresholds,
        "baseline_confidence": 0.15,
        "uncertainty": "high",
        "technical_warning": "stable_passive_baseline_not_yet_available; conservative_default_thresholds_are_active",
    }


class AttentionAnalyzer:
    engine_name = "mediapipe-face-landmarker-iris-solvepnp"
    model_version = "MediaPipe-0.10.35-face-landmarker-float16-v1"

    # Landmark indices exposed by the refined 478-point Face Landmarker task.
    LEFT_IRIS = (468, 469, 470, 471, 472)
    RIGHT_IRIS = (473, 474, 475, 476, 477)

    def __init__(self, provider: MediaPipeLandmarkProvider | None = None, ema_alpha: float = 0.36) -> None:
        from ..config import get_settings

        settings = get_settings()
        self.provider = provider or MediaPipeLandmarkProvider()
        self.ema_alpha = float(np.clip(ema_alpha, 0.05, 1.0))
        self.pose_min_confidence = float(np.clip(settings.head_pose_min_confidence, 0.0, 1.0))
        self.gaze_min_confidence = float(np.clip(settings.gaze_min_confidence, 0.0, 1.0))
        self.blink_ear_threshold = float(np.clip(settings.attention_blink_ear_threshold, 0.05, 0.30))
        self.default_thresholds = {
            "yaw_enter_degrees": settings.attention_yaw_enter_degrees,
            "pitch_enter_degrees": settings.attention_pitch_enter_degrees,
            "roll_enter_degrees": settings.attention_roll_enter_degrees,
            "gaze_horizontal_offset": settings.attention_gaze_horizontal_offset,
            "gaze_vertical_offset": settings.attention_gaze_vertical_offset,
            "hysteresis_ratio": settings.attention_hysteresis_ratio,
            "pose_min_confidence": self.pose_min_confidence,
            "gaze_min_confidence": self.gaze_min_confidence,
            "blink_ear_threshold": self.blink_ear_threshold,
        }
        self._states: dict[str, AttentionFilterState] = {}
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self.provider.available

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._states.pop(session_id, None)

    def analyze(self, image: np.ndarray, face: np.ndarray, *, session_id: str, baseline: dict[str, Any] | None = None) -> dict[str, Any]:
        total_started = time.perf_counter()
        landmark_started = time.perf_counter()
        try:
            landmarks = self.provider.detect(image)
        except RuntimeError as exc:
            return self._failure(
                "model_unavailable",
                str(exc),
                landmark_inference_latency_ms=round((time.perf_counter() - landmark_started) * 1000.0, 3),
                inference_latency_ms=round((time.perf_counter() - total_started) * 1000.0, 3),
            )
        landmark_latency_ms = (time.perf_counter() - landmark_started) * 1000.0
        if landmarks is None or len(landmarks) < 478:
            return self._failure(
                "landmark_unavailable",
                "MediaPipe did not return the refined 478-point face mesh",
                landmark_inference_latency_ms=round(landmark_latency_ms, 3),
                inference_latency_ms=round((time.perf_counter() - total_started) * 1000.0, 3),
            )
        return self.analyze_with_landmarks(
            image,
            face,
            landmarks,
            session_id=session_id,
            baseline=baseline,
            landmark_inference_latency_ms=landmark_latency_ms,
            total_started=total_started,
        )

    def analyze_with_landmarks(
        self,
        image: np.ndarray,
        face: np.ndarray,
        landmarks: np.ndarray,
        *,
        session_id: str,
        baseline: dict[str, Any] | None = None,
        landmark_inference_latency_ms: float = 0.0,
        total_started: float | None = None,
    ) -> dict[str, Any]:
        """Analyze one already-computed dense landmark result.

        Face-presence fallback and attention analysis can share one MediaPipe
        inference instead of running the dense model twice on the same frame.
        """
        started = total_started if total_started is not None else time.perf_counter()
        raw = self.analyze_landmarks(image, face, landmarks)
        raw["landmark_inference_latency_ms"] = round(float(landmark_inference_latency_ms), 3)
        if raw["status"] != "valid":
            raw["inference_latency_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            return raw
        result = self._apply_temporal_and_baseline(session_id, raw, baseline or {})
        result["inference_latency_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
        return result

    def analyze_landmarks(self, image: np.ndarray, face: np.ndarray, landmarks: np.ndarray) -> dict[str, Any]:
        height, width = image.shape[:2]
        quality = self._quality(image, face, landmarks)
        if quality["status"] != "valid":
            return self._failure(
                str(quality["status"]),
                str(quality["failure_reason"]),
                **{key: value for key, value in quality.items() if key not in {"status", "failure_reason"}},
            )
        pose_started = time.perf_counter()
        pose = self._head_pose(landmarks, width, height)
        pose_latency_ms = (time.perf_counter() - pose_started) * 1000.0
        gaze_started = time.perf_counter()
        gaze = self._gaze(image, landmarks, width, height)
        gaze_latency_ms = (time.perf_counter() - gaze_started) * 1000.0
        pose_status = "valid" if float(pose["pose_confidence"]) >= self.pose_min_confidence else "low_confidence"
        gaze_status = str(gaze.get("status", "low_confidence"))
        valid_count = int(pose_status == "valid") + int(gaze_status == "valid")
        if valid_count:
            status = "valid"
            failure_reason = None if valid_count == 2 else "One attention detector was suppressed because its confidence or visibility was insufficient"
        else:
            status = gaze_status if gaze_status != "valid" else pose_status
            failure_reason = gaze.get("failure_reason") or "Both gaze and head-pose confidence were below the safe threshold"
        return {
            "status": status,
            "failure_reason": failure_reason,
            "pose_status": pose_status,
            "pose_failure_reason": None if pose_status == "valid" else "Head-pose reprojection confidence was below the safe threshold",
            "gaze_status": gaze_status,
            "gaze_failure_reason": gaze.get("failure_reason"),
            **quality,
            **pose,
            **gaze,
            "engine": self.engine_name,
            "model_name": self.provider.model_name,
            "model_version": self.model_version,
            "head_pose_inference_latency_ms": round(pose_latency_ms, 3),
            "gaze_inference_latency_ms": round(gaze_latency_ms, 3),
        }

    def _quality(self, image: np.ndarray, face: np.ndarray, landmarks: np.ndarray) -> dict[str, Any]:
        height, width = image.shape[:2]
        x, y, fw, fh = [int(v) for v in face[:4]]
        x1, y1, x2, y2 = max(0, x), max(0, y), min(width, x + fw), min(height, y + fh)
        crop = image[y1:y2, x1:x2]
        face_ratio = float(max(fw, 0) * max(fh, 0) / max(width * height, 1))
        if crop.size == 0:
            return {"status": "landmark_unavailable", "failure_reason": "Invalid face crop", "landmark_confidence": 0.0}
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        contrast = float(gray.std())
        blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        detector_conf = float(face[14]) if len(face) > 14 and math.isfinite(float(face[14])) else 0.7
        finite_ratio = float(np.isfinite(landmarks).all(axis=1).mean())
        confidence = float(np.clip(0.38 * detector_conf + 0.27 * min(face_ratio / 0.12, 1.0) + 0.20 * min(contrast / 45.0, 1.0) + 0.15 * finite_ratio, 0.0, 1.0))
        common = {
            "brightness": round(brightness, 3),
            "contrast": round(contrast, 3),
            "blur_variance": round(blur, 3),
            "face_ratio": round(face_ratio, 5),
            "landmark_confidence": round(confidence, 4),
        }
        if face_ratio < 0.045:
            return {"status": "face_too_small", "failure_reason": "Face occupies too little of the frame for reliable iris geometry", **common}
        if brightness < 32 or contrast < 14:
            return {"status": "low_light", "failure_reason": "Lighting or contrast is too low for reliable eye tracking", **common}
        if brightness > 232:
            return {"status": "low_confidence", "failure_reason": "The face region is overexposed", **common}
        if blur < 22:
            return {"status": "low_confidence", "failure_reason": "The frame is too blurred for stable facial landmarks", **common}
        return {"status": "valid", "failure_reason": None, **common}

    def _head_pose(self, landmarks: np.ndarray, width: int, height: int) -> dict[str, Any]:
        points_2d = np.asarray(
            [
                _point(landmarks, 1, width, height),     # nose tip
                _point(landmarks, 152, width, height),   # chin
                _point(landmarks, 33, width, height),    # left eye outer corner
                _point(landmarks, 263, width, height),   # right eye outer corner
                _point(landmarks, 61, width, height),    # left mouth corner
                _point(landmarks, 291, width, height),   # right mouth corner
            ],
            dtype=np.float64,
        )
        points_3d = np.asarray(
            [
                (0.0, 0.0, 0.0),
                (0.0, -63.6, -12.5),
                (-43.3, 32.7, -26.0),
                (43.3, 32.7, -26.0),
                (-28.9, -28.9, -24.1),
                (28.9, -28.9, -24.1),
            ],
            dtype=np.float64,
        )
        focal = float(max(width, height))
        camera = np.asarray([[focal, 0.0, width / 2.0], [0.0, focal, height / 2.0], [0.0, 0.0, 1.0]], dtype=np.float64)
        distortion = np.zeros((4, 1), dtype=np.float64)
        success, rotation, translation = cv2.solvePnP(points_3d, points_2d, camera, distortion, flags=cv2.SOLVEPNP_ITERATIVE)
        if not success:
            return {"raw_yaw": 0.0, "raw_pitch": 0.0, "raw_roll": 0.0, "pose_confidence": 0.0, "reprojection_error_px": None}
        matrix, _ = cv2.Rodrigues(rotation)
        pitch, yaw, roll = [float(v) for v in cv2.RQDecomp3x3(matrix)[0]]
        projected, _ = cv2.projectPoints(points_3d, rotation, translation, camera, distortion)
        projected = projected.reshape(-1, 2)
        error = float(np.sqrt(np.mean(np.sum((projected - points_2d) ** 2, axis=1))))
        scale = max(float(np.linalg.norm(points_2d[2] - points_2d[3])), 1.0)
        normalized_error = error / scale
        confidence = float(np.clip(math.exp(-5.0 * normalized_error), 0.0, 1.0))
        return {
            "raw_yaw": round(yaw, 4),
            "raw_pitch": round(pitch, 4),
            "raw_roll": round(roll, 4),
            "pose_confidence": round(confidence, 4),
            "reprojection_error_px": round(error, 4),
        }

    def _gaze(self, image: np.ndarray, landmarks: np.ndarray, width: int, height: int) -> dict[str, Any]:
        left_outer, left_inner = _point(landmarks, 33, width, height), _point(landmarks, 133, width, height)
        right_inner, right_outer = _point(landmarks, 362, width, height), _point(landmarks, 263, width, height)
        left_upper = _mean_point(landmarks, (159, 160, 158), width, height)
        left_lower = _mean_point(landmarks, (145, 144, 153), width, height)
        right_upper = _mean_point(landmarks, (386, 385, 387), width, height)
        right_lower = _mean_point(landmarks, (374, 380, 373), width, height)
        left_iris = _mean_point(landmarks, self.LEFT_IRIS, width, height)
        right_iris = _mean_point(landmarks, self.RIGHT_IRIS, width, height)

        left_h = float(np.linalg.norm(left_inner - left_outer))
        right_h = float(np.linalg.norm(right_outer - right_inner))
        left_ear = float(np.linalg.norm(left_upper - left_lower) / max(left_h, 1e-6))
        right_ear = float(np.linalg.norm(right_upper - right_lower) / max(right_h, 1e-6))
        eyes_closed = (left_ear + right_ear) / 2.0 < self.blink_ear_threshold

        left_x = _projection_ratio(left_iris, np.asarray([min(left_outer[0], left_inner[0]), left_iris[1]]), np.asarray([max(left_outer[0], left_inner[0]), left_iris[1]]))
        right_x = _projection_ratio(right_iris, np.asarray([min(right_inner[0], right_outer[0]), right_iris[1]]), np.asarray([max(right_inner[0], right_outer[0]), right_iris[1]]))
        left_y = _projection_ratio(left_iris, left_upper, left_lower)
        right_y = _projection_ratio(right_iris, right_upper, right_lower)

        left_conf, left_reflection = self._eye_confidence(image, left_iris, left_h, left_ear)
        right_conf, right_reflection = self._eye_confidence(image, right_iris, right_h, right_ear)
        agreement = float(np.clip(1.0 - 2.0 * (abs(left_x - right_x) + 0.7 * abs(left_y - right_y)), 0.0, 1.0))
        confidence = float(np.clip((left_conf + right_conf) * 0.35 + agreement * 0.30, 0.0, 1.0))
        status = "valid"
        failure_reason = None
        if eyes_closed:
            status, failure_reason = "eyes_not_visible", "Eyes are closed or eyelid geometry is not reliable"
        elif left_reflection and right_reflection:
            status, failure_reason = "glasses_reflection", "Specular reflection obscures both iris regions"
        elif min(left_conf, right_conf) < 0.20:
            status, failure_reason = "low_confidence", "One or both eyes are not reliable enough for gaze classification"
        return {
            "status": status,
            "failure_reason": failure_reason,
            "gaze_x_ratio": round(float(np.mean([left_x, right_x])), 5),
            "gaze_y_ratio": round(float(np.mean([left_y, right_y])), 5),
            "left_eye_x_ratio": round(left_x, 5),
            "right_eye_x_ratio": round(right_x, 5),
            "left_eye_y_ratio": round(left_y, 5),
            "right_eye_y_ratio": round(right_y, 5),
            "left_eye_confidence": round(left_conf, 4),
            "right_eye_confidence": round(right_conf, 4),
            "gaze_confidence": round(confidence, 4),
            "eyes_closed": bool(eyes_closed),
            "left_eye_aspect_ratio": round(left_ear, 5),
            "right_eye_aspect_ratio": round(right_ear, 5),
            "glasses_reflection": bool(left_reflection or right_reflection),
        }

    @staticmethod
    def _eye_confidence(image: np.ndarray, iris: np.ndarray, eye_width: float, ear: float) -> tuple[float, bool]:
        radius = max(3, int(round(eye_width * 0.20)))
        x, y = int(round(iris[0])), int(round(iris[1]))
        x1, x2 = max(0, x - radius), min(image.shape[1], x + radius + 1)
        y1, y2 = max(0, y - radius), min(image.shape[0], y + radius + 1)
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            return 0.0, False
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        reflection_ratio = float(np.mean(gray >= 245))
        contrast = float(gray.std())
        geometry = float(np.clip((ear - 0.08) / 0.10, 0.0, 1.0))
        confidence = float(np.clip(0.55 * geometry + 0.30 * min(contrast / 45.0, 1.0) + 0.15 * (1.0 - min(reflection_ratio / 0.25, 1.0)), 0.0, 1.0))
        return confidence, reflection_ratio > 0.30

    def _apply_temporal_and_baseline(self, session_id: str, raw: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
        neutral_pose = baseline.get("neutral_pose", {})
        neutral_gaze = baseline.get("neutral_gaze", {})
        neutral_pose_vector = np.asarray([
            float(neutral_pose.get("yaw", 0.0)),
            float(neutral_pose.get("pitch", 0.0)),
            float(neutral_pose.get("roll", 0.0)),
        ], dtype=np.float64)
        relative_pose = np.asarray([
            float(raw["raw_yaw"]), float(raw["raw_pitch"]), float(raw["raw_roll"]),
        ], dtype=np.float64) - neutral_pose_vector
        relative_gaze = np.asarray([
            float(raw["gaze_x_ratio"]) - float(neutral_gaze.get("x_ratio", 0.5)),
            float(raw["gaze_y_ratio"]) - float(neutral_gaze.get("y_ratio", 0.5)),
        ], dtype=np.float64)
        pose_valid = raw.get("pose_status", "valid") == "valid" and float(raw.get("pose_confidence", 0.0)) >= self.pose_min_confidence
        gaze_valid = raw.get("gaze_status", raw.get("status", "low_confidence")) == "valid" and float(raw.get("gaze_confidence", 0.0)) >= self.gaze_min_confidence and not bool(raw.get("eyes_closed"))

        with self._lock:
            state = self._states.setdefault(session_id, AttentionFilterState())
            if pose_valid:
                state.pose = relative_pose if state.pose is None else self.ema_alpha * relative_pose + (1.0 - self.ema_alpha) * state.pose
            if gaze_valid:
                state.gaze = relative_gaze if state.gaze is None else self.ema_alpha * relative_gaze + (1.0 - self.ema_alpha) * state.gaze
            smoothed_pose = (state.pose.copy() if state.pose is not None else relative_pose)
            smoothed_gaze = (state.gaze.copy() if state.gaze is not None else relative_gaze)

            effective_baseline = {**baseline}
            effective_baseline["detector_thresholds"] = {
                **self.default_thresholds,
                **dict(baseline.get("detector_thresholds", {})),
            }
            pose_direction = self._classify_pose(smoothed_pose, state.pose_direction, effective_baseline) if pose_valid else "unknown"
            # Head compensation prevents the same physical head turn from also
            # becoming a second gaze violation, while preserving eye-only motion.
            compensated_gaze = smoothed_gaze.copy()
            compensated_gaze[0] -= float(np.clip(smoothed_pose[0] * 0.0012, -0.04, 0.04))
            compensated_gaze[1] -= float(np.clip(smoothed_pose[1] * 0.0010, -0.035, 0.035))
            gaze_direction = self._classify_gaze(compensated_gaze, state.gaze_direction, effective_baseline) if gaze_valid else "unknown"
            blink_detected = bool(raw.get("eyes_closed") and not state.eyes_closed)
            if pose_valid:
                state.pose_direction = pose_direction
            if gaze_valid:
                state.gaze_direction = gaze_direction
            state.eyes_closed = bool(raw.get("eyes_closed"))

        combined_state, dominant, duplicate = self._coordinate(
            pose_direction,
            gaze_direction,
            float(raw.get("pose_confidence", 0.0)),
            float(raw.get("gaze_confidence", 0.0)),
            bool(raw.get("eyes_closed")),
            str(raw.get("pose_status", "low_confidence")),
            str(raw.get("gaze_status", "low_confidence")),
        )
        if combined_state == "combined_look_away":
            combined_confidence = 0.5 * (float(raw["pose_confidence"]) + float(raw["gaze_confidence"]))
        elif combined_state == "head_only_look_away":
            combined_confidence = float(raw["pose_confidence"])
        elif combined_state == "eye_only_look_away":
            combined_confidence = float(raw["gaze_confidence"])
        elif combined_state == "screen_focused":
            valid_confidences = [value for value, valid in ((float(raw["pose_confidence"]), pose_valid), (float(raw["gaze_confidence"]), gaze_valid)) if valid]
            combined_confidence = min(valid_confidences) if valid_confidences else 0.0
        else:
            combined_confidence = 0.0
        direction = pose_direction if pose_direction not in {"center", "unknown"} else gaze_direction
        if combined_state == "combined_look_away" and pose_direction != gaze_direction:
            direction = f"gaze_{gaze_direction}_head_{pose_direction}"
        smoothed_absolute_pose = smoothed_pose + neutral_pose_vector
        return {
            **raw,
            "smoothed_yaw": round(float(smoothed_absolute_pose[0]), 4),
            "smoothed_pitch": round(float(smoothed_absolute_pose[1]), 4),
            "smoothed_roll": round(float(smoothed_absolute_pose[2]), 4),
            "neutral_relative_yaw": round(float(smoothed_pose[0]), 4),
            "neutral_relative_pitch": round(float(smoothed_pose[1]), 4),
            "neutral_relative_roll": round(float(smoothed_pose[2]), 4),
            "raw_neutral_relative_yaw": round(float(relative_pose[0]), 4),
            "raw_neutral_relative_pitch": round(float(relative_pose[1]), 4),
            "raw_neutral_relative_roll": round(float(relative_pose[2]), 4),
            "smoothed_gaze_x": round(float(smoothed_gaze[0]), 5),
            "smoothed_gaze_y": round(float(smoothed_gaze[1]), 5),
            "head_compensated_gaze_x": round(float(compensated_gaze[0]), 5),
            "head_compensated_gaze_y": round(float(compensated_gaze[1]), 5),
            "neutral_offset": {
                "yaw": float(neutral_pose.get("yaw", 0.0)),
                "pitch": float(neutral_pose.get("pitch", 0.0)),
                "roll": float(neutral_pose.get("roll", 0.0)),
                "gaze_x": float(neutral_gaze.get("x_ratio", 0.5)),
                "gaze_y": float(neutral_gaze.get("y_ratio", 0.5)),
            },
            "pose_direction": pose_direction,
            "gaze_direction": "eyes_closed" if raw.get("eyes_closed") else gaze_direction,
            "direction": direction,
            "blink_detected": blink_detected,
            "combined_state": combined_state,
            "dominant_detector": dominant,
            "duplicate_suppression": duplicate,
            "combined_confidence": round(float(np.clip(combined_confidence, 0.0, 1.0)), 4),
            "baseline_status": str(baseline.get("status", "collecting")),
            "baseline_confidence": round(float(baseline.get("baseline_confidence", 0.0)), 4),
            "baseline_uncertainty": str(baseline.get("uncertainty", "high")),
            "baseline_technical_warning": baseline.get("technical_warning"),
        }

    @staticmethod
    def _classify_pose(pose: np.ndarray, previous: str, baseline: dict[str, Any]) -> str:
        natural = baseline.get("natural_pose_range", {})
        thresholds = baseline.get("detector_thresholds", {})
        yaw_enter = max(float(thresholds.get("yaw_enter_degrees", 16.0)), float(natural.get("yaw", 4.0)) + 9.0)
        pitch_enter = max(float(thresholds.get("pitch_enter_degrees", 13.0)), float(natural.get("pitch", 4.0)) + 8.0)
        roll_enter = max(float(thresholds.get("roll_enter_degrees", 16.0)), float(natural.get("roll", 3.0)) + 9.0)
        hysteresis = float(np.clip(thresholds.get("hysteresis_ratio", 0.72), 0.4, 0.95))
        yaw_exit, pitch_exit, roll_exit = yaw_enter * hysteresis, pitch_enter * hysteresis, roll_enter * hysteresis
        yaw, pitch, roll = [float(v) for v in pose]
        if previous == "left" and yaw <= -yaw_exit:
            return "left"
        if previous == "right" and yaw >= yaw_exit:
            return "right"
        if previous == "up" and pitch <= -pitch_exit:
            return "up"
        if previous == "down" and pitch >= pitch_exit:
            return "down"
        if previous == "roll_left" and roll <= -roll_exit:
            return "roll_left"
        if previous == "roll_right" and roll >= roll_exit:
            return "roll_right"
        if yaw <= -yaw_enter:
            return "left"
        if yaw >= yaw_enter:
            return "right"
        if pitch <= -pitch_enter:
            return "up"
        if pitch >= pitch_enter:
            return "down"
        if roll <= -roll_enter:
            return "roll_left"
        if roll >= roll_enter:
            return "roll_right"
        return "center"

    @staticmethod
    def _classify_gaze(gaze: np.ndarray, previous: str, baseline: dict[str, Any]) -> str:
        neutral = baseline.get("neutral_gaze", {"x_ratio": 0.5, "y_ratio": 0.5})
        bounds = baseline.get("gaze_boundaries", {})
        x_abs = float(gaze[0] + float(neutral.get("x_ratio", 0.5)))
        y_abs = float(gaze[1] + float(neutral.get("y_ratio", 0.5)))
        thresholds = baseline.get("detector_thresholds", {})
        horizontal = float(thresholds.get("gaze_horizontal_offset", 0.075))
        vertical = float(thresholds.get("gaze_vertical_offset", 0.09))
        defaults = {
            "left": (float(neutral.get("x_ratio", 0.5)) - horizontal, "lte"),
            "right": (float(neutral.get("x_ratio", 0.5)) + horizontal, "gte"),
            "up": (float(neutral.get("y_ratio", 0.5)) - vertical, "lte"),
            "down": (float(neutral.get("y_ratio", 0.5)) + vertical, "gte"),
        }

        def triggered(value: float, direction: str, recovering: bool = False) -> bool:
            threshold, default_operator = defaults[direction]
            threshold = float(bounds.get(direction, threshold))
            operator = str(bounds.get(f"{direction}_operator", default_operator))
            margin = 0.018 if recovering else 0.0
            if operator == "lte":
                return value <= threshold + margin
            return value >= threshold - margin

        coordinate = {"left": x_abs, "right": x_abs, "up": y_abs, "down": y_abs}
        if previous in coordinate and triggered(coordinate[previous], previous, recovering=True):
            return previous
        for direction in ("left", "right", "up", "down"):
            if triggered(coordinate[direction], direction):
                return direction
        return "center"

    @staticmethod
    def _coordinate(
        pose: str,
        gaze: str,
        pose_conf: float,
        gaze_conf: float,
        eyes_closed: bool,
        pose_status: str,
        gaze_status: str,
    ) -> tuple[str, str, str]:
        if eyes_closed:
            return "eyes_closed", "none", "not_applicable"
        # Confidence policy is applied before coordination. Reusing the technical
        # status here preserves configurable thresholds instead of introducing a
        # second hidden hard-coded confidence cut-off.
        pose_valid = pose_status == "valid" and pose != "unknown"
        gaze_valid = gaze_status == "valid" and gaze != "unknown"
        pose_away = pose_valid and pose != "center"
        gaze_away = gaze_valid and gaze != "center"
        if pose_away and gaze_away:
            dominant = "coordinated" if abs(pose_conf - gaze_conf) < 0.20 else ("head_pose" if pose_conf > gaze_conf else "gaze")
            return "combined_look_away", dominant, "single_coordinated_event"
        if gaze_away:
            return "eye_only_look_away", "gaze", "gaze_only"
        if pose_away:
            return "head_only_look_away", "head_pose", "pose_only"
        if pose_valid and gaze_valid:
            return "screen_focused", "none", "no_duplicate"
        return "low_confidence", "none", "suppressed_low_confidence"

    def _failure(self, status: str, reason: str, **extra: Any) -> dict[str, Any]:
        return {
            "status": status,
            "failure_reason": reason,
            "gaze_direction": "unknown",
            "pose_direction": "unknown",
            "direction": "unknown",
            "gaze_confidence": 0.0,
            "left_eye_confidence": 0.0,
            "right_eye_confidence": 0.0,
            "eyes_closed": False,
            "blink_detected": False,
            "raw_yaw": 0.0,
            "raw_pitch": 0.0,
            "raw_roll": 0.0,
            "smoothed_yaw": 0.0,
            "smoothed_pitch": 0.0,
            "smoothed_roll": 0.0,
            "pose_confidence": 0.0,
            "landmark_confidence": float(extra.get("landmark_confidence", 0.0)),
            "combined_state": "landmark_unavailable" if status == "landmark_unavailable" else "low_confidence",
            "dominant_detector": "none",
            "duplicate_suppression": "suppressed_technical_state",
            "combined_confidence": 0.0,
            "landmark_inference_latency_ms": float(extra.get("landmark_inference_latency_ms", 0.0)),
            "head_pose_inference_latency_ms": float(extra.get("head_pose_inference_latency_ms", 0.0)),
            "gaze_inference_latency_ms": float(extra.get("gaze_inference_latency_ms", 0.0)),
            "inference_latency_ms": float(extra.get("inference_latency_ms", 0.0)),
            "engine": self.engine_name,
            "model_version": self.model_version,
            **extra,
        }
