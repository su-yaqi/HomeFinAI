from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.db import engine
from app.models import AIConnection, AIOperation, User, get_datetime_utc

IDEMPOTENCY_RETENTION_DAYS = 30
_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,100}$")


@dataclass(frozen=True)
class AuthorizedIdentity:
    user: User
    connection: AIConnection


def _json_default(value: object) -> str:
    if isinstance(value, uuid.UUID | date | datetime | Enum):
        return str(value.value if isinstance(value, Enum) else value)
    raise TypeError(f"Unsupported value in operation payload: {type(value).__name__}")


def canonical_payload(payload: Mapping[str, object]) -> str:
    return json.dumps(
        payload,
        default=_json_default,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def payload_hash(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_payload(payload).encode()).hexdigest()


def authorized_identity(
    session: Session, required_scopes: set[str]
) -> AuthorizedIdentity:
    access = get_access_token()
    claims = access.claims if access else None
    raw_connection_id = claims.get("connection_id") if claims else None
    if (
        not access
        or not access.subject
        or not raw_connection_id
        or not required_scopes.issubset(set(access.scopes))
    ):
        raise PermissionError("The AI connection lacks the required HomeFin scope")
    try:
        user_id = uuid.UUID(access.subject)
        connection_id = uuid.UUID(str(raw_connection_id))
    except ValueError as exc:
        raise PermissionError("The AI connection identity is invalid") from exc
    user = session.get(User, user_id)
    connection = session.get(AIConnection, connection_id)
    if (
        not user
        or not user.is_active
        or not connection
        or connection.user_id != user.id
    ):
        raise PermissionError("The HomeFin AI connection is not active")
    return AuthorizedIdentity(user=user, connection=connection)


def _validate_idempotency_key(value: str) -> None:
    if _IDEMPOTENCY_KEY_PATTERN.fullmatch(value) is None:
        raise ValueError(
            "idempotency_key must be 8-100 characters using letters, numbers, '.', '_', ':', or '-'"
        )


def _load_operation(
    session: Session,
    *,
    connection_id: uuid.UUID,
    tool_name: str,
    idempotency_key: str,
) -> AIOperation | None:
    return session.exec(
        select(AIOperation).where(
            AIOperation.connection_id == connection_id,
            AIOperation.tool_name == tool_name,
            AIOperation.idempotency_key == idempotency_key,
        )
    ).first()


def _replay_or_conflict(operation: AIOperation, request_hash: str) -> dict[str, Any]:
    if operation.request_hash != request_hash:
        raise ValueError(
            "The idempotency_key was already used with different parameters"
        )
    return dict(operation.result_payload)


def load_idempotent_replay(
    session: Session,
    *,
    identity: AuthorizedIdentity,
    tool_name: str,
    idempotency_key: str,
    request_payload: Mapping[str, object],
) -> dict[str, Any] | None:
    """Return a committed replay before interactive confirmation is requested."""
    _validate_idempotency_key(idempotency_key)
    existing = _load_operation(
        session,
        connection_id=identity.connection.id,
        tool_name=tool_name,
        idempotency_key=idempotency_key,
    )
    if existing is None:
        return None
    return _replay_or_conflict(existing, payload_hash(request_payload))


WriteCallback = Callable[
    [Session, AuthorizedIdentity], tuple[uuid.UUID | None, dict[str, Any]]
]


def execute_idempotent_write(
    *,
    required_scopes: set[str],
    tool_name: str,
    idempotency_key: str,
    request_payload: Mapping[str, object],
    resource_type: str,
    write: WriteCallback,
) -> dict[str, Any]:
    """Commit the domain write and its replay record in one DB transaction."""
    _validate_idempotency_key(idempotency_key)
    request_hash = payload_hash(request_payload)
    try:
        with Session(engine) as session, session.begin():
            identity = authorized_identity(session, required_scopes)
            existing = _load_operation(
                session,
                connection_id=identity.connection.id,
                tool_name=tool_name,
                idempotency_key=idempotency_key,
            )
            if existing:
                return _replay_or_conflict(existing, request_hash)
            resource_id, result = write(session, identity)
            session.add(
                AIOperation(
                    connection_id=identity.connection.id,
                    tool_name=tool_name,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    result_payload=result,
                    expires_at=get_datetime_utc()
                    + timedelta(days=IDEMPOTENCY_RETENTION_DAYS),
                )
            )
            session.flush()
            return result
    except IntegrityError:
        # A concurrent request may have won the operation uniqueness race. Its
        # domain mutation and operation row committed together, while this
        # transaction was fully rolled back by the context manager.
        with Session(engine) as session:
            identity = authorized_identity(session, required_scopes)
            existing = _load_operation(
                session,
                connection_id=identity.connection.id,
                tool_name=tool_name,
                idempotency_key=idempotency_key,
            )
            if existing:
                return _replay_or_conflict(existing, request_hash)
        raise ValueError(
            "The write conflicted with another database operation"
        ) from None


class ToolScopeVisibilityMiddleware:
    """Remove tools from tools/list when the bearer token lacks their scopes."""

    def __init__(self, tool_scopes: Mapping[str, set[str]]) -> None:
        self._tool_scopes = tool_scopes

    async def __call__(
        self, ctx: ServerRequestContext[Any, Any], call_next: CallNext
    ) -> HandlerResult:
        result = await call_next(ctx)
        if ctx.method != "tools/list" or not isinstance(result, dict):
            return result
        access = get_access_token()
        scopes = set(access.scopes) if access else set()
        raw_tools = result.get("tools")
        if not isinstance(raw_tools, list):
            return result
        return {
            **result,
            "tools": [
                tool
                for tool in raw_tools
                if isinstance(tool, dict)
                and self._tool_scopes.get(
                    str(tool.get("name")), {"finance:read"}
                ).issubset(scopes)
            ],
        }
