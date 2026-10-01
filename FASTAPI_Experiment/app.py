"""Expose the existing travel Agent through a small FastAPI service.

This first version deliberately keeps session state in memory and uses the
existing ``1.3-experiment`` Agent implementation.  The service boundary is
kept behind ``AgentService`` so SQLite, SSE, authentication, and rate limits
can be added without changing the HTTP models later.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field


# ``1.3-experiment`` is intentionally kept unchanged in this first service
# lab.  This import bridge makes the reuse explicit; a later
# refactor can move it into a normal package without changing this API.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAVEL_AGENT_DIR = PROJECT_ROOT / "1.3-experiment"
if str(TRAVEL_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(TRAVEL_AGENT_DIR))

from session_agent import (  # noqa: E402  (path bridge must run first)
    FeedbackType,
    SessionState,
    TurnResult,
    continue_session,
)


class SessionCreateRequest(BaseModel):
    """Input for creating a logical Agent conversation."""

    user_id: str = Field(default="demo-user", min_length=1, max_length=100)


class SessionCreateResponse(BaseModel):
    session_id: str
    user_id: str


class TurnRequest(BaseModel):
    """One user turn sent to an existing session.

    ``feedback_type`` is explicit on purpose.  The API does not let the
    language model decide whether a message counts as a rejection, which
    keeps session counters deterministic.
    """

    message: str = Field(min_length=1, max_length=4000)
    feedback_type: Literal["none", "accept", "reject"] = "none"


class TurnResponse(BaseModel):
    session_id: str
    answer: str
    feedback_type: FeedbackType
    reflected: bool
    consecutive_rejections: int
    strategy_version: int


class SessionSummary(BaseModel):
    session_id: str
    user_id: str
    message_count: int
    has_last_recommendation: bool
    consecutive_rejections: int
    reflection_count: int
    strategy_version: int


@dataclass
class _SessionRecord:
    state: SessionState
    lock: RLock


class InMemorySessionStore:
    """Thread-safe session registry for the first experiment iteration."""

    def __init__(self) -> None:
        self._records: dict[str, _SessionRecord] = {}
        self._lock = RLock()

    def create(self, user_id: str) -> SessionState:
        state = SessionState(session_id=str(uuid4()), user_id=user_id)
        with self._lock:
            self._records[state.session_id] = _SessionRecord(state, RLock())
        return state

    def get(self, session_id: str) -> _SessionRecord | None:
        with self._lock:
            return self._records.get(session_id)

    def count(self) -> int:
        with self._lock:
            return len(self._records)


class AgentService:
    """Application service that adapts HTTP requests to ``continue_session``."""

    def __init__(self, *, store: InMemorySessionStore | None = None, llm=None) -> None:
        self.store = store or InMemorySessionStore()
        self.llm = llm

    def create_session(self, user_id: str) -> SessionState:
        return self.store.create(user_id.strip())

    def turn(
        self,
        session_id: str,
        message: str,
        feedback_type: FeedbackType,
    ) -> TurnResult:
        record = self.store.get(session_id)
        if record is None:
            raise KeyError(session_id)

        # The lock protects mutable SessionState while the Agent processes a
        # turn.  Different sessions can still proceed independently.
        with record.lock:
            return continue_session(
                record.state,
                message,
                feedback_type=feedback_type,
                llm=self.llm,
                trace_memory=False,
            )

    def summary(self, session_id: str) -> SessionSummary:
        record = self.store.get(session_id)
        if record is None:
            raise KeyError(session_id)
        with record.lock:
            state = record.state
            return SessionSummary(
                session_id=state.session_id,
                user_id=state.user_id,
                message_count=len(state.messages),
                has_last_recommendation=state.last_recommendation is not None,
                consecutive_rejections=state.consecutive_rejections,
                reflection_count=state.reflection_count,
                strategy_version=state.reflection_count,
            )


def _not_found(session_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"会话不存在: {session_id}",
    )


def create_app(
    *,
    store: InMemorySessionStore | None = None,
    llm=None,
) -> FastAPI:
    """Create an app, allowing tests to inject a deterministic LLM and store."""

    app = FastAPI(
        title="Travel Agent FastAPI Experiment",
        version="0.1.0",
        description="将 1.3-experiment 的旅行 Agent 暴露为可调用的 HTTP 服务。",
    )
    app.state.agent_service = AgentService(store=store, llm=llm)

    @app.get("/health")
    def health(request: Request) -> dict[str, int | str]:
        service: AgentService = request.app.state.agent_service
        return {"status": "ok", "active_sessions": service.store.count()}

    @app.post(
        "/sessions",
        response_model=SessionCreateResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_session(
        request: Request,
        payload: SessionCreateRequest,
    ) -> SessionCreateResponse:
        service: AgentService = request.app.state.agent_service
        state = service.create_session(payload.user_id)
        return SessionCreateResponse(session_id=state.session_id, user_id=state.user_id)

    @app.get("/sessions/{session_id}", response_model=SessionSummary)
    def get_session(request: Request, session_id: str) -> SessionSummary:
        service: AgentService = request.app.state.agent_service
        try:
            return service.summary(session_id)
        except KeyError as exc:
            raise _not_found(session_id) from exc

    @app.post("/sessions/{session_id}/turns", response_model=TurnResponse)
    def create_turn(request: Request, session_id: str, payload: TurnRequest) -> TurnResponse:
        service: AgentService = request.app.state.agent_service
        try:
            result = service.turn(session_id, payload.message, payload.feedback_type)
        except KeyError as exc:
            raise _not_found(session_id) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        return TurnResponse(
            session_id=session_id,
            answer=result.answer,
            feedback_type=payload.feedback_type,
            reflected=result.reflected,
            consecutive_rejections=result.consecutive_rejections,
            strategy_version=result.strategy_version,
        )

    return app


app = create_app()


__all__ = [
    "AgentService",
    "InMemorySessionStore",
    "app",
    "create_app",
]
