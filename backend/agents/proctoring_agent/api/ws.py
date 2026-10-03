from __future__ import annotations

import asyncio
from collections import defaultdict

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import get_settings
from ..db import SessionLocal
from ..models import InterviewSession
from ..security import decode_token

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._roles: dict[str, dict[int, str]] = defaultdict(dict)  # session_id -> id(ws) -> role
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, websocket: WebSocket, *, role: str = "candidate") -> None:
        await websocket.accept()
        normalized = "hr" if str(role).lower() == "hr" else "candidate"
        async with self._lock:
            self._connections[session_id].add(websocket)
            self._roles[session_id][id(websocket)] = normalized

    async def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[session_id].discard(websocket)
            self._roles[session_id].pop(id(websocket), None)
            if not self._connections[session_id]:
                self._connections.pop(session_id, None)
                self._roles.pop(session_id, None)

    def presence(self, session_id: str) -> dict[str, int]:
        roles = list(self._roles.get(session_id, {}).values())
        candidates = sum(1 for role in roles if role != "hr")
        interviewers = sum(1 for role in roles if role == "hr")
        return {
            "candidates": candidates,
            "interviewers": interviewers,
            "total": len(roles),
        }

    async def broadcast(self, session_id: str, message: dict) -> None:
        stale: list[WebSocket] = []
        async with self._lock:
            targets = list(self._connections.get(session_id, set()))
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            await self.disconnect(session_id, ws)

    async def broadcast_presence(self, session_id: str) -> None:
        payload = {"type": "room_presence", **self.presence(session_id)}
        await self.broadcast(session_id, payload)

    async def relay_to_peers(self, session_id: str, sender: WebSocket, message: dict) -> None:
        async with self._lock:
            targets = [ws for ws in self._connections.get(session_id, set()) if ws is not sender]
        stale: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            await self.disconnect(session_id, ws)


manager = ConnectionManager()


@router.websocket("/ws/sessions/{session_id}")
async def session_socket(websocket: WebSocket, session_id: str, token: str):
    try:
        payload = decode_token(token, "candidate")
        if payload.get("session_id") != session_id:
            raise jwt.InvalidTokenError("session mismatch")
    except jwt.PyJWTError:
        await websocket.close(code=4401)
        return
    with SessionLocal() as db:
        session = db.get(InterviewSession, session_id)
        if session is None:
            await websocket.close(code=4404)
            return

    role = str(payload.get("participant_role") or "candidate").lower()
    await manager.connect(session_id, websocket, role=role)
    await manager.broadcast_presence(session_id)
    try:
        while True:
            data = await websocket.receive_json()
            with SessionLocal() as db:
                session = db.get(InterviewSession, session_id)
                if session is None:
                    await websocket.send_json({"type": "error", "message": "session not found"})
                    continue
                if data.get("type") == "presence":
                    # Allow client to refresh role claim (still bound to token).
                    await manager.broadcast_presence(session_id)
                    continue
                if data.get("type") == "webrtc_signal":
                    await manager.relay_to_peers(session_id, websocket, data)
                    continue
                if data.get("type") == "client_state":
                    elapsed = int(data.get("relative_ms") or 0)
                    session.current_client_elapsed_ms = max(session.current_client_elapsed_ms, max(0, elapsed))
                    db.commit()
                state = {
                    "type": "state",
                    "status": session.status,
                    "termination_reason": session.termination_reason,
                }
                settings = get_settings()
                if settings.test_mode or settings.candidate_debug_payloads:
                    state.update({
                        "risk_score": session.risk_score,
                        "risk_classification": session.risk_classification,
                        "tab_switch_count": session.tab_switch_count,
                    })
                await websocket.send_json(state)
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(session_id, websocket)
        await manager.broadcast_presence(session_id)
