import uuid

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.models import (
    Budget,
    BudgetCreate,
    BudgetPublic,
    BudgetsPublic,
    BudgetUpdate,
    Message,
    Transaction,
    TransactionType,
)
from app.utils import amount_to_cents, cents_to_amount, resolve_pagination


def _to_public(budget: Budget, used_cents: int | None) -> BudgetPublic:
    return BudgetPublic.model_validate(
        {
            **budget.model_dump(),
            "amount": cents_to_amount(budget.amount_cents),
            "used_amount": cents_to_amount(used_cents or 0),
        }
    )


def list_budgets(
    session: Session,
    *,
    owner_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    page: int | None = None,
    page_size: int | None = None,
) -> BudgetsPublic:
    offset, max_results = resolve_pagination(
        page=page, page_size=page_size, skip=skip, limit=limit
    )
    condition = Budget.owner_id == owner_id
    count = session.exec(
        select(func.count()).select_from(Budget).where(condition)
    ).one()
    budgets = session.exec(
        select(Budget)
        .where(condition)
        .order_by(col(Budget.year).desc(), col(Budget.created_at).desc())
        .offset(offset)
        .limit(max_results)
    ).all()
    budget_ids = [budget.id for budget in budgets]
    usage_map: dict[uuid.UUID, int] = {}
    if budget_ids:
        rows = session.exec(
            select(
                col(Transaction.budget_id),
                func.coalesce(func.sum(Transaction.amount_cents), 0),
            )
            .where(
                col(Transaction.budget_id).in_(budget_ids),
                Transaction.transaction_type == int(TransactionType.EXPENSE),
            )
            .group_by(col(Transaction.budget_id))
        ).all()
        usage_map = {
            budget_id: used for budget_id, used in rows if budget_id is not None
        }
    return BudgetsPublic(
        data=[_to_public(budget, usage_map.get(budget.id)) for budget in budgets],
        count=count,
    )


def create_budget(
    session: Session, *, owner_id: uuid.UUID, budget_in: BudgetCreate
) -> BudgetPublic:
    budget = Budget.model_validate(
        budget_in,
        update={
            "owner_id": owner_id,
            "amount_cents": amount_to_cents(budget_in.amount),
            "period": int(budget_in.period),
        },
    )
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return _to_public(budget, 0)


def update_budget(
    session: Session,
    *,
    owner_id: uuid.UUID,
    budget_id: uuid.UUID,
    budget_in: BudgetUpdate,
) -> BudgetPublic:
    budget = session.get(Budget, budget_id)
    if not budget or budget.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Budget not found")
    update_data = budget_in.model_dump(exclude_unset=True)
    if "amount" in update_data:
        amount = update_data.pop("amount")
        update_data["amount_cents"] = amount_to_cents(amount)
    if period := update_data.get("period"):
        update_data["period"] = int(period)
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
    return _to_public(budget, used)


def delete_budget(
    session: Session, *, owner_id: uuid.UUID, budget_id: uuid.UUID
) -> Message:
    budget = session.get(Budget, budget_id)
    if not budget or budget.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Budget not found")
    if session.exec(
        select(Transaction).where(Transaction.budget_id == budget.id)
    ).first():
        raise HTTPException(status_code=400, detail="Budget has related transactions")
    session.delete(budget)
    session.commit()
    return Message(message="Budget deleted successfully")
