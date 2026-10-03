"""Resume-driven STT correction for Agent 4 (works for every candidate).

No candidate-specific hardcoding. For each transcription we:
1. Extract vocabulary from THAT candidate's resume / JD / question.
2. Bias Whisper with that vocabulary.
3. Fuzzy-fix near-miss spans against resume terms + candidate name.
4. Optionally ask Meta Llama to fix remaining clear phonetic mishearings
   using ONLY that candidate's vocabulary.
"""

from __future__ import annotations

import logging
import os
import re
from difflib import SequenceMatcher
from typing import Any

from agents.evaluation_agent.evaluator import build_candidate_context
from agents.shared.llama_client import call_llama_json, llama_available

logger = logging.getLogger(__name__)

_WHISPER_PROMPT_MAX = 700
_TERM_LIMIT = 80

# Tiny language-level patterns that are true for any English interview transcript.
# These are NOT candidate/project specific.
_GENERIC_ENGLISH_FIXES: list[tuple[str, str]] = [
    (r"\bpost[-\s]?admission\b", "post-graduation"),
    (r"\b(?:and\s+)?demoted\s+to\s+be(?:\s+a)?\s+university\b", "Deemed to be University"),
    (r"\bdeemed\s+to\s+be(?:\s+a)?\s+university\b", "Deemed to be University"),
    (r"\bdeem(?:ed)?\s+utopi(?:a)?(?:\s+university)?\b", "Deemed to be University"),
]

_PROMPT_LEAK_RE = [
    re.compile(r"(?i)\bspeaker\s*name\s*[:,-]?\s*"),
    re.compile(r"(?i)\bspell these resume terms correctly when heard:?\s*"),
    re.compile(r"(?i)\binterview answer in indian english\.?\s*"),
]

_STOP_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "for",
    "with",
    "from",
    "into",
    "onto",
    "using",
    "about",
    "hello",
    "hi",
    "myself",
    "am",
    "is",
    "are",
    "was",
    "were",
    "have",
    "has",
    "had",
    "done",
    "doing",
    "work",
    "working",
    "worked",
    "project",
    "projects",
    "company",
    "currently",
    "located",
    "university",
    "college",
    "graduation",
    "trainee",
    "good",
    "morning",
    "name",
    "my",
    "i",
    "it",
    "at",
    "in",
    "on",
    "to",
    "of",
}


