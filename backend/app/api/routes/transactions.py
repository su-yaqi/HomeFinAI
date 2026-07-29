import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Budget,
    Category,
    EntryStatus,
    Transaction,
    TransactionBatchEnter,
    TransactionCreate,
    TransactionPublic,
    TransactionsPublic,
    TransactionType,
    TransactionUpdate,
    User,
)
from app.utils import amount_to_cents, cents_to_amount, resolve_pagination

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _handler_display_name(
    handler_user: User | None, handler_name: str | None
) -> str | None:
    if handler_user:
        return handler_user.full_name or handler_user.login_name
    return handler_name or None


def _transaction_public(
    transaction: Transaction, handler_user: User | None = None
) -> TransactionPublic:
    summary = transaction.summary or transaction.description
    return TransactionPublic.model_validate(
        {
            **transaction.model_dump(),
            "amount": cents_to_amount(transaction.amount_cents),
            "summary": summary,
            "description": summary,
            "handler_display_name": _handler_display_name(
                handler_user, transaction.handler_name
            ),
        }
    )


def _validate_transaction_links(
    session: SessionDep,
    current_user: CurrentUser,
    category_id: uuid.UUID,
    budget_id: uuid.UUID | None,
) -> None:
    category = session.get(Category, category_id)
    if not category or category.owner_id != current_user.id:
        raise HTTPException(status_code=400, detail="Category not found")
    if budget_id:
        budget = session.get(Budget, budget_id)
        if not budget or budget.owner_id != current_user.id:
            raise HTTPException(status_code=400, detail="Budget not found")


def _resolve_handler_user(
    session: SessionDep, handler_user_id: uuid.UUID | None, current_user: CurrentUser
) -> User:
    resolved_user_id = handler_user_id or current_user.id
    handler_user = session.get(User, resolved_user_id)
    if not handler_user or not handler_user.is_active:
        raise HTTPException(status_code=400, detail="Handler user not found")
    return handler_user


@router.get("/", response_model=TransactionsPublic)
def read_transactions(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 10,
    page: int | None = None,
    page_size: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    transaction_type: TransactionType | None = None,
    category_id: uuid.UUID | None = None,
    entry_status: EntryStatus | None = None,
    handler_user_id: uuid.UUID | None = None,
) -> Any:
    offset, max_results = resolve_pagination(
        page=page, page_size=page_size, skip=skip, limit=limit
    )
    conditions = [Transaction.owner_id == current_user.id]
    if start_date:
        conditions.append(Transaction.transaction_date >= start_date)
    if end_date:
        conditions.append(Transaction.transaction_date <= end_date)
    if transaction_type:
        conditions.append(Transaction.transaction_type == int(transaction_type))
    if category_id:
        conditions.append(Transaction.category_id == category_id)
    if entry_status:
        conditions.append(Transaction.entry_status == int(entry_status))
    if handler_user_id:
        conditions.append(Transaction.handler_user_id == handler_user_id)

    count = session.exec(
        select(func.count()).select_from(Transaction).where(*conditions)
    ).one()
    transactions = session.exec(
        select(Transaction)
        .where(*conditions)
        .order_by(
            col(Transaction.transaction_date).desc(), col(Transaction.created_at).desc()
        )
        .offset(offset)
        .limit(max_results)
    ).all()
    handler_user_ids = {
        transaction.handler_user_id
        for transaction in transactions
        if transaction.handler_user_id is not None
    }
    handler_users = {}
    if handler_user_ids:
        handler_users = {
            user.id: user
            for user in session.exec(
                select(User).where(col(User.id).in_(handler_user_ids))
            ).all()
        }
    return TransactionsPublic(
        data=[
            _transaction_public(
                transaction,
                handler_users.get(transaction.handler_user_id)
                if transaction.handler_user_id is not None
                else None,
            )
            for transaction in transactions
        ],
        count=count,
    )


@router.post("/", response_model=TransactionPublic)
def create_transaction(
    *, session: SessionDep, current_user: CurrentUser, transaction_in: TransactionCreate
) -> Any:
    _validate_transaction_links(
        session, current_user, transaction_in.category_id, transaction_in.budget_id
    )
    handler_user = _resolve_handler_user(
        session, transaction_in.handler_user_id, current_user
    )
    transaction = Transaction.model_validate(
        transaction_in,
        update={
            "owner_id": current_user.id,
            "amount_cents": amount_to_cents(transaction_in.amount),
            "transaction_type": int(transaction_in.transaction_type),
            "entry_status": int(transaction_in.entry_status),
            "handler_user_id": handler_user.id,
            "handler_name": handler_user.full_name or handler_user.login_name,
        },
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return _transaction_public(transaction, handler_user)


@router.get("/{transaction_id}", response_model=TransactionPublic)
def read_transaction(
    session: SessionDep, current_user: CurrentUser, transaction_id: uuid.UUID
) -> Any:
    transaction = session.get(Transaction, transaction_id)
    if not transaction or transaction.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    handler_user = (
        session.get(User, transaction.handler_user_id)
        if transaction.handler_user_id is not None
        else None
    )
    return _transaction_public(transaction, handler_user)


@router.put("/{transaction_id}", response_model=TransactionPublic)
def update_transaction(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    transaction_id: uuid.UUID,
    transaction_in: TransactionUpdate,
) -> Any:
    transaction = session.get(Transaction, transaction_id)
    if not transaction or transaction.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    update_data = transaction_in.model_dump(exclude_unset=True)
    category_id = update_data.get("category_id", transaction.category_id)
    budget_id = update_data.get("budget_id", transaction.budget_id)
    _validate_transaction_links(session, current_user, category_id, budget_id)
    if "amount" in update_data and update_data["amount"] is not None:
        update_data["amount_cents"] = amount_to_cents(update_data.pop("amount"))
    if (
        "transaction_type" in update_data
        and update_data["transaction_type"] is not None
    ):
        update_data["transaction_type"] = int(update_data["transaction_type"])
    if "entry_status" in update_data and update_data["entry_status"] is not None:
        update_data["entry_status"] = int(update_data["entry_status"])
    handler_user: User | None
    if "handler_user_id" in update_data:
        handler_user = _resolve_handler_user(
            session, update_data["handler_user_id"], current_user
        )
        update_data["handler_user_id"] = handler_user.id
        update_data["handler_name"] = handler_user.full_name or handler_user.login_name
    else:
        handler_user = (
            session.get(User, transaction.handler_user_id)
            if transaction.handler_user_id is not None
            else None
        )
    transaction.sqlmodel_update(update_data)
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return _transaction_public(transaction, handler_user)


@router.delete("/{transaction_id}")
def delete_transaction(
    session: SessionDep, current_user: CurrentUser, transaction_id: uuid.UUID
) -> Any:
    transaction = session.get(Transaction, transaction_id)
    if not transaction or transaction.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    session.delete(transaction)
    session.commit()
    return {"message": "Transaction deleted successfully"}


@router.post("/batch-enter")
def batch_enter_transactions(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    payload: TransactionBatchEnter,
) -> Any:
    statement = select(Transaction).where(
        Transaction.owner_id == current_user.id, col(Transaction.id).in_(payload.ids)
    )
    transactions = session.exec(statement).all()
    updated_ids: list[uuid.UUID] = []
    for transaction in transactions:
        transaction.entry_status = int(EntryStatus.ENTERED)
        session.add(transaction)
        updated_ids.append(transaction.id)
    session.commit()
    return {"updated_ids": updated_ids}
