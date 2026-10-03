from __future__ import annotations

import mimetypes
from pathlib import Path

import jwt
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select

from ..config import get_settings
from ..db import session_scope
from ..models import Evidence, Recording, Report
from ..security import decode_token
from ..services.recordings import iter_file_range
from .common import safe_file

router = APIRouter(prefix="/api/media", tags=["media"])


def _authorize(db, authorization: str | None, token: str | None) -> dict:
    value = token
    if authorization and authorization.lower().startswith("bearer "):
        value = authorization.split(" ", 1)[1]
    if not value:
        raise HTTPException(status_code=401, detail="HR access token required")
    from core.config import get_settings as main_settings
    from core.security import decode_access_token

    try:
        payload = decode_access_token(value, main_settings())
    except Exception:
        try:
            payload = decode_token(value, "media")
        except jwt.PyJWTError:
            try:
                payload = decode_token(value, "admin")
            except jwt.PyJWTError as exc:
                raise HTTPException(status_code=401, detail="invalid media token") from exc
        role = str(payload.get("role", "")).upper()
        if role not in {"HR", "ADMIN", "SUPERADMIN"}:
            raise HTTPException(status_code=403, detail="HR or admin access required")
        return payload

    role = str(payload.get("role", "")).upper()
    if role not in {"HR", "ADMIN", "SUPERADMIN"}:
        raise HTTPException(status_code=403, detail="HR or admin access required")
    return payload


def _serve_range(path: Path, request: Request, mime_type: str) -> Response:
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="media file is missing")
    size = path.stat().st_size
    range_header = request.headers.get("range")
    headers = {"Accept-Ranges": "bytes", "Content-Disposition": f'inline; filename="{path.name}"'}
    if not range_header:
        headers["Content-Length"] = str(size)
        return StreamingResponse(iter_file_range(path, 0, max(size - 1, 0)), media_type=mime_type, headers=headers)
    try:
        unit, spec = range_header.split("=", 1)
        if unit != "bytes":
            raise ValueError
        start_text, end_text = spec.split("-", 1)
        if start_text:
            start = int(start_text)
            end = int(end_text) if end_text else size - 1
        else:
            suffix = int(end_text)
            start = max(0, size - suffix)
            end = size - 1
        if start < 0 or end < start or start >= size:
            raise ValueError
        end = min(end, size - 1)
    except ValueError as exc:
        raise HTTPException(status_code=416, detail="invalid byte range", headers={"Content-Range": f"bytes */{size}"}) from exc
    headers.update({"Content-Range": f"bytes {start}-{end}/{size}", "Content-Length": str(end - start + 1)})
    return StreamingResponse(iter_file_range(path, start, end), status_code=206, media_type=mime_type, headers=headers)


@router.get("/recording/{recording_id}")
def recording_media(recording_id: str, request: Request, token: str | None = Query(None), authorization: str | None = Header(None)):
    with session_scope() as db:
        _authorize(db, authorization, token)
        record = db.get(Recording, recording_id)
        if record is None:
            raise HTTPException(status_code=404, detail="recording not found")
        return _serve_range(safe_file(record.path), request, record.mime_type)


@router.get("/evidence/{evidence_id}")
def evidence_media(evidence_id: str, request: Request, token: str | None = Query(None), authorization: str | None = Header(None)):
    with session_scope() as db:
        _authorize(db, authorization, token)
        record = db.get(Evidence, evidence_id)
        if record is None:
            raise HTTPException(status_code=404, detail="evidence not found")
        return _serve_range(safe_file(record.path), request, record.mime_type)


@router.get("/report/{report_id}/{kind}")
def report_media(report_id: str, kind: str, token: str | None = Query(None), authorization: str | None = Header(None)):
    if kind not in {"json", "html", "pdf"}:
        raise HTTPException(status_code=422, detail="kind must be json, html or pdf")
    with session_scope() as db:
        _authorize(db, authorization, token)
        report = db.get(Report, report_id)
        if report is None:
            raise HTTPException(status_code=404, detail="report not found")
        path_text = report.json_path if kind == "json" else report.html_path if kind == "html" else report.pdf_path
        if not path_text:
            raise HTTPException(status_code=404, detail="report file is missing")
        path = safe_file(path_text)
        media_type = "application/json" if kind == "json" else "text/html" if kind == "html" else "application/pdf"
        return FileResponse(path, media_type=media_type, filename=path.name)