def resume_correction_enabled() -> bool:
    raw = (os.getenv("STT_RESUME_CORRECTION") or "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _clean_term(value: str) -> str:
    text = " ".join((value or "").replace("\n", " ").split()).strip(" ,.;:|-")
    if len(text) < 3:
        return ""
    if text.lower() in _STOP_WORDS:
        return ""
    return text


def _add_term(terms: set[str], value: str) -> None:
    cleaned = _clean_term(value)
    if not cleaned:
        return
    terms.add(cleaned)

    # Short forms before common separators (project/company titles).
    for sep in (":", " - ", " – ", " — ", ",", "|"):
        if sep in cleaned:
            head = _clean_term(cleaned.split(sep, 1)[0])
            if head and len(head) >= 3:
                terms.add(head)

    words = cleaned.split()
    if 2 <= len(words) <= 5 and words[0][:1].isupper() and len(words[0]) >= 4:
        # Keep leading brand/company token (Infosys Limited → Infosys).
        lead = _clean_term(words[0])
        if lead:
            terms.add(lead)

    # CamelCase brands → spaced form for Whisper mis-segmentations (SmartCart → Smart Cart).
    if re.search(r"[a-z][A-Z]", cleaned) and " " not in cleaned and len(cleaned) <= 40:
        spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", cleaned)
        spaced = _clean_term(spaced)
        if spaced:
            terms.add(spaced)

    # Hyphenated brand also as spaced form for matching windows.
    if "-" in cleaned and " " not in cleaned and 3 <= len(cleaned) <= 40:
        spaced = cleaned.replace("-", " ")
        if spaced.lower() not in _STOP_WORDS:
            terms.add(spaced)


def _looks_like_person_name(text: str) -> bool:
    parts = [p for p in text.split() if p]
    if not (2 <= len(parts) <= 4):
        return False
    return all(p[:1].isupper() and p[1:].islower() for p in parts if p.isalpha())


def _add_structured_item(terms: set[str], item: Any) -> None:
    if isinstance(item, dict):
        for field in (
            "title",
            "name",
            "project",
            "company",
            "organization",
            "employer",
            "role",
            "degree",
            "institution",
            "university",
            "college",
            "school",
            "location",
            "city",
            "place",
            "skill",
        ):
            val = str(item.get(field) or "")
            if val:
                _add_term(terms, val)
        for field in ("description", "summary", "details"):
            blob = str(item.get(field) or "")
            if not blob:
                continue
            for line in blob.splitlines()[:8]:
                line = line.strip(" •-\t*")
                if 3 <= len(line) <= 90 and not line.endswith("."):
                    _add_term(terms, line)
    else:
        _add_term(terms, str(item)[:100])


def extract_resume_terms(
    *,
    full_name: str | None,
    evaluation_snapshot: dict[str, Any] | None,
    jd_text: str | None,
    job_position: str | None = None,
    question_text: str | None = None,
) -> list[str]:
    """Build a per-candidate vocabulary list from resume/JD/question text."""
    terms: set[str] = set()
    snap = evaluation_snapshot if isinstance(evaluation_snapshot, dict) else {}
    parsed = snap.get("parsed_resume") if isinstance(snap.get("parsed_resume"), dict) else {}

    if job_position:
        _add_term(terms, job_position)

    for skill in _as_list(snap.get("skills") or parsed.get("skills")):
        if isinstance(skill, dict):
            _add_term(terms, str(skill.get("skill") or skill.get("name") or ""))
        else:
            _add_term(terms, str(skill))

    for key in (
        "projects",
        "experience",
        "experience_entries",
        "education",
        "certifications",
        "achievements",
    ):
        for item in _as_list(parsed.get(key) or snap.get(key)):
            _add_structured_item(terms, item)

    for section in _as_list(parsed.get("sections")):
        if not isinstance(section, dict):
            continue
        heading = str(section.get("title") or section.get("heading") or section.get("name") or "")
        content = str(section.get("content") or section.get("text") or "")
        if heading:
            _add_term(terms, heading)
        for line in content.splitlines()[:24]:
            line = line.strip(" •-\t*")
            if not (3 <= len(line) <= 120):
                continue
            # Prefer title-like lines over long prose.
            if line.endswith(".") and len(line.split()) > 12:
                continue
            if re.search(r"[A-Z]", line) or "-" in line:
                _add_term(terms, line)
        for token in re.findall(r"\b[A-Za-z][A-Za-z0-9+#./-]{2,}\b", content):
            if "-" in token or any(ch.isupper() for ch in token[1:]):
                _add_term(terms, token)
            elif token.isupper() and 2 <= len(token) <= 12:
                _add_term(terms, token)

    # Pull proper-noun phrases from raw resume text.
    source = str(parsed.get("source_text") or snap.get("resume_text") or "")
    if source:
        for match in re.findall(
            r"\b(?:[A-Z][a-z0-9]+(?:[-/][A-Za-z0-9]+)+|[A-Z][a-z]+(?:\s+[A-Z][a-z0-9]+){0,5})\b",
            source[:8000],
        ):
            if not _looks_like_person_name(match) or match.lower() != (full_name or "").lower():
                _add_term(terms, match)

    if jd_text:
        for match in re.findall(r"\b[A-Za-z][A-Za-z0-9+#.-]{2,}\b", jd_text[:2000]):
            if match.isupper() or any(ch.isupper() for ch in match[1:]):
                _add_term(terms, match)

    if question_text:
        for match in re.findall(r"\b[A-Za-z][A-Za-z0-9+#.-]{2,}\b", question_text):
            if "-" in match or any(ch.isupper() for ch in match[1:]):
                _add_term(terms, match)

    # Candidate name is handled separately for intro/surname repair — keep it out of
    # general swap vocabulary so it is not forced into company/location slots.
    if full_name:
        name_l = full_name.strip().lower()
        terms = {t for t in terms if t.lower() != name_l}
        for part in full_name.split():
            if len(part) >= 3:
                terms = {t for t in terms if t.lower() != part.lower()}

    ranked = sorted(terms, key=lambda t: (-len(t), t.lower()))
    return ranked[:_TERM_LIMIT]


def strip_whisper_artifacts(text: str) -> str:
    """Remove prompt-echo / subtitle hallucinations Whisper often copies into the transcript."""
    out = str(text or "")
    for pattern in _PROMPT_LEAK_RE:
        out = pattern.sub(" ", out)
    out = re.sub(
        r"(?i)(?:^|(?<=[.!?]\s))speaker\s+name\b[^.!?]*[.!?]?",
        " ",
        out,
    )
    # Collapse immediate short repeats ("4 words, 4 words").
    out = re.sub(r"\b(.{3,40}?)(?:\s*[,;]\s*|\s+)\1\b", r"\1", out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip(" ,.;:-")


def build_whisper_prompt(
    terms: list[str],
    *,
    candidate_name: str | None = None,
) -> str | None:
    """Bias Whisper with a fake previous utterance — never instruction text.

    Whisper copies the prompt into the transcript. Phrases like 'Speaker name:'
    therefore appear as spoken words. Keep this as natural English only.
    """
    sentences: list[str] = []
    if candidate_name:
        sentences.append(f"Hello, my name is {candidate_name}.")
    ordered = sorted(
        terms,
        key=lambda t: (0 if ("-" in t or " " in t) else 1, -len(t), t.lower()),
    )
    vocab: list[str] = []
    size = 0
    for term in ordered:
        piece = term if not vocab else f", {term}"
        if size + len(piece) > 420:
            break
        vocab.append(term)
        size += len(piece)
    if vocab:
        sentences.append("I have worked with " + ", ".join(vocab[:18]) + ".")
    prompt = " ".join(sentences).strip()
    return prompt[:_WHISPER_PROMPT_MAX] if prompt else None


def _normalize_cmp(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _short_token_typo_match(a: str, b: str) -> bool:
    """Single-character edits on short tech tokens (AC2 → EC2, MONAIR → MONAI)."""
    na, nb = _normalize_cmp(a), _normalize_cmp(b)
    if not na or not nb:
        return False
    if min(len(na), len(nb)) < 3:
        return False
    if abs(len(na) - len(nb)) > 1:
        return False
    if max(len(na), len(nb)) > 8:
        return False
    if na == nb:
        return True
    if len(na) == len(nb):
        return sum(x != y for x, y in zip(na, nb)) <= 1
    # One insertion/deletion.
    short, long = (na, nb) if len(na) < len(nb) else (nb, na)
    for i in range(len(long)):
        if short == long[:i] + long[i + 1 :]:
            return True
    return False


def _phonetic_similarity(a: str, b: str) -> float:
    if _short_token_typo_match(a, b):
        return 0.92
    na, nb = _normalize_cmp(a), _normalize_cmp(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def _replace_ci(text: str, src: str, dst: str) -> tuple[str, bool]:
    pattern = re.compile(re.escape(src), re.IGNORECASE)
    out, n = pattern.subn(dst, text, count=1)
    return out, n > 0


def _apply_generic_english_fixes(text: str) -> tuple[str, list[dict[str, str]]]:
    out = text
    corrections: list[dict[str, str]] = []
    for pattern, replacement in _GENERIC_ENGLISH_FIXES:
        while True:
            m = re.search(pattern, out, flags=re.IGNORECASE)
            if not m:
                break
            src = m.group(0)
            if src.lower() == replacement.lower():
                break
            out = out[: m.start()] + replacement + out[m.end() :]
            corrections.append({"from": src, "to": replacement, "reason": "generic english"})
    return out, corrections


def _fix_candidate_name(text: str, candidate_name: str) -> tuple[str, list[dict[str, str]]]:
    """Repair near-miss name phrases/tokens using the candidate's actual name."""
    corrections: list[dict[str, str]] = []
    parts = [p for p in candidate_name.split() if p]
    if not parts:
        return text, corrections

    out = text
    n_parts = len(parts)
    # Match roughly the same number of name tokens after an intro cue.
    pattern = re.compile(
        rf"\b(?:myself|i am|my name is|this is(?: a)?)\s+"
        rf"((?:[A-Za-z][A-Za-z'\-]*)(?:\s+[A-Za-z][A-Za-z'\-]*){{0,{max(0, n_parts)}}})",
        flags=re.IGNORECASE,
    )
    m = pattern.search(out)
    if m:
        spoken = m.group(1).strip()
        # Stop before workplace/location glue words if captured.
        spoken = re.split(
            r"\s+(?:from|at|in|working|currently|and)\b",
            spoken,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()
        if (
            spoken
            and spoken.lower() != candidate_name.lower()
            and _phonetic_similarity(spoken, candidate_name) >= 0.55
        ):
            spoken_parts = spoken.split()
            # Keep valid middle names the candidate actually said.
            if len(spoken_parts) > len(parts):
                if (
                    spoken_parts[0].lower() == parts[0].lower()
                    and spoken_parts[-1].lower() == parts[-1].lower()
                ):
                    spoken = ""
            if spoken:
                out, changed = _replace_ci(out, spoken, candidate_name)
                if changed:
                    corrections.append(
                        {
                            "from": spoken,
                            "to": candidate_name,
                            "reason": "candidate name phrase",
                        }
                    )

    tokens = out.split()
    first_l = parts[0].lower()
    surname = parts[-1]
    for i, tok in enumerate(tokens):
        clean = tok.strip(".,;:'\"")
        if len(clean) < 3:
            continue
        near_first = i > 0 and tokens[i - 1].strip(".,;:'\"").lower() == first_l
        near_first = near_first or (
            i > 1 and tokens[i - 2].strip(".,;:'\"").lower() == first_l
        )
        replaced = False
        for part in parts[1:]:
            if clean.lower() == part.lower():
                continue
            sim = _phonetic_similarity(clean, part)
            if sim >= 0.78 or (near_first and sim >= 0.65):
                tokens[i] = tok.replace(clean, part)
                corrections.append(
                    {"from": clean, "to": part, "reason": "candidate name token"}
                )
                replaced = True
                break
        if replaced:
            continue
        if (
            clean.lower() != surname.lower()
            and len(clean) >= 4
            and abs(len(clean) - len(surname)) <= 2
            and _phonetic_similarity(clean, surname) >= 0.82
        ):
            tokens[i] = tok.replace(clean, surname)
            corrections.append(
                {"from": clean, "to": surname, "reason": "candidate surname"}
            )

    return " ".join(tokens), corrections


def _iter_windows(tokens: list[str], n: int) -> list[tuple[int, int, str, str]]:
    """Return (start, end, phrase, trailing_punct) windows."""
    windows: list[tuple[int, int, str, str]] = []
    if n < 1 or n > len(tokens):
        return windows
    for i in range(0, len(tokens) - n + 1):
        raw = " ".join(tokens[i : i + n])
        # Do not cross sentence boundaries.
        if any(t.endswith(".") and idx < n - 1 for idx, t in enumerate(tokens[i : i + n])):
            continue
        trailing = ""
        m = re.search(r"([.,;:]+)$", raw)
        if m:
            trailing = m.group(1)
            raw = raw[: -len(trailing)]
        phrase = raw.strip()
        if not phrase:
            continue
        # Windows must not cross conjunctions / clause breaks.
        core = [t.strip(".,;:'\"") for t in tokens[i : i + n]]
        if any(t.lower() in {"and", "or", "but", "then", "so", "working"} for t in core[1:-1]):
            continue
        if any(t.lower() in {"working", "currently", "graduation"} for t in core):
            # Avoid gluing clause verbs into education/company matches.
            if n >= 3:
                continue
        if core and core[0].lower() in {
            "and",
            "or",
            "but",
            "from",
            "at",
            "in",
            "on",
            "a",
            "an",
            "the",
            "is",
            "are",
            "was",
            "to",
            "of",
        }:
            if n > 1:
                continue
        windows.append((i, i + n, phrase, trailing))
    return windows


def _words(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[A-Za-z0-9]+", text or "")]


def _digits_and_percents(text: str) -> set[str]:
    return set(re.findall(r"\d+\.?\d*%?", text or ""))


def _terms_for_fuzzy_matching(
    resume_terms: list[str],
    *,
    job_position: str | None = None,
) -> list[str]:
    """Resume terms allowed as fuzzy replacement targets (not whisper-only)."""
    blocked: set[str] = set()
    if job_position:
        blocked.add(job_position.strip().lower())
        blocked.update(w.lower() for w in job_position.split() if len(w) >= 4)

    out: list[str] = []
    for term in resume_terms:
        if len(term) > 55 or len(term.split()) > 5:
            continue
        tl = term.lower()
        if tl in blocked:
            continue
        # Skip generic job-title lines that are not brands/projects.
        if (
            tl == (job_position or "").strip().lower()
            or (job_position and tl in job_position.lower() and " " in term)
        ):
            continue
        out.append(term)
    return out


def _is_safe_fuzzy_replacement(src: str, dst: str, *, sim: float) -> bool:
    """Reject replacements that inject resume facts or rewrite unrelated speech."""
    if not src or not dst or src.lower() == dst.lower():
        return False

    src_w = _words(src)
    dst_w = _words(dst)
    if not src_w or not dst_w:
        return False

    # Never inject numbers/percentages the candidate did not say.
    if _digits_and_percents(dst) - _digits_and_percents(src):
        return False

    # Do not expand much beyond what was spoken.
    if len(dst_w) > len(src_w) + 1:
        return False
    if len(src_w) == 1 and len(dst_w) >= 2 and sim < 0.88:
        return False

    direct = _phonetic_similarity(src, dst)
    if len(src_w) == 1 and len(dst_w) == 1 and direct < 0.72:
        return False
    if len(src_w) >= 2 and direct < 0.58 and sim < 0.80:
        return False

    # Every destination word must be grounded in a spoken word (phonetic overlap).
    for dw in dst_w:
        if dw in src_w:
            continue
        if any(_phonetic_similarity(dw, sw) >= 0.72 for sw in src_w):
            continue
        return False

    return True


def _best_replacement_form(phrase: str, term: str, variants: list[str]) -> str | None:
    """Pick the smallest resume form that fixes the spoken span."""
    candidates = [v for v in variants if v]
    if term not in candidates:
        candidates.append(term)
    scored = sorted(
        candidates,
        key=lambda v: (-_phonetic_similarity(phrase, v), len(v.split()), len(v)),
    )
    best = scored[0]
    if _phonetic_similarity(phrase, best) < 0.72:
        return None
    return best


def _match_variants(term: str) -> list[str]:
    """Surface forms used only for comparison (replacement stays `term`)."""
    variants = [term]
    if re.search(r"[a-z][A-Z]", term) and " " not in term:
        variants.append(re.sub(r"(?<=[a-z])(?=[A-Z])", " ", term))
    if "-" in term:
        variants.append(term.replace("-", " "))
    if " " in term:
        for tok in term.split():
            if len(tok) >= 3 and (tok.isupper() or any(ch.isdigit() for ch in tok)):
                variants.append(tok)
    # Unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        key = v.lower()
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out


def _canonical_resume_terms(resume_terms: list[str]) -> list[str]:
    """Prefer compact brand forms (SmartCart, Tater-Check) over spaced aliases."""
    best: dict[str, tuple[float, str]] = {}
    for term in resume_terms:
        if len(term) > 70 or len(term.split()) > 6:
            continue
        # Keep multi-word education names; drop other long prose.
        if len(term.split()) > 4 and not any(
            k in term.lower()
            for k in ("university", "college", "institute", "school", "deemed")
        ):
            continue
        norm = _normalize_cmp(term)
        if not norm:
            continue
        score = 0.0
        if re.search(r"[a-z][A-Z]", term):
            score += 3
        if "-" in term:
            score += 2
        if " " not in term:
            score += 2
        # Prefer short aliases over long title lines with same stem.
        score -= max(0, len(term.split()) - 2) * 0.5
        score += min(len(term), 40) / 100.0
        prev = best.get(norm)
        if prev is None or score > prev[0]:
            best[norm] = (score, term)
    return [t for _, t in sorted(best.values(), key=lambda x: (-x[0], -len(x[1]), x[1].lower()))]


def _fuzzy_fix_against_resume(
    text: str,
    resume_terms: list[str],
    *,
    job_position: str | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """Replace transcript spans that are phonetically close to a resume term."""
    corrections: list[dict[str, str]] = []
    match_terms = _terms_for_fuzzy_matching(resume_terms, job_position=job_position)
    if not match_terms:
        return text, corrections

    tokens = text.split()
    used: set[tuple[int, int]] = set()
    ranked = _canonical_resume_terms(match_terms)

    for term in ranked:
        variants = _match_variants(term)
        best: tuple[float, int, int, str, str, str] | None = None

        for variant in variants:
            variant_token_count = max(1, len(variant.split()))
            window_sizes = {variant_token_count}
            if variant_token_count == 1 and (
                "-" in term or re.search(r"[a-z][A-Z]", term)
            ):
                # CamelCase/hyphen brands are often spoken as two words.
                window_sizes.add(2)
            if variant_token_count >= 2 and len(variant.split()[0]) >= 4:
                window_sizes.add(1)

            for n in sorted(window_sizes):
                for start, end, phrase, trailing in _iter_windows(tokens, n):
                    if any(not (end <= a or start >= b) for a, b in used):
                        continue
                    if phrase.lower() in _STOP_WORDS:
                        continue
                    if len(phrase) <= 2:
                        continue
                    # Exact same text already — nothing to do.
                    if phrase == term:
                        continue
                    # Case/brand normalization still allowed (mediscan → MediScan).
                    if phrase.lower() == term.lower():
                        sim = 0.99
                    elif phrase.lower() in {
                        "pune",
                        "mumbai",
                        "delhi",
                        "india",
                        "karnataka",
                        "bangalore",
                        "chennai",
                        "hyderabad",
                    } and _normalize_cmp(phrase) != _normalize_cmp(variant):
                        continue
                    elif _normalize_cmp(phrase) == _normalize_cmp(variant):
                        sim = 0.99
                    else:
                        sim = max(
                            _phonetic_similarity(phrase, variant),
                            _phonetic_similarity(phrase, term),
                        )

                    if variant_token_count >= 3:
                        min_sim = 0.78
                    elif variant_token_count == 2 or "-" in term or re.search(
                        r"[a-z][A-Z]", term
                    ):
                        min_sim = 0.75
                    else:
                        min_sim = 0.82

                    plen = len(_normalize_cmp(phrase))
                    tlen = len(_normalize_cmp(variant))
                    if tlen and abs(plen - tlen) / tlen > 0.35 and sim < 0.92:
                        continue

                    if sim >= min_sim and (best is None or sim > best[0]):
                        replacement = _best_replacement_form(phrase, term, variants) or term
                        if not _is_safe_fuzzy_replacement(
                            phrase, replacement, sim=sim
                        ):
                            continue
                        best = (sim, start, end, phrase, trailing, replacement)

        if best is None:
            continue
        sim, start, end, phrase, trailing, replacement = best
        if phrase == replacement:
            continue
        used.add((start, end))
        tokens = tokens[:start] + [replacement + trailing] + tokens[end:]
        corrections.append(
            {
                "from": phrase,
                "to": replacement,
                "reason": f"fuzzy resume match ({sim:.2f})",
            }
        )

    return " ".join(tokens), corrections


def _destination_allowed(dst: str, resume_terms: list[str], candidate_name: str | None) -> bool:
    dst_l = dst.lower().strip()
    if not dst_l:
        return False
    if any(dst_l == t.lower() or dst_l in t.lower() or t.lower() in dst_l for t in resume_terms):
        return True
    if candidate_name and dst_l == candidate_name.strip().lower():
        return True
    if candidate_name:
        for part in candidate_name.split():
            if len(part) >= 3 and dst_l == part.lower():
                return True
    return False


def _is_safe_llm_fix(
    src: str,
    dst: str,
    *,
    resume_terms: list[str],
    candidate_name: str | None,
    transcript: str,
) -> bool:
    if not src or not dst or src.lower() == dst.lower():
        return False
    if src.lower() in _STOP_WORDS:
        return False
    if not _destination_allowed(dst, resume_terms, candidate_name):
        return False

    if _digits_and_percents(dst) - _digits_and_percents(src):
        return False
    if len(_words(dst)) > len(_words(src)) + 1:
        return False

    # Never turn a workplace/city mention into the candidate's personal name
    # unless it is clearly an intro ("my name is" / "myself" / "i am <name>").
    if candidate_name and dst.lower() == candidate_name.strip().lower():
        introish = bool(
            re.search(
                rf"\b(?:myself|my name is|this is|i am)\s+{re.escape(src)}\b",
                transcript,
                flags=re.IGNORECASE,
            )
        )
        if not introish and _phonetic_similarity(src, dst) < 0.55:
            return False

    sim = _phonetic_similarity(src, dst)
    # Multi-word / hyphen targets can be a bit looser (project titles).
    min_sim = 0.45 if (" " in src or " " in dst or "-" in dst) else 0.60
    if sim < min_sim:
        logger.info("Rejected LLM STT fix (sim=%.2f): %r → %r", sim, src, dst)
        return False
    return True


def _llm_correct(
    text: str,
    *,
    context: dict[str, str],
    resume_terms: list[str],
    question_text: str | None,
    candidate_name: str | None,
) -> tuple[str, list[dict[str, str]]]:
    if not resume_terms or not llama_available():
        return text, []

    vocab = ", ".join(resume_terms[:50])
    system_prompt = (
        "You correct speech-to-text errors in interview answers.\n"
        "You may ONLY change words that are clear phonetic mishearings of terms from the "
        "allowed vocabulary list for THIS candidate.\n"
        "Rules:\n"
        "1. Prefer ZERO changes when unsure.\n"
        "2. Do not invent employers, cities, degrees, or projects that are not in the vocabulary.\n"
        "3. Do not replace a company/city with the candidate's personal name.\n"
        "4. Keep sentence structure and filler words.\n"
        "5. Fix only spans that sound like a vocabulary term (spelling/pronunciation errors).\n"
        'Return JSON: {"corrections":[{"from":"...","to":"...","reason":"..."}]}'
    )
    user_prompt = f"""Allowed vocabulary (from this candidate's resume/JD):
{vocab}

Candidate name (intro/surname fixes only): {candidate_name or "N/A"}
Job position: {context.get("job_position") or "N/A"}
Skills: {context.get("skills") or "N/A"}
Question: {(question_text or "N/A")[:400]}

Transcript:
{text}
"""
    try:
        data = call_llama_json(
            system_prompt,
            user_prompt,
            temperature=0.0,
            max_tokens=1200,
        )
    except Exception as exc:
        logger.warning("Resume STT LLM correction failed: %s", exc)
        return text, []

    safe: list[dict[str, str]] = []
    for item in data.get("corrections") or []:
        if not isinstance(item, dict):
            continue
        src = str(item.get("from") or "").strip()
        dst = str(item.get("to") or "").strip()
        if not _is_safe_llm_fix(
            src,
            dst,
            resume_terms=resume_terms,
            candidate_name=candidate_name,
            transcript=text,
        ):
            continue
        safe.append(
            {
                "from": src,
                "to": dst,
                "reason": str(item.get("reason") or "resume phonetic fix").strip(),
            }
        )

    out = text
    for item in safe:
        out, changed = _replace_ci(out, item["from"], item["to"])
        if not changed:
            # Soft failure — keep listed but skip apply.
            continue
    return out, safe


def apply_deterministic_corrections(
    text: str,
    *,
    resume_terms: list[str],
    candidate_name: str | None = None,
    job_position: str | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """Generic English + per-candidate fuzzy/name fixes (no hardcoded projects)."""
    corrections: list[dict[str, str]] = []
    original = (text or "").strip()
    out = strip_whisper_artifacts(original)
    if out != original:
        corrections.append(
            {"from": original[:80], "to": out[:80], "reason": "whisper artifact cleanup"}
        )
    out, generic = _apply_generic_english_fixes(out)
    corrections.extend(generic)

    if candidate_name:
        out, name_fixes = _fix_candidate_name(out, candidate_name)
        corrections.extend(name_fixes)

    out, fuzzy = _fuzzy_fix_against_resume(
        out, resume_terms, job_position=job_position
    )
    corrections.extend(fuzzy)

    out = re.sub(r"\s{2,}", " ", out).strip()
    return out, corrections


def correct_transcript_with_resume(
    raw_text: str,
    *,
    context: dict[str, str],
    resume_terms: list[str],
    question_text: str | None = None,
    candidate_name: str | None = None,
) -> dict[str, Any]:
    """Full resume-driven correction pipeline for any candidate."""
    cleaned = (raw_text or "").strip()
    if not cleaned or not resume_correction_enabled():
        return {
            "text": cleaned,
            "raw_text": cleaned,
            "resume_corrected": False,
            "corrections": [],
        }

    text, corrections = apply_deterministic_corrections(
        cleaned,
        resume_terms=resume_terms or [],
        candidate_name=candidate_name,
        job_position=(context or {}).get("job_position"),
    )

    text, llm_fixes = _llm_correct(
        text,
        context=context or {},
        resume_terms=resume_terms or [],
        question_text=question_text,
        candidate_name=candidate_name,
    )
    corrections.extend(llm_fixes)

    changed = text != cleaned
    if changed:
        logger.info(
            "STT resume corrections (%s): %s",
            len(corrections),
            corrections[:5],
        )
    return {
        "text": text,
        "raw_text": cleaned,
        "resume_corrected": changed,
        "corrections": corrections,
    }


def build_stt_context(
    *,
    full_name: str | None,
    evaluation_snapshot: dict[str, Any] | None,
    jd_text: str | None,
    job_position: str | None = None,
    question_text: str | None = None,
) -> dict[str, Any]:
    """Bundle per-candidate vocabulary + context for transcription."""
    terms = extract_resume_terms(
        full_name=full_name,
        evaluation_snapshot=evaluation_snapshot,
        jd_text=jd_text,
        job_position=job_position,
        question_text=question_text,
    )
    context = build_candidate_context(
        jd_text=jd_text,
        evaluation_snapshot=evaluation_snapshot,
        job_position=job_position,
    )
    name = (full_name or "").strip() or None
    return {
        "resume_terms": terms,
        "whisper_prompt": build_whisper_prompt(terms, candidate_name=name),
        "context": context,
        "candidate_name": name,
    }
