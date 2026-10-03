from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class DetectionResult:
    passed: bool
    label: str
    confidence: float
    measurements: dict[str, Any] = field(default_factory=dict)
    vector: np.ndarray | None = None


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32).reshape(-1)
    b = np.asarray(b, dtype=np.float32).reshape(-1)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-12:
        return 0.0
    return float(np.dot(a, b) / denom)


def softmax(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    shifted = values - np.max(values)
    exp = np.exp(shifted)
    return exp / max(float(exp.sum()), 1e-12)


class ModelUnavailableError(RuntimeError):
    """Raised when a mandatory production AI model is unavailable or cannot load."""

