import re
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    CategoriesPublic,
    Category,
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
    Transaction,
)
from app.utils import resolve_pagination

router = APIRouter(prefix="/categories", tags=["categories"])


def _validate_color(color: str) -> None:
    if re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", color) is None:
        raise HTTPException(status_code=422, detail="Invalid color")


def _validate_category_parent(
    session: SessionDep,
    *,
    owner_id: uuid.UUID,
    category_id: uuid.UUID | None,
    parent_id: uuid.UUID | None,
) -> None:
    if parent_id is None:
        return
    visited: set[uuid.UUID] = set()
    current_id: uuid.UUID | None = parent_id
    while current_id is not None:
        if current_id == category_id or current_id in visited:
            raise HTTPException(
                status_code=400, detail="Category hierarchy cannot contain a cycle"
            )
        visited.add(current_id)
        parent = session.get(Category, current_id)
        if not parent or parent.owner_id != owner_id:
            raise HTTPException(status_code=400, detail="Invalid parent category")
        current_id = parent.parent_id


def _commit_category(session: SessionDep, category: Category) -> None:
    try:
        session.add(category)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Category name already exists")


@router.get("/", response_model=CategoriesPublic)
def read_categories(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    offset, max_results = resolve_pagination(
        page=page, page_size=page_size, skip=skip, limit=limit
    )
    count_statement = (
        select(func.count())
        .select_from(Category)
        .where(Category.owner_id == current_user.id)
    )
    count = session.exec(count_statement).one()
    statement = (
        select(Category)
        .where(Category.owner_id == current_user.id)
        .order_by(col(Category.created_at).desc())
        .offset(offset)
        .limit(max_results)
    )
    categories = session.exec(statement).all()
    return CategoriesPublic(
        data=[CategoryPublic.model_validate(category) for category in categories],
        count=count,
    )


@router.post("/", response_model=CategoryPublic)
def create_category(
    *, session: SessionDep, current_user: CurrentUser, category_in: CategoryCreate
) -> Any:
    _validate_color(category_in.color)
    _validate_category_parent(
        session,
        owner_id=current_user.id,
        category_id=None,
        parent_id=category_in.parent_id,
    )
    statement = select(Category).where(
        Category.owner_id == current_user.id, Category.name == category_in.name
    )
    if session.exec(statement).first():
        raise HTTPException(status_code=409, detail="Category name already exists")
    category = Category.model_validate(
        category_in, update={"owner_id": current_user.id}
    )
    _commit_category(session, category)
    session.refresh(category)
    return category


@router.put("/{category_id}", response_model=CategoryPublic)
def update_category(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    category_id: uuid.UUID,
    category_in: CategoryUpdate,
) -> Any:
    category = session.get(Category, category_id)
    if not category or category.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Category not found")
    update_data = category_in.model_dump(exclude_unset=True)
    parent_id = update_data.get("parent_id", category.parent_id)
    _validate_category_parent(
        session,
        owner_id=current_user.id,
        category_id=category.id,
        parent_id=parent_id,
    )
    if "color" in update_data and update_data["color"] is not None:
        _validate_color(update_data["color"])
    if "name" in update_data:
        statement = select(Category).where(
            Category.owner_id == current_user.id,
            Category.name == update_data["name"],
            Category.id != category.id,
        )
        if session.exec(statement).first():
            raise HTTPException(status_code=409, detail="Category name already exists")
    category.sqlmodel_update(update_data)
    _commit_category(session, category)
    session.refresh(category)
    return category


@router.delete("/{category_id}")
def delete_category(
    session: SessionDep, current_user: CurrentUser, category_id: uuid.UUID
) -> Any:
    category = session.get(Category, category_id)
    if not category or category.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Category not found")
    child = session.exec(
        select(Category).where(Category.parent_id == category.id)
    ).first()
    if child:
        raise HTTPException(status_code=400, detail="Category has child categories")
    linked_transaction = session.exec(
        select(Transaction).where(Transaction.category_id == category.id)
    ).first()
    if linked_transaction:
        raise HTTPException(status_code=400, detail="Category has related transactions")
    session.delete(category)
    session.commit()
    return {"message": "Category deleted successfully"}
