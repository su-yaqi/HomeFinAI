from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import (
    AIAuthorizationCode,
    AIAuthorizationDecision,
    AIConnection,
    AIOperation,
    AIRefreshToken,
    ApiToken,
    ApiTokenNonce,
    Budget,
    Category,
    DataJob,
    DataJobError,
    Transaction,
    User,
)
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


def _cleanup_db(session: Session) -> None:
    session.rollback()
    session.execute(delete(AIOperation))
    session.execute(delete(AIRefreshToken))
    session.execute(delete(AIAuthorizationCode))
    session.execute(delete(AIAuthorizationDecision))
    session.execute(delete(AIConnection))
    session.execute(delete(DataJobError))
    session.execute(delete(DataJob))
    session.execute(delete(ApiTokenNonce))
    session.execute(delete(ApiToken))
    session.execute(delete(Transaction))
    session.execute(delete(Budget))
    session.execute(delete(Category))
    session.execute(delete(User))
    session.commit()


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    if not settings.POSTGRES_DB.endswith("_test"):
        pytest.fail(
            "Refusing to run destructive test cleanup outside a dedicated *_test database",
            pytrace=False,
        )
    with Session(engine) as session:
        init_db(session)
        _cleanup_db(session)
        init_db(session)
        yield session
        _cleanup_db(session)


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
