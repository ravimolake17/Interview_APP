"""Resolve a clean job title from JD content (filename is last resort)."""

from __future__ import annotations

import re
from pathlib import Path

_RESUME_LIKE_MARKERS = (
    "highly motivated",
    "to design",
    "looking for",
    "seeking a",
    "we are",
    "candidate will",
    "responsible for",
)

_GENERIC_FILENAME = re.compile(
    r"^(?:jd|job(?:\s*description)?|untitled|document|file|new\s*document)(?:\s*\d+)?$",
    re.I,
)
_UUID_STEM = re.compile(
    r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
    re.I,
)
_VERSION_SUFFIX = re.compile(r"\s*(?:v\d+(?:\.\d+)*|final|copy|draft)\s*$", re.I)
_JD_PREFIX = re.compile(r"^(?:jd|job\s*description)\s+", re.I)


def _looks_like_resume_sentence(text: str) -> bool:
    lowered = text.lower().strip()
    if len(lowered) > 100:
        return True
    if any(marker in lowered for marker in _RESUME_LIKE_MARKERS):
        return True
    if lowered.count(" ") > 12:
        return True
    return False


def _usable_title(text: str | None) -> str | None:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip(" \t-–—:|")
    if not cleaned or len(cleaned) < 3 or len(cleaned) > 100:
        return None
    if _looks_like_resume_sentence(cleaned):
        return None
    return cleaned[:255]


def _title_from_jd_text(jd_text: str) -> str | None:
    for pattern in (
        r"(?im)^(?:job\s*title|position|role)\s*:\s*(.+)$",
        r"(?im)^(?:hiring|opening)\s*:\s*(.+)$",
        r"(?im)^job description\s*[–—-]\s*(.+)$",
    ):
        match = re.search(pattern, jd_text)
        if match:
            title = _usable_title(match.group(1))
            if title:
                return title

    for raw_line in jd_text.splitlines():
        line = raw_line.strip().lstrip("#*- ").strip()
        if not line or len(line) < 3:
            continue
        lowered = line.lower()
        if lowered.startswith(
            ("about", "responsibilit", "requirement", "summary", "education", "skill")
        ):
            continue
        labeled = re.sub(
            r"^(?:job\s*title|position|role)\s*:\s*",
            "",
            line,
            flags=re.I,
        ).strip()
        title = _usable_title(labeled)
        if title:
            return title
    return None


def _title_from_filename(filename: str) -> str | None:
    raw_stem = Path(filename).stem.strip()
    if not raw_stem or _UUID_STEM.match(raw_stem):
        return None
    stem = raw_stem.replace("_", " ").replace("-", " ")
    stem = re.sub(r"\s+", " ", stem).strip()
    stem = _VERSION_SUFFIX.sub("", stem).strip()
    stem = _JD_PREFIX.sub("", stem).strip()
    if not stem or _GENERIC_FILENAME.match(stem):
        return None
    return _usable_title(stem)


def resolve_job_position_from_jd(
    *,
    jd_text: str | None = None,
    jd_original_filename: str | None = None,
    parsed_job_title: str | None = None,
    stored_job_position: str | None = None,
) -> str:
    """Prefer the role parsed from JD content; use the file name only if nothing else exists."""
    parsed = _usable_title(parsed_job_title)
    if parsed:
        return parsed

    if jd_text:
        from_text = _title_from_jd_text(jd_text)
        if from_text:
            return from_text

    filename_title = _title_from_filename(jd_original_filename) if jd_original_filename else None
    stored = _usable_title(stored_job_position)
    if stored and jd_original_filename:
        raw_stem = Path(jd_original_filename).stem.replace("_", " ").replace("-", " ").strip()
        if stored.casefold() == raw_stem.casefold():
            stored = None

    if stored:
        return stored
    if filename_title:
        return filename_title
    return "Open Position"


def job_title_from_jd_content(
    *,
    jd_text: str | None = None,
    parsed_job_title: str | None = None,
) -> str:
    """Role name from JD body/parser only — never from the uploaded file name."""
    return resolve_job_position_from_jd(
        jd_text=jd_text,
        parsed_job_title=parsed_job_title,
        jd_original_filename=None,
        stored_job_position=None,
    )


def is_filename_as_title(title: str | None, filename: str | None) -> bool:
    cleaned = (title or "").strip()
    if not cleaned or not filename:
        return False
    path = Path(filename)
    stem = path.stem.replace("_", " ").replace("-", " ").strip()
    return cleaned.casefold() in {
        path.name.casefold(),
        path.stem.casefold(),
        stem.casefold(),
    }


def apply_jd_content_title(parsed: dict | None, jd_text: str | None) -> str:
    """Set parsed_jd.job_title from JD content and return the resolved title."""
    parsed = parsed if isinstance(parsed, dict) else {}
    title = job_title_from_jd_content(
        jd_text=jd_text,
        parsed_job_title=parsed.get("job_title"),
    )
    if title and title != "Open Position":
        parsed["job_title"] = title
    return title
