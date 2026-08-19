import time
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlmodel import Session

from app.core.config import settings
from app.core.security import _hotp, get_password_hash, verify_password
from app.crud import create_user
from app.models import User, UserCreate
from app.utils import generate_password_reset_token
from tests.utils.utils import (
    login_name_from_email,
    random_email,
    random_lower_string,
)


def test_get_access_token_by_login_name(client: TestClient) -> None:
    login_data = {
        "username": login_name_from_email(settings.FIRST_SUPERUSER),
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    assert r.status_code == 200
    assert "access_token" in tokens
    assert tokens["access_token"]


def test_login_rejects_incorrect_password(client: TestClient) -> None:
    login_data = {
        "username": login_name_from_email(settings.FIRST_SUPERUSER),
        "password": "incorrect",
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    assert r.status_code == 400


def test_use_access_token(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/login/test-token",
        headers=superuser_token_headers,
    )
    result = r.json()
    assert r.status_code == 200
    assert "email" in result


def test_password_reset_token_cannot_be_used_as_access_token(
    client: TestClient,
) -> None:
    reset_token = generate_password_reset_token(email=settings.FIRST_SUPERUSER)
    response = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers={"Authorization": f"Bearer {reset_token}"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_recovery_password(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    with (
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.SMTP_USER", "admin@example.com"),
    ):
        email = "test@example.com"
        r = client.post(
            f"{settings.API_V1_STR}/password-recovery/{email}",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 200
        assert r.json() == {
            "message": "If that email is registered, we sent a password recovery link"
        }


def test_recovery_password_user_not_exits(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    email = "jVgQr@example.com"
    r = client.post(
        f"{settings.API_V1_STR}/password-recovery/{email}",
        headers=normal_user_token_headers,
    )
    # Should return 200 with generic message to prevent email enumeration attacks
    assert r.status_code == 200
    assert r.json() == {
        "message": "If that email is registered, we sent a password recovery link"
    }


def test_reset_password(client: TestClient, db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    new_password = random_lower_string()

    user_create = UserCreate(
        email=email,
        full_name="Test User",
        password=password,
        is_active=True,
        is_superuser=False,
    )
    user = create_user(session=db, user_create=user_create)
    token = generate_password_reset_token(email=email)
    data = {"new_password": new_password, "token": token}

    r = client.post(
        f"{settings.API_V1_STR}/reset-password/",
        json=data,
    )

    assert r.status_code == 200
    assert r.json() == {"message": "Password updated successfully"}

    db.refresh(user)
    verified, _ = verify_password(new_password, user.hashed_password)
    assert verified

    reused = client.post(
        f"{settings.API_V1_STR}/reset-password/",
        json=data,
    )
    assert reused.status_code == 400
    assert reused.json() == {"detail": "Invalid token"}


def test_reset_password_invalid_token(
    client: TestClient,
) -> None:
    data = {"new_password": "changethis", "token": "invalid"}
    r = client.post(f"{settings.API_V1_STR}/reset-password/", json=data)
    response = r.json()

    assert "detail" in response
    assert r.status_code == 400
    assert response["detail"] == "Invalid token"


def test_login_with_bcrypt_password_upgrades_to_argon2(
    client: TestClient, db: Session
) -> None:
    """Test that logging in with a bcrypt password hash upgrades it to argon2."""
    email = random_email()
    password = random_lower_string()

    # Create a bcrypt hash directly (simulating legacy password)
    bcrypt_hasher = BcryptHasher()
    bcrypt_hash = bcrypt_hasher.hash(password)
    assert bcrypt_hash.startswith("$2")  # bcrypt hashes start with $2

    user = User(
        email=email,
        login_name=login_name_from_email(email),
        hashed_password=bcrypt_hash,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    assert user.hashed_password.startswith("$2")

    login_data = {
        "username": login_name_from_email(email),
        "password": password,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    assert r.status_code == 200
    tokens = r.json()
    assert "access_token" in tokens

    db.refresh(user)

    # Verify the hash was upgraded to argon2
    assert user.hashed_password.startswith("$argon2")

    verified, updated_hash = verify_password(password, user.hashed_password)
    assert verified
    # Should not need another update since it's already argon2
    assert updated_hash is None


def test_login_with_argon2_password_keeps_hash(client: TestClient, db: Session) -> None:
    """Test that logging in with an argon2 password hash does not update it."""
    email = random_email()
    password = random_lower_string()

    # Create an argon2 hash (current default)
    argon2_hash = get_password_hash(password)
    assert argon2_hash.startswith("$argon2")

    # Create user with argon2 hash
    user = User(
        email=email,
        login_name=login_name_from_email(email),
        hashed_password=argon2_hash,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    original_hash = user.hashed_password

    login_data = {
        "username": login_name_from_email(email),
        "password": password,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    assert r.status_code == 200
    tokens = r.json()
    assert "access_token" in tokens

    db.refresh(user)

    assert user.hashed_password == original_hash
    assert user.hashed_password.startswith("$argon2")


def test_login_requires_mfa_for_user_with_secret(
    client: TestClient, db: Session
) -> None:
    email = random_email()
    password = random_lower_string()
    secret = "JBSWY3DPEHPK3PXP"

    user = User(
        email=email,
        login_name=login_name_from_email(email),
        hashed_password=get_password_hash(password),
        is_active=True,
        mfa_secret=secret,
    )
    db.add(user)
    db.commit()

    missing_mfa_response = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": login_name_from_email(email), "password": password},
    )
    assert missing_mfa_response.status_code == 400
    assert missing_mfa_response.json() == {"detail": "Invalid MFA code"}

    valid_mfa_response = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={
            "username": login_name_from_email(email),
            "password": password,
            "mfa_code": _hotp(secret, int(time.time() // 30)),
        },
    )
    assert valid_mfa_response.status_code == 200
    assert valid_mfa_response.json()["access_token"]


def test_login_no_longer_requires_mfa_after_admin_reset(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    email = random_email()
    password = random_lower_string()
    user = create_user(
        session=db,
        user_create=UserCreate(email=email, password=password),
    )
    user.mfa_secret = "JBSWY3DPEHPK3PXP"
    db.add(user)
    db.commit()
    db.refresh(user)

    blocked_login_response = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": login_name_from_email(email), "password": password},
    )
    assert blocked_login_response.status_code == 400

    reset_response = client.post(
        f"{settings.API_V1_STR}/users/{user.id}/reset-mfa",
        headers=superuser_token_headers,
    )
    assert reset_response.status_code == 200

    login_response = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": login_name_from_email(email), "password": password},
    )
    assert login_response.status_code == 200
    assert login_response.json()["access_token"]


def test_cookie_login_and_logout(client: TestClient) -> None:
    login_response = client.post(
        f"{settings.API_V1_STR}/login",
        json={
            "login_name": login_name_from_email(settings.FIRST_SUPERUSER),
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    assert login_response.status_code == 200
    assert settings.SESSION_COOKIE_NAME in login_response.cookies
    assert settings.CSRF_COOKIE_NAME in login_response.cookies

    csrf_token = login_response.cookies[settings.CSRF_COOKIE_NAME]
    logout_response = client.post(
        f"{settings.API_V1_STR}/logout",
        headers={settings.CSRF_HEADER_NAME: csrf_token},
    )
    assert logout_response.status_code == 200
    assert logout_response.json() == {"message": "Logged out successfully"}
    set_cookie_headers = logout_response.headers.get_list("set-cookie")
    assert any(settings.SESSION_COOKIE_NAME in value for value in set_cookie_headers)
    assert any(settings.CSRF_COOKIE_NAME in value for value in set_cookie_headers)
    assert settings.SESSION_COOKIE_NAME not in client.cookies
    assert settings.CSRF_COOKIE_NAME not in client.cookies


def test_cookie_login_rejects_invalid_inactive_and_missing_mfa(
    client: TestClient, db: Session
) -> None:
    invalid_response = client.post(
        f"{settings.API_V1_STR}/login",
        json={"login_name": "missing-user", "password": "incorrect-password"},
    )
    assert invalid_response.status_code == 400
    assert invalid_response.json() == {"detail": "Incorrect login name or password"}

    password = random_lower_string()
    inactive = create_user(
        session=db,
        user_create=UserCreate(
            email=random_email(), password=password, is_active=False
        ),
    )
    inactive_response = client.post(
        f"{settings.API_V1_STR}/login",
        json={"login_name": inactive.login_name, "password": password},
    )
    assert inactive_response.status_code == 400
    assert inactive_response.json() == {"detail": "Inactive user"}

    mfa_user = create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=password),
    )
    mfa_user.mfa_secret = "JBSWY3DPEHPK3PXP"
    db.add(mfa_user)
    db.commit()
    mfa_response = client.post(
        f"{settings.API_V1_STR}/login",
        json={"login_name": mfa_user.login_name, "password": password},
    )
    assert mfa_response.status_code == 400
    assert mfa_response.json() == {"detail": "Invalid MFA code"}


def test_reset_password_rejects_missing_and_inactive_users(
    client: TestClient, db: Session
) -> None:
    missing_token = generate_password_reset_token(email=f"{uuid.uuid4()}@example.com")
    missing_response = client.post(
        f"{settings.API_V1_STR}/reset-password/",
        json={"new_password": random_lower_string(), "token": missing_token},
    )
    assert missing_response.status_code == 400
    assert missing_response.json() == {"detail": "Invalid token"}

    password = random_lower_string()
    inactive = create_user(
        session=db,
        user_create=UserCreate(
            email=random_email(), password=password, is_active=False
        ),
    )
    inactive_token = generate_password_reset_token(email=inactive.email)
    inactive_response = client.post(
        f"{settings.API_V1_STR}/reset-password/",
        json={"new_password": random_lower_string(), "token": inactive_token},
    )
    assert inactive_response.status_code == 400
    assert inactive_response.json() == {"detail": "Inactive user"}


def test_password_recovery_html_content(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/password-recovery-html-content/"
        f"{settings.FIRST_SUPERUSER}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert "html" in response.headers["content-type"]

    missing_response = client.post(
        f"{settings.API_V1_STR}/password-recovery-html-content/"
        f"{uuid.uuid4()}@example.com",
        headers=superuser_token_headers,
    )
    assert missing_response.status_code == 404
