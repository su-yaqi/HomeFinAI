import uuid

from fastapi import APIRouter
from sqlmodel import col, func, select

from app.api.agent_auth import AgentToken
from app.api.deps import SessionDep
from app.models import HandlerUserOption, HandlerUsersPublic, User

router = APIRouter(prefix="/agent", tags=["agent-transactions"])


@router.get("/handler-options", response_model=HandlerUsersPublic)
def read_agent_handler_options(
    session: SessionDep, token: AgentToken
) -> HandlerUsersPublic:
    active_condition = User.is_active == True  # noqa: E712
    count = session.exec(
        select(func.count()).select_from(User).where(active_condition)
    ).one()
    users = session.exec(
        select(User)
        .where(active_condition)
        .order_by(col(User.full_name).asc(), col(User.login_name).asc())
    ).all()

    token_owner = session.get(User, token.created_by)
    if token_owner and token_owner.is_active and token_owner not in users:
        users = [token_owner, *users]

    seen_ids: set[uuid.UUID] = set()
    options: list[HandlerUserOption] = []
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
