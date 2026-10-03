from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import FraudEvent, InterviewSession


def _within_storage(path: Path, storage: Path) -> bool:
    try:
        path.resolve().relative_to(storage.resolve())
        return True
    except (ValueError, OSError):
        return False


def best_effort_delete(path: Path, storage: Path, overwrite: bool = False) -> None:
    if not _within_storage(path, storage) or not path.exists() or not path.is_file():
        return
    if overwrite:
        # Best effort only: SSD wear-leveling and filesystem snapshots can defeat overwrite guarantees.
        try:
            size = path.stat().st_size
            with path.open("r+b", buffering=0) as handle:
                remaining = size
                block = b"\0" * min(1024 * 1024, max(size, 1))
                while remaining > 0:
                    chunk = block[: min(len(block), remaining)]
                    handle.write(chunk)
                    remaining -= len(chunk)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            pass
    path.unlink(missing_ok=True)


def session_file_paths(session: InterviewSession) -> list[Path]:
    paths: list[Path] = []
    for recording in session.recordings:
        paths.append(Path(recording.path))
    for chunk in session.chunks:
        paths.append(Path(chunk.path))
    for event in session.events:
        for evidence in event.evidence:
            paths.append(Path(evidence.path))
    for report in session.reports:
        if report.html_path:
            paths.append(Path(report.html_path))
        if report.pdf_path:
            paths.append(Path(report.pdf_path))
        if report.html_path:
            paths.append(Path(report.html_path).with_suffix(".json"))
    return paths


def delete_session_data(db: Session, session_id: str, storage: Path, overwrite: bool = False) -> bool:
    session = db.scalar(
        select(InterviewSession)
        .where(InterviewSession.id == session_id)
        .options(
            selectinload(InterviewSession.recordings),
            selectinload(InterviewSession.chunks),
            selectinload(InterviewSession.reports),
            selectinload(InterviewSession.events).selectinload(FraudEvent.evidence),
        )
    )
    if session is None:
        return False
    paths = session_file_paths(session)
    candidate = session.candidate
    db.delete(session)
    db.flush()
    # Remove a now-orphaned candidate record.
    remaining = db.scalar(select(InterviewSession.id).where(InterviewSession.candidate_id == candidate.id).limit(1))
    if remaining is None:
        db.delete(candidate)
    db.commit()
    for path in paths:
        best_effort_delete(path, storage, overwrite=overwrite)
    return True


def purge_expired(db: Session, storage: Path, retention_days: int, overwrite: bool = False) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    ids = db.scalars(
        select(InterviewSession.id).where(InterviewSession.ended_at.is_not(None), InterviewSession.ended_at < cutoff)
    ).all()
    deleted: list[str] = []
    for session_id in ids:
        if delete_session_data(db, session_id, storage, overwrite=overwrite):
            deleted.append(session_id)
    return deleted
