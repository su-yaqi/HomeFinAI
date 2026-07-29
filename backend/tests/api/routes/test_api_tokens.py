import string

from fastapi.testclient import TestClient

from app.core.config import settings


def test_create_and_disable_api_token(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    create_response = client.post(
        f"{settings.API_V1_STR}/system/api-tokens/",
        headers=superuser_token_headers,
        json={"name": "Agent Access", "generate_secret": True},
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["token"]
    assert created["token_prefix"]

    list_response = client.get(
        f"{settings.API_V1_STR}/system/api-tokens/",
        headers=superuser_token_headers,
    )
    assert list_response.status_code == 200
    token_id = list_response.json()["data"][0]["id"]

    disable_response = client.post(
        f"{settings.API_V1_STR}/system/api-tokens/{token_id}/disable",
        headers=superuser_token_headers,
    )
    assert disable_response.status_code == 200


def test_read_api_tokens_supports_page_and_page_size(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    for index in range(12):
        create_response = client.post(
            f"{settings.API_V1_STR}/system/api-tokens/",
            headers=superuser_token_headers,
            json={"name": f"Paged Token {index}", "generate_secret": False},
        )
        assert create_response.status_code == 200

    list_response = client.get(
        f"{settings.API_V1_STR}/system/api-tokens/?page=2&page_size=10",
        headers=superuser_token_headers,
    )

    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["count"] >= 12
    assert len(payload["data"]) >= 2
    assert len(payload["data"]) < 10


def test_create_api_token_uses_alphanumeric_value_and_can_be_deleted(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    create_response = client.post(
        f"{settings.API_V1_STR}/system/api-tokens/",
        headers=superuser_token_headers,
        json={"name": "Delete Me", "generate_secret": False},
    )
    assert create_response.status_code == 200
    token_payload = create_response.json()
    token = token_payload["token"]
    assert token
    assert set(token).issubset(set(string.ascii_letters + string.digits))

    list_response = client.get(
        f"{settings.API_V1_STR}/system/api-tokens/",
        headers=superuser_token_headers,
    )
    assert list_response.status_code == 200
    token_id = next(
        item["id"]
        for item in list_response.json()["data"]
        if item["token_prefix"] == token_payload["token_prefix"]
    )

    delete_response = client.delete(
        f"{settings.API_V1_STR}/system/api-tokens/{token_id}",
        headers=superuser_token_headers,
    )
    assert delete_response.status_code == 200

    deleted_list_response = client.get(
        f"{settings.API_V1_STR}/system/api-tokens/",
        headers=superuser_token_headers,
    )
    assert delete_response.json() == {"message": "API token deleted successfully"}
    assert all(item["id"] != token_id for item in deleted_list_response.json()["data"])

    agent_response = client.get(
        f"{settings.API_V1_STR}/agent/categories/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert agent_response.status_code == 401
    assert agent_response.json() == {"detail": "Invalid API token"}
