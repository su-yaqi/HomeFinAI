import uuid

from fastapi import APIRouter

from app.api.agent_auth import AgentToken
from app.api.deps import SessionDep
from app.models import (
    Message,
    TransactionCreate,
    TransactionPublic,
    TransactionsPublic,
    TransactionUpdate,
)
from app.services import transactions as transaction_service

router = APIRouter(prefix="/agent/transactions", tags=["agent-transactions"])


@router.get("/", response_model=TransactionsPublic)
def read_agent_transactions(
    session: SessionDep, token: AgentToken
) -> TransactionsPublic:
    return transaction_service.list_transactions(session, owner_id=token.created_by)


@router.post("/", response_model=TransactionPublic)
def create_agent_transaction(
    transaction_in: TransactionCreate, session: SessionDep, token: AgentToken
) -> TransactionPublic:
    return transaction_service.create_transaction(
        session, owner_id=token.created_by, transaction_in=transaction_in
    )


@router.get("/{transaction_id}", response_model=TransactionPublic)
def read_agent_transaction(
    transaction_id: uuid.UUID, session: SessionDep, token: AgentToken
) -> TransactionPublic:
    return transaction_service.get_transaction(
        session, owner_id=token.created_by, transaction_id=transaction_id
    )


@router.put("/{transaction_id}", response_model=TransactionPublic)
def update_agent_transaction(
    transaction_id: uuid.UUID,
    transaction_in: TransactionUpdate,
    session: SessionDep,
    token: AgentToken,
) -> TransactionPublic:
    return transaction_service.update_transaction(
        session,
        owner_id=token.created_by,
        transaction_id=transaction_id,
        transaction_in=transaction_in,
    )


@router.delete("/{transaction_id}", response_model=Message)
def delete_agent_transaction(
    transaction_id: uuid.UUID, session: SessionDep, token: AgentToken
) -> Message:
    return transaction_service.delete_transaction(
        session, owner_id=token.created_by, transaction_id=transaction_id
    )
