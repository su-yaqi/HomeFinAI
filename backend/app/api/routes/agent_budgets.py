import uuid

from fastapi import APIRouter

from app.api.agent_auth import AgentToken
from app.api.deps import SessionDep
from app.models import BudgetCreate, BudgetPublic, BudgetsPublic, BudgetUpdate, Message
from app.services import budgets as budget_service

router = APIRouter(prefix="/agent/budgets", tags=["agent-budgets"])


@router.get("/", response_model=BudgetsPublic)
def read_agent_budgets(
    session: SessionDep,
    token: AgentToken,
    skip: int = 0,
    limit: int = 100,
    page: int | None = None,
    page_size: int | None = None,
) -> BudgetsPublic:
    return budget_service.list_budgets(
        session,
        owner_id=token.created_by,
        skip=skip,
        limit=limit,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=BudgetPublic)
def create_agent_budget(
    budget_in: BudgetCreate, session: SessionDep, token: AgentToken
) -> BudgetPublic:
    return budget_service.create_budget(
        session, owner_id=token.created_by, budget_in=budget_in
    )


@router.put("/{budget_id}", response_model=BudgetPublic)
def update_agent_budget(
    budget_id: uuid.UUID,
    budget_in: BudgetUpdate,
    session: SessionDep,
    token: AgentToken,
) -> BudgetPublic:
    return budget_service.update_budget(
        session,
        owner_id=token.created_by,
        budget_id=budget_id,
        budget_in=budget_in,
    )


@router.delete("/{budget_id}", response_model=Message)
def delete_agent_budget(
    budget_id: uuid.UUID, session: SessionDep, token: AgentToken
) -> Message:
    return budget_service.delete_budget(
        session, owner_id=token.created_by, budget_id=budget_id
    )
