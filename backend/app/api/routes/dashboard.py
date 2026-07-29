from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import and_
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.models import (
    Budget,
    Category,
    DashboardBudgetUsage,
    DashboardCategoryShare,
    DashboardPublic,
    DashboardSummary,
    DashboardTrendPoint,
    Transaction,
    TransactionType,
)
from app.utils import cents_to_amount

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _shift_month(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


@router.get("/", response_model=DashboardPublic)
def read_dashboard(session: SessionDep, current_user: CurrentUser) -> Any:
    today = datetime.now(ZoneInfo(settings.BUSINESS_TIMEZONE)).date()
    month_start = date(today.year, today.month, 1)
    current_period_end = today + timedelta(days=1)

    month_totals = dict(
        session.exec(
            select(
                col(Transaction.transaction_type),
                func.coalesce(func.sum(Transaction.amount_cents), 0),
            )
            .where(
                Transaction.owner_id == current_user.id,
                Transaction.transaction_date >= month_start,
                Transaction.transaction_date < current_period_end,
            )
            .group_by(col(Transaction.transaction_type))
        ).all()
    )
    income_cents = month_totals.get(int(TransactionType.INCOME), 0)
    expense_cents = month_totals.get(int(TransactionType.EXPENSE), 0)

    trend_start = _shift_month(month_start, -5)
    month_key_expression = func.to_char(Transaction.transaction_date, "YYYY-MM").label(
        "month_key"
    )
    trend_rows = session.exec(
        select(
            month_key_expression,
            col(Transaction.transaction_type),
            func.coalesce(func.sum(Transaction.amount_cents), 0),
        )
        .where(
            Transaction.owner_id == current_user.id,
            Transaction.transaction_date >= trend_start,
            Transaction.transaction_date < current_period_end,
        )
        .group_by(
            month_key_expression,
            col(Transaction.transaction_type),
        )
    ).all()
    trend_totals = {
        (month_key, transaction_type): amount_cents
        for month_key, transaction_type, amount_cents in trend_rows
    }
    trends: list[DashboardTrendPoint] = []
    for offset in range(6):
        start = _shift_month(trend_start, offset)
        month_key = start.strftime("%Y-%m")
        trends.append(
            DashboardTrendPoint(
                month=month_key,
                income=cents_to_amount(
                    trend_totals.get((month_key, int(TransactionType.INCOME)), 0)
                ),
                expense=cents_to_amount(
                    trend_totals.get((month_key, int(TransactionType.EXPENSE)), 0)
                ),
            )
        )

    category_rows = session.exec(
        select(
            Category.name, Transaction.category_id, func.sum(Transaction.amount_cents)
        )
        .join(Category, col(Category.id) == col(Transaction.category_id))
        .where(
            Transaction.owner_id == current_user.id,
            Transaction.transaction_type == int(TransactionType.EXPENSE),
            Transaction.transaction_date >= month_start,
            Transaction.transaction_date < current_period_end,
        )
        .group_by(col(Category.name), col(Transaction.category_id))
    ).all()
    category_shares = [
        DashboardCategoryShare(
            category_id=category_id,
            category_name=name,
            amount=cents_to_amount(amount_cents or 0),
        )
        for name, category_id, amount_cents in category_rows
    ]

    year_start = date(today.year, 1, 1)
    budget_rows = session.exec(
        select(Budget, func.coalesce(func.sum(Transaction.amount_cents), 0))
        .outerjoin(
            Transaction,
            and_(
                col(Transaction.budget_id) == col(Budget.id),
                col(Transaction.transaction_type) == int(TransactionType.EXPENSE),
                col(Transaction.transaction_date) >= year_start,
                col(Transaction.transaction_date) < current_period_end,
            ),
        )
        .where(Budget.owner_id == current_user.id, Budget.year == today.year)
        .group_by(col(Budget.id))
    ).all()
    budget_usage = [
        DashboardBudgetUsage(
            budget_id=budget.id,
            budget_name=budget.name,
            amount=cents_to_amount(budget.amount_cents),
            used_amount=cents_to_amount(used),
        )
        for budget, used in budget_rows
    ]

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
