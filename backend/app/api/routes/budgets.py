import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import case, col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Budget,
    BudgetCreate,
    BudgetPublic,
    BudgetsPublic,
    BudgetUpdate,
    Transaction,
    TransactionType,
)
from app.utils import amount_to_cents, cents_to_amount, resolve_pagination

router = APIRouter(prefix="/budgets", tags=["budgets"])


def _budget_public_from_row(budget: Budget, used_cents: int | None) -> BudgetPublic:
    return BudgetPublic.model_validate(
        {
            **budget.model_dump(),
            "amount": cents_to_amount(budget.amount_cents),
            "used_amount": cents_to_amount(used_cents or 0),
        }
    )


@router.get("/", response_model=BudgetsPublic)
def read_budgets(
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
    count = session.exec(
        select(func.count()).select_from(Budget).where(Budget.owner_id == current_user.id)
    ).one()
    budgets = session.exec(
        select(Budget)
        .where(Budget.owner_id == current_user.id)
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
def create_budget(
    *, session: SessionDep, current_user: CurrentUser, budget_in: BudgetCreate
) -> Any:
    budget = Budget.model_validate(
        budget_in,
        update={
            "owner_id": current_user.id,
            "amount_cents": amount_to_cents(budget_in.amount),
            "period": int(budget_in.period),
        },
    )
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return _budget_public_from_row(budget, 0)


@router.put("/{budget_id}", response_model=BudgetPublic)
def update_budget(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    budget_id: uuid.UUID,
    budget_in: BudgetUpdate,
) -> Any:
    budget = session.get(Budget, budget_id)
    if not budget or budget.owner_id != current_user.id:
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


@router.delete("/{budget_id}")
def delete_budget(
    session: SessionDep, current_user: CurrentUser, budget_id: uuid.UUID
) -> Any:
    budget = session.get(Budget, budget_id)
    if not budget or budget.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Budget not found")
    linked = session.exec(select(Transaction).where(Transaction.budget_id == budget.id)).first()
    if linked:
        raise HTTPException(status_code=400, detail="Budget has related transactions")
    session.delete(budget)
    session.commit()
    return {"message": "Budget deleted successfully"}
