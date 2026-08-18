from typing import cast

from mcp.server.auth.handlers.authorize import AuthorizationHandler
from mcp.server.auth.handlers.token import TokenHandler
from mcp.server.auth.middleware.client_auth import ClientAuthenticator
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.ai_connector.oauth import AI_SCOPES, oauth_provider
from app.core.config import settings

authorization_handler = AuthorizationHandler(oauth_provider)
token_handler = TokenHandler(oauth_provider, ClientAuthenticator(oauth_provider))


async def oauth_metadata(_: Request) -> Response:
    issuer = settings.OAUTH_ISSUER_URL.rstrip("/")
    return JSONResponse(
        {
            "issuer": settings.OAUTH_ISSUER_URL,
            "authorization_endpoint": f"{issuer}/authorize",
            "token_endpoint": f"{issuer}/token",
            "scopes_supported": AI_SCOPES,
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["none"],
            "code_challenge_methods_supported": ["S256"],
            "client_id_metadata_document_supported": True,
            "authorization_response_iss_parameter_supported": True,
        },
        headers={"Cache-Control": "public, max-age=300"},
    )


async def authorize(request: Request) -> Response:
    return await authorization_handler.handle(request)


async def token(request: Request) -> Response:
    return cast(Response, await token_handler.handle(request))
