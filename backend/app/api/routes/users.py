import uuid
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, delete, func, select

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
    to_user_public,
)
from app.core.config import settings
from app.core.security import (
    generate_mfa_secret,
    get_password_hash,
    verify_password,
    verify_totp_code,
)
from app.models import (
    AdminResetPassword,
    HandlerUserOption,
    HandlerUsersPublic,
    Item,
    Message,
    MFAEnableRequest,
    MFASetupPublic,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.utils import generate_new_account_email, resolve_pagination, send_email

router = APIRouter(prefix="/users", tags=["users"])


def _build_mfa_otpauth_uri(user: User, secret: str) -> str:
    issuer = quote(settings.PROJECT_NAME)
    account_name = quote(user.login_name)
    return f"otpauth://totp/{issuer}:{account_name}?secret={secret}&issuer={issuer}"


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    """
    Retrieve users.
    """

    offset, max_results = resolve_pagination(
        page=page, page_size=page_size, skip=skip, limit=limit
    )
    count_statement = select(func.count()).select_from(User)
    count = session.exec(count_statement).one()

    statement = (
        select(User)
        .order_by(col(User.created_at).desc())
        .offset(offset)
        .limit(max_results)
    )
    users = session.exec(statement).all()

    users_public = [to_user_public(user) for user in users]
    return UsersPublic(data=users_public, count=count)


@router.get("/handler-options", response_model=HandlerUsersPublic)
def read_handler_options(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    offset, max_results = resolve_pagination(
        page=page, page_size=page_size, skip=skip, limit=limit
    )
    count = session.exec(
        select(func.count()).select_from(User).where(User.is_active == True)  # noqa: E712
    ).one()
    users = session.exec(
        select(User)
        .where(User.is_active == True)  # noqa: E712
        .order_by(col(User.full_name).asc(), col(User.login_name).asc())
        .offset(offset)
        .limit(max_results)
    ).all()
    if current_user.id not in {user.id for user in users}:
        current_user_row = session.get(User, current_user.id)
        if current_user_row and current_user_row.is_active:
            users = [current_user_row, *users]
    seen_ids: set[uuid.UUID] = set()
    options = []
    for user in users:
        if user.id in seen_ids:
            continue
        seen_ids.add(user.id)
        options.append(
            HandlerUserOption(
                id=user.id,
                full_name=user.full_name,
                login_name=user.login_name,
                display_name=user.full_name or user.login_name,
            )
        )
    return HandlerUsersPublic(data=options, count=count)


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    existing_login_name = crud.get_user_by_login_name(
        session=session, login_name=user_in.login_name
    )
    if existing_login_name:
        raise HTTPException(
            status_code=400,
            detail="The user with this login name already exists in the system.",
        )

    user = crud.create_user(session=session, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return to_user_public(user)


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    if user_in.login_name:
        existing_user = crud.get_user_by_login_name(
            session=session, login_name=user_in.login_name
        )
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this login name already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return to_user_public(current_user)


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    current_user.auth_version += 1
    session.add(current_user)
    session.commit()
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return to_user_public(current_user)


@router.post("/me/mfa/setup", response_model=MFASetupPublic)
def setup_mfa(current_user: CurrentUser) -> MFASetupPublic:
    secret = generate_mfa_secret()
    return MFASetupPublic(
        secret=secret,
        otpauth_uri=_build_mfa_otpauth_uri(current_user, secret),
    )


@router.post("/me/mfa/enable", response_model=Message)
def enable_mfa(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    payload: MFAEnableRequest,
) -> Message:
    if not verify_totp_code(payload.secret, payload.code):
        raise HTTPException(status_code=400, detail="Invalid MFA code")
    current_user.mfa_secret = payload.secret
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return Message(message="MFA enabled successfully")


@router.post("/me/mfa/reset", response_model=Message)
def reset_my_mfa(session: SessionDep, current_user: CurrentUser) -> Message:
    current_user.mfa_secret = None
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return Message(message="MFA reset successfully")


@router.post("/me/mfa/disable", response_model=Message)
def disable_my_mfa(session: SessionDep, current_user: CurrentUser) -> Message:
    current_user.mfa_secret = None
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return Message(message="MFA disabled successfully")


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


@router.post("/signup", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Backward-compatible public registration endpoint.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    if user_in.login_name:
        existing_login_name = crud.get_user_by_login_name(
            session=session, login_name=user_in.login_name
        )
        if existing_login_name:
            raise HTTPException(
                status_code=400,
                detail="The user with this login name already exists in the system",
            )
    user_create = UserCreate.model_validate(user_in.model_dump(exclude_none=True))
    user = crud.create_user(session=session, user_create=user_create)
    return to_user_public(user)


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    if user_id == current_user.id:
        return to_user_public(current_user)
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return to_user_public(user)


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    if user_in.login_name:
        existing_user = crud.get_user_by_login_name(
            session=session, login_name=user_in.login_name
        )
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this login name already exists"
            )

    db_user = crud.update_user(session=session, db_user=db_user, user_in=user_in)
    return to_user_public(db_user)


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    statement = delete(Item).where(col(Item.owner_id) == user_id)
    session.exec(statement)
    session.delete(user)
    session.commit()
    return Message(message="User deleted successfully")


@router.post(
    "/{user_id}/reset-password",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def reset_user_password(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    payload: AdminResetPassword,
) -> Message:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = get_password_hash(payload.new_password)
    user.auth_version += 1
    session.add(user)
    session.commit()
    return Message(message="Password updated successfully")


@router.post(
    "/{user_id}/reset-mfa",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def reset_user_mfa(*, session: SessionDep, user_id: uuid.UUID) -> Message:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.mfa_secret = None
    session.add(user)
    session.commit()
    session.refresh(user)
    return Message(message="MFA reset successfully")
