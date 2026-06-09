import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from sqlmodel import col, func, select

from app.api.agent_auth import authenticate_agent
from app.api.deps import SessionDep
from app.models import Budget, BudgetCreate, BudgetPublic, BudgetsPublic, BudgetUpdate, Message, Transaction, TransactionType
from app.utils import amount_to_cents, cents_to_amount, resolve_pagination

router = APIRouter(prefix="/agent/budgets", tags=["agent-budgets"])


def _budget_public_from_row(budget: Budget, used_cents: int | None) -> BudgetPublic:
    return BudgetPublic.model_validate(
        {
            **budget.model_dump(),
            "amount": cents_to_amount(budget.amount_cents),
            "used_amount": cents_to_amount(used_cents or 0),
        }
    )


@router.get("/", response_model=BudgetsPublic)
async def read_agent_budgets(
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
        select(func.count()).select_from(Budget).where(Budget.owner_id == token.created_by)
    ).one()
    budgets = session.exec(
        select(Budget)
        .where(Budget.owner_id == token.created_by)
        .order_by(col(Budget.year).desc(), col(Budget.created_at).desc())
        .offset(offset)
        .limit(max_results)
    ).all()
    budget_ids = [budget.id for budget in budgets]
    usage_map: dict[uuid.UUID, int] = {}
    if budget_ids:
        rows = session.exec(
            select(Transaction.budget_id, func.coalesce(func.sum(Transaction.amount_cents), 0))
            .where(
                Transaction.budget_id.in_(budget_ids),
                Transaction.transaction_type == int(TransactionType.EXPENSE),
            )
            .group_by(Transaction.budget_id)
        ).all()
        usage_map = {budget_id: used for budget_id, used in rows if budget_id is not None}
    return BudgetsPublic(
        data=[_budget_public_from_row(budget, usage_map.get(budget.id)) for budget in budgets],
        count=count,
    )


@router.post("/", response_model=BudgetPublic)
async def create_agent_budget(
    request: Request,
    budget_in: BudgetCreate,
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
    budget = Budget.model_validate(
        budget_in,
        update={
            "owner_id": token.created_by,
            "amount_cents": amount_to_cents(budget_in.amount),
            "period": int(budget_in.period),
        },
    )
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return _budget_public_from_row(budget, 0)


@router.put("/{budget_id}", response_model=BudgetPublic)
async def update_agent_budget(
    request: Request,
    budget_id: uuid.UUID,
    budget_in: BudgetUpdate,
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
    budget = session.get(Budget, budget_id)
    if not budget or budget.owner_id != token.created_by:
        raise HTTPException(status_code=404, detail="Budget not found")
    update_data = budget_in.model_dump(exclude_unset=True)
    if "amount" in update_data and update_data["amount"] is not None:
        update_data["amount_cents"] = amount_to_cents(update_data.pop("amount"))
    if "period" in update_data and update_data["period"] is not None:
        update_data["period"] = int(update_data["period"])
    budget.sqlmodel_update(update_data)
    session.add(budget)
    session.commit()
    session.refresh(budget)
    used = session.exec(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
            Transaction.budget_id == budget.id,
            Transaction.transaction_type == int(TransactionType.EXPENSE),
        )
    ).one()
    return _budget_public_from_row(budget, used)


@router.delete("/{budget_id}", response_model=Message)
async def delete_agent_budget(
    request: Request,
    budget_id: uuid.UUID,
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
    budget = session.get(Budget, budget_id)
    if not budget or budget.owner_id != token.created_by:
        raise HTTPException(status_code=404, detail="Budget not found")
    linked = session.exec(select(Transaction).where(Transaction.budget_id == budget.id)).first()
    if linked:
        raise HTTPException(status_code=400, detail="Budget has related transactions")
    session.delete(budget)
    session.commit()
    return Message(message="Budget deleted successfully")
