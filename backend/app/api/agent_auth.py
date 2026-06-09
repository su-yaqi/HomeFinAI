import hashlib
import hmac
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from sqlmodel import select

from app.api.deps import SessionDep
from app.models import ApiToken


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

    if any([x_api_secret, x_timestamp, x_signature]):
        if not all([x_api_secret, x_timestamp, x_signature, token.secret_hash]):
            raise HTTPException(status_code=401, detail="Invalid HMAC signature")
        if hash_value(x_api_secret) != token.secret_hash:
            raise HTTPException(status_code=401, detail="Invalid HMAC signature")
        expected = hmac.new(
            x_api_secret.encode(),
            msg=f"{x_timestamp}:{request.method}:{request.url.path}:{body_text}".encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, x_signature):
            raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    token.last_used_at = datetime.now(timezone.utc)
    session.add(token)
    session.commit()
    session.refresh(token)
    return token
