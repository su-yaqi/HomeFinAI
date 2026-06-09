from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import User
from app.models import EntryStatus, TransactionType
from tests.utils.user import create_random_user


def test_transaction_filters_and_batch_enter(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    category = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=normal_user_token_headers,
        json={"name": "Salary", "color": "#abcdef"},
    ).json()
    created = []
    for day in ["2026-05-27", "2026-05-28"]:
        response = client.post(
            f"{settings.API_V1_STR}/transactions/",
        headers=normal_user_token_headers,
        json={
            "category_id": category["id"],
            "transaction_type": TransactionType.INCOME,
            "amount": 100,
            "entry_status": EntryStatus.PENDING,
            "transaction_date": day,
        },
    )
        assert response.status_code == 200
        created.append(response.json())

    me_response = client.get(
        f"{settings.API_V1_STR}/users/me", headers=normal_user_token_headers
    )
    assert me_response.status_code == 200
    current_user = me_response.json()

    filtered = client.get(
        f"{settings.API_V1_STR}/transactions/?handler_user_id={current_user['id']}&start_date=2026-05-28",
        headers=normal_user_token_headers,
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] == 1

    batch = client.post(
        f"{settings.API_V1_STR}/transactions/batch-enter",
        headers=normal_user_token_headers,
        json={"ids": [created[0]["id"], created[1]["id"]]},
    )
    assert batch.status_code == 200
    assert len(batch.json()["updated_ids"]) == 2


def test_transactions_support_page_size_and_handler_user_linking(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    category = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=normal_user_token_headers,
        json={"name": "Handler Category", "color": "#112233"},
    ).json()
    me_response = client.get(
        f"{settings.API_V1_STR}/users/me", headers=normal_user_token_headers
    )
    assert me_response.status_code == 200
    current_user = me_response.json()

    handler_user = create_random_user(db)
    handler_user.full_name = "Casey Handler"
    db.add(handler_user)
    db.commit()
    db.refresh(handler_user)

    created_ids: list[str] = []
    for index in range(12):
        response = client.post(
            f"{settings.API_V1_STR}/transactions/",
            headers=normal_user_token_headers,
            json={
                "category_id": category["id"],
                "transaction_type": TransactionType.EXPENSE,
                "amount": 20 + index,
                "entry_status": EntryStatus.PENDING,
                "transaction_date": f"2026-05-{index + 1:02d}",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        created_ids.append(payload["id"])
        assert payload["handler_user_id"] == current_user["id"]
        assert payload["handler_display_name"] == (
            current_user["full_name"] or current_user["login_name"]
        )

    update_response = client.put(
        f"{settings.API_V1_STR}/transactions/{created_ids[0]}",
        headers=normal_user_token_headers,
        json={"handler_user_id": str(handler_user.id)},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["handler_user_id"] == str(handler_user.id)
    assert updated["handler_display_name"] == "Casey Handler"

    paged_response = client.get(
        f"{settings.API_V1_STR}/transactions/?page=2&page_size=10",
        headers=normal_user_token_headers,
    )
    assert paged_response.status_code == 200
    paged_payload = paged_response.json()
    assert paged_payload["count"] >= 12
    assert len(paged_payload["data"]) >= 2
    assert len(paged_payload["data"]) < 10

    filtered_response = client.get(
        f"{settings.API_V1_STR}/transactions/?handler_user_id={handler_user.id}",
        headers=normal_user_token_headers,
    )
    assert filtered_response.status_code == 200
    filtered_payload = filtered_response.json()
    assert filtered_payload["count"] == 1
    assert filtered_payload["data"][0]["handler_display_name"] == "Casey Handler"


def test_transactions_support_summary_and_structured_detail(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    category = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=normal_user_token_headers,
        json={"name": "Meals", "color": "#ff6600"},
    ).json()

    create_response = client.post(
        f"{settings.API_V1_STR}/transactions/",
        headers=normal_user_token_headers,
        json={
            "category_id": category["id"],
            "transaction_type": TransactionType.EXPENSE,
            "amount": 45.8,
            "entry_status": EntryStatus.ENTERED,
            "transaction_date": "2026-05-29",
            "summary": "麦当劳",
            "detail": {
                "note": "晚饭",
                "items": [
                    {"name": "双层吉士汉堡套餐", "remark": "加可乐"},
                    {"name": "麦乐鸡"},
                ],
            },
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["summary"] == "麦当劳"
    assert created["detail"]["note"] == "晚饭"
    assert created["detail"]["items"][0]["name"] == "双层吉士汉堡套餐"
    assert created["description"] == "麦当劳"

    update_response = client.put(
        f"{settings.API_V1_STR}/transactions/{created['id']}",
        headers=normal_user_token_headers,
        json={
            "summary": "逛超市",
            "detail": {
                "note": "周末采购",
                "items": [{"name": "牛奶"}, {"name": "鸡蛋"}],
            },
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["summary"] == "逛超市"
    assert updated["detail"]["items"][1]["name"] == "鸡蛋"
    assert updated["description"] == "逛超市"


def test_transactions_reject_invalid_detail_shape(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    category = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=normal_user_token_headers,
        json={"name": "Transport", "color": "#0088ff"},
    ).json()

    response = client.post(
        f"{settings.API_V1_STR}/transactions/",
        headers=normal_user_token_headers,
        json={
            "category_id": category["id"],
            "transaction_type": TransactionType.EXPENSE,
            "amount": 18.6,
            "entry_status": EntryStatus.PENDING,
            "transaction_date": "2026-05-30",
            "summary": "打车",
            "detail": {"items": [{"remark": "缺少名称"}]},
        },
    )
    assert response.status_code == 422
