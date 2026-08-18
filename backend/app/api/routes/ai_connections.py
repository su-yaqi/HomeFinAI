import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException
from sqlmodel import col, func, select

from app.ai_connector.oauth import oauth_provider
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    AIConnection,
    AIConnectionPublic,
    AIConnectionsPublic,
    AIConnectionStatus,
    Message,
    get_datetime_utc,
)
from app.utils import resolve_pagination

router = APIRouter(prefix="/ai-connections", tags=["ai-connections"])


@router.get("/", response_model=AIConnectionsPublic)
def list_ai_connections(
    session: SessionDep,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 10,
) -> AIConnectionsPublic:
    offset, limit = resolve_pagination(page=page, page_size=page_size)
    condition = AIConnection.user_id == current_user.id
    count = session.exec(
        select(func.count()).select_from(AIConnection).where(condition)
    ).one()
    rows = session.exec(
        select(AIConnection)
        .where(condition)
        .order_by(col(AIConnection.created_at).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return AIConnectionsPublic(
        data=[AIConnectionPublic.model_validate(row) for row in rows], count=count
    )


@router.get("/authorization-request")
def read_authorization_request(
    request: str, current_user: CurrentUser
) -> dict[str, Any]:
    try:
        payload = oauth_provider.describe_authorization(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "client_id": payload["client_id"],
        "client_name": payload["client_name"],
        "redirect_uri": payload["redirect_uri"],
        "scopes": payload["scopes"],
        "user_id": str(current_user.id),
        "user_name": current_user.full_name or current_user.login_name,
    }


@router.post("/authorization-request")
def decide_authorization_request(
    current_user: CurrentUser,
    request: Annotated[str, Body(embed=True)],
    approved: Annotated[bool, Body(embed=True)],
) -> dict[str, str]:
    try:
        redirect_url = oauth_provider.complete_authorization(
            user=current_user, request_token=request, approved=approved
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"redirect_url": redirect_url}


@router.delete("/{connection_id}", response_model=Message)
def revoke_ai_connection(
    connection_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Message:
    connection = session.get(AIConnection, connection_id)
    if not connection or connection.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="AI connection not found")
    if connection.status != AIConnectionStatus.REVOKED.value:
        connection.status = AIConnectionStatus.REVOKED.value
        connection.revoked_at = get_datetime_utc()
        session.add(connection)
        session.commit()
    return Message(message="AI connection revoked")
