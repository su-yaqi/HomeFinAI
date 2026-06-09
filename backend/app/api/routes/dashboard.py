from datetime import date
from typing import Any

from fastapi import APIRouter
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Budget,
    Category,
    DashboardBudgetUsage,
    DashboardCategoryShare,
    DashboardPublic,
    DashboardSummary,
    DashboardTrendPoint,
    EntryStatus,
    Transaction,
    TransactionType,
)
from app.utils import cents_to_amount

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/", response_model=DashboardPublic)
def read_dashboard(session: SessionDep, current_user: CurrentUser) -> Any:
    today = date.today()
    month_start = date(today.year, today.month, 1)

    month_transactions = session.exec(
        select(Transaction).where(
            Transaction.owner_id == current_user.id,
            Transaction.transaction_date >= month_start,
        )
    ).all()
    income_cents = sum(
        t.amount_cents
        for t in month_transactions
        if t.transaction_type == int(TransactionType.INCOME)
    )
    expense_cents = sum(
        t.amount_cents
        for t in month_transactions
        if t.transaction_type == int(TransactionType.EXPENSE)
    )

    trends: list[DashboardTrendPoint] = []
    for offset in range(5, -1, -1):
        year = today.year
        month = today.month - offset
        while month <= 0:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        start = date(year, month, 1)
        end = date(year + (month // 12), (month % 12) + 1, 1) if month < 12 else date(year + 1, 1, 1)
        rows = session.exec(
            select(Transaction).where(
                Transaction.owner_id == current_user.id,
                Transaction.transaction_date >= start,
                Transaction.transaction_date < end,
            )
        ).all()
        trends.append(
            DashboardTrendPoint(
                month=f"{year:04d}-{month:02d}",
                income=cents_to_amount(
                    sum(
                        t.amount_cents
                        for t in rows
                        if t.transaction_type == int(TransactionType.INCOME)
                    )
                ),
                expense=cents_to_amount(
                    sum(
                        t.amount_cents
                        for t in rows
                        if t.transaction_type == int(TransactionType.EXPENSE)
                    )
                ),
            )
        )

    category_rows = session.exec(
        select(Category.name, Transaction.category_id, func.sum(Transaction.amount_cents))
        .join(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.owner_id == current_user.id,
            Transaction.transaction_type == int(TransactionType.EXPENSE),
            Transaction.transaction_date >= month_start,
        )
        .group_by(Category.name, Transaction.category_id)
    ).all()
    category_shares = [
        DashboardCategoryShare(
            category_id=category_id,
            category_name=name,
            amount=cents_to_amount(amount_cents or 0),
        )
        for name, category_id, amount_cents in category_rows
    ]

    budgets = session.exec(
        select(Budget).where(Budget.owner_id == current_user.id, Budget.year == today.year)
    ).all()
    budget_usage: list[DashboardBudgetUsage] = []
    for budget in budgets:
        used = session.exec(
            select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
                Transaction.budget_id == budget.id,
                Transaction.transaction_type == int(TransactionType.EXPENSE),
            )
        ).one()
        budget_usage.append(
            DashboardBudgetUsage(
                budget_id=budget.id,
                budget_name=budget.name,
                amount=cents_to_amount(budget.amount_cents),
                used_amount=cents_to_amount(used),
            )
        )

    return DashboardPublic(
        summary=DashboardSummary(
            income=cents_to_amount(income_cents),
            expense=cents_to_amount(expense_cents),
            balance=cents_to_amount(income_cents - expense_cents),
        ),
        trends=trends,
        category_shares=category_shares,
        budget_usage=budget_usage,
    )
