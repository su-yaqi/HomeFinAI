from fastapi.testclient import TestClient

from app.core.config import settings


def test_agent_budget_crud(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    token_response = client.post(
        f"{settings.API_V1_STR}/system/api-tokens/",
        headers=superuser_token_headers,
        json={"name": "Agent Budget CRUD"},
    )
    assert token_response.status_code == 200
    token = token_response.json()["token"]
    agent_headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        f"{settings.API_V1_STR}/agent/budgets/",
        headers=agent_headers,
        json={
            "name": "Agent Budget",
            "year": 2026,
            "period": 1,
            "amount": 300.5,
        },
    )
    assert create_response.status_code == 200
    budget = create_response.json()
    assert budget["amount"] == 300.5
    assert budget["used_amount"] == 0

    list_response = client.get(
        f"{settings.API_V1_STR}/agent/budgets/",
        headers=agent_headers,
    )
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["count"] == 1
    assert payload["data"][0]["id"] == budget["id"]

    update_response = client.put(
        f"{settings.API_V1_STR}/agent/budgets/{budget['id']}",
        headers=agent_headers,
        json={"amount": 450, "name": "Updated Agent Budget"},
    )
    assert update_response.status_code == 200
    updated_budget = update_response.json()
    assert updated_budget["amount"] == 450
    assert updated_budget["name"] == "Updated Agent Budget"

    delete_response = client.delete(
        f"{settings.API_V1_STR}/agent/budgets/{budget['id']}",
        headers=agent_headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Budget deleted successfully"
