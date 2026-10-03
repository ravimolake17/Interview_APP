from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from typing import Any, Iterable

VOICE_SENTENCES: tuple[tuple[str, str], ...] = (
    ("voice-01", "Honesty and regular effort help us achieve meaningful success."),
    ("voice-02", "Clear communication makes teamwork easier and more productive every day."),
    ("voice-03", "Consistent learning helps people improve their skills over time."),
    ("voice-04", "Good preparation builds confidence before every important interview."),
    ("voice-05", "Responsible choices create trust and support long term professional growth."),
)

_WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?", re.IGNORECASE)


@dataclass(frozen=True)
class WordResult:
    expected_index: int
    expected: str
    recognized: str | None
    state: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "expected_index": self.expected_index,
            "expected": self.expected,
            "recognized": self.recognized,
            "state": self.state,
        }


@dataclass(frozen=True)
class SentenceResult:
    passed: bool
    failure_reason: str | None
    completion_percentage: float
    expected_words: list[str]
    recognized_words: list[str]
    word_results: list[WordResult]
    repeated_words: list[str]
    extra_words: list[str]
    completed_count: int
    skipped_count: int
    incorrect_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "failure_reason": self.failure_reason,
            "completion_percentage": self.completion_percentage,
            "expected_words": self.expected_words,
            "recognized_words": self.recognized_words,
            "word_results": [item.as_dict() for item in self.word_results],
            "repeated_words": self.repeated_words,
            "extra_words": self.extra_words,
            "completed_count": self.completed_count,
            "skipped_count": self.skipped_count,
            "incorrect_count": self.incorrect_count,
        }


def normalize_words(text: str | None) -> list[str]:
    if not text:
        return []
    return [match.group(0).lower() for match in _WORD_RE.finditer(text)]


def sentence_by_id(sentence_id: str) -> tuple[str, str]:
    for item in VOICE_SENTENCES:
        if item[0] == sentence_id:
            return item
    raise KeyError(sentence_id)


def choose_sentence(*, exclude_id: str | None = None) -> tuple[str, str]:
    choices = [item for item in VOICE_SENTENCES if item[0] != exclude_id] or list(VOICE_SENTENCES)
    return secrets.choice(choices)


def _edit_operations(expected: list[str], recognized: list[str]) -> list[tuple[str, str | None, str | None]]:
    """Return a deterministic minimum-edit alignment.

    Operations are equal, replace, delete (expected word skipped), and insert
    (unexpected/repeated recognized word). Ties prefer equal/replace, then
    delete, then insert so the candidate-facing result is stable.
    """
    rows, cols = len(expected) + 1, len(recognized) + 1
    cost = [[0] * cols for _ in range(rows)]
    op = [[""] * cols for _ in range(rows)]
    for i in range(1, rows):
        cost[i][0] = i
        op[i][0] = "delete"
    for j in range(1, cols):
        cost[0][j] = j
        op[0][j] = "insert"

    for i in range(1, rows):
        for j in range(1, cols):
            same = expected[i - 1] == recognized[j - 1]
            candidates = [
                (cost[i - 1][j - 1] + (0 if same else 1), "equal" if same else "replace", 0),
                (cost[i - 1][j] + 1, "delete", 1),
                (cost[i][j - 1] + 1, "insert", 2),
            ]
            best = min(candidates, key=lambda item: (item[0], item[2]))
            cost[i][j], op[i][j] = best[0], best[1]

    output: list[tuple[str, str | None, str | None]] = []
    i, j = len(expected), len(recognized)
    while i or j:
        operation = op[i][j]
        if operation in {"equal", "replace"}:
            output.append((operation, expected[i - 1], recognized[j - 1]))
            i -= 1
            j -= 1
        elif operation == "delete":
            output.append((operation, expected[i - 1], None))
            i -= 1
        elif operation == "insert":
            output.append((operation, None, recognized[j - 1]))
            j -= 1
        else:
            raise RuntimeError("sentence alignment entered an invalid state")
    output.reverse()
    return output


def evaluate_sentence(
    expected_text: str,
    recognized_text: str | None,
    *,
    minimum_completion: float = 0.80,
    maximum_skipped: int = 1,
    maximum_incorrect: int = 1,
) -> SentenceResult:
    expected = normalize_words(expected_text)
    recognized = normalize_words(recognized_text)
    if not expected:
        raise ValueError("verification sentence contains no words")

    aligned = _edit_operations(expected, recognized)
    results: list[WordResult] = []
    extras: list[str] = []
    seen_recognized: dict[str, int] = {}
    repeated: list[str] = []
    expected_index = 0
    completed = skipped = incorrect = 0

    for operation, expected_word, recognized_word in aligned:
        if recognized_word is not None:
            seen_recognized[recognized_word] = seen_recognized.get(recognized_word, 0) + 1
            if seen_recognized[recognized_word] > 1 and recognized_word not in repeated:
                repeated.append(recognized_word)
        if operation == "insert":
            if recognized_word is not None:
                extras.append(recognized_word)
            continue
        if expected_word is None:
            continue
        if operation == "equal":
            state = "completed"
            completed += 1
        elif operation == "delete":
            state = "skipped"
            skipped += 1
        else:
            state = "incorrect"
            incorrect += 1
        results.append(WordResult(expected_index, expected_word, recognized_word, state))
        expected_index += 1

    completion = round((completed / len(expected)) * 100.0, 2)
    passed = True
    failure_reason: str | None = None
    if not recognized:
        passed, failure_reason = False, "no_speech_detected"
    elif len(recognized) < max(2, int(len(expected) * 0.45)):
        passed, failure_reason = False, "sentence_not_completed"
    elif completion < minimum_completion * 100:
        passed, failure_reason = False, "sentence_not_completed"
    elif skipped > maximum_skipped:
        passed, failure_reason = False, "too_many_words_skipped"
    elif incorrect > maximum_incorrect:
        passed, failure_reason = False, "too_many_incorrect_words"
    elif len(extras) > max(2, len(expected) // 3):
        passed, failure_reason = False, "unrelated_speech_detected"

    return SentenceResult(
        passed=passed,
        failure_reason=failure_reason,
        completion_percentage=completion,
        expected_words=expected,
        recognized_words=recognized,
        word_results=results,
        repeated_words=repeated,
        extra_words=extras,
        completed_count=completed,
        skipped_count=skipped,
        incorrect_count=incorrect,
    )


def serialize_word_results(items: Iterable[WordResult]) -> list[dict[str, Any]]:
    return [item.as_dict() for item in items]
