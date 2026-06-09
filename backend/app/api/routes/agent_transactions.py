import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from sqlmodel import select

from app.api.agent_auth import authenticate_agent
from app.api.deps import SessionDep
from app.models import (
    Message,
    Transaction,
    TransactionCreate,
    TransactionPublic,
    TransactionUpdate,
    TransactionsPublic,
    User,
)
from app.utils import amount_to_cents, cents_to_amount

router = APIRouter(prefix="/agent/transactions", tags=["agent-transactions"])


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
            "handler_display_name": (
                (handler_user.full_name or handler_user.login_name)
                if handler_user
                else transaction.handler_name
            ),
        }
    )


@router.get("/", response_model=TransactionsPublic)
async def read_agent_transactions(
    request: Request,
    session: SessionDep,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
    x_api_secret: str | None = Header(default=None),
    x_timestamp: str | None = Header(default=None),
    x_signature: str | None = Header(default=None),
) -> Any:
    body_text = (await request.body()).decode()
    token = authenticate_agent(session, request, body_text, authorization, x_api_token, x_api_secret, x_timestamp, x_signature)
    transactions = session.exec(select(Transaction).where(Transaction.owner_id == token.created_by)).all()
    handler_user_ids = {
        transaction.handler_user_id
        for transaction in transactions
        if transaction.handler_user_id is not None
    }
    handler_users = {}
    if handler_user_ids:
        handler_users = {
            user.id: user
            for user in session.exec(select(User).where(User.id.in_(handler_user_ids))).all()
        }
    return TransactionsPublic(
        data=[
            _transaction_public(
                transaction, handler_users.get(transaction.handler_user_id)
            )
            for transaction in transactions
        ],
        count=len(transactions),
    )


@router.post("/", response_model=TransactionPublic)
async def create_agent_transaction(
    request: Request,
    transaction_in: TransactionCreate,
    session: SessionDep,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
    x_api_secret: str | None = Header(default=None),
    x_timestamp: str | None = Header(default=None),
    x_signature: str | None = Header(default=None),
) -> Any:
    body_text = (await request.body()).decode()
    token = authenticate_agent(session, request, body_text, authorization, x_api_token, x_api_secret, x_timestamp, x_signature)
    requested_handler_id = transaction_in.handler_user_id or token.created_by
    handler_user = session.get(User, requested_handler_id)
    if not handler_user or not handler_user.is_active:
        raise HTTPException(status_code=400, detail="Handler user not found")
    transaction = Transaction.model_validate(
        transaction_in,
        update={
            "owner_id": token.created_by,
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
async def read_agent_transaction(
    request: Request,
    transaction_id: uuid.UUID,
    session: SessionDep,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
    x_api_secret: str | None = Header(default=None),
    x_timestamp: str | None = Header(default=None),
    x_signature: str | None = Header(default=None),
) -> Any:
    body_text = (await request.body()).decode()
    token = authenticate_agent(session, request, body_text, authorization, x_api_token, x_api_secret, x_timestamp, x_signature)
    transaction = session.get(Transaction, transaction_id)
    if not transaction or transaction.owner_id != token.created_by:
        raise HTTPException(status_code=404, detail="Transaction not found")
    handler_user = (
        session.get(User, transaction.handler_user_id)
        if transaction.handler_user_id is not None
        else None
    )
    return _transaction_public(transaction, handler_user)


@router.put("/{transaction_id}", response_model=TransactionPublic)
async def update_agent_transaction(
    request: Request,
    transaction_id: uuid.UUID,
    transaction_in: TransactionUpdate,
    session: SessionDep,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
    x_api_secret: str | None = Header(default=None),
    x_timestamp: str | None = Header(default=None),
    x_signature: str | None = Header(default=None),
) -> Any:
    body_text = (await request.body()).decode()
    token = authenticate_agent(session, request, body_text, authorization, x_api_token, x_api_secret, x_timestamp, x_signature)
    transaction = session.get(Transaction, transaction_id)
    if not transaction or transaction.owner_id != token.created_by:
        raise HTTPException(status_code=404, detail="Transaction not found")
    update_data = transaction_in.model_dump(exclude_unset=True)
    if "amount" in update_data and update_data["amount"] is not None:
        update_data["amount_cents"] = amount_to_cents(update_data.pop("amount"))
    if "transaction_type" in update_data and update_data["transaction_type"] is not None:
        update_data["transaction_type"] = int(update_data["transaction_type"])
    if "entry_status" in update_data and update_data["entry_status"] is not None:
        update_data["entry_status"] = int(update_data["entry_status"])
    if "handler_user_id" in update_data:
        resolved_handler_id = update_data["handler_user_id"] or token.created_by
        handler_user = session.get(User, resolved_handler_id)
        if not handler_user or not handler_user.is_active:
            raise HTTPException(status_code=400, detail="Handler user not found")
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


@router.delete("/{transaction_id}", response_model=Message)
async def delete_agent_transaction(
    request: Request,
    transaction_id: uuid.UUID,
    session: SessionDep,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
    x_api_secret: str | None = Header(default=None),
    x_timestamp: str | None = Header(default=None),
    x_signature: str | None = Header(default=None),
) -> Any:
    body_text = (await request.body()).decode()
    token = authenticate_agent(session, request, body_text, authorization, x_api_token, x_api_secret, x_timestamp, x_signature)
    transaction = session.get(Transaction, transaction_id)
    if not transaction or transaction.owner_id != token.created_by:
        raise HTTPException(status_code=404, detail="Transaction not found")
    session.delete(transaction)
    session.commit()
    return Message(message="Transaction deleted successfully")
