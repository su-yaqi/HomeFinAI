import secrets
import warnings
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    SESSION_COOKIE_NAME: str = "session_token"
    CSRF_COOKIE_NAME: str = "csrf_token"
    CSRF_HEADER_NAME: str = "X-CSRF-Token"
    FRONTEND_HOST: str = "http://localhost:5173"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    DATA_JOBS_STORAGE_DIR: str = "/tmp/homefin-data-jobs"
    DATA_JOB_MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024
    DATA_JOB_MAX_UNCOMPRESSED_BYTES: int = 100 * 1024 * 1024
    DATA_JOB_MAX_ARCHIVE_FILES: int = 100
    DATA_JOB_MAX_ACTIVE_JOBS: int = 2
    DATA_JOB_RETENTION_DAYS: int = 30
    DATA_JOB_STALE_MINUTES: int = 60
    BUSINESS_TIMEZONE: str = "Asia/Shanghai"
    MCP_RESOURCE_URL: str = "http://127.0.0.1:8000/mcp"
    OAUTH_ISSUER_URL: str = "http://127.0.0.1:8000/"
    AI_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    AI_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    AI_AUTHORIZATION_CODE_EXPIRE_MINUTES: int = 5
    AI_CIMD_ALLOWED_HOSTS: Annotated[list[str] | str, BeforeValidator(parse_cors)] = [
        "chatgpt.com"
    ]

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        normalized = (value or "").strip().lower()
        placeholder_prefixes = (
            "changethis",
            "replace-with",
            "replace_me",
            "replace-me",
            "<",
        )
        if not normalized or normalized.startswith(placeholder_prefixes):
            message = (
                f"The value of {var_name} is empty or still a placeholder; "
                "replace it with a strong secret before deployment."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    def _check_secret_length(
        self, var_name: str, value: str | None, *, minimum: int
    ) -> None:
        if value and len(value) < minimum:
            message = f"The value of {var_name} must be at least {minimum} characters."
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )
        self._check_secret_length("SECRET_KEY", self.SECRET_KEY, minimum=32)
        self._check_secret_length(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD, minimum=12
        )
        self._check_secret_length(
            "POSTGRES_PASSWORD", self.POSTGRES_PASSWORD, minimum=12
        )

        if self.ENVIRONMENT != "local":
            sensitive_values = {
                self.SECRET_KEY,
                self.POSTGRES_PASSWORD,
                self.FIRST_SUPERUSER_PASSWORD,
            }
            if len(sensitive_values) != 3:
                raise ValueError(
                    "Security-sensitive credentials must use distinct values."
                )

        if self.DATA_JOB_MAX_UPLOAD_BYTES <= 0:
            raise ValueError("DATA_JOB_MAX_UPLOAD_BYTES must be greater than zero")
        if self.DATA_JOB_MAX_UNCOMPRESSED_BYTES < self.DATA_JOB_MAX_UPLOAD_BYTES:
            raise ValueError(
                "DATA_JOB_MAX_UNCOMPRESSED_BYTES must be at least DATA_JOB_MAX_UPLOAD_BYTES"
            )
        if self.DATA_JOB_MAX_ARCHIVE_FILES <= 0 or self.DATA_JOB_MAX_ACTIVE_JOBS <= 0:
            raise ValueError("Data job limits must be greater than zero")
        if self.DATA_JOB_RETENTION_DAYS <= 0 or self.DATA_JOB_STALE_MINUTES <= 0:
            raise ValueError("Data job retention values must be greater than zero")
        try:
            ZoneInfo(self.BUSINESS_TIMEZONE)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("BUSINESS_TIMEZONE must be a valid IANA timezone") from exc

        self.OAUTH_ISSUER_URL = self.OAUTH_ISSUER_URL.rstrip("/") + "/"
        resource = urlsplit(self.MCP_RESOURCE_URL)
        issuer = urlsplit(self.OAUTH_ISSUER_URL)
        loopback_hosts = {"127.0.0.1", "::1", "localhost"}
        for name, parsed in (
            ("MCP_RESOURCE_URL", resource),
            ("OAUTH_ISSUER_URL", issuer),
        ):
            if not parsed.scheme or not parsed.hostname:
                raise ValueError(f"{name} must be an absolute URL")
            if parsed.scheme != "https" and parsed.hostname not in loopback_hosts:
                raise ValueError(f"{name} must use HTTPS outside loopback")
            if parsed.query or parsed.fragment:
                raise ValueError(f"{name} must not contain query or fragment")
        if resource.path.rstrip("/") != "/mcp":
            raise ValueError("MCP_RESOURCE_URL path must be /mcp")
        if issuer.path not in {"", "/"}:
            raise ValueError("OAUTH_ISSUER_URL must not contain a path")
        if not self.AI_CIMD_ALLOWED_HOSTS:
            raise ValueError("AI_CIMD_ALLOWED_HOSTS must not be empty")
        if (
            self.AI_ACCESS_TOKEN_EXPIRE_MINUTES <= 0
            or self.AI_REFRESH_TOKEN_EXPIRE_DAYS <= 0
            or self.AI_AUTHORIZATION_CODE_EXPIRE_MINUTES <= 0
        ):
            raise ValueError("AI OAuth token lifetimes must be greater than zero")

        return self


settings = Settings()  # type: ignore
