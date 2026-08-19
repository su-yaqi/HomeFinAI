from __future__ import annotations

import hashlib
import ipaddress
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
from jwt.exceptions import InvalidTokenError
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import (
    InvalidRedirectUriError,
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthToken,
)
from pydantic import AnyUrl
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.models import (
    AIAuthorizationCode,
    AIAuthorizationDecision,
    AIConnection,
    AIConnectionStatus,
    AIRefreshToken,
    User,
    get_datetime_utc,
)

AI_SCOPES = [
    "finance:read",
    "transactions:write",
    "transactions:delete",
    "budgets:write",
    "budgets:delete",
    "categories:write",
    "categories:delete",
]
MCP_ACCESS_TOKEN_TYPE = "mcp_access"
OAUTH_CONSENT_TOKEN_TYPE = "oauth_consent"


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _validate_loopback_redirect(registered: str, requested: str) -> bool:
    expected = urlsplit(registered)
    actual = urlsplit(requested)
    allowed = {"127.0.0.1", "::1"}
    if expected.hostname not in allowed or actual.hostname != expected.hostname:
        return False
    if expected.scheme != "http" or actual.scheme != "http":
        return False
    if expected.username or expected.password or actual.username or actual.password:
        return False
    if expected.path != actual.path or expected.query != actual.query:
        return False
    if expected.fragment or actual.fragment:
        return False
    try:
        return (
            expected.port is None
            and actual.port is not None
            and 1 <= actual.port <= 65535
        )
    except ValueError:
        return False


class CIMDClientInformation(OAuthClientInformationFull):
    def validate_redirect_uri(self, redirect_uri: AnyUrl | None) -> AnyUrl:
        if redirect_uri is None:
            return super().validate_redirect_uri(redirect_uri)
        requested = str(redirect_uri)
        for registered in self.redirect_uris or []:
            registered_text = str(registered)
            if requested == registered_text or _validate_loopback_redirect(
                registered_text, requested
            ):
                return redirect_uri
        raise InvalidRedirectUriError(
            f"Redirect URI '{redirect_uri}' not registered for client"
        )


class HomeFinAuthorizationCode(AuthorizationCode):
    connection_id: uuid.UUID


class HomeFinRefreshToken(RefreshToken):
    record_id: uuid.UUID
    connection_id: uuid.UUID
    family_id: uuid.UUID


