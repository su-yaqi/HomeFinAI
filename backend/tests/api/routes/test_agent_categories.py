from fastapi.testclient import TestClient

from app.core.config import settings


def test_agent_category_crud(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    token_response = client.post(
        f"{settings.API_V1_STR}/system/api-tokens/",
        headers=superuser_token_headers,
        json={"name": "Agent Category CRUD"},
    )
    assert token_response.status_code == 200
    token = token_response.json()["token"]
    agent_headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        f"{settings.API_V1_STR}/agent/categories/",
        headers=agent_headers,
        json={"name": "Agent Category", "color": "#654321"},
    )
    assert create_response.status_code == 200
    category = create_response.json()
    assert category["name"] == "Agent Category"

    list_response = client.get(
        f"{settings.API_V1_STR}/agent/categories/",
        headers=agent_headers,
    )
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["count"] == 1
    assert payload["data"][0]["id"] == category["id"]

    update_response = client.put(
        f"{settings.API_V1_STR}/agent/categories/{category['id']}",
        headers=agent_headers,
        json={"name": "Updated Agent Category", "color": "#123456"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Updated Agent Category"
    assert updated["color"] == "#123456"

    delete_response = client.delete(
        f"{settings.API_V1_STR}/agent/categories/{category['id']}",
        headers=agent_headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Category deleted successfully"
