import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Category,
    CategoriesPublic,
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
    Transaction,
)
from app.utils import resolve_pagination

router = APIRouter(prefix="/categories", tags=["categories"])


def _validate_color(color: str) -> None:
    if not color.startswith("#") or len(color) not in {4, 7}:
        raise HTTPException(status_code=422, detail="Invalid color")


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
        select(func.count()).select_from(Category).where(Category.owner_id == current_user.id)
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
    if category_in.parent_id:
        parent = session.get(Category, category_in.parent_id)
        if not parent or parent.owner_id != current_user.id:
            raise HTTPException(status_code=400, detail="Invalid parent category")
    statement = select(Category).where(
        Category.owner_id == current_user.id, Category.name == category_in.name
    )
    if session.exec(statement).first():
        raise HTTPException(status_code=409, detail="Category name already exists")
    category = Category.model_validate(category_in, update={"owner_id": current_user.id})
    session.add(category)
    session.commit()
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
    parent_id = update_data.get("parent_id")
    if parent_id == category.id:
        raise HTTPException(status_code=400, detail="Category cannot be its own parent")
    if parent_id:
        parent = session.get(Category, parent_id)
        if not parent or parent.owner_id != current_user.id:
            raise HTTPException(status_code=400, detail="Invalid parent category")
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
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.delete("/{category_id}")
def delete_category(
    session: SessionDep, current_user: CurrentUser, category_id: uuid.UUID
) -> Any:
    category = session.get(Category, category_id)
    if not category or category.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Category not found")
    child = session.exec(select(Category).where(Category.parent_id == category.id)).first()
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
