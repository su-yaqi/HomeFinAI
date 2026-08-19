from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import jwt
from jwt.exceptions import InvalidTokenError
from mcp.server import MCPServer
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from app.ai_connector.operations import (
    AuthorizedIdentity,
    authorized_identity,
    execute_idempotent_write,
    load_idempotent_replay,
    payload_hash,
)
from app.core.config import settings
from app.core.db import engine
from app.models import (
    Budget,
    BudgetCreate,
    BudgetPeriod,
    BudgetUpdate,
    Category,
    CategoryCreate,
    CategoryUpdate,
    EntryStatus,
    TransactionCreate,
    TransactionType,
    TransactionUpdate,
    User,
    get_datetime_utc,
)
from app.services import budgets as budget_service
from app.services import categories as category_service
from app.services import transactions as transaction_service

TOOL_SCOPES: dict[str, set[str]] = {
    "get_financial_overview": {"finance:read"},
    "search_transactions": {"finance:read"},
    "get_budget_status": {"finance:read"},
    "list_categories": {"finance:read"},
    "get_transaction_options": {"finance:read", "transactions:write"},
    "create_transaction": {"finance:read", "transactions:write"},
    "update_transaction": {"finance:read", "transactions:write"},
    "delete_transaction": {"finance:read", "transactions:delete"},
    "create_budget": {"finance:read", "budgets:write"},
    "update_budget": {"finance:read", "budgets:write"},
    "delete_budget": {"finance:read", "budgets:delete"},
    "create_category": {"finance:read", "categories:write"},
    "update_category": {"finance:read", "categories:write"},
    "delete_category": {"finance:read", "categories:delete"},
}

read_annotations = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)
create_annotations = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)
change_annotations = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=True,
    open_world_hint=False,
)


class ResourceSnapshot(BaseModel):
    fingerprint: str
    preview: dict[str, Any]
    replay_result: dict[str, Any] | None = None


class TransactionCreateInput(BaseModel):
    category_id: uuid.UUID
    transaction_type: TransactionType
    amount: float = Field(gt=0)
    budget_id: uuid.UUID | None = None
    summary: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    detail: dict[str, Any] | None = None
    entry_status: EntryStatus = EntryStatus.PENDING
    handler_user_id: uuid.UUID | None = None
    transaction_date: date | None = None


class BudgetCreateInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0)
    period: BudgetPeriod
    year: int | None = Field(default=None, ge=1900, le=3000)


class CategoryCreateInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: uuid.UUID | None = None
    color: str | None = Field(default=None, min_length=4, max_length=20)


def _business_today() -> date:
    return datetime.now(ZoneInfo(settings.BUSINESS_TIMEZONE)).date()


def _snapshot(preview: dict[str, Any]) -> ResourceSnapshot:
    return ResourceSnapshot(fingerprint=payload_hash(preview), preview=preview)


def _assert_snapshot(expected: ResourceSnapshot, actual: ResourceSnapshot) -> None:
    if expected.fingerprint != actual.fingerprint:
        raise ValueError(
            "The target or one of its dependencies changed after confirmation; review and confirm again"
        )


WRITE_CONFIRMATION_TOKEN_TYPE = "homefin_write_confirmation"
WRITE_CONFIRMATION_TTL = timedelta(minutes=5)