class HomeFinOAuthProvider(
    OAuthAuthorizationServerProvider[
        HomeFinAuthorizationCode, HomeFinRefreshToken, AccessToken
    ]
):
    def __init__(self) -> None:
        self._client_cache: dict[str, tuple[float, CIMDClientInformation]] = {}

    @staticmethod
    def _validate_client_id(client_id: str) -> None:
        parsed = urlsplit(client_id)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise ValueError("CIMD client_id must be an HTTPS URL")
        try:
            ipaddress.ip_address(parsed.hostname)
        except ValueError:
            pass
        else:
            raise ValueError("CIMD client_id must not use an IP literal")
        if parsed.hostname not in settings.AI_CIMD_ALLOWED_HOSTS:
            raise ValueError("CIMD client host is not allowed")

    async def get_client(self, client_id: str) -> CIMDClientInformation | None:
        cached = self._client_cache.get(client_id)
        if cached and cached[0] > time.time():
            return cached[1]
        try:
            self._validate_client_id(client_id)
            async with httpx.AsyncClient(
                follow_redirects=False,
                timeout=httpx.Timeout(10.0),
            ) as client:
                response = await client.get(
                    client_id,
                    headers={"Accept": "application/json"},
                )
            response.raise_for_status()
            if "application/json" not in response.headers.get("content-type", ""):
                return None
            if len(response.content) > 64 * 1024:
                return None
            raw = response.json()
            if raw.get("client_id") not in {None, client_id}:
                return None
            metadata = OAuthClientMetadata.model_validate(raw)
            if not metadata.redirect_uris:
                return None
            if metadata.token_endpoint_auth_method not in {None, "none"}:
                return None
            if "authorization_code" not in set(
                metadata.grant_types or ["authorization_code"]
            ):
                return None
            metadata_values = metadata.model_dump(
                exclude={"token_endpoint_auth_method", "grant_types", "scope"}
            )
            info = CIMDClientInformation(
                **metadata_values,
                client_id=client_id,
                client_secret=None,
                token_endpoint_auth_method="none",
                grant_types=["authorization_code", "refresh_token"],
                scope=" ".join(AI_SCOPES),
                issuer=settings.OAUTH_ISSUER_URL,
            )
        except (httpx.HTTPError, ValueError, TypeError):
            return None
        self._client_cache[client_id] = (time.time() + 300, info)
        return info

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        raise NotImplementedError("Dynamic client registration is disabled")

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        scopes = sorted(set(params.scopes or ["finance:read"]))
        if any(scope not in AI_SCOPES for scope in scopes):
            raise AuthorizeError("invalid_scope", "Unsupported HomeFin scope")
        if (
            any(scope != "finance:read" for scope in scopes)
            and "finance:read" not in scopes
        ):
            raise AuthorizeError(
                "invalid_scope", "finance:read is required for write or delete scopes"
            )
        resource = params.resource or settings.MCP_RESOURCE_URL
        if resource != settings.MCP_RESOURCE_URL:
            raise AuthorizeError("invalid_target", "Invalid MCP resource")
        now = datetime.now(timezone.utc)
        payload = {
            "typ": OAUTH_CONSENT_TOKEN_TYPE,
            "client_id": client.client_id,
            "client_name": client.client_name or "AI client",
            "redirect_uri": str(params.redirect_uri),
            "code_challenge": params.code_challenge,
            "scopes": scopes,
            "state": params.state,
            "resource": resource,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        request_token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        return f"{settings.FRONTEND_HOST.rstrip('/')}/connect/authorize?{urlencode({'request': request_token})}"

    def complete_authorization(
        self, *, user: User, request_token: str, approved: bool
    ) -> str:
        payload = self.describe_authorization(request_token)

        redirect_uri = str(payload["redirect_uri"])
        raw_state = payload.get("state")
        state = raw_state if isinstance(raw_state, str) else None
        raw_code = secrets.token_urlsafe(32)
        now = get_datetime_utc()
        try:
            with Session(engine) as session, session.begin():
                request_jti = uuid.UUID(str(payload["jti"]))
                if session.exec(
                    select(AIAuthorizationDecision).where(
                        AIAuthorizationDecision.request_jti == request_jti
                    )
                ).first():
                    raise ValueError("Authorization request was already decided")
                session.add(
                    AIAuthorizationDecision(
                        request_jti=request_jti,
                        user_id=user.id,
                        approved=approved,
                    )
                )
                session.flush()
                if approved:
                    connection = AIConnection(
                        user_id=user.id,
                        client_id=str(payload["client_id"]),
                        client_name=str(payload.get("client_name") or "AI client"),
                        scopes=[
                            str(scope)
                            for scope in payload.get("scopes", ["finance:read"])
                        ],
                        auth_version=user.auth_version,
                    )
                    session.add(connection)
                    session.flush()
                    session.add(
                        AIAuthorizationCode(
                            connection_id=connection.id,
                            code_hash=_token_hash(raw_code),
                            redirect_uri=redirect_uri,
                            code_challenge=str(payload["code_challenge"]),
                            expires_at=now
                            + timedelta(
                                minutes=settings.AI_AUTHORIZATION_CODE_EXPIRE_MINUTES
                            ),
                        )
                    )
        except IntegrityError:
            raise ValueError("Authorization request was already decided") from None
        if not approved:
            return construct_redirect_uri(
                redirect_uri,
                error="access_denied",
                error_description="The user denied the request",
                state=state,
            )
        return construct_redirect_uri(
            redirect_uri,
            code=raw_code,
            state=state,
            iss=settings.OAUTH_ISSUER_URL,
        )

    def describe_authorization(self, request_token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                request_token,
                settings.SECRET_KEY,
                algorithms=["HS256"],
                options={"require": ["exp", "typ", "jti", "client_id", "redirect_uri"]},
            )
            if payload["typ"] != OAUTH_CONSENT_TOKEN_TYPE:
                raise ValueError("Invalid consent token type")
        except (InvalidTokenError, KeyError, ValueError) as exc:
            raise ValueError("Invalid or expired authorization request") from exc
        return payload

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> HomeFinAuthorizationCode | None:
        with Session(engine) as session:
            row = session.exec(
                select(AIAuthorizationCode).where(
                    AIAuthorizationCode.code_hash == _token_hash(authorization_code)
                )
            ).first()
            if (
                not row
                or row.used_at is not None
                or row.expires_at <= get_datetime_utc()
            ):
                return None
            connection = session.get(AIConnection, row.connection_id)
            if not connection or connection.client_id != client.client_id:
                return None
            return HomeFinAuthorizationCode(
                code=authorization_code,
                scopes=connection.scopes,
                expires_at=row.expires_at.timestamp(),
                client_id=connection.client_id,
                code_challenge=row.code_challenge,
                redirect_uri=AnyUrl(row.redirect_uri),
                redirect_uri_provided_explicitly=True,
                resource=settings.MCP_RESOURCE_URL,
                subject=str(connection.user_id),
                connection_id=connection.id,
            )

    def _issue_access_token(self, connection: AIConnection) -> str:
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {
                "typ": MCP_ACCESS_TOKEN_TYPE,
                "sub": str(connection.user_id),
                "client_id": connection.client_id,
                "conn": str(connection.id),
                "scope": connection.scopes,
                "ver": connection.auth_version,
                "iss": settings.OAUTH_ISSUER_URL,
                "aud": settings.MCP_RESOURCE_URL,
                "iat": now,
                "exp": now + timedelta(minutes=settings.AI_ACCESS_TOKEN_EXPIRE_MINUTES),
            },
            settings.SECRET_KEY,
            algorithm="HS256",
        )

    @staticmethod
    def _new_refresh_token(
        connection_id: uuid.UUID, family_id: uuid.UUID | None = None
    ) -> tuple[str, AIRefreshToken]:
        raw = secrets.token_urlsafe(48)
        return raw, AIRefreshToken(
            connection_id=connection_id,
            token_hash=_token_hash(raw),
            family_id=family_id or uuid.uuid4(),
            expires_at=get_datetime_utc()
            + timedelta(days=settings.AI_REFRESH_TOKEN_EXPIRE_DAYS),
        )

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: HomeFinAuthorizationCode,
    ) -> OAuthToken:
        with Session(engine) as session, session.begin():
            row = session.exec(
                select(AIAuthorizationCode)
                .where(
                    AIAuthorizationCode.code_hash
                    == _token_hash(authorization_code.code)
                )
                .with_for_update()
            ).first()
            connection = session.get(AIConnection, authorization_code.connection_id)
            if not row or row.used_at is not None or not connection:
                raise TokenError(
                    "invalid_grant", "Authorization code is no longer valid"
                )
            if connection.client_id != client.client_id:
                raise TokenError("invalid_client", "Client mismatch")
            row.used_at = get_datetime_utc()
            raw_refresh, refresh = self._new_refresh_token(connection.id)
            session.add(row)
            session.add(refresh)
            session.flush()
            access = self._issue_access_token(connection)
            granted_scopes = list(connection.scopes)
        return OAuthToken(
            access_token=access,
            expires_in=settings.AI_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            scope=" ".join(granted_scopes),
            refresh_token=raw_refresh,
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> HomeFinRefreshToken | None:
        with Session(engine) as session:
            row = session.exec(
                select(AIRefreshToken).where(
                    AIRefreshToken.token_hash == _token_hash(refresh_token)
                )
            ).first()
            if not row:
                return None
            connection = session.get(AIConnection, row.connection_id)
            if not connection or connection.client_id != client.client_id:
                return None
            if row.used_at is not None or row.revoked_at is not None:
                connection.status = AIConnectionStatus.REAUTH_REQUIRED.value
                connection.revoked_at = get_datetime_utc()
                for family_token in session.exec(
                    select(AIRefreshToken).where(
                        AIRefreshToken.family_id == row.family_id
                    )
                ).all():
                    family_token.revoked_at = get_datetime_utc()
                    session.add(family_token)
                session.add(connection)
                session.commit()
                return None
            if row.expires_at <= get_datetime_utc():
                return None
            return HomeFinRefreshToken(
                token=refresh_token,
                client_id=connection.client_id,
                scopes=connection.scopes,
                expires_at=int(row.expires_at.timestamp()),
                subject=str(connection.user_id),
                record_id=row.id,
                connection_id=connection.id,
                family_id=row.family_id,
            )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: HomeFinRefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        reuse_detected = False
        raw_refresh = ""
        access = ""
        with Session(engine) as session, session.begin():
            row = session.exec(
                select(AIRefreshToken)
                .where(AIRefreshToken.id == refresh_token.record_id)
                .with_for_update()
            ).first()
            connection = session.get(AIConnection, refresh_token.connection_id)
            user = session.get(User, connection.user_id) if connection else None
            if (
                row
                and connection
                and (row.used_at is not None or row.revoked_at is not None)
            ):
                now = get_datetime_utc()
                connection.status = AIConnectionStatus.REAUTH_REQUIRED.value
                connection.revoked_at = now
                session.add(connection)
                for family_token in session.exec(
                    select(AIRefreshToken).where(
                        AIRefreshToken.family_id == row.family_id
                    )
                ).all():
                    family_token.revoked_at = now
                    session.add(family_token)
                reuse_detected = True
            if (
                not row
                or reuse_detected
                or not connection
                or connection.status != AIConnectionStatus.ACTIVE.value
                or not user
                or not user.is_active
                or user.auth_version != connection.auth_version
            ):
                if not reuse_detected:
                    raise TokenError(
                        "invalid_grant", "Refresh token is no longer valid"
                    )
            else:
                row.used_at = get_datetime_utc()
                raw_refresh, replacement = self._new_refresh_token(
                    connection.id, refresh_token.family_id
                )
                session.add(replacement)
                session.flush()
                row.replaced_by_id = replacement.id
                session.add(row)
                access = self._issue_access_token(connection)
        if reuse_detected:
            raise TokenError(
                "invalid_grant", "Refresh token reuse revoked the connection"
            )
        return OAuthToken(
            access_token=access,
            expires_in=settings.AI_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            scope=" ".join(scopes),
            refresh_token=raw_refresh,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"],
                audience=settings.MCP_RESOURCE_URL,
                issuer=settings.OAUTH_ISSUER_URL,
                options={"require": ["exp", "sub", "typ", "conn", "scope"]},
            )
            if payload["typ"] != MCP_ACCESS_TOKEN_TYPE:
                return None
            connection_id = uuid.UUID(payload["conn"])
            user_id = uuid.UUID(payload["sub"])
        except (InvalidTokenError, KeyError, ValueError):
            return None
        with Session(engine) as session:
            connection = session.get(AIConnection, connection_id)
            user = session.get(User, user_id)
            if (
                not connection
                or connection.user_id != user_id
                or connection.status != AIConnectionStatus.ACTIVE.value
                or connection.auth_version != payload.get("ver")
                or not user
                or not user.is_active
                or user.auth_version != connection.auth_version
            ):
                return None
            client_id = connection.client_id
            scopes = list(connection.scopes)
            connection.last_used_at = get_datetime_utc()
            session.add(connection)
            session.commit()
        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=int(payload["exp"]),
            resource=settings.MCP_RESOURCE_URL,
            subject=str(user_id),
            claims={
                "iss": settings.OAUTH_ISSUER_URL,
                "connection_id": str(connection_id),
            },
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        return await self.load_access_token(token)

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        if isinstance(token, HomeFinRefreshToken):
            with Session(engine) as session:
                connection = session.get(AIConnection, token.connection_id)
                if connection:
                    connection.status = AIConnectionStatus.REVOKED.value
                    connection.revoked_at = get_datetime_utc()
                    session.add(connection)
                    session.commit()


oauth_provider = HomeFinOAuthProvider()
