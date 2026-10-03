from __future__ import annotations

import gc
import importlib.util
import logging
import re
import threading
from functools import lru_cache
from importlib import metadata
from pathlib import Path
from typing import Any

from agents.screening_agent.config import settings

logger = logging.getLogger(__name__)

# Docling's DocumentConverter keeps native PDF state on the instance.
# Concurrent convert() calls (bulk /extract) can mix page text across files.
_EXTRACT_LOCK = threading.Lock()


class DoclingDependencyError(RuntimeError):
    """Raised when Docling or a configured OCR backend is unavailable."""


class DoclingConversionError(RuntimeError):
    """Raised when Docling cannot convert a supplied document."""


# Docling can emit placeholders such as ``<!-- image -->`` when a resume has
# a profile photo, logo, icon, or other image near the top of the page. Those
# placeholders are document metadata, not candidate text. If left in the
# exported Markdown, a first-line name heuristic can incorrectly use the
# placeholder as the candidate's name.
_HTML_IMAGE_COMMENT_RE = re.compile(
    r"<!--\s*(?:image|img|picture|figure|photo|logo)(?:\s*[:=-]\s*.*?)?\s*-->",
    flags=re.IGNORECASE,
)
_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^\n)]*\)")
_STANDALONE_IMAGE_PLACEHOLDER_RE = re.compile(
    r"(?im)^[ \t]*(?:\[?(?:image|img|picture|figure|photo|logo)\]?|"
    r"<(?:image|img)(?:\s[^>]*)?/?>)[ \t]*$"
)


def _clean_exported_text(value: Any) -> str:
    """Remove non-content image markers while preserving resume text/layout.

    This intentionally removes only image-like placeholders. Other Markdown,
    headings, bullets, tables, and ordinary HTML text remain unchanged.
    """
    text = str(value or "").replace("\u00a0", " ")
    text = _HTML_IMAGE_COMMENT_RE.sub("", text)
    text = _MARKDOWN_IMAGE_RE.sub("", text)
    text = _STANDALONE_IMAGE_PLACEHOLDER_RE.sub("", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _package_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def dependency_status() -> dict[str, Any]:
    """Return lightweight dependency diagnostics without loading ML models."""
    docling_version = _package_version("docling")
    easyocr_version = _package_version("easyocr")
    pdfium_version = _package_version("pypdfium2")
    return {
        "docling": {
            "installed": docling_version is not None,
            "version": docling_version,
        },
        "easyocr": {
            "installed": easyocr_version is not None,
            "version": easyocr_version,
            "required_for_scanned_pdfs": True,
        },
        "pypdfium2": {
            "installed": pdfium_version is not None,
            "version": pdfium_version,
            "used_for_embedded_text_fallback": True,
        },
        "pdf_ocr_mode": settings.PDF_OCR_MODE,
    }


@lru_cache(maxsize=2)
def _get_converter(enable_ocr: bool):
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError as exc:
        logger.exception("Docling import failed")
        raise DoclingDependencyError(
            "Docling is not installed. Run: pip install -r requirements.txt "
            f"(import error: {exc})"
        ) from exc

    if enable_ocr:
        if importlib.util.find_spec("easyocr") is None:
            raise DoclingDependencyError(
                'EasyOCR is not installed. Run: pip install "docling[easyocr]==2.107.0"'
            )
        try:
            from docling.datamodel.pipeline_options import EasyOcrOptions

            ocr_options = EasyOcrOptions(
                lang=["en"],
                use_gpu=False,
                download_enabled=settings.OCR_DOWNLOAD_ENABLED,
                bitmap_area_threshold=0.05,
            )
            pdf_options = PdfPipelineOptions(
                do_ocr=True,
                ocr_options=ocr_options,
                do_table_structure=True,
            )
        except Exception as exc:
            raise DoclingDependencyError(
                "EasyOCR could not be initialized. Reinstall OCR dependencies with "
                'pip install --upgrade --force-reinstall "docling[easyocr]==2.107.0"'
            ) from exc
    else:
        pdf_options = PdfPipelineOptions(
            do_ocr=False,
            do_table_structure=True,
        )

    try:
        return DocumentConverter(
            allowed_formats=[InputFormat.PDF, InputFormat.DOCX],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
            },
        )
    except Exception as exc:
        mode = "with EasyOCR" if enable_ocr else "without OCR"
        raise DoclingDependencyError(
            f"Docling could not initialize {mode}. Check the server terminal for details."
        ) from exc


