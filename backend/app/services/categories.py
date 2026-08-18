import re
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.models import (
    CategoriesPublic,
    Category,
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
    Message,
    Transaction,
)
from app.utils import resolve_pagination


def _validate_color(color: str) -> None:
    if re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", color) is None:
        raise HTTPException(status_code=422, detail="Invalid color")


def _validate_parent(
    session: Session,
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


def _commit(session: Session, category: Category) -> None:
    try:
        session.add(category)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Category name already exists")


def list_categories(
    session: Session,
    *,
    owner_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    page: int | None = None,
    page_size: int | None = None,
) -> CategoriesPublic:
    offset, max_results = resolve_pagination(
        page=page, page_size=page_size, skip=skip, limit=limit
    )
    condition = Category.owner_id == owner_id
    count = session.exec(
        select(func.count()).select_from(Category).where(condition)
    ).one()
    categories = session.exec(
        select(Category)
        .where(condition)
        .order_by(col(Category.created_at).desc())
        .offset(offset)
        .limit(max_results)
    ).all()
    return CategoriesPublic(
        data=[CategoryPublic.model_validate(category) for category in categories],
        count=count,
    )


def create_category(
    session: Session, *, owner_id: uuid.UUID, category_in: CategoryCreate
) -> CategoryPublic:
    _validate_color(category_in.color)
    _validate_parent(
        session,
        owner_id=owner_id,
        category_id=None,
        parent_id=category_in.parent_id,
    )
    existing = session.exec(
        select(Category).where(
            Category.owner_id == owner_id, Category.name == category_in.name
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Category name already exists")
    category = Category.model_validate(category_in, update={"owner_id": owner_id})
    _commit(session, category)
    session.refresh(category)
    return CategoryPublic.model_validate(category)


def update_category(
    session: Session,
    *,
    owner_id: uuid.UUID,
    category_id: uuid.UUID,
    category_in: CategoryUpdate,
) -> CategoryPublic:
    category = session.get(Category, category_id)
    if not category or category.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Category not found")
    update_data = category_in.model_dump(exclude_unset=True)
    _validate_parent(
        session,
        owner_id=owner_id,
        category_id=category.id,
        parent_id=update_data.get("parent_id", category.parent_id),
    )
    if color := update_data.get("color"):
        _validate_color(color)
    if name := update_data.get("name"):
        existing = session.exec(
            select(Category).where(
                Category.owner_id == owner_id,
                Category.name == name,
                Category.id != category.id,
            )
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Category name already exists")
    category.sqlmodel_update(update_data)
    _commit(session, category)
    session.refresh(category)
    return CategoryPublic.model_validate(category)


def delete_category(
    session: Session, *, owner_id: uuid.UUID, category_id: uuid.UUID
) -> Message:
    category = session.get(Category, category_id)
    if not category or category.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Category not found")
    if session.exec(select(Category).where(Category.parent_id == category.id)).first():
        raise HTTPException(status_code=400, detail="Category has child categories")
    if session.exec(
        select(Transaction).where(Transaction.category_id == category.id)
    ).first():
        raise HTTPException(status_code=400, detail="Category has related transactions")
    session.delete(category)
    session.commit()
    return Message(message="Category deleted successfully")
