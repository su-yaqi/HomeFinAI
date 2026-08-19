from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
    to_user_public,
)
from app.core import security
from app.core.config import settings
from app.models import LoginRequest, Message, NewPassword, Token, UserPublic, UserUpdate
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
def login_access_token(
    session: SessionDep,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    mfa_code: Annotated[str | None, Form()] = None,
) -> Token:
    user = crud.authenticate(
        session=session,
        login_name=username,
        password=password,
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect login name or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    if user.mfa_secret:
        if not mfa_code or not security.verify_totp_code(user.mfa_secret, mfa_code):
            raise HTTPException(status_code=400, detail="Invalid MFA code")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id,
            expires_delta=access_token_expires,
            auth_version=user.auth_version,
        )
    )


@router.post("/login", response_model=UserPublic)
def login(
    session: SessionDep, credentials: LoginRequest, response: Response
) -> UserPublic:
    """Create a cookie-backed authenticated session."""
    user = crud.authenticate(
        session=session,
        login_name=credentials.login_name,
        password=credentials.password,
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect login name or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    if user.mfa_secret:
        if not credentials.mfa_code or not security.verify_totp_code(
            user.mfa_secret, credentials.mfa_code
        ):
            raise HTTPException(status_code=400, detail="Invalid MFA code")

    session_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    session_token = security.create_session_token(
        user.id,
        expires_delta=session_expires,
        auth_version=user.auth_version,
    )
    csrf_token = security.generate_csrf_token()
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT != "local",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        secure=settings.ENVIRONMENT != "local",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return to_user_public(user)


@router.post("/logout")
def logout() -> Any:
    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    response.delete_cookie(settings.CSRF_COOKIE_NAME)
    return response


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    return to_user_public(current_user)


@router.post("/password-recovery/{email}")
def recover_password(email: str, session: SessionDep) -> Message:
    """
    Password Recovery
    """
    user = crud.get_user_by_email(session=session, email=email)

    # Always return the same response to prevent email enumeration attacks
    # Only send email if user actually exists
    if user:
        password_reset_token = generate_password_reset_token(
            email=email, auth_version=user.auth_version
        )
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )
        send_email(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return Message(
        message="If that email is registered, we sent a password recovery link"
    )


@router.post("/reset-password/")
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    """
    Reset password
    """
    reset_claims = verify_password_reset_token(token=body.token)
    if not reset_claims:
        raise HTTPException(status_code=400, detail="Invalid token")
    email, auth_version = reset_claims
    user = crud.get_user_by_email(session=session, email=email)
    if not user:
        # Don't reveal that the user doesn't exist - use same error as invalid token
        raise HTTPException(status_code=400, detail="Invalid token")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    if user.auth_version != auth_version:
        raise HTTPException(status_code=400, detail="Invalid token")
    user_in_update = UserUpdate(password=body.new_password)
    crud.update_user(
        session=session,
        db_user=user,
        user_in=user_in_update,
    )
    return Message(message="Password updated successfully")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """
    HTML Content for Password Recovery
    """
    user = crud.get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(
        email=email, auth_version=user.auth_version
    )
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )
