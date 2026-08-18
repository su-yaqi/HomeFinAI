from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.request_state import RequestStateSecurity
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import ToolAnnotations
from pydantic import AnyHttpUrl
from sqlalchemy import and_
from sqlmodel import Session, col, func, select
from starlette.applications import Starlette
from starlette.types import Receive, Scope, Send

from app.ai_connector.oauth import oauth_provider
from app.ai_connector.operations import ToolScopeVisibilityMiddleware
from app.ai_connector.write_tools import TOOL_SCOPES, register_write_tools
from app.core.config import settings
from app.core.db import engine
from app.models import (
    Budget,
    Category,
    EntryStatus,
    Transaction,
    TransactionType,
    User,
)
from app.services import budgets as budget_service
from app.services import categories as category_service
from app.services import transactions as transaction_service
from app.utils import cents_to_amount

SERVER_INSTRUCTIONS = (
    "HomeFin provides private household finance tools. Amounts are in yuan and dates use the configured "
    f"business timezone ({settings.BUSINESS_TIMEZONE}). Never infer access to another user: every result is "
    "restricted to the HomeFin user who authorized this connection. Read tools do not change data. Every "
    "write or delete requires HomeFin input_required confirmation and an idempotency key; never claim a write "
    "succeeded until the tool returns a committed result."
)

read_annotations = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)

mcp_server = MCPServer(
    name="homefin",
    title="HomeFin",
    description="Private household finance MCP connector",
    instructions=SERVER_INSTRUCTIONS,
    version="0.9.0",
    token_verifier=oauth_provider,
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(settings.OAUTH_ISSUER_URL),
        resource_server_url=AnyHttpUrl(settings.MCP_RESOURCE_URL),
        required_scopes=["finance:read"],
    ),
    request_state_security=RequestStateSecurity(
        keys=[
            hashlib.sha256(
                f"{settings.SECRET_KEY}:homefin-mcp-request-state".encode()
            ).digest()
        ],
        ttl=300,
        audience="homefin",
    ),
    middleware=[ToolScopeVisibilityMiddleware(TOOL_SCOPES)],
)


def _authorized_user(session: Session, required_scopes: set[str]) -> User:
    access = get_access_token()
    if (
        not access
        or not required_scopes.issubset(set(access.scopes))
        or not access.subject
    ):
        raise PermissionError("The AI connection lacks the required HomeFin scope")
    user = session.get(User, uuid.UUID(access.subject))
    if not user or not user.is_active:
        raise PermissionError("The HomeFin user is not active")
    return user


