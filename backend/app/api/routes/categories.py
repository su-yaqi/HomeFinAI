import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    CategoriesPublic,
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
    Message,
)
from app.services import categories as category_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("/", response_model=CategoriesPublic)
def read_categories(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    page: int | None = None,
    page_size: int | None = None,
) -> CategoriesPublic:
    return category_service.list_categories(
        session,
        owner_id=current_user.id,
        skip=skip,
        limit=limit,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=CategoryPublic)
def create_category(
    *, session: SessionDep, current_user: CurrentUser, category_in: CategoryCreate
) -> CategoryPublic:
    return category_service.create_category(
        session, owner_id=current_user.id, category_in=category_in
    )


@router.put("/{category_id}", response_model=CategoryPublic)
def update_category(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    category_id: uuid.UUID,
    category_in: CategoryUpdate,
) -> CategoryPublic:
    return category_service.update_category(
        session,
        owner_id=current_user.id,
        category_id=category_id,
        category_in=category_in,
    )


@router.delete("/{category_id}", response_model=Message)
def delete_category(
    session: SessionDep, current_user: CurrentUser, category_id: uuid.UUID
) -> Message:
    return category_service.delete_category(
        session, owner_id=current_user.id, category_id=category_id
    )
