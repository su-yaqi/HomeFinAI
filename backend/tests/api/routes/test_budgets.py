from fastapi.testclient import TestClient

from app.core.config import settings
from app.models import EntryStatus, TransactionType


def test_budget_used_amount_counts_expense_transactions(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    category = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=normal_user_token_headers,
        json={"name": "Groceries", "color": "#123456"},
    ).json()
    budget = client.post(
        f"{settings.API_V1_STR}/budgets/",
        headers=normal_user_token_headers,
        json={"name": "May Food", "year": 2026, "period": 1, "amount": 500},
    ).json()
    expense_response = client.post(
        f"{settings.API_V1_STR}/transactions/",
        headers=normal_user_token_headers,
        json={
            "category_id": category["id"],
            "transaction_type": TransactionType.EXPENSE,
            "amount": 88.5,
            "budget_id": budget["id"],
            "entry_status": EntryStatus.PENDING,
            "transaction_date": "2026-05-28",
        },
    )
    assert expense_response.status_code == 200

    budgets_response = client.get(
        f"{settings.API_V1_STR}/budgets/", headers=normal_user_token_headers
    )
    assert budgets_response.status_code == 200
    assert budgets_response.json()["data"][0]["used_amount"] >= 88.5
