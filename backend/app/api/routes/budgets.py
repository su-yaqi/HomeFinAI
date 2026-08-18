import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.models import BudgetCreate, BudgetPublic, BudgetsPublic, BudgetUpdate, Message
from app.services import budgets as budget_service

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("/", response_model=BudgetsPublic)
def read_budgets(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    page: int | None = None,
    page_size: int | None = None,
) -> BudgetsPublic:
    return budget_service.list_budgets(
        session,
        owner_id=current_user.id,
        skip=skip,
        limit=limit,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=BudgetPublic)
def create_budget(
    *, session: SessionDep, current_user: CurrentUser, budget_in: BudgetCreate
) -> BudgetPublic:
    return budget_service.create_budget(
        session, owner_id=current_user.id, budget_in=budget_in
    )


@router.put("/{budget_id}", response_model=BudgetPublic)
def update_budget(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    budget_id: uuid.UUID,
    budget_in: BudgetUpdate,
) -> BudgetPublic:
    return budget_service.update_budget(
        session,
        owner_id=current_user.id,
        budget_id=budget_id,
        budget_in=budget_in,
    )


@router.delete("/{budget_id}", response_model=Message)
def delete_budget(
    session: SessionDep, current_user: CurrentUser, budget_id: uuid.UUID
) -> Message:
    return budget_service.delete_budget(
        session, owner_id=current_user.id, budget_id=budget_id
    )
