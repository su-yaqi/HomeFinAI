import hashlib
import hmac
import secrets
import time

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import EntryStatus, TransactionType
from tests.utils.user import create_random_user


def _signed_agent_headers(
    *, token: str, secret: str, path: str, timestamp: int, nonce: str | None = None
) -> dict[str, str]:
    timestamp_text = str(timestamp)
    nonce = nonce or secrets.token_hex(16)
    signature = hmac.new(
        secret.encode(),
        msg=f"{timestamp_text}:{nonce}:GET:{path}:".encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return {
        "Authorization": f"Bearer {token}",
        "X-API-Secret": secret,
        "X-Timestamp": timestamp_text,
        "X-Nonce": nonce,
        "X-Signature": signature,
    }


def test_agent_token_with_secret_requires_fresh_hmac(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    token_response = client.post(
        f"{settings.API_V1_STR}/system/api-tokens/",
        headers=superuser_token_headers,
        json={"name": "Signed Agent", "generate_secret": True},
    )
    assert token_response.status_code == 200
    credentials = token_response.json()
    path = f"{settings.API_V1_STR}/agent/categories/"

    unsigned_response = client.get(
        path,
        headers={"Authorization": f"Bearer {credentials['token']}"},
    )
    assert unsigned_response.status_code == 401

    stale_headers = _signed_agent_headers(
        token=credentials["token"],
        secret=credentials["secret"],
        path=path,
        timestamp=int(time.time()) - 600,
    )
    stale_response = client.get(path, headers=stale_headers)
    assert stale_response.status_code == 401
    assert stale_response.json() == {"detail": "Expired HMAC timestamp"}

    valid_headers = _signed_agent_headers(
        token=credentials["token"],
        secret=credentials["secret"],
        path=path,
        timestamp=int(time.time()),
    )
    valid_response = client.get(path, headers=valid_headers)
    assert valid_response.status_code == 200

    replay_response = client.get(path, headers=valid_headers)
    assert replay_response.status_code == 401
    assert replay_response.json() == {"detail": "Replayed HMAC request"}


def test_agent_transaction_crud(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    category = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=superuser_token_headers,
        json={"name": "Agent Category", "color": "#654321"},
    ).json()
    token_response = client.post(
        f"{settings.API_V1_STR}/system/api-tokens/",
        headers=superuser_token_headers,
        json={"name": "Agent CRUD"},
    )
    assert token_response.status_code == 200
    token = token_response.json()["token"]
    agent_headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        f"{settings.API_V1_STR}/agent/transactions/",
        headers=agent_headers,
        json={
            "category_id": category["id"],
            "transaction_type": TransactionType.EXPENSE,
            "amount": 12.34,
            "entry_status": EntryStatus.PENDING,
            "transaction_date": "2026-05-28",
            "summary": "打车",
            "detail": {"note": "从公司回家", "items": [{"name": "出租车"}]},
        },
    )
    assert create_response.status_code == 200
    transaction = create_response.json()
    assert transaction["amount"] == 12.34
    assert transaction["handler_user_id"]
    assert transaction["summary"] == "打车"
    assert transaction["detail"]["items"][0]["name"] == "出租车"
    assert transaction["description"] == "打车"

    read_response = client.get(
        f"{settings.API_V1_STR}/agent/transactions/{transaction['id']}",
        headers=agent_headers,
    )
    assert read_response.status_code == 200

    update_response = client.put(
        f"{settings.API_V1_STR}/agent/transactions/{transaction['id']}",
        headers=agent_headers,
        json={
            "amount": 20.0,
            "summary": "充电",
            "detail": {"items": [{"name": "国网快充", "remark": "80%"}]},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["amount"] == 20.0
    assert update_response.json()["summary"] == "充电"

    invalid_detail_response = client.post(
        f"{settings.API_V1_STR}/agent/transactions/",
        headers=agent_headers,
        json={
            "category_id": category["id"],
            "transaction_type": TransactionType.EXPENSE,
            "amount": 22.0,
            "entry_status": EntryStatus.PENDING,
            "transaction_date": "2026-05-29",
            "summary": "加油",
            "detail": {"items": [{}]},
        },
    )
    assert invalid_detail_response.status_code == 422

    delete_response = client.delete(
        f"{settings.API_V1_STR}/agent/transactions/{transaction['id']}",
        headers=agent_headers,
    )
    assert delete_response.status_code == 200


def test_agent_transactions_reject_cross_owner_category_and_budget(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    foreign_category = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=normal_user_token_headers,
        json={"name": "Foreign Category", "color": "#334455"},
    ).json()
    foreign_budget = client.post(
        f"{settings.API_V1_STR}/budgets/",
        headers=normal_user_token_headers,
        json={"name": "Foreign Budget", "year": 2026, "period": 1, "amount": 500},
    ).json()
    own_category = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=superuser_token_headers,
        json={"name": "Owned Category", "color": "#556677"},
    ).json()
    token_response = client.post(
        f"{settings.API_V1_STR}/system/api-tokens/",
        headers=superuser_token_headers,
        json={"name": "Agent Ownership Validation"},
    )
    agent_headers = {"Authorization": f"Bearer {token_response.json()['token']}"}
    payload = {
        "transaction_type": TransactionType.EXPENSE,
        "amount": 42,
        "entry_status": EntryStatus.PENDING,
        "transaction_date": "2026-06-09",
    }

    foreign_category_response = client.post(
        f"{settings.API_V1_STR}/agent/transactions/",
        headers=agent_headers,
        json={**payload, "category_id": foreign_category["id"]},
    )
    assert foreign_category_response.status_code == 400
    assert foreign_category_response.json() == {"detail": "Category not found"}

    foreign_budget_response = client.post(
        f"{settings.API_V1_STR}/agent/transactions/",
        headers=agent_headers,
        json={
            **payload,
            "category_id": own_category["id"],
            "budget_id": foreign_budget["id"],
        },
    )
    assert foreign_budget_response.status_code == 400
    assert foreign_budget_response.json() == {"detail": "Budget not found"}


def test_agent_can_read_handler_options_and_use_selected_handler(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    category = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=superuser_token_headers,
        json={"name": "Agent Handler Category", "color": "#445566"},
    ).json()
    handler_user = create_random_user(db)
    handler_user.full_name = "Agent Handler"
    db.add(handler_user)
    db.commit()
    db.refresh(handler_user)

    token_response = client.post(
        f"{settings.API_V1_STR}/system/api-tokens/",
        headers=superuser_token_headers,
        json={"name": "Agent Handler Options"},
    )
    assert token_response.status_code == 200
    agent_headers = {"Authorization": f"Bearer {token_response.json()['token']}"}

    handlers_response = client.get(
        f"{settings.API_V1_STR}/agent/handler-options",
        headers=agent_headers,
    )
    assert handlers_response.status_code == 200
    handlers_payload = handlers_response.json()
    assert handlers_payload["count"] >= 1
    selected_handler = next(
        handler
        for handler in handlers_payload["data"]
        if handler["id"] == str(handler_user.id)
    )
    assert selected_handler["display_name"] == "Agent Handler"

    create_response = client.post(
        f"{settings.API_V1_STR}/agent/transactions/",
        headers=agent_headers,
        json={
            "category_id": category["id"],
            "transaction_type": TransactionType.EXPENSE,
            "amount": 66.0,
            "entry_status": EntryStatus.PENDING,
            "transaction_date": "2026-06-08",
            "summary": "带经手人的账单",
            "handler_user_id": selected_handler["id"],
        },
    )
    assert create_response.status_code == 200
    transaction = create_response.json()
    assert transaction["handler_user_id"] == selected_handler["id"]
    assert transaction["handler_display_name"] == "Agent Handler"


def test_agent_update_with_null_handler_falls_back_to_token_owner(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    category = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=superuser_token_headers,
        json={"name": "Agent Null Handler Category", "color": "#223344"},
    ).json()
    alternate_handler = create_random_user(db)
    alternate_handler.full_name = "Alternate Handler"
    db.add(alternate_handler)
    db.commit()
    db.refresh(alternate_handler)

    token_response = client.post(
        f"{settings.API_V1_STR}/system/api-tokens/",
        headers=superuser_token_headers,
        json={"name": "Agent Null Handler"},
    )
    assert token_response.status_code == 200
    token = token_response.json()["token"]
    agent_headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        f"{settings.API_V1_STR}/agent/transactions/",
        headers=agent_headers,
        json={
            "category_id": category["id"],
            "transaction_type": TransactionType.EXPENSE,
            "amount": 88.0,
            "entry_status": EntryStatus.PENDING,
            "transaction_date": "2026-06-08",
            "summary": "初始经手人",
            "handler_user_id": str(alternate_handler.id),
        },
    )
    assert create_response.status_code == 200
    transaction = create_response.json()
    assert transaction["handler_user_id"] == str(alternate_handler.id)

    update_response = client.put(
        f"{settings.API_V1_STR}/agent/transactions/{transaction['id']}",
        headers=agent_headers,
        json={
            "handler_user_id": None,
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["handler_user_id"] != str(alternate_handler.id)
    assert updated["handler_display_name"] != "Alternate Handler"
