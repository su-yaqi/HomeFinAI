import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, delete, select

from app.api.deps import SessionDep
from app.models import ApiToken, ApiTokenNonce

HMAC_MAX_CLOCK_SKEW_SECONDS = 300


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _token_value(authorization: str | None, x_api_token: str | None) -> str:
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    if x_api_token:
        return x_api_token
    raise HTTPException(status_code=401, detail="Missing API token")


def _active_token(session: SessionDep, token_value: str) -> ApiToken:
    token = session.exec(
        select(ApiToken).where(ApiToken.token_hash == hash_value(token_value))
    ).first()
    if not token or not token.is_active:
        raise HTTPException(status_code=401, detail="Invalid API token")
    if token.expires_at and token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Expired API token")
    return token


def _verify_hmac(
    token: ApiToken,
    request: Request,
    body_text: str,
    x_api_secret: str | None,
    x_timestamp: str | None,
    x_nonce: str | None,
    x_signature: str | None,
) -> str | None:
    hmac_headers = [x_api_secret, x_timestamp, x_nonce, x_signature]
    if not token.secret_hash:
        if any(hmac_headers):
            raise HTTPException(status_code=401, detail="Invalid HMAC signature")
        return None
    if not all(hmac_headers):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    assert x_api_secret is not None
    assert x_timestamp is not None
    assert x_nonce is not None
    assert x_signature is not None
    try:
        timestamp = int(x_timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid HMAC timestamp")
    if abs(time.time() - timestamp) > HMAC_MAX_CLOCK_SKEW_SECONDS:
        raise HTTPException(status_code=401, detail="Expired HMAC timestamp")
    if not 16 <= len(x_nonce) <= 128:
        raise HTTPException(status_code=401, detail="Invalid HMAC nonce")
    if not hmac.compare_digest(hash_value(x_api_secret), token.secret_hash):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    expected = hmac.new(
        x_api_secret.encode(),
        msg=(
            f"{x_timestamp}:{x_nonce}:{request.method}:{request.url.path}:{body_text}"
        ).encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, x_signature):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    return x_nonce


def authenticate_agent(
    session: SessionDep,
    request: Request,
    body_text: str,
    authorization: str | None,
    x_api_token: str | None,
    x_api_secret: str | None,
    x_timestamp: str | None,
    x_nonce: str | None,
    x_signature: str | None,
) -> ApiToken:
    token = _active_token(session, _token_value(authorization, x_api_token))
    nonce = _verify_hmac(
        token,
        request,
        body_text,
        x_api_secret,
        x_timestamp,
        x_nonce,
        x_signature,
    )
    if nonce:
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=HMAC_MAX_CLOCK_SKEW_SECONDS * 2
        )
        session.exec(
            delete(ApiTokenNonce).where(col(ApiTokenNonce.created_at) < cutoff)
        )
        session.add(ApiTokenNonce(token_id=token.id, nonce=nonce))

    token.last_used_at = datetime.now(timezone.utc)
    session.add(token)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=401, detail="Replayed HMAC request")
    session.refresh(token)
    return token


async def get_agent_token(
    request: Request,
    session: SessionDep,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
    x_api_secret: str | None = Header(default=None),
    x_timestamp: str | None = Header(default=None),
    x_nonce: str | None = Header(default=None),
    x_signature: str | None = Header(default=None),
) -> ApiToken:
    return authenticate_agent(
        session,
        request,
        (await request.body()).decode(),
        authorization,
        x_api_token,
        x_api_secret,
        x_timestamp,
        x_nonce,
        x_signature,
    )


AgentToken = Annotated[ApiToken, Depends(get_agent_token)]
