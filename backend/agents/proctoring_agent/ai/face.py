from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from ..config import get_settings
from .common import DetectionResult, cosine_similarity, softmax
from .attention import AttentionAnalyzer


@dataclass
class FaceQuality:
    accepted: bool
    reasons: list[str]
    blur_variance: float
    brightness: float
    contrast: float
    face_ratio: float
    edge_margin_ratio: float
    yaw_proxy: float = 0.0
    pitch_proxy: float = 0.0
    roll_degrees: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reasons": self.reasons,
            "blur_variance": round(self.blur_variance, 3),
            "brightness": round(self.brightness, 3),
            "contrast": round(self.contrast, 3),
            "face_ratio": round(self.face_ratio, 4),
            "edge_margin_ratio": round(self.edge_margin_ratio, 4),
            "yaw_proxy": round(self.yaw_proxy, 4),
            "pitch_proxy": round(self.pitch_proxy, 4),
            "roll_degrees": round(self.roll_degrees, 3),
        }


class FaceEngine:
    """CPU face detector/recognizer based on OpenCV YuNet and SFace."""

    engine_name = "opencv-yunet-sface"
    model_version = "YuNet-2023mar+SFace-2021dec"

    def __init__(self, detector_path: Path | None = None, recognizer_path: Path | None = None) -> None:
        settings = get_settings()
        self.detector_path = detector_path or settings.models_dir / "face_detection_yunet_2023mar.onnx"
        self.recognizer_path = recognizer_path or settings.models_dir / "face_recognition_sface_2021dec.onnx"
        self._detector = None
        self._recognizer = None
        self._score_threshold = float(np.clip(settings.face_detection_score_threshold, 0.30, 0.95))
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self.detector_path.exists() and self.recognizer_path.exists()

    def _load(self) -> None:
        if self._detector is not None and self._recognizer is not None:
            return
        with self._lock:
            if self._detector is not None and self._recognizer is not None:
                return
            if not self.available:
                raise FileNotFoundError("YuNet/SFace model files are missing; run setup_agent5.ps1")
            if self._detector is None:
                self._detector = cv2.FaceDetectorYN.create(
                    str(self.detector_path), "", (320, 320), self._score_threshold, 0.3, 5000, cv2.dnn.DNN_BACKEND_OPENCV, cv2.dnn.DNN_TARGET_CPU
                )
            if self._recognizer is None:
                self._recognizer = cv2.FaceRecognizerSF.create(str(self.recognizer_path), "")

    def detect(self, image: np.ndarray) -> np.ndarray:
        self._load()
        if image is None or image.size == 0:
            return np.empty((0, 15), dtype=np.float32)
        height, width = image.shape[:2]
        with self._lock:
            self._detector.setInputSize((width, height))
            _, faces = self._detector.detect(image)
        return np.empty((0, 15), dtype=np.float32) if faces is None else faces

    def quality(self, image: np.ndarray, face: np.ndarray) -> FaceQuality:
        height, width = image.shape[:2]
        x, y, w, h = [max(0, int(v)) for v in face[:4]]
        x2, y2 = min(width, x + w), min(height, y + h)
        crop = image[y:y2, x:x2]
        if crop.size == 0:
            return FaceQuality(False, ["invalid face crop"], 0, 0, 0, 0, 0)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(gray.mean())
        contrast = float(gray.std())
        face_ratio = float((w * h) / max(width * height, 1))
        margins = [x / width, y / height, (width - x2) / width, (height - y2) / height]
        edge_margin = float(min(margins))
        # YuNet provides two eye centres, nose tip and two mouth corners.
        # These normalized landmark ratios are a conservative pose-quality gate,
        # not an identity feature and not a calibrated head-pose estimate.
        left_eye = np.asarray(face[4:6], dtype=np.float64)
        right_eye = np.asarray(face[6:8], dtype=np.float64)
        nose = np.asarray(face[8:10], dtype=np.float64)
        eye_mid = (left_eye + right_eye) / 2.0
        eye_distance = float(np.linalg.norm(right_eye - left_eye))
        if eye_distance > 1e-6 and np.isfinite([*left_eye, *right_eye, *nose]).all():
            yaw_proxy = float((nose[0] - eye_mid[0]) / eye_distance)
            pitch_proxy = float((nose[1] - eye_mid[1]) / eye_distance)
            roll_degrees = float(math.degrees(math.atan2(right_eye[1] - left_eye[1], right_eye[0] - left_eye[0])))
        else:
            yaw_proxy = pitch_proxy = roll_degrees = 0.0

        reasons: list[str] = []
        if face_ratio < 0.07:
            reasons.append("face is too small")
        if blur < 35:
            reasons.append("image is too blurred")
        if brightness < 35:
            reasons.append("lighting is too dark")
        if brightness > 225:
            reasons.append("lighting is overexposed")
        if contrast < 18:
            reasons.append("image contrast is too low")
        if edge_margin < 0.005:
            reasons.append("face is partially outside the frame")
        if eye_distance <= 1e-6:
            reasons.append("facial landmarks are invalid")
        else:
            if abs(yaw_proxy) > 0.48:
                reasons.append("face yaw is too large")
            if pitch_proxy < 0.18 or pitch_proxy > 1.55:
                reasons.append("face pitch is too large")
            if abs(roll_degrees) > 28:
                reasons.append("face roll is too large")
        return FaceQuality(
            not reasons, reasons, blur, brightness, contrast, face_ratio, edge_margin, yaw_proxy, pitch_proxy, roll_degrees
        )

    def embedding(self, image: np.ndarray, face: np.ndarray) -> np.ndarray:
        self._load()
        with self._lock:
            if self._recognizer is None:
                raise RuntimeError("SFace recognizer is not loaded")
            aligned = self._recognizer.alignCrop(image, face)
            feature = self._recognizer.feature(aligned)
        vector = np.asarray(feature, dtype=np.float32).reshape(-1)
        if vector.size == 0 or not np.isfinite(vector).all():
            raise RuntimeError("SFace returned an empty or non-finite embedding")
        norm = float(np.linalg.norm(vector))
        if not np.isfinite(norm) or norm <= 1e-8:
            raise RuntimeError("SFace returned an invalid zero-norm embedding")
        return vector / norm

    def enroll(self, image: np.ndarray) -> DetectionResult:
        faces = self.detect(image)
        if len(faces) == 0:
            return DetectionResult(False, "no_face", 1.0, {"face_count": 0, "engine": self.engine_name, "model_version": self.model_version})
        if len(faces) > 1:
            return DetectionResult(False, "multiple_faces", min(1.0, float(len(faces)) / 3), {"face_count": int(len(faces)), "engine": self.engine_name, "model_version": self.model_version})
        quality = self.quality(image, faces[0])
        if not quality.accepted:
            return DetectionResult(False, "poor_quality", 0.0, {**quality.as_dict(), "engine": self.engine_name, "model_version": self.model_version})
        vector = self.embedding(image, faces[0])
        return DetectionResult(True, "face_enrolled", float(faces[0][14]), {"face_count": 1, "quality": quality.as_dict(), "engine": self.engine_name, "model_version": self.model_version}, vector)

    def verify(self, image: np.ndarray, baseline: np.ndarray, threshold: float | None = None) -> DetectionResult:
        faces = self.detect(image)
        if len(faces) == 0:
            return DetectionResult(False, "no_face", 1.0, {"face_count": 0, "engine": self.engine_name, "model_version": self.model_version})
        if len(faces) > 1:
            return DetectionResult(False, "multiple_faces", min(1.0, float(len(faces)) / 3), {"face_count": int(len(faces)), "engine": self.engine_name, "model_version": self.model_version})
        return self.verify_detected(image, faces[0], baseline, threshold=threshold)

    def verify_detected(self, image: np.ndarray, face: np.ndarray, baseline: np.ndarray, threshold: float | None = None) -> DetectionResult:
        """Verify the already-detected face without running YuNet a second time.

        Continuous monitoring previously detected a face, then invoked ``verify``
        which ran a second independent detector pass on the same frame. A marginal
        face could therefore be counted once and then disappear during identity
        verification. Reusing the accepted detection keeps face count and identity
        state consistent and saves one CPU inference per visual request.
        """
        quality = self.quality(image, face)
        if not quality.accepted:
            # A blurred, dark, overexposed, tiny or badly posed face is not
            # evidence of a different identity. Keep this path separate so
            # continuous monitoring cannot convert camera quality into fraud.
            return DetectionResult(False, "poor_quality", 0.0, {"face_count": 1, "quality": quality.as_dict(), "engine": self.engine_name, "model_version": self.model_version})
        baseline = np.asarray(baseline, dtype=np.float32).reshape(-1)
        if baseline.size == 0 or not np.isfinite(baseline).all():
            raise ValueError("stored face baseline is empty or non-finite")
        baseline_norm = float(np.linalg.norm(baseline))
        if not np.isfinite(baseline_norm) or baseline_norm <= 1e-8:
            raise ValueError("stored face baseline has zero norm")
        baseline = baseline / baseline_norm
        vector = self.embedding(image, face)
        similarity = cosine_similarity(vector, baseline)
        threshold = threshold if threshold is not None else get_settings().face_similarity_threshold
        passed = similarity >= threshold
        confidence = min(1.0, abs(similarity - threshold) / max(1.0 - threshold, 1e-6) + 0.5)
        return DetectionResult(
            passed,
            "face_match" if passed else "face_mismatch",
            confidence,
            {"similarity": similarity, "threshold": threshold, "face_count": 1, "quality": quality.as_dict(), "engine": self.engine_name, "model_version": self.model_version},
            vector,
        )


