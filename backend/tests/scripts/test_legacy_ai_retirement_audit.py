import pytest

from app.legacy_ai_retirement_audit import (
    CONFIRMATION_VALUE,
    enforce_retirement_confirmation,
)


def test_retirement_gate_passes_without_affected_integrations() -> None:
    enforce_retirement_confirmation([], None)


def test_retirement_gate_requires_exact_confirmation() -> None:
    affected = [{"name": "legacy-client", "is_active": True}]
    with pytest.raises(RuntimeError, match="permanently disabled"):
        enforce_retirement_confirmation(affected, None)
    with pytest.raises(RuntimeError, match="permanently disabled"):
        enforce_retirement_confirmation(affected, "yes")
    enforce_retirement_confirmation(affected, CONFIRMATION_VALUE)
