from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.models import EntryStatus, TransactionType


def test_dashboard_returns_summary_sections(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    category = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=normal_user_token_headers,
        json={"name": "Dashboard Food", "color": "#222222"},
    ).json()
    budget = client.post(
        f"{settings.API_V1_STR}/budgets/",
        headers=normal_user_token_headers,
        json={"name": "Dashboard Budget", "year": 2026, "period": 1, "amount": 300},
    ).json()
    transaction_response = client.post(
        f"{settings.API_V1_STR}/transactions/",
        headers=normal_user_token_headers,
        json={
            "category_id": category["id"],
            "transaction_type": TransactionType.EXPENSE,
            "amount": 30,
            "budget_id": budget["id"],
            "entry_status": EntryStatus.ENTERED,
            "transaction_date": "2026-05-28",
        },
    )
    assert transaction_response.status_code == 200

    response = client.get(
        f"{settings.API_V1_STR}/dashboard/", headers=normal_user_token_headers
    )
    assert response.status_code == 200
    payload = response.json()
    assert "summary" in payload
    assert "trends" in payload
    assert "category_shares" in payload
    assert "budget_usage" in payload


def test_dashboard_excludes_future_and_other_year_transactions(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    category = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=normal_user_token_headers,
        json={"name": "Dashboard Date Bounds", "color": "#334455"},
    ).json()
    budget = client.post(
        f"{settings.API_V1_STR}/budgets/",
        headers=normal_user_token_headers,
        json={
            "name": "Dashboard Date Budget",
            "year": 2026,
            "period": 1,
            "amount": 300,
        },
    ).json()

    for transaction_date, amount in (
        ("2025-12-31", 20),
        ("2026-07-10", 30),
        ("2026-07-30", 70),
    ):
        response = client.post(
            f"{settings.API_V1_STR}/transactions/",
            headers=normal_user_token_headers,
            json={
                "category_id": category["id"],
                "transaction_type": TransactionType.EXPENSE,
                "amount": amount,
                "budget_id": budget["id"],
                "entry_status": EntryStatus.ENTERED,
                "transaction_date": transaction_date,
            },
        )
        assert response.status_code == 200

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            return cls(2026, 7, 18, 12, 0, tzinfo=tz)

    with patch("app.api.routes.dashboard.datetime", FixedDateTime):
        response = client.get(
            f"{settings.API_V1_STR}/dashboard/",
            headers=normal_user_token_headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["expense"] == 30
    category_share = next(
        item
        for item in payload["category_shares"]
        if item["category_id"] == category["id"]
    )
    assert category_share["amount"] == 30
    budget_usage = next(
        item for item in payload["budget_usage"] if item["budget_id"] == budget["id"]
    )
    assert budget_usage["used_amount"] == 30
