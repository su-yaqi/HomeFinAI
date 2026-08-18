import uuid
from datetime import date

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.models import (
    Budget,
    Category,
    EntryStatus,
    Message,
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


def _to_public(
    transaction: Transaction, handler_user: User | None = None
) -> TransactionPublic:
    summary = transaction.summary or transaction.description
    handler_display_name = transaction.handler_name or None
    if handler_user:
        handler_display_name = handler_user.full_name or handler_user.login_name
    return TransactionPublic.model_validate(
        {
            **transaction.model_dump(),
            "amount": cents_to_amount(transaction.amount_cents),
            "summary": summary,
            "description": summary,
            "handler_display_name": handler_display_name,
        }
    )


def _validate_links(
    session: Session,
    *,
    owner_id: uuid.UUID,
    category_id: uuid.UUID,
    budget_id: uuid.UUID | None,
) -> None:
    category = session.get(Category, category_id)
    if not category or category.owner_id != owner_id:
        raise HTTPException(status_code=400, detail="Category not found")
    if budget_id:
        budget = session.get(Budget, budget_id)
        if not budget or budget.owner_id != owner_id:
            raise HTTPException(status_code=400, detail="Budget not found")


def _resolve_handler(
    session: Session, *, handler_user_id: uuid.UUID | None, owner_id: uuid.UUID
) -> User:
    handler_user = session.get(User, handler_user_id or owner_id)
    if not handler_user or not handler_user.is_active:
        raise HTTPException(status_code=400, detail="Handler user not found")
    return handler_user


def list_transactions(
    session: Session,
    *,
    owner_id: uuid.UUID,
    skip: int = 0,
    limit: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    transaction_type: TransactionType | None = None,
    category_id: uuid.UUID | None = None,
    entry_status: EntryStatus | None = None,
    handler_user_id: uuid.UUID | None = None,
) -> TransactionsPublic:
    conditions = [Transaction.owner_id == owner_id]
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
    statement = (
        select(Transaction)
        .where(*conditions)
        .order_by(
            col(Transaction.transaction_date).desc(), col(Transaction.created_at).desc()
        )
    )
    if limit is not None:
        offset, max_results = resolve_pagination(
            page=page, page_size=page_size, skip=skip, limit=limit
        )
        statement = statement.offset(offset).limit(max_results)
    transactions = session.exec(statement).all()
    handler_ids = {
        transaction.handler_user_id
        for transaction in transactions
        if transaction.handler_user_id is not None
    }
    handlers = {}
    if handler_ids:
        handlers = {
            user.id: user
            for user in session.exec(
                select(User).where(col(User.id).in_(handler_ids))
            ).all()
        }
    return TransactionsPublic(
        data=[
            _to_public(
                transaction,
                handlers.get(transaction.handler_user_id)
                if transaction.handler_user_id is not None
                else None,
            )
            for transaction in transactions
        ],
        count=count,
    )


def create_transaction(
    session: Session, *, owner_id: uuid.UUID, transaction_in: TransactionCreate
) -> TransactionPublic:
    _validate_links(
        session,
        owner_id=owner_id,
        category_id=transaction_in.category_id,
        budget_id=transaction_in.budget_id,
    )
    handler = _resolve_handler(
        session, handler_user_id=transaction_in.handler_user_id, owner_id=owner_id
    )
    transaction = Transaction.model_validate(
        transaction_in,
        update={
            "owner_id": owner_id,
            "amount_cents": amount_to_cents(transaction_in.amount),
            "transaction_type": int(transaction_in.transaction_type),
            "entry_status": int(transaction_in.entry_status),
            "handler_user_id": handler.id,
            "handler_name": handler.full_name or handler.login_name,
        },
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return _to_public(transaction, handler)


def get_transaction(
    session: Session, *, owner_id: uuid.UUID, transaction_id: uuid.UUID
) -> TransactionPublic:
    transaction = session.get(Transaction, transaction_id)
    if not transaction or transaction.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    handler = (
        session.get(User, transaction.handler_user_id)
        if transaction.handler_user_id is not None
        else None
    )
    return _to_public(transaction, handler)


def update_transaction(
    session: Session,
    *,
    owner_id: uuid.UUID,
    transaction_id: uuid.UUID,
    transaction_in: TransactionUpdate,
) -> TransactionPublic:
    transaction = session.get(Transaction, transaction_id)
    if not transaction or transaction.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    update_data = transaction_in.model_dump(exclude_unset=True)
    _validate_links(
        session,
        owner_id=owner_id,
        category_id=update_data.get("category_id", transaction.category_id),
        budget_id=update_data.get("budget_id", transaction.budget_id),
    )
    if "amount" in update_data:
        amount = update_data.pop("amount")
        update_data["amount_cents"] = amount_to_cents(amount)
    if transaction_type := update_data.get("transaction_type"):
        update_data["transaction_type"] = int(transaction_type)
    if entry_status := update_data.get("entry_status"):
        update_data["entry_status"] = int(entry_status)
    handler: User | None
    if "handler_user_id" in update_data:
        handler = _resolve_handler(
            session,
            handler_user_id=update_data["handler_user_id"],
            owner_id=owner_id,
        )
        update_data["handler_user_id"] = handler.id
        update_data["handler_name"] = handler.full_name or handler.login_name
    else:
        handler = (
            session.get(User, transaction.handler_user_id)
            if transaction.handler_user_id is not None
            else None
        )
    transaction.sqlmodel_update(update_data)
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return _to_public(transaction, handler)


def delete_transaction(
    session: Session, *, owner_id: uuid.UUID, transaction_id: uuid.UUID
) -> Message:
    transaction = session.get(Transaction, transaction_id)
    if not transaction or transaction.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    session.delete(transaction)
    session.commit()
    return Message(message="Transaction deleted successfully")


def batch_enter_transactions(
    session: Session, *, owner_id: uuid.UUID, payload: TransactionBatchEnter
) -> list[uuid.UUID]:
    transactions = session.exec(
        select(Transaction).where(
            Transaction.owner_id == owner_id, col(Transaction.id).in_(payload.ids)
        )
    ).all()
    updated_ids: list[uuid.UUID] = []
    for transaction in transactions:
        transaction.entry_status = int(EntryStatus.ENTERED)
        session.add(transaction)
        updated_ids.append(transaction.id)
    session.commit()
    return updated_ids
