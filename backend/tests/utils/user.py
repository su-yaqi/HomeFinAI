from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User, UserCreate, UserUpdate
from tests.utils.utils import (
    login_name_from_email,
    random_email,
    random_lower_string,
)


def user_authentication_headers(
    *, client: TestClient, email: str, password: str
) -> dict[str, str]:
    data = {
        "username": login_name_from_email(email),
        "password": password,
    }

    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=data)
    response = r.json()
    auth_token = response["access_token"]
    return {"Authorization": f"Bearer {auth_token}"}


def create_random_user(db: Session) -> User:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    return user


def authentication_token_from_email(
    *, client: TestClient, email: str, db: Session
) -> dict[str, str]:
    """
    Return a valid token for the user with given email.

    If the user doesn't exist it is created first.
    """
    db.rollback()
    password = random_lower_string()
    user = crud.get_user_by_email(session=db, email=email)
    if not user:
        login_name = login_name_from_email(email)
        existing_login_name_user = crud.get_user_by_login_name(
            session=db, login_name=login_name
        )
        if existing_login_name_user:
            user_in_update = UserUpdate(email=email, password=password)
            user = crud.update_user(
                session=db, db_user=existing_login_name_user, user_in=user_in_update
            )
        else:
            user_in_create = UserCreate(
                email=email, login_name=login_name, password=password
            )
            user = crud.create_user(session=db, user_create=user_in_create)
    else:
        user_in_update = UserUpdate(password=password)
        if not user.id:
            raise Exception("User id not set")
        user = crud.update_user(session=db, db_user=user, user_in=user_in_update)

    return user_authentication_headers(client=client, email=email, password=password)
