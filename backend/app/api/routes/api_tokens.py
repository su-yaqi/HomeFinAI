import hashlib
import secrets
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.models import (
    ApiToken,
    ApiTokenCreate,
    ApiTokenPublic,
    ApiTokenSecretPublic,
    ApiTokensPublic,
    Message,
)
from app.utils import resolve_pagination

router = APIRouter(prefix="/system/api-tokens", tags=["api-tokens"])


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@router.get("/", response_model=ApiTokensPublic)
def read_api_tokens(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    page: int | None = None,
    page_size: int | None = None,
) -> Any:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    offset, max_results = resolve_pagination(
        page=page, page_size=page_size, skip=skip, limit=limit
    )
    count = session.exec(select(func.count()).select_from(ApiToken)).one()
    tokens = session.exec(
        select(ApiToken).order_by(col(ApiToken.created_at).desc()).offset(offset).limit(max_results)
    ).all()
    return ApiTokensPublic(
        data=[ApiTokenPublic.model_validate(token) for token in tokens],
        count=count,
    )


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ApiTokenSecretPublic,
)
def create_api_token(
    *, session: SessionDep, current_user: CurrentUser, token_in: ApiTokenCreate
) -> Any:
    plain_token = secrets.token_hex(24)
    token_prefix = plain_token[:12]
    plain_secret = secrets.token_hex(24) if token_in.generate_secret else None
    token = ApiToken(
        name=token_in.name,
        expires_at=token_in.expires_at,
        token_prefix=token_prefix,
        token_hash=_hash_value(plain_token),
        secret_hash=_hash_value(plain_secret) if plain_secret else None,
        created_by=current_user.id,
    )
    session.add(token)
    session.commit()
    return ApiTokenSecretPublic(token=plain_token, secret=plain_secret, token_prefix=token_prefix)


@router.post(
    "/{token_id}/disable",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def disable_api_token(session: SessionDep, token_id: uuid.UUID) -> Any:
    token = session.get(ApiToken, token_id)
    if not token:
        raise HTTPException(status_code=404, detail="API token not found")
    token.is_active = False
    session.add(token)
    session.commit()
    return Message(message="API token disabled successfully")


@router.delete(
    "/{token_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def delete_api_token(session: SessionDep, token_id: uuid.UUID) -> Any:
    token = session.get(ApiToken, token_id)
    if not token:
        raise HTTPException(status_code=404, detail="API token not found")
    session.delete(token)
    session.commit()
    return Message(message="API token deleted successfully")
