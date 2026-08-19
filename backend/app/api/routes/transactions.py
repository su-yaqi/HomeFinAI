import uuid
from datetime import date

from fastapi import APIRouter
from sqlmodel import SQLModel

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    EntryStatus,
    Message,
    TransactionBatchEnter,
    TransactionCreate,
    TransactionPublic,
    TransactionsPublic,
    TransactionType,
    TransactionUpdate,
)
from app.services import transactions as transaction_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


class TransactionBatchEnterPublic(SQLModel):
    updated_ids: list[uuid.UUID]


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
) -> TransactionsPublic:
    return transaction_service.list_transactions(
        session,
        owner_id=current_user.id,
        skip=skip,
        limit=limit,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        transaction_type=transaction_type,
        category_id=category_id,
        entry_status=entry_status,
        handler_user_id=handler_user_id,
    )


@router.post("/", response_model=TransactionPublic)
def create_transaction(
    *, session: SessionDep, current_user: CurrentUser, transaction_in: TransactionCreate
) -> TransactionPublic:
    return transaction_service.create_transaction(
        session, owner_id=current_user.id, transaction_in=transaction_in
    )


@router.get("/{transaction_id}", response_model=TransactionPublic)
def read_transaction(
    session: SessionDep, current_user: CurrentUser, transaction_id: uuid.UUID
) -> TransactionPublic:
    return transaction_service.get_transaction(
        session, owner_id=current_user.id, transaction_id=transaction_id
    )


@router.put("/{transaction_id}", response_model=TransactionPublic)
def update_transaction(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    transaction_id: uuid.UUID,
    transaction_in: TransactionUpdate,
) -> TransactionPublic:
    return transaction_service.update_transaction(
        session,
        owner_id=current_user.id,
        transaction_id=transaction_id,
        transaction_in=transaction_in,
    )


@router.delete("/{transaction_id}", response_model=Message)
def delete_transaction(
    session: SessionDep, current_user: CurrentUser, transaction_id: uuid.UUID
) -> Message:
    return transaction_service.delete_transaction(
        session, owner_id=current_user.id, transaction_id=transaction_id
    )


@router.post("/batch-enter", response_model=TransactionBatchEnterPublic)
def batch_enter_transactions(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    payload: TransactionBatchEnter,
) -> TransactionBatchEnterPublic:
    return TransactionBatchEnterPublic(
        updated_ids=transaction_service.batch_enter_transactions(
            session, owner_id=current_user.id, payload=payload
        )
    )