class HeadPoseGazeEngine(AttentionAnalyzer):
    """MediaPipe refined face/iris landmarks with passive-baseline pose and gaze.

    ``analyze`` is the production path and performs one landmark inference for
    both detectors. ``head_pose`` and ``gaze`` remain compatibility adapters for
    older tests/integrations; callers should not invoke both for the same frame.
    """

    def head_pose(self, image: np.ndarray, face: np.ndarray, session_id: str = "legacy") -> dict[str, Any]:
        result = self.analyze(image, face, session_id=session_id, baseline={})
        return {
            **result,
            "yaw": float(result.get("smoothed_yaw", result.get("raw_yaw", 0.0))),
            "pitch": float(result.get("smoothed_pitch", result.get("raw_pitch", 0.0))),
            "roll": float(result.get("smoothed_roll", result.get("raw_roll", 0.0))),
            "direction": str(result.get("pose_direction", "unknown")),
            "confidence": float(result.get("pose_confidence", 0.0)),
        }

    def gaze(self, image: np.ndarray, face: np.ndarray, session_id: str = "legacy") -> dict[str, Any]:
        result = self.analyze(image, face, session_id=session_id, baseline={})
        return {
            **result,
            "direction": str(result.get("gaze_direction", "unknown")),
            "confidence": float(result.get("gaze_confidence", 0.0)),
            "x_ratio": float(result.get("gaze_x_ratio", 0.5)),
            "y_ratio": float(result.get("gaze_y_ratio", 0.5)),
        }


