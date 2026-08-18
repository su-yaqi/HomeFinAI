import uuid

from fastapi import APIRouter

from app.api.agent_auth import AgentToken
from app.api.deps import SessionDep
from app.models import (
    CategoriesPublic,
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
    Message,
)
from app.services import categories as category_service

router = APIRouter(prefix="/agent/categories", tags=["agent-categories"])


@router.get("/", response_model=CategoriesPublic)
def read_agent_categories(
    session: SessionDep,
    token: AgentToken,
    skip: int = 0,
    limit: int = 100,
    page: int | None = None,
    page_size: int | None = None,
) -> CategoriesPublic:
    return category_service.list_categories(
        session,
        owner_id=token.created_by,
        skip=skip,
        limit=limit,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=CategoryPublic)
def create_agent_category(
    category_in: CategoryCreate, session: SessionDep, token: AgentToken
) -> CategoryPublic:
    return category_service.create_category(
        session, owner_id=token.created_by, category_in=category_in
    )


@router.put("/{category_id}", response_model=CategoryPublic)
def update_agent_category(
    category_id: uuid.UUID,
    category_in: CategoryUpdate,
    session: SessionDep,
    token: AgentToken,
) -> CategoryPublic:
    return category_service.update_category(
        session,
        owner_id=token.created_by,
        category_id=category_id,
        category_in=category_in,
    )


@router.delete("/{category_id}", response_model=Message)
def delete_agent_category(
    category_id: uuid.UUID, session: SessionDep, token: AgentToken
) -> Message:
    return category_service.delete_category(
        session, owner_id=token.created_by, category_id=category_id
    )
