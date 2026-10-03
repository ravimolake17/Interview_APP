from __future__ import annotations

import hashlib
import html
import json
from datetime import timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..models import (
    AttentionBaseline,
    AuditLog,
    DetectorMetric,
    DeviceCheck,
    FraudEvent,
    InterviewSession,
    RecordingChunk,
    Report,
    ReviewDecision,
    SystemError,
    VerificationAttempt,
    VoiceSentenceAttempt,
)
from .recordings import sha256_file
from .risk import calculate_score


FINAL_SESSION_STATES = {"completed", "terminated"}
VISUAL_EVENT_TYPES = {"face_mismatch", "no_face", "multiple_faces", "face_spoof_concern", "gaze_violation", "head_pose_violation", "attention_look_away", "camera_interruption"}
VOICE_EVENT_TYPES = {"voice_mismatch", "possible_additional_speaker", "background_conversation", "overlapping_speech", "microphone_interruption"}
TAB_EVENT_TYPES = {"first_tab_switch", "tab_switch", "repeated_tab_switch"}


def _iso(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()


def _path_integrity(path_text: str | None, expected_checksum: str | None) -> dict[str, Any]:
    if not path_text:
        return {"exists": False, "checksum_matches": False, "failure_reason": "path is not stored"}
    path = Path(path_text)
    if not path.exists() or not path.is_file():
        return {"exists": False, "checksum_matches": False, "failure_reason": f"file is missing: {path}"}
    size = path.stat().st_size
    if size <= 0:
        return {"exists": True, "size_bytes": size, "checksum_matches": False, "failure_reason": "file is empty"}
    actual = sha256_file(path)
    matches = bool(expected_checksum and actual.lower() == expected_checksum.lower())
    return {
        "exists": True,
        "size_bytes": size,
        "actual_sha256": actual,
        "expected_sha256": expected_checksum,
        "checksum_matches": matches,
        "failure_reason": None if matches else "stored checksum is missing or does not match the file",
    }


def _required_evidence(event_type: str) -> set[str]:
    if event_type in TAB_EVENT_TYPES:
        return {"metadata", "video"}
    if event_type in VOICE_EVENT_TYPES:
        return {"audio", "video"}
    if event_type in VISUAL_EVENT_TYPES:
        return {"screenshot", "video"}
    return set()


def _assert_final_report_ready(db: Session, session: InterviewSession) -> None:
    if session.status not in FINAL_SESSION_STATES or session.ended_at is None:
        raise ValueError("final report requires a completed or terminated session with an end timestamp")
    # Reports are intentionally allowed when recording/evidence is incomplete.
    # Missing artifacts are labelled in report_readiness and technical_issues;
    # the API never returns fake success or claims missing evidence exists.


def build_report_data(db: Session, session_id: str) -> dict[str, Any]:
    session = db.scalar(
        select(InterviewSession)
        .where(InterviewSession.id == session_id)
        .options(
            selectinload(InterviewSession.candidate),
            selectinload(InterviewSession.events).selectinload(FraudEvent.evidence),
            selectinload(InterviewSession.recordings),
        )
    )
    if session is None:
        raise ValueError("session not found")
    events = sorted(session.events, key=lambda e: (e.relative_ms, e.server_timestamp))
    score, classification, explanation = calculate_score(events)
    review_adjusted_events = [event for event in events if event.review_status != "dismissed"]
    adjusted_score, adjusted_classification, adjusted_explanation = calculate_score(review_adjusted_events)
    device = db.scalar(select(DeviceCheck).where(DeviceCheck.session_id == session_id).order_by(DeviceCheck.created_at.desc()))
    attention_baseline = db.scalar(select(AttentionBaseline).where(AttentionBaseline.session_id == session_id))
    attempts = db.scalars(select(VerificationAttempt).where(VerificationAttempt.session_id == session_id).order_by(VerificationAttempt.created_at)).all()
    sentence_attempts = db.scalars(select(VoiceSentenceAttempt).where(VoiceSentenceAttempt.session_id == session_id).order_by(VoiceSentenceAttempt.created_at)).all()
    detector_metrics = db.scalars(select(DetectorMetric).where(DetectorMetric.session_id == session_id).order_by(DetectorMetric.created_at)).all()
    reviews = db.scalars(select(ReviewDecision).where(ReviewDecision.session_id == session_id).order_by(ReviewDecision.created_at)).all()
    errors = db.scalars(select(SystemError).where(SystemError.session_id == session_id).order_by(SystemError.created_at)).all()
    audit_rows = db.scalars(select(AuditLog).where(AuditLog.target_id == session_id).order_by(AuditLog.created_at)).all()

    duration = None
    if session.started_at and session.ended_at:
        started = session.started_at if session.started_at.tzinfo else session.started_at.replace(tzinfo=timezone.utc)
        ended = session.ended_at if session.ended_at.tzinfo else session.ended_at.replace(tzinfo=timezone.utc)
        duration = max(0.0, (ended - started).total_seconds())

    summaries: dict[str, dict[str, Any]] = {}
    evidence_manifest: list[dict[str, Any]] = []
    technical_issues: list[dict[str, Any]] = [
        {"component": item.component, "message": item.message, "details": item.details, "resolved": item.resolved, "created_at": _iso(item.created_at)}
        for item in errors
    ]
    model_inventory: dict[str, dict[str, Any]] = {}
    timeline: list[dict[str, Any]] = []

    for event in events:
        item = summaries.setdefault(event.event_type, {"count": 0, "total_duration_ms": 0, "risk_total": 0.0})
        item["count"] += 1
        item["total_duration_ms"] += event.duration_ms
        item["risk_total"] = round(item["risk_total"] + event.risk_contribution, 3)
        measurements = dict(event.measurements or {})
        engine = measurements.get("engine") or measurements.get("model_engine")
        model_version = measurements.get("model_version")
        if engine:
            model_inventory[str(engine)] = {"engine": str(engine), "model_version": model_version}
        evidence_rows = []
        present_kinds: set[str] = set()
        for evidence in event.evidence:
            integrity = _path_integrity(evidence.path, evidence.checksum)
            present_kinds.add(evidence.kind)
            entry = {
                "id": evidence.id,
                "event_id": event.id,
                "event_type": event.event_type,
                "kind": evidence.kind,
                "mime_type": evidence.mime_type,
                "size_bytes": evidence.size_bytes,
                "duration_seconds": evidence.duration_seconds,
                "creation_status": evidence.creation_status,
                "checksum": evidence.checksum,
                "integrity": integrity,
                "url": f"/api/media/evidence/{evidence.id}",
            }
            evidence_rows.append(entry)
            evidence_manifest.append(entry)
            if evidence.creation_status != "ready" or not integrity.get("checksum_matches"):
                technical_issues.append({"component": "evidence_integrity", "message": f"Evidence {evidence.id} is not integrity-valid", "details": entry, "resolved": False})
        missing = sorted(_required_evidence(event.event_type) - present_kinds)
        if missing:
            technical_issues.append({
                "component": "evidence_generation",
                "message": f"Event {event.id} is missing required evidence: {', '.join(missing)}",
                "details": {"event_id": event.id, "event_type": event.event_type, "missing_kinds": missing},
                "resolved": False,
            })
        timeline.append({
            "id": event.id,
            "type": event.event_type,
            "state": event.state,
            "client_timestamp": _iso(event.client_timestamp),
            "server_timestamp": _iso(event.server_timestamp),
            "relative_ms": event.relative_ms,
            "start_ms": event.start_ms,
            "end_ms": event.end_ms,
            "duration_ms": event.duration_ms,
            "confidence": event.confidence,
            "measurements": measurements,
            "risk_contribution": event.risk_contribution,
            "explanation": event.explanation,
            "review_status": event.review_status,
            "evidence": evidence_rows,
            "evidence_complete": not missing and all(row["creation_status"] == "ready" and row["integrity"].get("checksum_matches") for row in evidence_rows),
            "missing_evidence": missing,
        })

    chunk_count = db.scalar(select(func.count()).select_from(RecordingChunk).where(RecordingChunk.session_id == session.id)) or 0
    valid_full_recordings = [
        item for item in session.recordings
        if item.kind == "full_interview" and item.validation_status == "valid" and Path(item.path).is_file() and Path(item.path).stat().st_size > 0
    ]
    recording_complete = bool(valid_full_recordings)
    if chunk_count and not session.recording_upload_complete:
        technical_issues.append({
            "component": "recording_upload",
            "message": "The final report was generated while the recording upload queue was incomplete.",
            "details": {"chunk_count": chunk_count, "recording_expected_chunks": session.recording_expected_chunks},
            "resolved": False,
        })
    if not recording_complete:
        technical_issues.append({
            "component": "recording_availability",
            "message": "A validated full interview recording is unavailable; conclusions must rely on the remaining persisted signals and human review.",
            "details": {"recording_count": len(session.recordings), "chunk_count": chunk_count},
            "resolved": False,
        })
    evidence_total = sum(len(event.evidence) for event in events)
    confirmed_events = len(events)
    evidence_coverage = 1.0 if confirmed_events == 0 else min(1.0, evidence_total / max(1, confirmed_events))
    confidence_components = [
        1.0 if session.initial_face_verified else 0.0,
        1.0 if session.initial_voice_verified else 0.0,
        1.0 if recording_complete else 0.0,
        evidence_coverage,
        1.0 if not errors else max(0.0, 1.0 - min(len(errors), 5) * 0.15),
    ]
    evaluation_confidence = round(sum(confidence_components) / len(confidence_components), 3)

    recordings = []
    for rec in session.recordings:
        integrity = _path_integrity(rec.path, rec.checksum)
        row = {
            "id": rec.id,
            "kind": rec.kind,
            "size_bytes": rec.size_bytes,
            "duration_seconds": rec.duration_seconds,
            "video_codec": rec.video_codec,
            "audio_codec": rec.audio_codec,
            "validation_status": rec.validation_status,
            "validation_details": rec.validation_details,
            "checksum": rec.checksum,
            "integrity": integrity,
            "url": f"/api/media/recording/{rec.id}",
        }
        recordings.append(row)
        if rec.validation_status != "valid" or not integrity.get("checksum_matches"):
            technical_issues.append({"component": "recording_integrity", "message": f"Recording {rec.id} did not pass final integrity validation", "details": row, "resolved": False})

    return {
        "report_version": 2,
        "generated_by": "Agent5",
        "human_review_required": True,
        "candidate": {"id": session.candidate.id, "full_name": session.candidate.full_name, "email": session.candidate.email},
        "session": {
            "id": session.id,
            "status": session.status,
            "started_at": _iso(session.started_at),
            "ended_at": _iso(session.ended_at),
            "duration_seconds": duration,
            "termination_reason": session.termination_reason,
            "tab_switch_count": session.tab_switch_count,
            "recording_expected_chunks": session.recording_expected_chunks,
            "recording_upload_complete": session.recording_upload_complete,
        },
        "device_checks": None if not device else {"camera_ok": device.camera_ok, "microphone_ok": device.microphone_ok, "details": device.details},
        "initial_verification": {
            "face_enrolled": session.face_enrolled,
            "voice_enrolled": session.voice_enrolled,
            "face_verified": session.initial_face_verified,
            "voice_verified": session.initial_voice_verified,
        },
        "attention_baseline": None if attention_baseline is None else {
            "mode": "automatic_passive",
            "status": attention_baseline.status,
            "ready": attention_baseline.status == "ready",
            "accepted_samples": attention_baseline.accepted_samples,
            "rejected_samples": attention_baseline.rejected_samples,
            "baseline_confidence": attention_baseline.baseline_confidence,
            "neutral_pose": {"yaw": attention_baseline.neutral_yaw, "pitch": attention_baseline.neutral_pitch, "roll": attention_baseline.neutral_roll},
            "neutral_gaze": {"x_ratio": attention_baseline.neutral_gaze_x, "y_ratio": attention_baseline.neutral_gaze_y},
            "measurements": attention_baseline.measurements,
            "quality": attention_baseline.quality,
            "technical_warning": attention_baseline.technical_warning,
            "started_relative_ms": attention_baseline.started_relative_ms,
            "ready_relative_ms": attention_baseline.ready_relative_ms,
            "model_name": attention_baseline.model_name,
            "model_version": attention_baseline.model_version,
            "updated_at": _iso(attention_baseline.updated_at),
        },
        "voice_sentence_attempts": [
            {"id": a.id, "stage": a.stage, "sentence_id": a.sentence_id, "sentence_text": a.sentence_text, "recognized_transcript": a.recognized_transcript, "recognition_available": a.recognition_available, "word_results": a.word_results, "completion_percentage": a.completion_percentage, "passed": a.passed, "failure_reason": a.failure_reason, "details": a.details, "created_at": _iso(a.created_at)}
            for a in sentence_attempts
        ],
        "detector_metrics": [
            {"id": m.id, "detector": m.detector, "sequence_number": m.sequence_number, "captured_at": _iso(m.captured_at), "server_received_at": _iso(m.server_received_at), "inference_ms": m.inference_ms, "api_ms": m.api_ms, "queue_depth": m.queue_depth, "dropped_stale": m.dropped_stale, "status": m.status, "error": m.error, "details": m.details, "created_at": _iso(m.created_at)}
            for m in detector_metrics
        ],
        "verification_attempts": [
            {"id": a.id, "kind": a.kind, "stage": a.stage, "passed": a.passed, "similarity": a.similarity, "confidence": a.confidence, "measurements": a.measurements, "created_at": _iso(a.created_at)}
            for a in attempts
        ],
        "model_inventory": sorted(model_inventory.values(), key=lambda item: item["engine"]),
        "detector_summary": summaries,
        "report_readiness": {
            "status": "complete" if recording_complete and session.recording_upload_complete else "partial",
            "recording_available": recording_complete,
            "recording_upload_complete": session.recording_upload_complete,
            "confirmed_event_count": confirmed_events,
            "evidence_artifact_count": evidence_total,
            "evidence_coverage_ratio": round(evidence_coverage, 3),
            "evaluation_confidence": evaluation_confidence,
            "uncertainty_label": "standard_review" if evaluation_confidence >= 0.8 and recording_complete and session.recording_upload_complete else "elevated_uncertainty" if evaluation_confidence >= 0.5 else "high_uncertainty",
        },
        "risk": {
            "score": score,
            "classification": classification,
            "contributions_by_type": explanation,
            "automated_score": score,
            "automated_classification": classification,
            "review_adjusted_score": adjusted_score,
            "review_adjusted_classification": adjusted_classification,
            "review_adjusted_contributions_by_type": adjusted_explanation,
            "dismissed_event_count": len(events) - len(review_adjusted_events),
            "decision_support_only": True,
        },
        "timeline": timeline,
        "recordings": recordings,
        "evidence_integrity_manifest": evidence_manifest,
        "technical_issues": technical_issues,
        "human_reviews": [
            {"id": r.id, "admin_id": r.admin_id, "decision": r.decision, "notes": r.notes, "created_at": _iso(r.created_at)} for r in reviews
        ],
        "audit_information": [
            {"id": row.id, "actor_type": row.actor_type, "actor_id": row.actor_id, "action": row.action, "details": row.details, "created_at": _iso(row.created_at)} for row in audit_rows
        ],
        "limitations": [
            "AI signals are decision support and require human review.",
            "RGB-only anti-spoofing cannot reliably defeat every replay or 3D-mask attack.",
            "Additional-speaker, overlap, head-pose and gaze states are confidence-based review signals, not proof of misconduct.",
        ],
    }


def render_html(data: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape("" if value is None else str(value))

    def evidence_links(event: dict[str, Any]) -> str:
        links = [f"<a class='media-link' href='{esc(item['url'])}'>{esc(item['kind'])}:{esc(item['id'])}</a>" for item in event.get("evidence", [])]
        if event.get("missing_evidence"):
            links.append(f"<span class='error'>Missing: {esc(', '.join(event['missing_evidence']))}</span>")
        return "<br>".join(links) or "Not applicable"

    timeline_rows = "".join(
        f"<tr><td>{event['relative_ms']/1000:.2f}s</td><td>{esc(event['type'])}</td><td>{esc(event['state'])}</td><td>{event['duration_ms']/1000:.2f}s</td><td>{event['confidence']:.2f}</td><td>{event['risk_contribution']:.2f}</td><td>{esc(event['explanation'])}</td><td>{evidence_links(event)}</td></tr>"
        for event in data["timeline"]
    ) or "<tr><td colspan='8'>No confirmed events</td></tr>"
    recording_rows = "".join(
        f"<tr><td><a class='media-link' href='{esc(item['url'])}'>{esc(item['id'])}</a></td><td>{esc(item['kind'])}</td><td>{esc(item['duration_seconds'])}</td><td>{esc(item['video_codec'])}</td><td>{esc(item['audio_codec'])}</td><td>{esc(item['validation_status'])}</td><td>{'pass' if item['integrity'].get('checksum_matches') else esc(item['integrity'].get('failure_reason'))}</td></tr>"
        for item in data["recordings"]
    ) or "<tr><td colspan='7'>No finalized recording</td></tr>"
    evidence_rows = "".join(
        f"<tr><td>{esc(item['event_id'])}</td><td>{esc(item['kind'])}</td><td>{esc(item['id'])}</td><td>{esc(item['checksum'])}</td><td>{'pass' if item['integrity'].get('checksum_matches') else esc(item['integrity'].get('failure_reason'))}</td></tr>"
        for item in data["evidence_integrity_manifest"]
    ) or "<tr><td colspan='5'>No evidence artifacts</td></tr>"
    issue_rows = "".join(
        f"<tr><td>{esc(item['component'])}</td><td>{esc(item['message'])}</td><td>{esc(item.get('resolved', False))}</td><td><pre>{esc(json.dumps(item.get('details', {}), indent=2))}</pre></td></tr>"
        for item in data["technical_issues"]
    ) or "<tr><td colspan='4'>No recorded technical issues</td></tr>"
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Agent5 Interview Report — Final Fraud Review</title>
<style>@page{{size:A4 landscape;margin:14mm}}body{{font-family:Arial,sans-serif;max-width:1400px;margin:32px auto;color:#172033;line-height:1.35}}table{{width:100%;border-collapse:collapse;margin-bottom:24px;table-layout:fixed}}th,td{{border:1px solid #ccd3df;padding:7px;text-align:left;vertical-align:top;overflow-wrap:anywhere}}th{{background:#26364a;color:white}}.notice{{background:#fff4ce;padding:12px;border-left:4px solid #d98e00}}.error{{color:#a40000}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;margin:0}}a{{overflow-wrap:anywhere}}footer{{margin-top:30px;color:#667085}}</style></head><body>
<h1>Agent5 Interview Report — Final Fraud Review</h1><div class='notice'>Decision support only. Human review is required. Report completeness: {esc(data['report_readiness']['status'])}; evaluation confidence: {esc(data['report_readiness']['evaluation_confidence'])}.</div>
<h2>Candidate and session summary</h2><table><tbody><tr><th>Candidate</th><td>{esc(data['candidate']['full_name'])} ({esc(data['candidate']['email'])})</td><th>Session ID</th><td>{esc(data['session']['id'])}</td></tr><tr><th>Status</th><td>{esc(data['session']['status'])}</td><th>Termination</th><td>{esc(data['session']['termination_reason'] or 'normal completion')}</td></tr><tr><th>Start</th><td>{esc(data['session']['started_at'])}</td><th>End / duration</th><td>{esc(data['session']['ended_at'])} / {esc(data['session']['duration_seconds'])}s</td></tr></tbody></table>
<h2>Fraud-risk score</h2><p><strong>{data['risk']['score']:.2f}/100 — {esc(data['risk']['classification'])}</strong></p><pre>{esc(json.dumps(data['risk'], indent=2))}</pre>
<h2>Chronological event timeline</h2><table><thead><tr><th>Time</th><th>Event</th><th>State</th><th>Duration</th><th>Confidence</th><th>Risk</th><th>Explanation</th><th>Evidence</th></tr></thead><tbody>{timeline_rows}</tbody></table>
<h2>Recording validation</h2><table><thead><tr><th>ID</th><th>Kind</th><th>Duration</th><th>Video</th><th>Audio</th><th>FFprobe status</th><th>Integrity</th></tr></thead><tbody>{recording_rows}</tbody></table>
<h2>Evidence Integrity Manifest</h2><table><thead><tr><th>Event ID</th><th>Kind</th><th>Evidence ID</th><th>SHA-256</th><th>Integrity</th></tr></thead><tbody>{evidence_rows}</tbody></table>
<h2>Detector summaries and models</h2><pre>{esc(json.dumps({'detector_summary': data['detector_summary'], 'model_inventory': data['model_inventory'], 'attention_baseline': data['attention_baseline']}, indent=2))}</pre>
<h2>Human review</h2><pre>{esc(json.dumps(data['human_reviews'], indent=2))}</pre>
<h2>Technical issues</h2><table><thead><tr><th>Component</th><th>Issue</th><th>Resolved</th><th>Details</th></tr></thead><tbody>{issue_rows}</tbody></table>
<h2>Audit information</h2><pre>{esc(json.dumps(data['audit_information'], indent=2))}</pre>
<h2>Known limitations</h2><ul>{''.join(f'<li>{esc(x)}</li>' for x in data['limitations'])}</ul>
<footer>Session {esc(data['session']['id'])} · Agent5 report version {data['report_version']}</footer>
<script>for (const link of document.querySelectorAll('.media-link')) {{ if (location.search) link.href += location.search; }}</script></body></html>"""


def render_pdf(data: dict[str, Any], path: Path) -> None:
    styles = getSampleStyleSheet()
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=7, leading=9, wordWrap="CJK")
    tiny = ParagraphStyle("Tiny", parent=small, fontSize=6, leading=7)
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    session_id = str(data["session"]["id"])

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(12 * mm, 7 * mm, f"Agent5 · Session {session_id}")
        canvas.drawRightString(landscape(A4)[0] - 12 * mm, 7 * mm, f"Page {document.page}")
        canvas.restoreState()

    readiness = data.get("report_readiness", {})
    readiness_status = html.escape(str(readiness.get("status", "unknown")).title())
    confidence = html.escape(str(readiness.get("evaluation_confidence", "unknown")).title())
    uncertainty = html.escape(str(readiness.get("uncertainty_label", "Not specified")))
    story = [
        Paragraph("Agent5 Final Fraud Review Report", styles["Title"]),
        Paragraph("Decision support only. Human review is required.", styles["Heading3"]),
        Paragraph(
            f"Report completeness: <b>{readiness_status}</b> &nbsp; | &nbsp; "
            f"Evaluation confidence: <b>{confidence}</b> &nbsp; | &nbsp; "
            f"Uncertainty: {uncertainty}",
            small,
        ),
        Spacer(1, 5),
    ]
    summary = [
        ["Candidate", Paragraph(html.escape(f"{data['candidate']['full_name']} ({data['candidate']['email']})"), small), "Session", Paragraph(html.escape(session_id), small)],
        ["Status", data["session"]["status"], "Termination", data["session"]["termination_reason"] or "normal completion"],
        ["Duration", f"{float(data['session']['duration_seconds'] or 0):.2f} seconds", "Risk", f"{data['risk']['score']:.2f}/100 - {data['risk']['classification']}"],
    ]
    summary_table = Table(summary, colWidths=[25*mm, 90*mm, 25*mm, 115*mm])
    summary_table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.4, colors.grey), ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#e8eef6")), ("BACKGROUND", (2,0), (2,-1), colors.HexColor("#e8eef6")), ("VALIGN", (0,0), (-1,-1), "TOP")]))
    story += [summary_table, Spacer(1, 8), Paragraph("Chronological event timeline", styles["Heading2"])]
    rows = [["Time", "Event", "Duration", "Confidence", "Risk", "Explanation", "Evidence status"]]
    for event in data["timeline"]:
        evidence_status = "complete" if event["evidence_complete"] else "missing: " + ", ".join(event["missing_evidence"])
        rows.append([
            f"{event['relative_ms']/1000:.2f}s", Paragraph(html.escape(event["type"]), small), f"{event['duration_ms']/1000:.2f}s", f"{event['confidence']:.2f}", f"{event['risk_contribution']:.2f}", Paragraph(html.escape(event["explanation"]), small), Paragraph(html.escape(evidence_status), small),
        ])
    if len(rows) == 1:
        rows.append(["-", "No confirmed events", "-", "-", "-", "-", "-"])
    table = Table(rows, colWidths=[19*mm, 34*mm, 20*mm, 20*mm, 17*mm, 105*mm, 60*mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#26364a")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), 0.4, colors.grey), ("VALIGN", (0,0), (-1,-1), "TOP"), ("FONTSIZE", (0,0), (-1,-1), 7), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f4f6f8")])]))
    story += [table, PageBreak(), Paragraph("Recording validation", styles["Heading2"])]
    recording_rows = [["Recording ID", "Duration", "Codecs", "Validation", "SHA-256 integrity"]]
    for item in data["recordings"]:
        recording_rows.append([Paragraph(item["id"], tiny), str(item["duration_seconds"]), Paragraph(f"{item['video_codec']} / {item['audio_codec']}", small), item["validation_status"], Paragraph(item["checksum"], tiny)])
    if len(recording_rows) == 1:
        recording_rows.append(["-", "-", "-", "No recording", "-"])
    rec_table = Table(recording_rows, colWidths=[60*mm, 25*mm, 40*mm, 35*mm, 115*mm], repeatRows=1)
    rec_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#26364a")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), 0.4, colors.grey), ("VALIGN", (0,0), (-1,-1), "TOP")]))
    story += [rec_table, Spacer(1, 8), Paragraph("Evidence Integrity Manifest", styles["Heading2"])]
    evidence_rows = [["Event ID", "Kind", "Evidence ID", "SHA-256", "Status"]]
    for item in data["evidence_integrity_manifest"]:
        evidence_rows.append([Paragraph(item["event_id"], tiny), item["kind"], Paragraph(item["id"], tiny), Paragraph(item["checksum"], tiny), "pass" if item["integrity"].get("checksum_matches") else Paragraph(str(item["integrity"].get("failure_reason")), tiny)])
    if len(evidence_rows) == 1:
        evidence_rows.append(["-", "-", "-", "-", "No evidence artifacts"])
    ev_table = Table(evidence_rows, colWidths=[58*mm, 24*mm, 58*mm, 105*mm, 30*mm], repeatRows=1)
    ev_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#26364a")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), 0.4, colors.grey), ("VALIGN", (0,0), (-1,-1), "TOP")]))
    story += [ev_table, PageBreak(), Paragraph("Fraud-risk score breakdown", styles["Heading2"])]
    risk_rows = [["Detector/event type", "Capped contribution"]]
    for key, value in sorted(data["risk"]["contributions_by_type"].items()):
        risk_rows.append([Paragraph(html.escape(str(key)), small), f"{float(value):.2f}"])
    if len(risk_rows) == 1:
        risk_rows.append(["No risk-bearing events", "0.00"])
    risk_table = Table(risk_rows, colWidths=[180*mm, 60*mm], repeatRows=1)
    risk_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#26364a")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), 0.4, colors.grey), ("VALIGN", (0,0), (-1,-1), "TOP")]))
    story += [risk_table, Spacer(1, 8), Paragraph("Model inventory", styles["Heading2"])]
    model_rows = [["Engine", "Model version"]]
    for item in data["model_inventory"]:
        model_rows.append([Paragraph(html.escape(str(item.get("engine") or "-")), small), Paragraph(html.escape(str(item.get("model_version") or "not recorded")), small)])
    if len(model_rows) == 1:
        model_rows.append(["No model metadata was attached to confirmed events", "-"])
    model_table = Table(model_rows, colWidths=[135*mm, 105*mm], repeatRows=1)
    model_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#26364a")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), 0.4, colors.grey), ("VALIGN", (0,0), (-1,-1), "TOP")]))
    story += [model_table, Spacer(1, 8), Paragraph("Human review", styles["Heading2"])]
    if data["human_reviews"]:
        review_rows = [["Decision", "Notes", "Timestamp"]]
        for review in data["human_reviews"]:
            review_rows.append([Paragraph(html.escape(review["decision"]), small), Paragraph(html.escape(review["notes"]), small), Paragraph(html.escape(str(review["created_at"])), small)])
        review_table = Table(review_rows, colWidths=[45*mm, 155*mm, 55*mm], repeatRows=1)
        review_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#26364a")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), 0.4, colors.grey), ("VALIGN", (0,0), (-1,-1), "TOP")]))
        story.append(review_table)
    else:
        story.append(Paragraph("No human-review decision was recorded when this report was generated.", small))
    story += [Spacer(1, 8), Paragraph("Technical issues and limitations", styles["Heading2"])]
    if data["technical_issues"]:
        for item in data["technical_issues"]:
            story.append(Paragraph(f"• {html.escape(item['component'])}: {html.escape(item['message'])}", small))
    else:
        story.append(Paragraph("No recorded technical issues.", small))
    for limitation in data["limitations"]:
        story.append(Paragraph(f"• {html.escape(limitation)}", small))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def generate_report(db: Session, session_id: str) -> Report:
    session = db.scalar(
        select(InterviewSession).where(InterviewSession.id == session_id).options(selectinload(InterviewSession.recordings))
    )
    if session is None:
        raise ValueError("session not found")
    _assert_final_report_ready(db, session)
    data = build_report_data(db, session_id)
    directory = get_settings().resolved_storage_dir / "reports"
    directory.mkdir(parents=True, exist_ok=True)
    html_path = directory / f"{session_id}.html"
    json_path = directory / f"{session_id}.json"
    pdf_path = directory / f"{session_id}.pdf"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    html_path.write_text(render_html(data), encoding="utf-8")
    render_pdf(data, pdf_path)
    checksums = {"json": sha256_file(json_path), "html": sha256_file(html_path), "pdf": sha256_file(pdf_path)}
    artifact_manifest = {
        kind: {"path": str(path), "sha256": checksums[kind], "size_bytes": path.stat().st_size}
        for kind, path in {"json": json_path, "html": html_path, "pdf": pdf_path}.items()
    }
    existing = db.scalar(select(Report).where(Report.session_id == session_id).order_by(Report.version.desc()))
    if existing:
        existing.json_data = data
        existing.json_path = str(json_path)
        existing.html_path = str(html_path)
        existing.pdf_path = str(pdf_path)
        existing.checksum = checksums["html"]
        existing.json_checksum = checksums["json"]
        existing.html_checksum = checksums["html"]
        existing.pdf_checksum = checksums["pdf"]
        existing.integrity_manifest = artifact_manifest
        db.add(existing)
        db.flush()
        return existing
    report = Report(
        session_id=session_id,
        json_data=data,
        json_path=str(json_path),
        html_path=str(html_path),
        pdf_path=str(pdf_path),
        checksum=checksums["html"],
        json_checksum=checksums["json"],
        html_checksum=checksums["html"],
        pdf_checksum=checksums["pdf"],
        integrity_manifest=artifact_manifest,
    )
    db.add(report)
    db.flush()
    return report