def _period_range(
    period: Literal[
        "current_month", "last_month", "current_year", "last_6_months", "custom"
    ],
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date]:
    today = datetime.now(ZoneInfo(settings.BUSINESS_TIMEZONE)).date()
    month_start = date(today.year, today.month, 1)
    if period == "custom":
        if not start_date or not end_date:
            raise ValueError("custom requires start_date and end_date")
        start, end = start_date, end_date
    elif start_date or end_date:
        raise ValueError("start_date and end_date are only valid with custom")
    elif period == "current_month":
        start, end = month_start, today
    elif period == "last_month":
        previous_end = month_start - timedelta(days=1)
        start, end = date(previous_end.year, previous_end.month, 1), previous_end
    elif period == "current_year":
        start, end = date(today.year, 1, 1), today
    else:
        month_index = today.year * 12 + today.month - 6
        start = date(month_index // 12, month_index % 12 + 1, 1)
        end = today
    if start > end or (end - start).days > 366:
        raise ValueError(
            "The requested range must be ordered and no longer than 366 days"
        )
    return start, end


@mcp_server.tool(annotations=read_annotations, structured_output=True)
def get_financial_overview(
    period: Literal[
        "current_month", "last_month", "current_year", "last_6_months", "custom"
    ] = "current_month",
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, object]:
    """Return income, expense, balance, category share, and budget use for a date range."""
    start, end = _period_range(period, start_date, end_date)
    with Session(engine) as session:
        user = _authorized_user(session, {"finance:read"})
        totals = dict(
            session.exec(
                select(
                    col(Transaction.transaction_type),
                    func.coalesce(func.sum(Transaction.amount_cents), 0),
                )
                .where(
                    Transaction.owner_id == user.id,
                    Transaction.transaction_date >= start,
                    Transaction.transaction_date <= end,
                )
                .group_by(col(Transaction.transaction_type))
            ).all()
        )
        income = totals.get(int(TransactionType.INCOME), 0)
        expense = totals.get(int(TransactionType.EXPENSE), 0)
        categories = session.exec(
            select(Category.name, func.sum(Transaction.amount_cents))
            .join(Category, col(Category.id) == col(Transaction.category_id))
            .where(
                Transaction.owner_id == user.id,
                Transaction.transaction_type == int(TransactionType.EXPENSE),
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end,
            )
            .group_by(col(Category.name))
        ).all()
        budgets = session.exec(
            select(Budget, func.coalesce(func.sum(Transaction.amount_cents), 0))
            .outerjoin(
                Transaction,
                and_(
                    col(Transaction.budget_id) == col(Budget.id),
                    col(Transaction.transaction_type) == int(TransactionType.EXPENSE),
                    col(Transaction.transaction_date) >= start,
                    col(Transaction.transaction_date) <= end,
                ),
            )
            .where(Budget.owner_id == user.id)
            .group_by(col(Budget.id))
        ).all()
        trend_rows = session.exec(
            select(
                func.date_trunc("month", Transaction.transaction_date).label("month"),
                col(Transaction.transaction_type),
                func.coalesce(func.sum(Transaction.amount_cents), 0),
            )
            .where(
                Transaction.owner_id == user.id,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end,
            )
            .group_by("month", col(Transaction.transaction_type))
            .order_by("month")
        ).all()
    trend_map: dict[str, dict[str, int]] = {}
    for month, transaction_type, amount in trend_rows:
        key = month.date().isoformat()
        point = trend_map.setdefault(key, {"income_cents": 0, "expense_cents": 0})
        if transaction_type == int(TransactionType.INCOME):
            point["income_cents"] = amount or 0
        else:
            point["expense_cents"] = amount or 0
    return {
        "amount_unit": "yuan",
        "business_timezone": settings.BUSINESS_TIMEZONE,
        "filters": {
            "period": period,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "summary": {
            "income": cents_to_amount(income),
            "expense": cents_to_amount(expense),
            "balance": cents_to_amount(income - expense),
        },
        "trends": [
            {
                "period_start": period_start,
                "income": cents_to_amount(point["income_cents"]),
                "expense": cents_to_amount(point["expense_cents"]),
                "balance": cents_to_amount(
                    point["income_cents"] - point["expense_cents"]
                ),
            }
            for period_start, point in trend_map.items()
        ],
        "category_shares": [
            {"category_name": name, "amount": cents_to_amount(amount or 0)}
            for name, amount in categories
        ],
        "budget_usage": [
            {
                "budget_id": str(budget.id),
                "budget_name": budget.name,
                "amount": cents_to_amount(budget.amount_cents),
                "used_amount": cents_to_amount(used or 0),
            }
            for budget, used in budgets
        ],
    }


@mcp_server.tool(annotations=read_annotations, structured_output=True)
def search_transactions(
    keyword: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    transaction_type: TransactionType | None = None,
    category_id: uuid.UUID | None = None,
    budget_id: uuid.UUID | None = None,
    entry_status: EntryStatus | None = None,
    handler_user_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, object]:
    """Search the authorized user's transactions with bounded structured filters."""
    if page_size not in {10, 20, 50, 100} or page < 1:
        raise ValueError(
            "page must be positive and page_size must be 10, 20, 50, or 100"
        )
    business_today = datetime.now(ZoneInfo(settings.BUSINESS_TIMEZONE)).date()
    effective_end_date = end_date or business_today
    if start_date and start_date > effective_end_date:
        raise ValueError("start_date must not be after the effective end_date")
    with Session(engine) as session:
        user = _authorized_user(session, {"finance:read"})
        if category_id:
            category = session.get(Category, category_id)
            if not category or category.owner_id != user.id:
                raise ValueError("category_id is not available to the authorized user")
        if budget_id:
            budget = session.get(Budget, budget_id)
            if not budget or budget.owner_id != user.id:
                raise ValueError("budget_id is not available to the authorized user")
        if handler_user_id:
            handler = session.get(User, handler_user_id)
            if not handler or not handler.is_active:
                raise ValueError("handler_user_id is not an active handler")
        result = transaction_service.list_transactions(
            session,
            owner_id=user.id,
            limit=page_size,
            page=page,
            page_size=page_size,
            start_date=start_date,
            end_date=effective_end_date,
            transaction_type=transaction_type,
            category_id=category_id,
            budget_id=budget_id,
            entry_status=entry_status,
            handler_user_id=handler_user_id,
            keyword=keyword,
        )
    return {
        "amount_unit": "yuan",
        "business_timezone": settings.BUSINESS_TIMEZONE,
        "page": page,
        "page_size": page_size,
        "count": result.count,
        "filters": {
            "keyword": keyword,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": effective_end_date.isoformat(),
            "transaction_type": transaction_type,
            "category_id": str(category_id) if category_id else None,
            "budget_id": str(budget_id) if budget_id else None,
            "entry_status": entry_status,
            "handler_user_id": str(handler_user_id) if handler_user_id else None,
        },
        "data": [item.model_dump(mode="json") for item in result.data],
    }


@mcp_server.tool(annotations=read_annotations, structured_output=True)
def get_budget_status(
    year: int | None = None, page: int = 1, page_size: int = 20
) -> dict[str, object]:
    """Return budget amount, used amount, remaining amount, and usage ratio."""
    business_year = year or datetime.now(ZoneInfo(settings.BUSINESS_TIMEZONE)).year
    if not 2000 <= business_year <= 2100 or page_size not in {10, 20, 50, 100}:
        raise ValueError("Invalid year or page_size")
    with Session(engine) as session:
        user = _authorized_user(session, {"finance:read"})
        result = budget_service.list_budgets(
            session,
            owner_id=user.id,
            page=page,
            page_size=page_size,
            limit=page_size,
            year=business_year,
        )
    data = []
    for item in result.data:
        remaining = item.amount - item.used_amount
        data.append(
            {
                **item.model_dump(mode="json"),
                "remaining_amount": round(remaining, 2),
                "usage_ratio": round(item.used_amount / item.amount, 4)
                if item.amount
                else None,
            }
        )
    return {
        "amount_unit": "yuan",
        "year": business_year,
        "data": data,
        "count": result.count,
    }


@mcp_server.tool(annotations=read_annotations, structured_output=True)
def list_categories(page: int = 1, page_size: int = 50) -> dict[str, object]:
    """List the authorized user's categories and stable parent paths."""
    if page < 1 or page_size not in {10, 20, 50, 100}:
        raise ValueError("Invalid pagination")
    with Session(engine) as session:
        user = _authorized_user(session, {"finance:read"})
        result = category_service.list_categories(
            session, owner_id=user.id, page=page, page_size=page_size, limit=page_size
        )
        all_categories = session.exec(
            select(Category).where(Category.owner_id == user.id)
        ).all()
        category_map = {row.id: row for row in all_categories}
        data = []
        for row in result.data:
            names = [row.name]
            seen = {row.id}
            parent_id = row.parent_id
            while parent_id is not None:
                if parent_id in seen or parent_id not in category_map:
                    raise ValueError("Category hierarchy is inconsistent")
                parent = category_map[parent_id]
                seen.add(parent.id)
                names.append(parent.name)
                parent_id = parent.parent_id
            data.append(
                {**row.model_dump(mode="json"), "path": " / ".join(reversed(names))}
            )
    return {"page": page, "page_size": page_size, "count": result.count, "data": data}


register_write_tools(mcp_server)


def create_mcp_app() -> Starlette:
    parsed = urlsplit(settings.MCP_RESOURCE_URL)
    host = parsed.netloc
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return mcp_server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[host],
            allowed_origins=[origin, settings.FRONTEND_HOST.rstrip("/")],
        ),
        host=parsed.hostname or "127.0.0.1",
    )


class MCPApplication:
    def __init__(self) -> None:
        self._app: Starlette | None = None

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        app = create_mcp_app()
        self._app = app
        try:
            async with app.router.lifespan_context(app):
                yield
        finally:
            self._app = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self._app is None:
            raise RuntimeError("HomeFin MCP application is not running")
        await self._app(scope, receive, send)


mcp_app = MCPApplication()
