import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from sqlmodel import col, func, select

from app.api.agent_auth import authenticate_agent
from app.api.deps import SessionDep
from app.models import (
    CategoriesPublic,
    Category,
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
    Message,
    Transaction,
)
from app.api.routes.categories import _validate_color
from app.utils import resolve_pagination

router = APIRouter(prefix="/agent/categories", tags=["agent-categories"])


@router.get("/", response_model=CategoriesPublic)
async def read_agent_categories(
    request: Request,
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    page: int | None = None,
    page_size: int | None = None,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
    x_api_secret: str | None = Header(default=None),
    x_timestamp: str | None = Header(default=None),
    x_signature: str | None = Header(default=None),
) -> Any:
    body_text = (await request.body()).decode()
    token = authenticate_agent(
        session, request, body_text, authorization, x_api_token, x_api_secret, x_timestamp, x_signature
    )
    offset, max_results = resolve_pagination(
        page=page, page_size=page_size, skip=skip, limit=limit
    )
    count = session.exec(
        select(func.count()).select_from(Category).where(Category.owner_id == token.created_by)
    ).one()
    categories = session.exec(
        select(Category)
        .where(Category.owner_id == token.created_by)
        .order_by(col(Category.created_at).desc())
        .offset(offset)
        .limit(max_results)
    ).all()
    return CategoriesPublic(
        data=[CategoryPublic.model_validate(category) for category in categories],
        count=count,
    )


@router.post("/", response_model=CategoryPublic)
async def create_agent_category(
    request: Request,
    category_in: CategoryCreate,
    session: SessionDep,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
    x_api_secret: str | None = Header(default=None),
    x_timestamp: str | None = Header(default=None),
    x_signature: str | None = Header(default=None),
) -> Any:
    body_text = (await request.body()).decode()
    token = authenticate_agent(
        session, request, body_text, authorization, x_api_token, x_api_secret, x_timestamp, x_signature
    )
    _validate_color(category_in.color)
    if category_in.parent_id:
        parent = session.get(Category, category_in.parent_id)
        if not parent or parent.owner_id != token.created_by:
            raise HTTPException(status_code=400, detail="Invalid parent category")
    statement = select(Category).where(
        Category.owner_id == token.created_by, Category.name == category_in.name
    )
    if session.exec(statement).first():
        raise HTTPException(status_code=409, detail="Category name already exists")
    category = Category.model_validate(category_in, update={"owner_id": token.created_by})
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.put("/{category_id}", response_model=CategoryPublic)
async def update_agent_category(
    request: Request,
    category_id: uuid.UUID,
    category_in: CategoryUpdate,
    session: SessionDep,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
    x_api_secret: str | None = Header(default=None),
    x_timestamp: str | None = Header(default=None),
    x_signature: str | None = Header(default=None),
) -> Any:
    body_text = (await request.body()).decode()
    token = authenticate_agent(
        session, request, body_text, authorization, x_api_token, x_api_secret, x_timestamp, x_signature
    )
    category = session.get(Category, category_id)
    if not category or category.owner_id != token.created_by:
        raise HTTPException(status_code=404, detail="Category not found")
    update_data = category_in.model_dump(exclude_unset=True)
    parent_id = update_data.get("parent_id")
    if parent_id == category.id:
        raise HTTPException(status_code=400, detail="Category cannot be its own parent")
    if parent_id:
        parent = session.get(Category, parent_id)
        if not parent or parent.owner_id != token.created_by:
            raise HTTPException(status_code=400, detail="Invalid parent category")
    if "color" in update_data and update_data["color"] is not None:
        _validate_color(update_data["color"])
    if "name" in update_data:
        statement = select(Category).where(
            Category.owner_id == token.created_by,
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


@router.delete("/{category_id}", response_model=Message)
async def delete_agent_category(
    request: Request,
    category_id: uuid.UUID,
    session: SessionDep,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
    x_api_secret: str | None = Header(default=None),
    x_timestamp: str | None = Header(default=None),
    x_signature: str | None = Header(default=None),
) -> Any:
    body_text = (await request.body()).decode()
    token = authenticate_agent(
        session, request, body_text, authorization, x_api_token, x_api_secret, x_timestamp, x_signature
    )
    category = session.get(Category, category_id)
    if not category or category.owner_id != token.created_by:
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
    return Message(message="Category deleted successfully")