def _confirmation_gate(
    *,
    tool_name: str,
    action: str,
    idempotency_key: str,
    request_payload: dict[str, Any],
    snapshot: ResourceSnapshot,
    confirm: bool,
    confirmation_id: str | None,
) -> dict[str, Any] | None:
    """Return a portable two-phase confirmation response or validate phase two.

    MCP clients such as Codex can call Streamable HTTP tools without providing a
    back-channel for server-initiated ``elicitation/create`` requests.  The
    signed confirmation ID keeps the same exact-operation and five-minute
    guarantees while travelling as ordinary structured tool output.
    """
    if snapshot.replay_result is not None:
        return snapshot.replay_result

    request_digest = payload_hash(request_payload)
    with Session(engine) as session:
        identity = authorized_identity(session, TOOL_SCOPES[tool_name])
        expected = {
            "sub": str(identity.user.id),
            "connection_id": str(identity.connection.id),
            "tool_name": tool_name,
            "idempotency_key": idempotency_key,
            "request_hash": request_digest,
            "snapshot_fingerprint": snapshot.fingerprint,
        }

    if not confirm:
        expires_at = get_datetime_utc() + WRITE_CONFIRMATION_TTL
        token = jwt.encode(
            {
                "typ": WRITE_CONFIRMATION_TOKEN_TYPE,
                **expected,
                "iat": get_datetime_utc(),
                "exp": expires_at,
            },
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        return {
            "status": "input_required",
            "confirmation_id": token,
            "expires_at": expires_at.isoformat(),
            "action": action,
            "preview": snapshot.preview,
            "instructions": (
                "Ask the user to review this exact preview. Only after approval, "
                "call the same tool with unchanged business arguments and "
                "idempotency_key, confirm=true, and this confirmation_id."
            ),
        }

    if not confirmation_id:
        raise ValueError("confirmation_id is required when confirm is true")
    try:
        claims = jwt.decode(
            confirmation_id,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            options={
                "require": [
                    "typ",
                    "sub",
                    "connection_id",
                    "tool_name",
                    "idempotency_key",
                    "request_hash",
                    "snapshot_fingerprint",
                    "iat",
                    "exp",
                ]
            },
        )
    except InvalidTokenError as exc:
        raise ValueError("The write confirmation is invalid or expired") from exc
    if claims.get("typ") != WRITE_CONFIRMATION_TOKEN_TYPE or any(
        claims.get(key) != value for key, value in expected.items()
    ):
        raise ValueError(
            "The write confirmation does not match this user, connection, or exact operation"
        )
    return None


def _replay_snapshot(result: dict[str, Any]) -> ResourceSnapshot:
    return ResourceSnapshot(
        fingerprint="committed-idempotent-replay",
        preview={},
        replay_result=result,
    )


def _owned_category(
    session: Session, identity: AuthorizedIdentity, category_id: uuid.UUID
) -> Category:
    category = session.get(Category, category_id)
    if not category or category.owner_id != identity.user.id:
        raise ValueError("Category not found for the authorized HomeFin user")
    return category


def _owned_budget(
    session: Session, identity: AuthorizedIdentity, budget_id: uuid.UUID
) -> Budget:
    budget = session.get(Budget, budget_id)
    if not budget or budget.owner_id != identity.user.id:
        raise ValueError("Budget not found for the authorized HomeFin user")
    return budget


def _active_handler(
    session: Session, identity: AuthorizedIdentity, handler_id: uuid.UUID | None
) -> User:
    handler = session.get(User, handler_id or identity.user.id)
    if not handler or not handler.is_active:
        raise ValueError("Handler user is not active")
    return handler


def _transaction_create_state(
    session: Session,
    identity: AuthorizedIdentity,
    transaction: TransactionCreateInput,
) -> tuple[TransactionCreate, ResourceSnapshot]:
    category = _owned_category(session, identity, transaction.category_id)
    budget = (
        _owned_budget(session, identity, transaction.budget_id)
        if transaction.budget_id
        else None
    )
    handler = _active_handler(session, identity, transaction.handler_user_id)
    resolved = TransactionCreate.model_validate(
        {
            **transaction.model_dump(),
            "transaction_date": transaction.transaction_date or _business_today(),
            "handler_user_id": handler.id,
        }
    )
    preview = {
        "transaction": resolved.model_dump(mode="json"),
        "category": {"id": str(category.id), "name": category.name},
        "budget": ({"id": str(budget.id), "name": budget.name} if budget else None),
        "handler": {
            "id": str(handler.id),
            "name": handler.full_name or handler.login_name,
        },
    }
    return resolved, _snapshot(preview)


def resolve_create_transaction_snapshot(
    transaction: TransactionCreateInput,
    idempotency_key: str,
) -> ResourceSnapshot:
    with Session(engine) as session:
        identity = authorized_identity(session, TOOL_SCOPES["create_transaction"])
        replay = load_idempotent_replay(
            session,
            identity=identity,
            tool_name="create_transaction",
            idempotency_key=idempotency_key,
            request_payload=transaction.model_dump(mode="json"),
        )
        if replay is not None:
            return _replay_snapshot(replay)
        return _transaction_create_state(session, identity, transaction)[1]


def _transaction_change_state(
    session: Session,
    identity: AuthorizedIdentity,
    transaction_id: uuid.UUID,
    changes: TransactionUpdate | None,
) -> ResourceSnapshot:
    current = transaction_service.get_transaction(
        session, owner_id=identity.user.id, transaction_id=transaction_id
    )
    related: dict[str, Any] = {}
    if changes is not None:
        changed = changes.model_dump(exclude_unset=True)
        if "category_id" in changed and changed["category_id"] is not None:
            category = _owned_category(session, identity, changed["category_id"])
            related["category"] = {"id": str(category.id), "name": category.name}
        if "budget_id" in changed and changed["budget_id"] is not None:
            budget = _owned_budget(session, identity, changed["budget_id"])
            related["budget"] = {"id": str(budget.id), "name": budget.name}
        if "handler_user_id" in changed:
            handler = _active_handler(session, identity, changed["handler_user_id"])
            related["handler"] = {
                "id": str(handler.id),
                "name": handler.full_name or handler.login_name,
            }
    return _snapshot(
        {
            "current": current.model_dump(mode="json"),
            "changes": (
                changes.model_dump(mode="json", exclude_unset=True)
                if changes is not None
                else None
            ),
            "related": related,
        }
    )


def resolve_update_transaction_snapshot(
    transaction_id: uuid.UUID, changes: TransactionUpdate, idempotency_key: str
) -> ResourceSnapshot:
    if not changes.model_fields_set:
        raise ValueError("At least one transaction field must be provided")
    with Session(engine) as session:
        identity = authorized_identity(session, TOOL_SCOPES["update_transaction"])
        replay = load_idempotent_replay(
            session,
            identity=identity,
            tool_name="update_transaction",
            idempotency_key=idempotency_key,
            request_payload={
                "transaction_id": transaction_id,
                "changes": changes.model_dump(mode="json", exclude_unset=True),
            },
        )
        if replay is not None:
            return _replay_snapshot(replay)
        return _transaction_change_state(session, identity, transaction_id, changes)


def resolve_delete_transaction_snapshot(
    transaction_id: uuid.UUID,
    idempotency_key: str,
) -> ResourceSnapshot:
    with Session(engine) as session:
        identity = authorized_identity(session, TOOL_SCOPES["delete_transaction"])
        replay = load_idempotent_replay(
            session,
            identity=identity,
            tool_name="delete_transaction",
            idempotency_key=idempotency_key,
            request_payload={"transaction_id": transaction_id},
        )
        if replay is not None:
            return _replay_snapshot(replay)
        return _transaction_change_state(session, identity, transaction_id, None)


def _budget_state(
    session: Session,
    identity: AuthorizedIdentity,
    budget_id: uuid.UUID,
    changes: BudgetUpdate | None,
) -> ResourceSnapshot:
    current = budget_service.list_budgets(
        session, owner_id=identity.user.id, limit=10000
    )
    budget = next((item for item in current.data if item.id == budget_id), None)
    if budget is None:
        raise ValueError("Budget not found for the authorized HomeFin user")
    return _snapshot(
        {
            "current": budget.model_dump(mode="json"),
            "changes": (
                changes.model_dump(mode="json", exclude_unset=True)
                if changes is not None
                else None
            ),
        }
    )


def _budget_create_state(budget: BudgetCreateInput) -> ResourceSnapshot:
    resolved = BudgetCreate(
        name=budget.name,
        amount=budget.amount,
        period=budget.period,
        year=budget.year or _business_today().year,
    )
    return _snapshot({"budget": resolved.model_dump(mode="json")})


def resolve_create_budget_snapshot(
    budget: BudgetCreateInput, idempotency_key: str
) -> ResourceSnapshot:
    with Session(engine) as session:
        identity = authorized_identity(session, TOOL_SCOPES["create_budget"])
        replay = load_idempotent_replay(
            session,
            identity=identity,
            tool_name="create_budget",
            idempotency_key=idempotency_key,
            request_payload=budget.model_dump(mode="json"),
        )
        if replay is not None:
            return _replay_snapshot(replay)
    return _budget_create_state(budget)


def resolve_update_budget_snapshot(
    budget_id: uuid.UUID, changes: BudgetUpdate, idempotency_key: str
) -> ResourceSnapshot:
    if not changes.model_fields_set:
        raise ValueError("At least one budget field must be provided")
    with Session(engine) as session:
        identity = authorized_identity(session, TOOL_SCOPES["update_budget"])
        replay = load_idempotent_replay(
            session,
            identity=identity,
            tool_name="update_budget",
            idempotency_key=idempotency_key,
            request_payload={
                "budget_id": budget_id,
                "changes": changes.model_dump(mode="json", exclude_unset=True),
            },
        )
        if replay is not None:
            return _replay_snapshot(replay)
        return _budget_state(session, identity, budget_id, changes)


def resolve_delete_budget_snapshot(
    budget_id: uuid.UUID, idempotency_key: str
) -> ResourceSnapshot:
    with Session(engine) as session:
        identity = authorized_identity(session, TOOL_SCOPES["delete_budget"])
        replay = load_idempotent_replay(
            session,
            identity=identity,
            tool_name="delete_budget",
            idempotency_key=idempotency_key,
            request_payload={"budget_id": budget_id},
        )
        if replay is not None:
            return _replay_snapshot(replay)
        return _budget_state(session, identity, budget_id, None)


def _category_state(
    session: Session,
    identity: AuthorizedIdentity,
    category_id: uuid.UUID,
    changes: CategoryUpdate | None,
) -> ResourceSnapshot:
    category = _owned_category(session, identity, category_id)
    related: dict[str, Any] = {}
    if changes is not None:
        changed = changes.model_dump(exclude_unset=True)
        if "parent_id" in changed and changed["parent_id"] is not None:
            parent = _owned_category(session, identity, changed["parent_id"])
            related["parent"] = {"id": str(parent.id), "name": parent.name}
    return _snapshot(
        {
            "current": category.model_dump(mode="json"),
            "changes": (
                changes.model_dump(mode="json", exclude_unset=True)
                if changes is not None
                else None
            ),
            "related": related,
        }
    )


def _category_create_state(
    session: Session,
    identity: AuthorizedIdentity,
    category: CategoryCreateInput,
) -> ResourceSnapshot:
    related: dict[str, Any] = {}
    if category.parent_id:
        parent = _owned_category(session, identity, category.parent_id)
        related["parent"] = {"id": str(parent.id), "name": parent.name}
    resolved = CategoryCreate(
        name=category.name,
        parent_id=category.parent_id,
        color=category.color or "#64748b",
    )
    return _snapshot({"category": resolved.model_dump(mode="json"), "related": related})


def resolve_create_category_snapshot(
    category: CategoryCreateInput,
    idempotency_key: str,
) -> ResourceSnapshot:
    with Session(engine) as session:
        identity = authorized_identity(session, TOOL_SCOPES["create_category"])
        replay = load_idempotent_replay(
            session,
            identity=identity,
            tool_name="create_category",
            idempotency_key=idempotency_key,
            request_payload=category.model_dump(mode="json"),
        )
        if replay is not None:
            return _replay_snapshot(replay)
        return _category_create_state(session, identity, category)


def resolve_update_category_snapshot(
    category_id: uuid.UUID, changes: CategoryUpdate, idempotency_key: str
) -> ResourceSnapshot:
    if not changes.model_fields_set:
        raise ValueError("At least one category field must be provided")
    with Session(engine) as session:
        identity = authorized_identity(session, TOOL_SCOPES["update_category"])
        replay = load_idempotent_replay(
            session,
            identity=identity,
            tool_name="update_category",
            idempotency_key=idempotency_key,
            request_payload={
                "category_id": category_id,
                "changes": changes.model_dump(mode="json", exclude_unset=True),
            },
        )
        if replay is not None:
            return _replay_snapshot(replay)
        return _category_state(session, identity, category_id, changes)


def resolve_delete_category_snapshot(
    category_id: uuid.UUID, idempotency_key: str
) -> ResourceSnapshot:
    with Session(engine) as session:
        identity = authorized_identity(session, TOOL_SCOPES["delete_category"])
        replay = load_idempotent_replay(
            session,
            identity=identity,
            tool_name="delete_category",
            idempotency_key=idempotency_key,
            request_payload={"category_id": category_id},
        )
        if replay is not None:
            return _replay_snapshot(replay)
        return _category_state(session, identity, category_id, None)


def register_write_tools(server: MCPServer[Any]) -> None:
    @server.tool(annotations=read_annotations, structured_output=True)
    def get_transaction_options() -> dict[str, Any]:
        """Return exact IDs and labels allowed when creating or updating transactions."""
        with Session(engine) as session:
            identity = authorized_identity(
                session, TOOL_SCOPES["get_transaction_options"]
            )
            categories = session.exec(
                select(Category)
                .where(Category.owner_id == identity.user.id)
                .order_by(col(Category.name))
            ).all()
            budgets = session.exec(
                select(Budget)
                .where(Budget.owner_id == identity.user.id)
                .order_by(col(Budget.year).desc(), col(Budget.name))
            ).all()
            handlers = session.exec(
                select(User)
                .where(col(User.is_active).is_(True))
                .order_by(col(User.login_name))
            ).all()
        return {
            "categories": [
                {"id": str(item.id), "name": item.name, "parent_id": item.parent_id}
                for item in categories
            ],
            "budgets": [
                {"id": str(item.id), "name": item.name, "year": item.year}
                for item in budgets
            ],
            "handlers": [
                {
                    "id": str(item.id),
                    "name": item.full_name or item.login_name,
                }
                for item in handlers
            ],
            "transaction_types": [item.name for item in TransactionType],
            "entry_statuses": [item.name for item in EntryStatus],
        }

    @server.tool(annotations=create_annotations, structured_output=True)
    def create_transaction(
        transaction: TransactionCreateInput,
        idempotency_key: str,
        confirm: bool = False,
        confirmation_id: str | None = None,
    ) -> dict[str, Any]:
        """Create one transaction after HomeFin obtains exact user confirmation."""
        request_payload = transaction.model_dump(mode="json")
        snapshot = resolve_create_transaction_snapshot(transaction, idempotency_key)
        gate = _confirmation_gate(
            tool_name="create_transaction",
            action=f"create transaction {transaction.model_dump_json()}",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            snapshot=snapshot,
            confirm=confirm,
            confirmation_id=confirmation_id,
        )
        if gate is not None:
            return gate

        def write(
            session: Session, identity: AuthorizedIdentity
        ) -> tuple[uuid.UUID, dict[str, Any]]:
            transaction_in, current = _transaction_create_state(
                session, identity, transaction
            )
            _assert_snapshot(snapshot, current)
            result = transaction_service.create_transaction(
                session,
                owner_id=identity.user.id,
                transaction_in=transaction_in,
                commit=False,
            )
            payload = result.model_dump(mode="json")
            return result.id, payload

        return execute_idempotent_write(
            required_scopes=TOOL_SCOPES["create_transaction"],
            tool_name="create_transaction",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            resource_type="transaction",
            write=write,
        )

    @server.tool(annotations=change_annotations, structured_output=True)
    def update_transaction(
        transaction_id: uuid.UUID,
        changes: TransactionUpdate,
        idempotency_key: str,
        confirm: bool = False,
        confirmation_id: str | None = None,
    ) -> dict[str, Any]:
        """Update explicit fields on one transaction after user confirmation."""
        request_payload = {
            "transaction_id": transaction_id,
            "changes": changes.model_dump(mode="json", exclude_unset=True),
        }
        snapshot = resolve_update_transaction_snapshot(
            transaction_id, changes, idempotency_key
        )
        gate = _confirmation_gate(
            tool_name="update_transaction",
            action=(
                f"update transaction {transaction_id} with "
                f"{changes.model_dump_json(exclude_unset=True)}"
            ),
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            snapshot=snapshot,
            confirm=confirm,
            confirmation_id=confirmation_id,
        )
        if gate is not None:
            return gate

        def write(
            session: Session, identity: AuthorizedIdentity
        ) -> tuple[uuid.UUID, dict[str, Any]]:
            current = _transaction_change_state(
                session, identity, transaction_id, changes
            )
            _assert_snapshot(snapshot, current)
            result = transaction_service.update_transaction(
                session,
                owner_id=identity.user.id,
                transaction_id=transaction_id,
                transaction_in=changes,
                commit=False,
            )
            return result.id, result.model_dump(mode="json")

        return execute_idempotent_write(
            required_scopes=TOOL_SCOPES["update_transaction"],
            tool_name="update_transaction",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            resource_type="transaction",
            write=write,
        )

    @server.tool(annotations=change_annotations, structured_output=True)
    def delete_transaction(
        transaction_id: uuid.UUID,
        idempotency_key: str,
        confirm: bool = False,
        confirmation_id: str | None = None,
    ) -> dict[str, Any]:
        """Permanently delete one transaction after user confirmation."""
        request_payload = {"transaction_id": transaction_id}
        snapshot = resolve_delete_transaction_snapshot(transaction_id, idempotency_key)
        gate = _confirmation_gate(
            tool_name="delete_transaction",
            action=f"permanently delete transaction {transaction_id}",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            snapshot=snapshot,
            confirm=confirm,
            confirmation_id=confirmation_id,
        )
        if gate is not None:
            return gate

        def write(
            session: Session, identity: AuthorizedIdentity
        ) -> tuple[uuid.UUID, dict[str, Any]]:
            current = _transaction_change_state(session, identity, transaction_id, None)
            _assert_snapshot(snapshot, current)
            transaction_service.delete_transaction(
                session,
                owner_id=identity.user.id,
                transaction_id=transaction_id,
                commit=False,
            )
            return transaction_id, {
                "deleted": True,
                "transaction_id": str(transaction_id),
                "deleted_resource": current.preview["current"],
            }

        return execute_idempotent_write(
            required_scopes=TOOL_SCOPES["delete_transaction"],
            tool_name="delete_transaction",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            resource_type="transaction",
            write=write,
        )

    @server.tool(annotations=create_annotations, structured_output=True)
    def create_budget(
        budget: BudgetCreateInput,
        idempotency_key: str,
        confirm: bool = False,
        confirmation_id: str | None = None,
    ) -> dict[str, Any]:
        """Create one budget after HomeFin obtains exact user confirmation."""
        request_payload = budget.model_dump(mode="json")
        snapshot = resolve_create_budget_snapshot(budget, idempotency_key)
        gate = _confirmation_gate(
            tool_name="create_budget",
            action=f"create budget {budget.model_dump_json()}",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            snapshot=snapshot,
            confirm=confirm,
            confirmation_id=confirmation_id,
        )
        if gate is not None:
            return gate

        def write(
            session: Session, identity: AuthorizedIdentity
        ) -> tuple[uuid.UUID, dict[str, Any]]:
            current = _budget_create_state(budget)
            _assert_snapshot(snapshot, current)
            budget_in = BudgetCreate.model_validate(current.preview["budget"])
            result = budget_service.create_budget(
                session,
                owner_id=identity.user.id,
                budget_in=budget_in,
                commit=False,
            )
            payload = result.model_dump(mode="json")
            payload["remaining_amount"] = result.amount - result.used_amount
            return result.id, payload

        return execute_idempotent_write(
            required_scopes=TOOL_SCOPES["create_budget"],
            tool_name="create_budget",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            resource_type="budget",
            write=write,
        )

    @server.tool(annotations=change_annotations, structured_output=True)
    def update_budget(
        budget_id: uuid.UUID,
        changes: BudgetUpdate,
        idempotency_key: str,
        confirm: bool = False,
        confirmation_id: str | None = None,
    ) -> dict[str, Any]:
        """Update explicit fields on one budget after user confirmation."""
        request_payload = {
            "budget_id": budget_id,
            "changes": changes.model_dump(mode="json", exclude_unset=True),
        }
        snapshot = resolve_update_budget_snapshot(budget_id, changes, idempotency_key)
        gate = _confirmation_gate(
            tool_name="update_budget",
            action=(
                f"update budget {budget_id} with "
                f"{changes.model_dump_json(exclude_unset=True)}"
            ),
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            snapshot=snapshot,
            confirm=confirm,
            confirmation_id=confirmation_id,
        )
        if gate is not None:
            return gate

        def write(
            session: Session, identity: AuthorizedIdentity
        ) -> tuple[uuid.UUID, dict[str, Any]]:
            current = _budget_state(session, identity, budget_id, changes)
            _assert_snapshot(snapshot, current)
            result = budget_service.update_budget(
                session,
                owner_id=identity.user.id,
                budget_id=budget_id,
                budget_in=changes,
                commit=False,
            )
            payload = result.model_dump(mode="json")
            payload["remaining_amount"] = result.amount - result.used_amount
            return result.id, payload

        return execute_idempotent_write(
            required_scopes=TOOL_SCOPES["update_budget"],
            tool_name="update_budget",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            resource_type="budget",
            write=write,
        )

    @server.tool(annotations=change_annotations, structured_output=True)
    def delete_budget(
        budget_id: uuid.UUID,
        idempotency_key: str,
        confirm: bool = False,
        confirmation_id: str | None = None,
    ) -> dict[str, Any]:
        """Permanently delete one unreferenced budget after user confirmation."""
        request_payload = {"budget_id": budget_id}
        snapshot = resolve_delete_budget_snapshot(budget_id, idempotency_key)
        gate = _confirmation_gate(
            tool_name="delete_budget",
            action=f"permanently delete budget {budget_id}",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            snapshot=snapshot,
            confirm=confirm,
            confirmation_id=confirmation_id,
        )
        if gate is not None:
            return gate

        def write(
            session: Session, identity: AuthorizedIdentity
        ) -> tuple[uuid.UUID, dict[str, Any]]:
            current = _budget_state(session, identity, budget_id, None)
            _assert_snapshot(snapshot, current)
            budget_service.delete_budget(
                session,
                owner_id=identity.user.id,
                budget_id=budget_id,
                commit=False,
            )
            return budget_id, {
                "deleted": True,
                "budget_id": str(budget_id),
                "deleted_resource": current.preview["current"],
            }

        return execute_idempotent_write(
            required_scopes=TOOL_SCOPES["delete_budget"],
            tool_name="delete_budget",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            resource_type="budget",
            write=write,
        )

    @server.tool(annotations=create_annotations, structured_output=True)
    def create_category(
        category: CategoryCreateInput,
        idempotency_key: str,
        confirm: bool = False,
        confirmation_id: str | None = None,
    ) -> dict[str, Any]:
        """Create one category after HomeFin obtains exact user confirmation."""
        request_payload = category.model_dump(mode="json")
        snapshot = resolve_create_category_snapshot(category, idempotency_key)
        gate = _confirmation_gate(
            tool_name="create_category",
            action=f"create category {category.model_dump_json()}",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            snapshot=snapshot,
            confirm=confirm,
            confirmation_id=confirmation_id,
        )
        if gate is not None:
            return gate

        def write(
            session: Session, identity: AuthorizedIdentity
        ) -> tuple[uuid.UUID, dict[str, Any]]:
            current = _category_create_state(session, identity, category)
            _assert_snapshot(snapshot, current)
            category_in = CategoryCreate.model_validate(current.preview["category"])
            result = category_service.create_category(
                session,
                owner_id=identity.user.id,
                category_in=category_in,
                commit=False,
            )
            return result.id, result.model_dump(mode="json")

        return execute_idempotent_write(
            required_scopes=TOOL_SCOPES["create_category"],
            tool_name="create_category",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            resource_type="category",
            write=write,
        )

    @server.tool(annotations=change_annotations, structured_output=True)
    def update_category(
        category_id: uuid.UUID,
        changes: CategoryUpdate,
        idempotency_key: str,
        confirm: bool = False,
        confirmation_id: str | None = None,
    ) -> dict[str, Any]:
        """Update explicit fields on one category after user confirmation."""
        request_payload = {
            "category_id": category_id,
            "changes": changes.model_dump(mode="json", exclude_unset=True),
        }
        snapshot = resolve_update_category_snapshot(
            category_id, changes, idempotency_key
        )
        gate = _confirmation_gate(
            tool_name="update_category",
            action=(
                f"update category {category_id} with "
                f"{changes.model_dump_json(exclude_unset=True)}"
            ),
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            snapshot=snapshot,
            confirm=confirm,
            confirmation_id=confirmation_id,
        )
        if gate is not None:
            return gate

        def write(
            session: Session, identity: AuthorizedIdentity
        ) -> tuple[uuid.UUID, dict[str, Any]]:
            current = _category_state(session, identity, category_id, changes)
            _assert_snapshot(snapshot, current)
            result = category_service.update_category(
                session,
                owner_id=identity.user.id,
                category_id=category_id,
                category_in=changes,
                commit=False,
            )
            return result.id, result.model_dump(mode="json")

        return execute_idempotent_write(
            required_scopes=TOOL_SCOPES["update_category"],
            tool_name="update_category",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            resource_type="category",
            write=write,
        )

    @server.tool(annotations=change_annotations, structured_output=True)
    def delete_category(
        category_id: uuid.UUID,
        idempotency_key: str,
        confirm: bool = False,
        confirmation_id: str | None = None,
    ) -> dict[str, Any]:
        """Permanently delete one unreferenced category after user confirmation."""
        request_payload = {"category_id": category_id}
        snapshot = resolve_delete_category_snapshot(category_id, idempotency_key)
        gate = _confirmation_gate(
            tool_name="delete_category",
            action=f"permanently delete category {category_id}",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            snapshot=snapshot,
            confirm=confirm,
            confirmation_id=confirmation_id,
        )
        if gate is not None:
            return gate

        def write(
            session: Session, identity: AuthorizedIdentity
        ) -> tuple[uuid.UUID, dict[str, Any]]:
            current = _category_state(session, identity, category_id, None)
            _assert_snapshot(snapshot, current)
            category_service.delete_category(
                session,
                owner_id=identity.user.id,
                category_id=category_id,
                commit=False,
            )
            return category_id, {
                "deleted": True,
                "category_id": str(category_id),
                "deleted_resource": current.preview["current"],
            }

        return execute_idempotent_write(
            required_scopes=TOOL_SCOPES["delete_category"],
            tool_name="delete_category",
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            resource_type="category",
            write=write,
        )
