import uuid
from datetime import date, datetime, timezone
from enum import Enum, IntEnum
from typing import Any, cast

from pydantic import ConfigDict, EmailStr, field_validator, model_validator
from sqlalchemy import CheckConstraint, Column, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    login_name: str = Field(unique=True, index=True, max_length=100)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)

    @model_validator(mode="before")
    @classmethod
    def populate_login_name(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        values = cast(dict[str, Any], data)
        if values.get("login_name"):
            return values
        email = values.get("email")
        if isinstance(email, str) and "@" in email:
            values["login_name"] = email.split("@", 1)[0]
        return values


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    login_name: str | None = Field(default=None, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore[assignment]
    login_name: str | None = Field(default=None, max_length=100)  # type: ignore[assignment]
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)
    login_name: str | None = Field(default=None, max_length=100)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    mfa_secret: str | None = Field(default=None, max_length=255)
    auth_version: int = Field(default=0, nullable=False)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    categories: list["Category"] = Relationship(
        back_populates="owner", cascade_delete=True
    )
    budgets: list["Budget"] = Relationship(back_populates="owner", cascade_delete=True)
    transactions: list["Transaction"] = Relationship(
        back_populates="owner",
        cascade_delete=True,
        sa_relationship_kwargs={"foreign_keys": "[Transaction.owner_id]"},
    )
    handled_transactions: list["Transaction"] = Relationship(
        back_populates="handler_user",
        sa_relationship_kwargs={"foreign_keys": "[Transaction.handler_user_id]"},
    )
    api_tokens: list["ApiToken"] = Relationship(
        back_populates="creator", cascade_delete=True
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    has_mfa: bool = False
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


class HandlerUserOption(SQLModel):
    id: uuid.UUID
    full_name: str | None = None
    login_name: str
    display_name: str


class HandlerUsersPublic(SQLModel):
    data: list[HandlerUserOption]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore[assignment]


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


class BudgetPeriod(IntEnum):
    MONTH = 1
    QUARTER = 2
    YEAR = 3


class TransactionType(IntEnum):
    INCOME = 1
    EXPENSE = 2


class EntryStatus(IntEnum):
    PENDING = 1
    SKIPPED = 2
    ENTERED = 3


class CategoryBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: uuid.UUID | None = Field(default=None, foreign_key="category.id")
    color: str = Field(min_length=4, max_length=20)


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    parent_id: uuid.UUID | None = Field(default=None)
    color: str | None = Field(default=None, min_length=4, max_length=20)


class Category(CategoryBase, table=True):
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_category_owner_name"),
        CheckConstraint(
            "color ~ '^#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?$'",
            name="ck_category_color_hex",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner: User | None = Relationship(back_populates="categories")


class CategoryPublic(CategoryBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class CategoriesPublic(SQLModel):
    data: list[CategoryPublic]
    count: int


class BudgetBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=1900, le=3000)
    period: BudgetPeriod


class BudgetCreate(BudgetBase):
    amount: float = Field(gt=0)


class BudgetUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    year: int | None = Field(default=None, ge=1900, le=3000)
    period: BudgetPeriod | None = None
    amount: float | None = Field(default=None, gt=0)


class Budget(BudgetBase, table=True):
    period: int = Field(nullable=False)  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    amount_cents: int = Field(nullable=False)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner: User | None = Relationship(back_populates="budgets")


class BudgetPublic(BudgetBase):
    id: uuid.UUID
    amount: float
    used_amount: float = 0
    owner_id: uuid.UUID
    created_at: datetime | None = None


class BudgetsPublic(SQLModel):
    data: list[BudgetPublic]
    count: int


def _normalize_transaction_detail(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("detail must be an object")

    normalized: dict[str, Any] = dict(value)
    note = normalized.get("note")
    if note is not None and not isinstance(note, str):
        raise ValueError("detail.note must be a string")

    items = normalized.get("items")
    if items is not None:
        if not isinstance(items, list):
            raise ValueError("detail.items must be a list")
        normalized_items: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("detail.items entries must be objects")
            item_copy = dict(item)
            name = item_copy.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("detail.items entries require a non-empty name")
            item_copy["name"] = name.strip()
            normalized_items.append(item_copy)
        normalized["items"] = normalized_items

    return normalized


def _normalize_transaction_summary_fields(data: object) -> object:
    if not isinstance(data, dict):
        return data
    values = cast(dict[str, Any], data)
    if "summary" not in values and values.get("description"):
        values["summary"] = values["description"]
    if "description" not in values and values.get("summary"):
        values["description"] = values["summary"]
    return values


class TransactionBase(SQLModel):
    model_config = ConfigDict(extra="ignore")  # type: ignore[assignment]

    category_id: uuid.UUID = Field(foreign_key="category.id")
    transaction_type: TransactionType
    budget_id: uuid.UUID | None = Field(default=None, foreign_key="budget.id")
    summary: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    detail: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    entry_status: EntryStatus
    handler_user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id")
    transaction_date: date

    @model_validator(mode="before")
    @classmethod
    def normalize_summary_aliases(cls, data: object) -> object:
        return _normalize_transaction_summary_fields(data)

    @field_validator("detail")
    @classmethod
    def validate_detail(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _normalize_transaction_detail(value)


class TransactionCreate(TransactionBase):
    amount: float = Field(gt=0)


class TransactionUpdate(SQLModel):
    model_config = ConfigDict(extra="ignore")  # type: ignore[assignment]

    category_id: uuid.UUID | None = None
    transaction_type: TransactionType | None = None
    amount: float | None = Field(default=None, gt=0)
    budget_id: uuid.UUID | None = None
    summary: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    detail: dict[str, Any] | None = None
    entry_status: EntryStatus | None = None
    handler_user_id: uuid.UUID | None = None
    transaction_date: date | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_summary_aliases(cls, data: object) -> object:
        return _normalize_transaction_summary_fields(data)

    @field_validator("detail")
    @classmethod
    def validate_detail(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _normalize_transaction_detail(value)


class Transaction(TransactionBase, table=True):
    transaction_type: int = Field(nullable=False)  # type: ignore[assignment]
    entry_status: int = Field(nullable=False)  # type: ignore[assignment]
    handler_name: str | None = Field(default=None, max_length=100)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    amount_cents: int = Field(nullable=False)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner: User | None = Relationship(
        back_populates="transactions",
        sa_relationship_kwargs={"foreign_keys": "[Transaction.owner_id]"},
    )
    handler_user: User | None = Relationship(
        back_populates="handled_transactions",
        sa_relationship_kwargs={"foreign_keys": "[Transaction.handler_user_id]"},
    )


class TransactionPublic(TransactionBase):
    id: uuid.UUID
    amount: float
    owner_id: uuid.UUID
    handler_display_name: str | None = None
    created_at: datetime | None = None


class TransactionsPublic(SQLModel):
    data: list[TransactionPublic]
    count: int


class TransactionBatchEnter(SQLModel):
    ids: list[uuid.UUID] = Field(min_length=1)


class ApiTokenBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    expires_at: datetime | None = None


class ApiTokenCreate(ApiTokenBase):
    generate_secret: bool = False


class ApiToken(ApiTokenBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    token_prefix: str = Field(max_length=20)
    token_hash: str = Field(max_length=255)
    secret_hash: str | None = Field(default=None, max_length=255)
    is_active: bool = True
    created_by: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    last_used_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    creator: User | None = Relationship(back_populates="api_tokens")


class ApiTokenPublic(ApiTokenBase):
    id: uuid.UUID
    token_prefix: str
    is_active: bool
    created_by: uuid.UUID
    last_used_at: datetime | None = None
    created_at: datetime | None = None


class ApiTokensPublic(SQLModel):
    data: list[ApiTokenPublic]
    count: int


class ApiTokenSecretPublic(SQLModel):
    token: str
    secret: str | None = None
    token_prefix: str


class ApiTokenNonce(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("token_id", "nonce", name="uq_apitokennonce_token_nonce"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    token_id: uuid.UUID = Field(
        foreign_key="apitoken.id", nullable=False, ondelete="CASCADE", index=True
    )
    nonce: str = Field(min_length=16, max_length=128)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class DataJobType(str, Enum):
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"


class DataJobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DataJobBase(SQLModel):
    job_type: DataJobType
    status: DataJobStatus = DataJobStatus.PENDING
    template_version: str = Field(default="v1", max_length=20)


class DataJob(DataJobBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_by: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    source_file_path: str | None = Field(default=None, max_length=500)
    result_file_path: str | None = Field(default=None, max_length=500)
    error_file_path: str | None = Field(default=None, max_length=500)
    total_rows: int = 0
    success_rows: int = 0
    failed_rows: int = 0
    skipped_rows: int = 0
    progress_percent: int = 0
    failure_reason: str | None = Field(default=None, max_length=500)
    started_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class DataJobErrorBase(SQLModel):
    sheet_name: str = Field(min_length=1, max_length=100)
    row_number: int = Field(ge=1)
    field_name: str = Field(min_length=1, max_length=100)
    error_message: str = Field(min_length=1, max_length=500)
    raw_key: str | None = Field(default=None, max_length=255)


class DataJobError(DataJobErrorBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_id: uuid.UUID = Field(
        foreign_key="datajob.id", nullable=False, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class DataJobPublic(DataJobBase):
    id: uuid.UUID
    created_by: uuid.UUID
    total_rows: int
    success_rows: int
    failed_rows: int
    skipped_rows: int
    progress_percent: int
    failure_reason: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None
    has_result_file: bool = False
    has_error_file: bool = False


class DataJobsPublic(SQLModel):
    data: list[DataJobPublic]
    count: int


class DashboardSummary(SQLModel):
    income: float
    expense: float
    balance: float


class DashboardTrendPoint(SQLModel):
    month: str
    income: float
    expense: float


class DashboardCategoryShare(SQLModel):
    category_id: uuid.UUID
    category_name: str
    amount: float


class DashboardBudgetUsage(SQLModel):
    budget_id: uuid.UUID
    budget_name: str
    amount: float
    used_amount: float


class DashboardPublic(SQLModel):
    summary: DashboardSummary
    trends: list[DashboardTrendPoint]
    category_shares: list[DashboardCategoryShare]
    budget_usage: list[DashboardBudgetUsage]


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None
    typ: str | None = None
    ver: int = 0


class LoginRequest(SQLModel):
    login_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=6)


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class AdminResetPassword(SQLModel):
    new_password: str = Field(min_length=8, max_length=128)


class MFASecretPublic(SQLModel):
    secret: str


class MFASetupPublic(SQLModel):
    secret: str
    otpauth_uri: str


class MFAEnableRequest(SQLModel):
    secret: str = Field(min_length=16, max_length=255)
    code: str = Field(min_length=6, max_length=6)
