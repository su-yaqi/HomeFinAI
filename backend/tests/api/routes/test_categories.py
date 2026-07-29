from fastapi.testclient import TestClient

from app.core.config import settings


def test_create_and_read_categories(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    payload = {"name": "Food", "color": "#ff0000"}
    create_response = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=normal_user_token_headers,
        json=payload,
    )
    assert create_response.status_code == 200
    category = create_response.json()
    assert category["name"] == "Food"

    list_response = client.get(
        f"{settings.API_V1_STR}/categories/", headers=normal_user_token_headers
    )
    assert list_response.status_code == 200
    assert list_response.json()["count"] >= 1


def test_read_categories_supports_page_and_page_size(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    for index in range(12):
        create_response = client.post(
            f"{settings.API_V1_STR}/categories/",
            headers=normal_user_token_headers,
            json={"name": f"Paged Category {index}", "color": "#ff0000"},
        )
        assert create_response.status_code == 200

    list_response = client.get(
        f"{settings.API_V1_STR}/categories/?page=2&page_size=10",
        headers=normal_user_token_headers,
    )

    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["count"] >= 12
    assert len(payload["data"]) >= 2
    assert len(payload["data"]) < 10


def test_delete_category_blocked_by_child(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    parent = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=normal_user_token_headers,
        json={"name": "Transport", "color": "#00ff00"},
    ).json()
    child_response = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=normal_user_token_headers,
        json={"name": "Taxi", "color": "#00ff11", "parent_id": parent["id"]},
    )
    assert child_response.status_code == 200

    delete_response = client.delete(
        f"{settings.API_V1_STR}/categories/{parent['id']}",
        headers=normal_user_token_headers,
    )
    assert delete_response.status_code == 400
    assert delete_response.json()["detail"] == "Category has child categories"


def test_categories_reject_invalid_hex_and_parent_cycles(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    invalid_color = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=normal_user_token_headers,
        json={"name": "Invalid Color", "color": "#zzzzzz"},
    )
    assert invalid_color.status_code == 422

    parent = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=normal_user_token_headers,
        json={"name": "Cycle Parent", "color": "#123456"},
    ).json()
    child = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=normal_user_token_headers,
        json={
            "name": "Cycle Child",
            "color": "#abcdef",
            "parent_id": parent["id"],
        },
    ).json()
    cycle_response = client.put(
        f"{settings.API_V1_STR}/categories/{parent['id']}",
        headers=normal_user_token_headers,
        json={"parent_id": child["id"]},
    )
    assert cycle_response.status_code == 400
    assert (
        cycle_response.json()["detail"] == "Category hierarchy cannot contain a cycle"
    )
