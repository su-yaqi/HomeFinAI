import uuid

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

    blocked_delete = client.delete(
        f"{settings.API_V1_STR}/budgets/{budget['id']}",
        headers=normal_user_token_headers,
    )
    assert blocked_delete.status_code == 400
    assert blocked_delete.json() == {"detail": "Budget has related transactions"}


def test_budget_create_update_paginate_and_delete(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    created_ids: list[str] = []
    for index in range(12):
        create_response = client.post(
            f"{settings.API_V1_STR}/budgets/",
            headers=normal_user_token_headers,
            json={
                "name": f"Budget {index}",
                "year": 2026,
                "period": 1,
                "amount": 100 + index,
            },
        )
        assert create_response.status_code == 200
        created_ids.append(create_response.json()["id"])

    update_response = client.put(
        f"{settings.API_V1_STR}/budgets/{created_ids[0]}",
        headers=normal_user_token_headers,
        json={"name": "Updated Budget", "period": 2, "amount": 321.45},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Budget"
    assert update_response.json()["period"] == 2
    assert update_response.json()["amount"] == 321.45

    page_response = client.get(
        f"{settings.API_V1_STR}/budgets/?page=2&page_size=10",
        headers=normal_user_token_headers,
    )
    assert page_response.status_code == 200
    assert page_response.json()["count"] >= 12
    assert 2 <= len(page_response.json()["data"]) < 10

    delete_response = client.delete(
        f"{settings.API_V1_STR}/budgets/{created_ids[0]}",
        headers=normal_user_token_headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json() == {"message": "Budget deleted successfully"}


def test_budget_update_and_delete_missing(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    missing_id = uuid.uuid4()
    update_response = client.put(
        f"{settings.API_V1_STR}/budgets/{missing_id}",
        headers=normal_user_token_headers,
        json={"name": "Missing"},
    )
    assert update_response.status_code == 404
    assert update_response.json() == {"detail": "Budget not found"}

    delete_response = client.delete(
        f"{settings.API_V1_STR}/budgets/{missing_id}",
        headers=normal_user_token_headers,
    )
    assert delete_response.status_code == 404
    assert delete_response.json() == {"detail": "Budget not found"}