def _normalize_section_key(heading: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(heading or "").casefold())


def _is_education_heading(heading: str) -> bool:
    key = _normalize_section_key(heading)
    return key.startswith("education") or key in {
        "education",
        "academic",
        "academics",
        "qualification",
        "qualifications",
        "academicbackground",
        "academicqualifications",
    }


def _peeled_education_from_text(text: str) -> str:
    """Take degree/institute/score lines even when they landed under Experience."""
    from agents.screening_agent.services.resume_profile_service import (
        _DEGREE_LINE,
        _EDUCATION_HEADING,
        _clip_education_span,
    )
    from agents.screening_agent.services.section_detector import detect_sections

    if not str(text or "").strip():
        return ""

    sections = detect_sections(text)
    candidates: list[str] = []
    for index, section in enumerate(sections):
        heading = str(section.get("heading") or "")
        body = str(section.get("body") or "")
        if _EDUCATION_HEADING.search(heading):
            clipped = _clip_education_span(body)
            if _DEGREE_LINE.search(clipped):
                return clipped
            for later in sections[index + 1 :]:
                peeled = _clip_education_span(str(later.get("body") or ""))
                if _DEGREE_LINE.search(peeled):
                    return peeled
                peeled = _clip_education_span(
                    f"{later.get('heading') or ''}\n{later.get('body') or ''}"
                )
                if _DEGREE_LINE.search(peeled):
                    return peeled
        candidates.append(_clip_education_span(body))

    for clipped in candidates:
        if _DEGREE_LINE.search(clipped):
            return clipped
    return ""


