import random
import string

from fastapi.testclient import TestClient

from app.core.config import settings


def random_lower_string() -> str:
    return "".join(random.choices(string.ascii_lowercase, k=32))


def random_email() -> str:
    return f"{random_lower_string()}@{random_lower_string()}.com"


def login_name_from_email(email: str) -> str:
    return email.split("@", 1)[0]


def get_superuser_token_headers(client: TestClient) -> dict[str, str]:
    login_data = {
        "username": login_name_from_email(settings.FIRST_SUPERUSER),
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}
