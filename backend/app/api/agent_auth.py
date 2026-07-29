import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, delete, select

from app.api.deps import SessionDep
from app.models import ApiToken, ApiTokenNonce

HMAC_MAX_CLOCK_SKEW_SECONDS = 300


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


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
    token_value = x_api_token
    if authorization and authorization.startswith("Bearer "):
        token_value = authorization.removeprefix("Bearer ").strip()
    if not token_value:
        raise HTTPException(status_code=401, detail="Missing API token")

    token = session.exec(
        select(ApiToken).where(ApiToken.token_hash == hash_value(token_value))
    ).first()
    if not token or not token.is_active:
        raise HTTPException(status_code=401, detail="Invalid API token")
    if token.expires_at and token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Expired API token")

    hmac_headers = [x_api_secret, x_timestamp, x_nonce, x_signature]
    if token.secret_hash:
        if not all(hmac_headers):
            raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    elif any(hmac_headers):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    if token.secret_hash:
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
                f"{x_timestamp}:{x_nonce}:{request.method}:"
                f"{request.url.path}:{body_text}"
            ).encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, x_signature):
            raise HTTPException(status_code=401, detail="Invalid HMAC signature")

        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=HMAC_MAX_CLOCK_SKEW_SECONDS * 2
        )
        session.exec(
            delete(ApiTokenNonce).where(col(ApiTokenNonce.created_at) < cutoff)
        )
        session.add(ApiTokenNonce(token_id=token.id, nonce=x_nonce))

    token.last_used_at = datetime.now(timezone.utc)
    session.add(token)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=401, detail="Replayed HMAC request")
    session.refresh(token)
    return token
