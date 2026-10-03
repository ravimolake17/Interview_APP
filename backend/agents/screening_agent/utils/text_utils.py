from __future__ import annotations

import re
from collections import Counter


_STOPWORDS = {
    "and", "the", "with", "for", "from", "that", "this", "will", "are", "our",
    "you", "your", "have", "has", "into", "using", "use", "must", "should", "role",
    "team", "work", "working", "candidate", "job", "position", "required", "preferred",
    "skills", "skill", "experience", "years", "year", "responsibilities", "requirements",
    "ability", "knowledge", "strong", "good", "excellent", "including", "such", "other",
    "related", "minimum", "plus", "nice", "looking", "seeking", "develop", "development",
    "title", "education", "bachelor", "master", "degree", "field", "certification", "certified",
    "applications", "application", "models", "model", "design", "intelligent",
    "various", "multiple", "etc", "well", "new", "high", "quality", "based",
    "across", "within", "environment", "environments", "duties",
}


def clean_lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip(" \t•*-–—") for line in text.splitlines() if line.strip()]


def dedupe_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        cleaned = re.sub(r"\s+", " ", value).strip(" \t,;.-")
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            output.append(cleaned)
    return output


def extract_keywords(text: str, limit: int = 30) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,}", text.casefold())
    counts = Counter(word.strip(".-") for word in words)
    ranked = [
        word for word, _count in counts.most_common()
        if word not in _STOPWORDS and not word.isdigit()
    ]
    return ranked[:limit]


def text_contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = re.sub(r"\s+", " ", text.casefold())
    normalized_phrase = re.sub(r"\s+", " ", phrase.casefold()).strip()
    return bool(normalized_phrase and normalized_phrase in normalized_text)
