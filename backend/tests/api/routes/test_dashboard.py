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