def _rebuild_text_from_sections(sections: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for section in sections:
        heading = str(section.get("heading") or "").strip()
        body = str(section.get("body") or "").strip()
        if heading and heading.casefold() != "header":
            parts.append(heading)
        if body:
            parts.append(body)
    return "\n\n".join(parts).strip()


def _reconcile_missing_section_bodies(
    primary_text: str,
    secondary_text: str,
) -> tuple[str, list[str]]:
    """
    Fill empty known section bodies in primary text from a secondary extraction.

    Layout engines (e.g. Docling markdown) sometimes drop the first lines of a
    new page when the section heading stayed on the previous page. The embedded
    text layer often still has those lines. This merge is heading-driven and
    content-agnostic — it never hardcodes degree names or employers.
    """
    if not primary_text.strip() or not secondary_text.strip():
        return primary_text, []

    # Local import avoids import cycles at module load.
    from agents.screening_agent.services.section_detector import (
        _is_known_section_heading,
        detect_sections,
    )

    from agents.screening_agent.services.resume_profile_service import _DEGREE_LINE

    primary_sections = detect_sections(primary_text)
    secondary_sections = detect_sections(secondary_text)
    secondary_bodies: dict[str, str] = {}
    for section in secondary_sections:
        heading = str(section.get("heading") or "")
        body = str(section.get("body") or "").strip()
        if not body or not _is_known_section_heading(heading):
            continue
        key = _normalize_section_key(heading)
        # Prefer the longest body if duplicate headings appear.
        if len(body) > len(secondary_bodies.get(key, "")):
            secondary_bodies[key] = body

    peeled_education = _peeled_education_from_text(secondary_text)
    if not secondary_bodies and not peeled_education:
        return primary_text, []

    repaired: list[dict[str, Any]] = []
    recovered: list[str] = []
    changed = False
    for section in primary_sections:
        heading = str(section.get("heading") or "")
        body = str(section.get("body") or "").strip()
        key = _normalize_section_key(heading)
        alt = secondary_bodies.get(key, "")
        # Empty or heading-only stub — recover from secondary extractor.
        if (
            _is_known_section_heading(heading)
            and alt
            and len(alt) > len(body)
            and (not body or body.casefold() == heading.casefold().lstrip("# ").strip())
        ):
            body = alt
            changed = True
            recovered.append(heading.lstrip("# ").strip() or key)
        # Two-column PDFs: Docling often leaves EDUCATION with a job date
        # while the degree is in the embedded text layer under Experience.
        if (
            _is_education_heading(heading)
            and peeled_education
            and not _DEGREE_LINE.search(body)
        ):
            body = peeled_education
            changed = True
            recovered.append(heading.lstrip("# ").strip() or "Education")
        repaired.append({"heading": heading, "body": body})

    if peeled_education and not any(
        _is_education_heading(str(section.get("heading") or "")) for section in repaired
    ):
        repaired.append({"heading": "EDUCATION", "body": peeled_education})
        recovered.append("Education")
        changed = True

    if not changed:
        return primary_text, []
    return _rebuild_text_from_sections(repaired), recovered


def _enrich_pdf_payload_with_text_layer(payload: dict[str, Any], file_path: str) -> dict[str, Any]:
    """Recover page-break section bodies Docling may drop, using the PDF text layer."""
    try:
        fallback = _extract_pdf_text_fallback(file_path)
    except Exception:
        logger.debug("PDF text-layer enrichment unavailable", exc_info=True)
        return payload

    primary = str(payload.get("full_text") or "")
    secondary = str(fallback.get("full_text") or "")
    merged, recovered = _reconcile_missing_section_bodies(primary, secondary)
    if not recovered:
        return payload

    enriched = dict(payload)
    enriched["full_text"] = merged
    # Prefer text-layer pages when available — they preserve cross-page bodies.
    if fallback.get("pages"):
        enriched["pages"] = fallback["pages"]
    warning = str(enriched.get("extraction_warning") or "").strip()
    note = (
        "Recovered section body text across page breaks from the PDF text layer "
        f"for: {', '.join(recovered)}."
    )
    enriched["extraction_warning"] = f"{warning} {note}".strip() if warning else note
    logger.info(
        "Recovered %s empty section(s) across page breaks via PDF text layer: %s",
        len(recovered),
        ", ".join(recovered),
    )
    return enriched


def _payload_from_result(result: Any) -> dict[str, Any]:
    doc = result.document
    full_text = _clean_exported_text(doc.export_to_markdown())
    if not full_text:
        raise DoclingConversionError("Docling returned empty text from the file.")

    pages: list[dict[str, Any]] = []
    try:
        page_texts: dict[int, list[str]] = {}
        for item, _level in doc.iterate_items():
            provenance = getattr(item, "prov", None)
            if not provenance:
                continue
            for entry in provenance:
                page_no = int(getattr(entry, "page_no", 1))
                item_text = _clean_exported_text(getattr(item, "text", ""))
                if item_text:
                    page_texts.setdefault(page_no, []).append(item_text)
        pages = [
            {"page": page_no, "text": "\n".join(page_texts[page_no])}
            for page_no in sorted(page_texts)
        ]
    except Exception:
        logger.warning(
            "Could not build page-level provenance; returning one logical page."
        )

    if not pages:
        pages = [{"page": 1, "text": full_text}]
    return {"pages": pages, "full_text": full_text}


def _extract_pdf_text_fallback(file_path: str) -> dict[str, Any]:
    """Extract an embedded PDF text layer without Docling ML model assets."""
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise DoclingDependencyError(
            "pypdfium2 is unavailable. Reinstall dependencies with: "
            "pip install -r requirement.txt"
        ) from exc

    pages: list[dict[str, Any]] = []
    document = None
    try:
        document = pdfium.PdfDocument(file_path)
        for page_index in range(len(document)):
            page = document[page_index]
            text_page = None
            try:
                text_page = page.get_textpage()
                page_text = _clean_exported_text(text_page.get_text_range())
                pages.append({"page": page_index + 1, "text": page_text})
            finally:
                if text_page is not None:
                    text_page.close()
                page.close()
    except Exception as exc:
        raise DoclingConversionError(
            "The PDF text layer could not be read by the fallback extractor."
        ) from exc
    finally:
        if document is not None:
            document.close()

    full_text = "\n\f\n".join(
        str(page["text"]).strip() for page in pages if str(page["text"]).strip()
    ).strip()
    if not full_text:
        raise DoclingConversionError(
            "The PDF does not contain a readable embedded text layer."
        )

    return {
        "pages": pages or [{"page": 1, "text": full_text}],
        "full_text": full_text,
        "extraction_warning": (
            "Docling layout processing was unavailable, so the embedded PDF "
            "text layer was extracted with the pypdfium2 fallback."
        ),
    }


def _has_meaningful_text(text: str) -> bool:
    """Reject tiny/empty text layers so scanned PDFs can fall back to OCR."""
    normalized = re.sub(r"\s+", " ", text).strip()
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9@.+#/-]*", normalized)
    alphanumeric_count = sum(char.isalnum() for char in normalized)
    return len(words) >= 8 and alphanumeric_count >= 40


def _run_conversion(file_path: str, *, enable_ocr: bool) -> dict[str, Any]:
    converter = _get_converter(enable_ocr)
    result = converter.convert(file_path)
    return _payload_from_result(result)


def _extract_docx_text_fallback(file_path: str) -> dict[str, Any]:
    """Extract DOCX text with python-docx when Docling's native stack is unavailable.

    Docling imports ``docling_parse.pdf_parsers`` at package load time even for
    DOCX. On some Windows setups that native DLL fails, so uploads would 503
    without a pure-Python fallback.
    """
    try:
        from docx import Document
    except ImportError as exc:
        raise DoclingDependencyError(
            "python-docx is not installed. Run: pip install python-docx"
        ) from exc

    try:
        document = Document(file_path)
    except Exception as exc:
        raise DoclingConversionError(
            "The DOCX file could not be read by the fallback extractor."
        ) from exc

    blocks: list[str] = []
    for paragraph in document.paragraphs:
        text = " ".join(str(paragraph.text or "").split()).strip()
        if text:
            blocks.append(text)

    for table in document.tables:
        for row in table.rows:
            cells = [
                " ".join(str(cell.text or "").split()).strip()
                for cell in row.cells
            ]
            cells = [cell for cell in cells if cell]
            if cells:
                blocks.append(" | ".join(cells))

    full_text = _clean_exported_text("\n".join(blocks))
    if not full_text:
        raise DoclingConversionError(
            "The DOCX file does not contain readable text."
        )

    return {
        "pages": [{"page": 1, "text": full_text}],
        "full_text": full_text,
        "extraction_warning": (
            "Docling was unavailable, so DOCX text was extracted with the "
            "python-docx fallback. Complex layout may be limited."
        ),
    }


def _clear_converter_cache() -> None:
    clear = getattr(_get_converter, "cache_clear", None)
    if callable(clear):
        clear()
    gc.collect()


def _convert_docx(file_path: str) -> dict[str, Any]:
    try:
        return _run_conversion(file_path, enable_ocr=False)
    except DoclingDependencyError as dep_exc:
        logger.warning(
            "Docling unavailable for DOCX (%s); trying python-docx fallback",
            dep_exc,
        )
        try:
            payload = _extract_docx_text_fallback(file_path)
            _clear_converter_cache()
            logger.info("DOCX conversion succeeded using the python-docx fallback")
            return payload
        except (DoclingConversionError, DoclingDependencyError):
            raise
        except Exception as fallback_exc:
            logger.exception("python-docx DOCX fallback failed")
            raise DoclingConversionError(
                "Docling and the DOCX fallback both failed. Confirm the file "
                "opens correctly in Word."
            ) from fallback_exc
    except Exception as exc:
        logger.exception("Docling DOCX conversion failed")
        try:
            payload = _extract_docx_text_fallback(file_path)
            _clear_converter_cache()
            logger.info(
                "DOCX conversion succeeded using the python-docx fallback "
                "after Docling conversion error"
            )
            return payload
        except Exception:
            logger.debug("python-docx fallback also failed", exc_info=True)
        raise DoclingConversionError(
            "Docling could not convert the DOCX file. Confirm that it opens correctly in Word."
        ) from exc


def _convert_pdf(file_path: str) -> dict[str, Any]:
    mode = settings.PDF_OCR_MODE
    errors: list[Exception] = []

    # ``never`` explicitly requests an embedded-text-only path. Reading the
    # text layer directly avoids initializing Docling layout models (which may
    # need separately downloaded assets) and prevents unnecessary network/model
    # startup for a mode that is not allowed to use OCR anyway.
    if mode == "never":
        try:
            payload = _extract_pdf_text_fallback(file_path)
            if _has_meaningful_text(str(payload.get("full_text", ""))):
                payload["extraction_warning"] = (
                    "PDF_OCR_MODE=never extracted the embedded PDF text layer "
                    "without OCR. Complex visual reading order may be limited."
                )
                logger.info("PDF conversion succeeded using embedded text only")
                return payload
        except (DoclingConversionError, DoclingDependencyError) as exc:
            errors.append(exc)
            logger.debug("Embedded PDF text extraction failed", exc_info=True)

        raise DoclingConversionError(
            "The PDF has no readable text layer and OCR is disabled. Set "
            "PDF_OCR_MODE=auto or PDF_OCR_MODE=always and restart the server."
        ) from (errors[-1] if errors else None)

    # In auto mode, try Docling without OCR first. This preserves layout when
    # model assets are available; a digital-text fallback keeps the endpoint
    # functional when those assets are unavailable.
    if mode == "auto":
        try:
            payload = _run_conversion(file_path, enable_ocr=False)
            if _has_meaningful_text(str(payload.get("full_text", ""))):
                payload = _enrich_pdf_payload_with_text_layer(payload, file_path)
                logger.info("PDF conversion succeeded using the embedded text layer")
                return payload
            logger.info(
                "PDF text layer was insufficient; OCR fallback will be attempted"
            )
        except DoclingDependencyError as dep_exc:
            # Native Windows DLL failures (docling_parse.pdf_parsers) should not
            # hard-fail digital PDFs when pypdfium2 can still read the text layer.
            logger.warning(
                "Docling unavailable (%s); trying embedded-text fallback",
                dep_exc,
            )
            try:
                fallback = _extract_pdf_text_fallback(file_path)
                if _has_meaningful_text(str(fallback.get("full_text", ""))):
                    _get_converter.cache_clear()
                    gc.collect()
                    logger.info(
                        "PDF conversion succeeded using the embedded-text fallback "
                        "(Docling native import failed)"
                    )
                    return fallback
            except (DoclingConversionError, DoclingDependencyError) as fallback_exc:
                errors.append(fallback_exc)
                logger.warning(
                    "Embedded PDF text fallback failed after Docling dependency error (%s)",
                    type(fallback_exc).__name__,
                )
            errors.append(dep_exc)
        except Exception as exc:
            logger.warning(
                "Docling PDF conversion without OCR failed (%s); trying the "
                "embedded-text fallback",
                type(exc).__name__,
            )
            logger.debug("Docling PDF conversion failure details", exc_info=True)
            try:
                fallback = _extract_pdf_text_fallback(file_path)
                if _has_meaningful_text(str(fallback.get("full_text", ""))):
                    # A failed Docling PDF initialization can retain native PDF
                    # handles in exception cycles. Drop the cached converter and
                    # collect them before returning the successful fallback.
                    _get_converter.cache_clear()
                    del exc
                    gc.collect()
                    logger.info(
                        "PDF conversion succeeded using the embedded-text fallback"
                    )
                    return fallback
            except (DoclingConversionError, DoclingDependencyError) as fallback_exc:
                errors.append(fallback_exc)
                logger.warning(
                    "Embedded PDF text fallback failed (%s)",
                    type(fallback_exc).__name__,
                )
                logger.debug("Embedded PDF fallback failure details", exc_info=True)

    try:
        payload = _run_conversion(file_path, enable_ocr=True)
        payload = _enrich_pdf_payload_with_text_layer(payload, file_path)
        ocr_note = (
            "OCR was used because the PDF did not contain enough readable embedded text."
        )
        existing = str(payload.get("extraction_warning") or "").strip()
        payload["extraction_warning"] = (
            f"{existing} {ocr_note}".strip() if existing else ocr_note
        )
        logger.info("PDF conversion succeeded with EasyOCR")
        return payload
    except DoclingDependencyError:
        raise
    except Exception as exc:
        errors.append(exc)
        logger.exception("Docling PDF conversion with OCR failed")

    raise DoclingConversionError(
        "Docling could not convert the uploaded PDF. Confirm that the PDF opens "
        "normally and that OCR support is installed."
    ) from errors[-1]


def _convert(file_path: str) -> dict[str, Any]:
    extension = Path(file_path).suffix.lower()
    if extension == ".docx":
        return _convert_docx(file_path)
    if extension == ".pdf":
        return _convert_pdf(file_path)
    raise DoclingConversionError(
        f"Unsupported document extension: {extension or 'unknown'}"
    )


def extract_text_from_pdf(file_path: str) -> dict[str, Any]:
    logger.info("Docling PDF extraction started (OCR mode: %s)", settings.PDF_OCR_MODE)
    with _EXTRACT_LOCK:
        return _convert(file_path)


def extract_text_from_docx(file_path: str) -> dict[str, Any]:
    logger.info("Docling DOCX extraction started")
    with _EXTRACT_LOCK:
        return _convert(file_path)