class AntiSpoofEngine:
    """MiniFASNet ONNX passive RGB signal. It is never used alone for termination."""

    engine_name = "opencv-dnn-minifasnetv2"
    model_version = "MiniFASNetV2-weights-release"

    def __init__(self, model_path: Path | None = None) -> None:
        self.model_path = model_path or get_settings().models_dir / "MiniFASNetV2.onnx"
        self._net = None
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self.model_path.exists()

    def _load(self) -> None:
        if self._net is None and self.available:
            self._net = cv2.dnn.readNetFromONNX(str(self.model_path))
            self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

    def analyze(self, image: np.ndarray, face: np.ndarray) -> dict[str, Any]:
        self._load()
        if self._net is None:
            return {"available": False, "label": "not_evaluated", "confidence": 0.0, "engine": self.engine_name, "model_version": self.model_version}
        x, y, w, h = [int(v) for v in face[:4]]
        cx, cy = x + w / 2, y + h / 2
        scale = 2.7
        nw, nh = w * scale, h * scale
        x1, y1 = max(0, int(cx - nw / 2)), max(0, int(cy - nh / 2))
        x2, y2 = min(image.shape[1], int(cx + nw / 2)), min(image.shape[0], int(cy + nh / 2))
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            return {"available": True, "label": "unknown", "confidence": 0.0, "engine": self.engine_name, "model_version": self.model_version}
        blob = cv2.dnn.blobFromImage(crop, scalefactor=1.0 / 255.0, size=(80, 80), mean=(0, 0, 0), swapRB=True, crop=False)
        with self._lock:
            self._net.setInput(blob)
            output = self._net.forward().reshape(-1)
        probs = softmax(output)
        # The selected MiniFASNetV2 export uses a configurable live-class index.
        # The bundled model manifest records index 0 for [live, print, replay].
        live_index = min(max(get_settings().anti_spoof_live_class, 0), len(probs) - 1)
        live_prob = float(probs[live_index])
        return {
            "available": True,
            "label": "live" if live_prob >= 0.70 else "spoof_concern",
            "confidence": max(live_prob, 1.0 - live_prob),
            "live_probability": live_prob,
            "class_probabilities": probs.tolist(),
            "review_only": True,
            "engine": self.engine_name,
            "model_version": self.model_version,
        }
