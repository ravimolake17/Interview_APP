from __future__ import annotations

import os
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

from fastapi import HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from agents.screening_agent.config import settings
from agents.screening_agent.services.docling_extractor import extract_text_from_docx, extract_text_from_pdf

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}
_CHUNK_SIZE = 1024 * 1024
_MAX_DOCX_MEMBERS = 2_000
UPLOADS_ROOT = Path(__file__).resolve().parent.parent / "uploads"


def get_uploads_root() -> Path:
    UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
    return UPLOADS_ROOT


def _get_extension(filename: str) -> str:
    return Path(filename).suffix.casefold()


def _validate_signature(extension: str, file_path: str, first_bytes: bytes) -> None:
    if extension == ".pdf":
        if first_bytes.startswith(b"%PDF-"):
            return
        with open(file_path, "rb") as handle:
            header = handle.read(1024)
        if b"%PDF-" not in header:
            raise HTTPException(
                status_code=400,
                detail=(
                    "The uploaded file is not a valid PDF. "
                    "It may be renamed, corrupted, or exported incorrectly — try re-saving as PDF or upload DOCX."
                ),
            )
        return
    if extension == ".docx" and not first_bytes.startswith(b"PK"):
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid DOCX file.")


def _validate_docx_container(file_path: str, max_uncompressed_bytes: int) -> None:
    try:
        with zipfile.ZipFile(file_path) as archive:
            members = archive.infolist()
            names = {member.filename for member in members}
            required = {"[Content_Types].xml", "word/document.xml"}
            if not required.issubset(names):
                raise HTTPException(status_code=400, detail="The uploaded file is not a valid DOCX document.")
            if len(members) > _MAX_DOCX_MEMBERS:
                raise HTTPException(status_code=400, detail="The DOCX archive contains too many internal files.")
            if any(member.flag_bits & 0x1 for member in members):
                raise HTTPException(status_code=400, detail="Encrypted DOCX archives are not supported.")
            total_uncompressed = sum(member.file_size for member in members)
            if total_uncompressed > max_uncompressed_bytes:
                raise HTTPException(
                    status_code=413,
                    detail="The expanded DOCX document is too large to process safely.",
                )
            bad_member = archive.testzip()
            if bad_member is not None:
                raise HTTPException(status_code=400, detail="The DOCX archive is corrupted.")
    except HTTPException:
        raise
    except (zipfile.BadZipFile, OSError) as exc:
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid DOCX document.") from exc


async def _persist_upload(file: UploadFile, category: str) -> tuple[str, dict]:
    """Validate the upload and copy it to disk. Returns (temp_path, stored meta)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename.")

    extension = _get_extension(file.filename)
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type. Supported formats: .docx, .pdf.")

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    temp_path: str | None = None
    size = 0
    first_bytes = b""

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
            temp_path = temp_file.name
            while chunk := await file.read(_CHUNK_SIZE):
                if not first_bytes:
                    first_bytes = chunk[:8]
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB upload limit.",
                    )
                temp_file.write(chunk)

        if size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        _validate_signature(extension, temp_path, first_bytes)
        if extension == ".docx":
            await run_in_threadpool(
                _validate_docx_container,
                temp_path,
                settings.MAX_DOCX_UNCOMPRESSED_MB * 1024 * 1024,
            )

        safe_name = Path(file.filename).name
        stored_name = f"{uuid.uuid4().hex}{extension}"
        target_dir = get_uploads_root() / category
        target_dir.mkdir(parents=True, exist_ok=True)
        stored_path = target_dir / stored_name
        shutil.copy2(temp_path, stored_path)

        return temp_path, {
            "original_filename": safe_name,
            "stored_name": stored_name,
            "stored_relative_path": f"{category}/{stored_name}",
            "stored_url": f"/screening-files/{category}/{stored_name}",
            "extension": extension,
        }
    except Exception:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise
    finally:
        try:
            await file.close()
        except Exception:
            pass


def _cleanup_temp(temp_path: str | None) -> None:
    if temp_path and os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except OSError:
            pass


async def store_uploaded_document(file: UploadFile, category: str) -> dict:
    """Save a resume/JD to disk without extracting text (extract queue)."""
    temp_path, stored = await _persist_upload(file, category)
    _cleanup_temp(temp_path)
    return stored


async def ingest_document(file: UploadFile, category: str) -> dict:
    temp_path, stored = await _persist_upload(file, category)
    try:
        extension = stored["extension"]
        extractor = extract_text_from_pdf if extension == ".pdf" else extract_text_from_docx
        extracted = await run_in_threadpool(extractor, temp_path)
        text = str(extracted.get("full_text", "")).strip()
        if not text:
            raise HTTPException(status_code=422, detail="No readable text found in the file.")

        return {
            **stored,
            "pages": len(extracted.get("pages", [])),
            "text": text,
            "extraction_warning": extracted.get("extraction_warning"),
        }
    finally:
        _cleanup_temp(temp_path)
