import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "PROJECT_NAME": "HomeFin",
        "ENVIRONMENT": "production",
        "SECRET_KEY": "secret-key-that-is-longer-than-thirty-two-characters",
        "FIRST_SUPERUSER": "admin@example.com",
        "FIRST_SUPERUSER_PASSWORD": "strong-admin-password",
        "POSTGRES_SERVER": "db",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "strong-database-password",
        "POSTGRES_DB": "app",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_production_rejects_documented_placeholder_secrets() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        _production_settings(
            SECRET_KEY="replace-with-a-long-random-secret-key",
            FIRST_SUPERUSER_PASSWORD="replace-with-a-strong-admin-password",
            POSTGRES_PASSWORD="replace-with-a-strong-database-password",
        )


def test_production_rejects_short_or_reused_secrets() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        _production_settings(SECRET_KEY="short-secret")

    reused = "shared-secret-value-that-is-long-enough"
    with pytest.raises(ValidationError, match="distinct"):
        _production_settings(
            SECRET_KEY=reused,
            FIRST_SUPERUSER_PASSWORD=reused,
        )


def test_settings_reject_invalid_data_job_limits_and_timezone() -> None:
    with pytest.raises(
        ValidationError,
        match="DATA_JOB_MAX_UNCOMPRESSED_BYTES must be at least",
    ):
        _production_settings(
            DATA_JOB_MAX_UPLOAD_BYTES=10,
            DATA_JOB_MAX_UNCOMPRESSED_BYTES=9,
        )

    with pytest.raises(ValidationError, match="valid IANA timezone"):
        _production_settings(BUSINESS_TIMEZONE="Mars/Olympus_Mons")
