from typing import Any

from fastapi import APIRouter, Header, Request
from sqlmodel import col, func, select

from app.api.agent_auth import authenticate_agent
from app.api.deps import SessionDep
from app.models import HandlerUserOption, HandlerUsersPublic, User

router = APIRouter(prefix="/agent", tags=["agent-transactions"])


@router.get("/handler-options", response_model=HandlerUsersPublic)
async def read_agent_handler_options(
    request: Request,
    session: SessionDep,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
    x_api_secret: str | None = Header(default=None),
    x_timestamp: str | None = Header(default=None),
    x_signature: str | None = Header(default=None),
) -> Any:
    body_text = (await request.body()).decode()
    token = authenticate_agent(
        session,
        request,
        body_text,
        authorization,
        x_api_token,
        x_api_secret,
        x_timestamp,
        x_signature,
    )
    count = session.exec(
        select(func.count()).select_from(User).where(User.is_active == True)  # noqa: E712
    ).one()
    users = session.exec(
        select(User)
        .where(User.is_active == True)  # noqa: E712
        .order_by(col(User.full_name).asc(), col(User.login_name).asc())
    ).all()

    token_owner = session.get(User, token.created_by)
    if token_owner and token_owner.is_active and token_owner.id not in {user.id for user in users}:
        users = [token_owner, *users]

    seen_ids: set = set()
    options = []
    for user in users:
        if user.id in seen_ids:
            continue
        seen_ids.add(user.id)
        options.append(
            HandlerUserOption(
                id=user.id,
                full_name=user.full_name,
                login_name=user.login_name,
                display_name=user.full_name or user.login_name,
            )
        )

    return HandlerUsersPublic(data=options, count=count)
