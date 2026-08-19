import asyncio
import base64
import hashlib
import uuid
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi.testclient import TestClient
from pydantic import AnyUrl
from pytest import MonkeyPatch
from sqlmodel import Session, func, select

import app.ai_connector.oauth as oauth_module
from app.ai_connector.oauth import AI_SCOPES, CIMDClientInformation, oauth_provider
from app.core.config import settings
from app.core.db import engine
from app.models import AIOperation, Transaction


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _codex_client() -> CIMDClientInformation:
    return CIMDClientInformation(
        client_id="https://chatgpt.com/oauth/codex/test/client.json",
        client_name="Codex Desktop",
        redirect_uris=[AnyUrl("http://127.0.0.1/callback/codex-test")],
        token_endpoint_auth_method="none",
        grant_types=["authorization_code", "refresh_token"],
        scope="finance:read transactions:write",
        application_type="native",
    )


def _authorize_full_scope_codex(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch: MonkeyPatch,
) -> str:
    suffix = uuid.uuid4().hex
    callback_path = f"/callback/{suffix}"
    client_info = CIMDClientInformation(
        client_id=f"https://chatgpt.com/oauth/codex/{suffix}/client.json",
        client_name="Codex Full Scope Test",
        redirect_uris=[AnyUrl(f"http://127.0.0.1{callback_path}")],
        token_endpoint_auth_method="none",
        grant_types=["authorization_code", "refresh_token"],
        scope=" ".join(AI_SCOPES),
        application_type="native",
    )

    async def fake_get_client(client_id: str) -> CIMDClientInformation | None:
        return client_info if client_id == client_info.client_id else None

    monkeypatch.setattr(oauth_provider, "get_client", fake_get_client)
    verifier = "full-scope-verifier-" + "a" * 48
    redirect_uri = f"http://127.0.0.1:17322{callback_path}"
    authorize_response = client.get(
        "/authorize",
        params={
            "client_id": client_info.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "code_challenge": _challenge(verifier),
            "code_challenge_method": "S256",
            "scope": " ".join(AI_SCOPES),
            "resource": settings.MCP_RESOURCE_URL,
            "state": suffix,
        },
        follow_redirects=False,
    )
    assert authorize_response.status_code == 302
    request_token = parse_qs(urlsplit(authorize_response.headers["location"]).query)[
        "request"
    ][0]
    decision = client.post(
        f"{settings.API_V1_STR}/ai-connections/authorization-request",
        json={"request": request_token, "approved": True},
        headers=superuser_token_headers,
    )
    assert decision.status_code == 200
    code = parse_qs(urlsplit(decision.json()["redirect_url"]).query)["code"][0]
    token_response = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_info.client_id,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
            "resource": settings.MCP_RESOURCE_URL,
        },
    )
    assert token_response.status_code == 200
    token_payload = cast(dict[str, Any], token_response.json())
    return str(token_payload["access_token"])


def _mcp_tool_call(
    client: TestClient,
    access_token: str,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": "tools/call",
            "params": {
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientInfo": {
                        "name": "codex-full-scope-test",
                        "version": "1.0",
                    },
                    "io.modelcontextprotocol/clientCapabilities": {},
                },
                "name": name,
                "arguments": arguments,
            },
        },
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2026-07-28",
            "Mcp-Method": "tools/call",
            "Mcp-Name": name,
            "Host": "127.0.0.1:8000",
        },
    )
    assert response.status_code == 200, response.text
    payload = cast(dict[str, Any], response.json())
    result = payload["result"]
    assert isinstance(result, dict)
    return result


def _confirmed_mcp_write(
    client: TestClient,
    access_token: str,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    pending = _mcp_tool_call(client, access_token, name, arguments)
    assert pending["isError"] is False
    confirmation = pending["structuredContent"]
    assert confirmation["status"] == "input_required"
    confirmed = _mcp_tool_call(
        client,
        access_token,
        name,
        {
            **arguments,
            "confirm": True,
            "confirmation_id": confirmation["confirmation_id"],
        },
    )
    assert confirmed["isError"] is False, confirmed
    structured_content = confirmed["structuredContent"]
    assert isinstance(structured_content, dict)
    return structured_content


def test_oauth_metadata_advertises_cimd_public_client(client: TestClient) -> None:
    response = client.get("/.well-known/oauth-authorization-server")
    assert response.status_code == 200
    payload = response.json()
    assert payload["client_id_metadata_document_supported"] is True
    assert payload["token_endpoint_auth_methods_supported"] == ["none"]
    assert payload["code_challenge_methods_supported"] == ["S256"]
    assert "registration_endpoint" not in payload
    resource_metadata = client.get("/.well-known/oauth-protected-resource/mcp")
    assert resource_metadata.status_code == 200
    assert resource_metadata.json()["authorization_servers"] == [payload["issuer"]]


def test_legacy_ai_routes_are_not_registered(client: TestClient) -> None:
    openapi_paths = client.get(f"{settings.API_V1_STR}/openapi.json").json()["paths"]
    assert not any(path.startswith("/api/v1/agent/") for path in openapi_paths)
    assert not any(
        path.startswith("/api/v1/system/api-tokens") for path in openapi_paths
    )
    assert client.get(f"{settings.API_V1_STR}/agent/transactions/").status_code == 404
    assert client.get(f"{settings.API_V1_STR}/system/api-tokens/").status_code == 404


def test_codex_loopback_redirect_allows_only_ephemeral_port() -> None:
    client_info = _codex_client()
    accepted = client_info.validate_redirect_uri(
        AnyUrl("http://127.0.0.1:17321/callback/codex-test")
    )
    assert str(accepted) == "http://127.0.0.1:17321/callback/codex-test"

    for invalid in (
        "http://localhost:17321/callback/codex-test",
        "http://127.0.0.1:17321/callback/other",
        "https://127.0.0.1:17321/callback/codex-test",
    ):
        try:
            client_info.validate_redirect_uri(AnyUrl(invalid))
        except Exception:
            pass
        else:
            raise AssertionError(f"Expected redirect to be rejected: {invalid}")


def test_codex_cimd_document_is_materialized_without_duplicate_fields(
    monkeypatch: MonkeyPatch,
) -> None:
    client_id = "https://chatgpt.com/oauth/codex/callback-id/client.json"
    raw_metadata = {
        "client_id": client_id,
        "client_uri": "https://chatgpt.com/codex",
        "application_type": "native",
        "redirect_uris": [
            "http://127.0.0.1/callback/callback-id",
            "http://localhost/callback/callback-id",
        ],
        "token_endpoint_auth_method": "none",
        "token_endpoint_auth_methods_supported": ["none"],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "client_name": "Codex",
    }

    class FakeAsyncClient:
        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, url: str, headers: dict[str, str]) -> httpx.Response:
            assert url == client_id
            assert headers == {"Accept": "application/json"}
            return httpx.Response(
                200,
                headers={"Content-Type": "application/json"},
                json=raw_metadata,
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(
        oauth_module.httpx,
        "AsyncClient",
        lambda **_: FakeAsyncClient(),
    )
    oauth_provider._client_cache.clear()
    client_info = asyncio.run(oauth_provider.get_client(client_id))

    assert client_info is not None
    assert client_info.client_name == "Codex"
    assert client_info.token_endpoint_auth_method == "none"
    assert client_info.grant_types == ["authorization_code", "refresh_token"]
    assert client_info.scope == " ".join(oauth_module.AI_SCOPES)
    assert client_info.validate_redirect_uri(
        AnyUrl("http://127.0.0.1:54161/callback/callback-id")
    )


def test_codex_cimd_pkce_authorization_flow(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch: MonkeyPatch,
) -> None:
    client_info = _codex_client()

    async def fake_get_client(client_id: str) -> CIMDClientInformation | None:
        return client_info if client_id == client_info.client_id else None

    monkeypatch.setattr(oauth_provider, "get_client", fake_get_client)
    verifier = "codex-verifier-" + "a" * 48
    redirect_uri = "http://127.0.0.1:17321/callback/codex-test"
    authorize_response = client.get(
        "/authorize",
        params={
            "client_id": client_info.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "code_challenge": _challenge(verifier),
            "code_challenge_method": "S256",
            "scope": "finance:read transactions:write",
            "resource": settings.MCP_RESOURCE_URL,
            "state": "codex-state",
        },
        follow_redirects=False,
    )
    assert authorize_response.status_code == 302
    consent_url = urlsplit(authorize_response.headers["location"])
    request_token = parse_qs(consent_url.query)["request"][0]

    preview = client.get(
        f"{settings.API_V1_STR}/ai-connections/authorization-request",
        params={"request": request_token},
        headers=superuser_token_headers,
    )
    assert preview.status_code == 200
    assert preview.json()["client_name"] == "Codex Desktop"

    decision = client.post(
        f"{settings.API_V1_STR}/ai-connections/authorization-request",
        json={"request": request_token, "approved": True},
        headers=superuser_token_headers,
    )
    assert decision.status_code == 200
    callback = urlsplit(decision.json()["redirect_url"])
    callback_params = parse_qs(callback.query)
    assert callback_params["state"] == ["codex-state"]
    assert callback_params["iss"] == [settings.OAUTH_ISSUER_URL]

    repeated_decision = client.post(
        f"{settings.API_V1_STR}/ai-connections/authorization-request",
        json={"request": request_token, "approved": True},
        headers=superuser_token_headers,
    )
    assert repeated_decision.status_code == 400
    assert "already decided" in repeated_decision.json()["detail"]

    token_response = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_info.client_id,
            "code": callback_params["code"][0],
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
            "resource": settings.MCP_RESOURCE_URL,
        },
    )
    assert token_response.status_code == 200
    tokens = token_response.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    verified = asyncio.run(oauth_provider.load_access_token(tokens["access_token"]))
    assert verified is not None
    assert verified.subject
    assert set(verified.scopes) == {"finance:read", "transactions:write"}

    mcp_headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2026-07-28",
        "Mcp-Method": "server/discover",
        "Host": "127.0.0.1:8000",
    }
    meta = {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientInfo": {
            "name": "codex-test",
            "version": "1.0",
        },
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    discovery = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "server/discover",
            "params": {"_meta": meta},
        },
        headers=mcp_headers,
    )
    assert discovery.status_code == 200
    assert "result" in discovery.json()

    mcp_headers["Mcp-Method"] = "tools/list"
    tools = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {"_meta": meta},
        },
        headers=mcp_headers,
    )
    assert tools.status_code == 200
    assert {tool["name"] for tool in tools.json()["result"]["tools"]} == {
        "get_financial_overview",
        "search_transactions",
        "get_budget_status",
        "list_categories",
        "get_transaction_options",
        "create_transaction",
        "update_transaction",
    }

    category_response = client.post(
        f"{settings.API_V1_STR}/categories/",
        json={"name": f"Codex Test {uuid.uuid4()}", "color": "#64748b"},
        headers=superuser_token_headers,
    )
    assert category_response.status_code == 200
    category_id = category_response.json()["id"]
    arguments: dict[str, Any] = {
        "transaction": {
            "category_id": category_id,
            "transaction_type": 2,
            "amount": 12.34,
            "summary": "Codex confirmed lunch",
            "detail": {"note": "team lunch paid by Codex"},
            "entry_status": 1,
            "transaction_date": "2026-08-18",
        },
        "idempotency_key": f"codex-test-{uuid.uuid4()}",
    }
    mcp_headers["Mcp-Method"] = "tools/call"
    mcp_headers["Mcp-Name"] = "create_transaction"
    pending_response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "_meta": meta,
                "name": "create_transaction",
                "arguments": arguments,
            },
        },
        headers=mcp_headers,
    )
    assert pending_response.status_code == 200, pending_response.text
    pending = pending_response.json()["result"]
    assert pending["isError"] is False
    pending_content = pending["structuredContent"]
    assert pending_content["status"] == "input_required"
    assert pending_content["confirmation_id"]
    assert pending_content["preview"]["transaction"]["amount"] == 12.34
    with Session(engine) as session:
        assert session.exec(select(func.count()).select_from(Transaction)).one() == 0

    confirmed_response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "_meta": meta,
                "name": "create_transaction",
                "arguments": {
                    **arguments,
                    "transaction": {
                        **arguments["transaction"],
                        "handler_user_id": None,
                    },
                    "confirm": True,
                    "confirmation_id": pending_content["confirmation_id"],
                },
            },
        },
        headers=mcp_headers,
    )
    assert confirmed_response.status_code == 200
    confirmed = confirmed_response.json()["result"]
    assert confirmed["isError"] is False
    assert confirmed["structuredContent"]["amount"] == 12.34
    with Session(engine) as session:
        assert session.exec(select(func.count()).select_from(Transaction)).one() == 1
        assert session.exec(select(func.count()).select_from(AIOperation)).one() == 1

    replay_response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "_meta": meta,
                "name": "create_transaction",
                "arguments": arguments,
            },
        },
        headers=mcp_headers,
    )
    replay = replay_response.json()["result"]
    assert replay["isError"] is False
    assert replay["structuredContent"] == confirmed["structuredContent"]
    with Session(engine) as session:
        assert session.exec(select(func.count()).select_from(Transaction)).one() == 1
        assert session.exec(select(func.count()).select_from(AIOperation)).one() == 1

    conflicting_arguments = {
        **arguments,
        "transaction": {**arguments["transaction"], "amount": 99.99},
    }
    conflict_response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "_meta": meta,
                "name": "create_transaction",
                "arguments": conflicting_arguments,
            },
        },
        headers=mcp_headers,
    )
    conflict = conflict_response.json()["result"]
    assert conflict["isError"] is True
    assert "different parameters" in conflict["content"][0]["text"]

    mcp_headers["Mcp-Name"] = "search_transactions"
    search_response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "_meta": meta,
                "name": "search_transactions",
                "arguments": {"keyword": "team lunch", "page": 1, "page_size": 20},
            },
        },
        headers=mcp_headers,
    )
    search_result = search_response.json()["result"]
    assert search_result["isError"] is False
    assert search_result["structuredContent"]["count"] == 1
    assert search_result["structuredContent"]["data"][0]["summary"] == (
        "Codex confirmed lunch"
    )

    mcp_headers["Mcp-Name"] = "get_financial_overview"
    overview_response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "_meta": meta,
                "name": "get_financial_overview",
                "arguments": {
                    "period": "custom",
                    "start_date": "2026-08-18",
                    "end_date": "2026-08-18",
                },
            },
        },
        headers=mcp_headers,
    )
    overview = overview_response.json()["result"]["structuredContent"]
    assert overview["summary"]["expense"] == 12.34
    assert overview["trends"][0]["expense"] == 12.34

    refreshed_response = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_info.client_id,
            "refresh_token": tokens["refresh_token"],
            "resource": settings.MCP_RESOURCE_URL,
        },
    )
    assert refreshed_response.status_code == 200
    refreshed = refreshed_response.json()
    assert refreshed["refresh_token"] != tokens["refresh_token"]
    assert asyncio.run(oauth_provider.load_access_token(refreshed["access_token"]))

    reused_response = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_info.client_id,
            "refresh_token": tokens["refresh_token"],
            "resource": settings.MCP_RESOURCE_URL,
        },
    )
    assert reused_response.status_code == 400
    assert (
        asyncio.run(oauth_provider.load_access_token(refreshed["access_token"])) is None
    )


def test_full_scope_mcp_crud_tools_require_confirmation_and_commit(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch: MonkeyPatch,
) -> None:
    access_token = _authorize_full_scope_codex(
        client, superuser_token_headers, monkeypatch
    )
    unique = uuid.uuid4().hex[:10]

    root_arguments: dict[str, Any] = {
        "category": {
            "name": f"MCP Root {unique}",
            "color": "#334155",
        },
        "idempotency_key": f"category-root-{unique}",
    }
    root_pending = _mcp_tool_call(
        client, access_token, "create_category", root_arguments
    )
    assert root_pending["isError"] is False
    root_confirmation = root_pending["structuredContent"]["confirmation_id"]
    mismatched = _mcp_tool_call(
        client,
        access_token,
        "create_category",
        {
            **root_arguments,
            "category": {**root_arguments["category"], "name": f"Changed {unique}"},
            "confirm": True,
            "confirmation_id": root_confirmation,
        },
    )
    assert mismatched["isError"] is True
    assert "does not match" in mismatched["content"][0]["text"]
    root_confirmed = _mcp_tool_call(
        client,
        access_token,
        "create_category",
        {
            **root_arguments,
            "confirm": True,
            "confirmation_id": root_confirmation,
        },
    )
    assert root_confirmed["isError"] is False
    root_id = root_confirmed["structuredContent"]["id"]

    child = _confirmed_mcp_write(
        client,
        access_token,
        "create_category",
        {
            "category": {
                "name": f"MCP Child {unique}",
                "parent_id": root_id,
                "color": "#0f766e",
            },
            "idempotency_key": f"category-child-{unique}",
        },
    )
    child_id = child["id"]
    budget = _confirmed_mcp_write(
        client,
        access_token,
        "create_budget",
        {
            "budget": {
                "name": f"MCP Budget {unique}",
                "amount": 500,
                "period": 1,
                "year": 2026,
            },
            "idempotency_key": f"budget-create-{unique}",
        },
    )
    budget_id = budget["id"]

    options = _mcp_tool_call(client, access_token, "get_transaction_options", {})[
        "structuredContent"
    ]
    assert any(item["id"] == child_id for item in options["categories"])
    assert any(item["id"] == budget_id for item in options["budgets"])
    handler_id = options["handlers"][0]["id"]

    transaction = _confirmed_mcp_write(
        client,
        access_token,
        "create_transaction",
        {
            "transaction": {
                "category_id": child_id,
                "budget_id": budget_id,
                "transaction_type": 2,
                "amount": 25.5,
                "summary": f"MCP expense {unique}",
                "description": "full-scope connector test",
                "detail": {"source": "pytest"},
                "entry_status": 3,
                "handler_user_id": handler_id,
                "transaction_date": "2026-08-18",
            },
            "idempotency_key": f"transaction-create-{unique}",
        },
    )
    transaction_id = transaction["id"]

    invalid_confirmation = _mcp_tool_call(
        client,
        access_token,
        "update_budget",
        {
            "budget_id": budget_id,
            "changes": {"amount": 650},
            "idempotency_key": f"budget-invalid-confirmation-{unique}",
            "confirm": True,
            "confirmation_id": "not-a-signed-confirmation",
        },
    )
    assert invalid_confirmation["isError"] is True
    assert "invalid or expired" in invalid_confirmation["content"][0]["text"]

    updated_budget = _confirmed_mcp_write(
        client,
        access_token,
        "update_budget",
        {
            "budget_id": budget_id,
            "changes": {"name": f"Updated Budget {unique}", "amount": 650},
            "idempotency_key": f"budget-update-{unique}",
        },
    )
    assert updated_budget["amount"] == 650
    updated_child = _confirmed_mcp_write(
        client,
        access_token,
        "update_category",
        {
            "category_id": child_id,
            "changes": {
                "name": f"Updated Child {unique}",
                "parent_id": root_id,
                "color": "#115e59",
            },
            "idempotency_key": f"category-update-{unique}",
        },
    )
    assert updated_child["name"] == f"Updated Child {unique}"
    updated_transaction = _confirmed_mcp_write(
        client,
        access_token,
        "update_transaction",
        {
            "transaction_id": transaction_id,
            "changes": {
                "summary": f"Updated MCP expense {unique}",
                "category_id": root_id,
                "handler_user_id": None,
            },
            "idempotency_key": f"transaction-update-{unique}",
        },
    )
    assert updated_transaction["summary"] == f"Updated MCP expense {unique}"

    search = _mcp_tool_call(
        client,
        access_token,
        "search_transactions",
        {
            "keyword": unique,
            "start_date": "2026-08-01",
            "end_date": "2026-08-31",
            "transaction_type": 2,
            "category_id": root_id,
            "budget_id": budget_id,
            "entry_status": 3,
            "handler_user_id": handler_id,
            "page": 1,
            "page_size": 10,
        },
    )["structuredContent"]
    assert search["count"] == 1
    budget_status = _mcp_tool_call(
        client,
        access_token,
        "get_budget_status",
        {"year": 2026, "page": 1, "page_size": 10},
    )["structuredContent"]
    assert any(item["id"] == budget_id for item in budget_status["data"])
    categories = _mcp_tool_call(
        client,
        access_token,
        "list_categories",
        {"page": 1, "page_size": 100},
    )["structuredContent"]
    child_row = next(item for item in categories["data"] if item["id"] == child_id)
    assert child_row["path"].endswith(f"Updated Child {unique}")
    overview = _mcp_tool_call(
        client,
        access_token,
        "get_financial_overview",
        {
            "period": "custom",
            "start_date": "2026-08-01",
            "end_date": "2026-08-31",
        },
    )["structuredContent"]
    assert overview["summary"]["expense"] >= 25.5

    for period in ("current_month", "last_month", "current_year", "last_6_months"):
        period_result = _mcp_tool_call(
            client,
            access_token,
            "get_financial_overview",
            {"period": period},
        )
        assert period_result["isError"] is False

    for name, arguments, message in (
        (
            "search_transactions",
            {"page": 0, "page_size": 11},
            "page must be positive",
        ),
        (
            "get_budget_status",
            {"year": 1900, "page": 1, "page_size": 10},
            "Invalid year",
        ),
        (
            "list_categories",
            {"page": 0, "page_size": 50},
            "Invalid pagination",
        ),
        (
            "get_financial_overview",
            {"period": "custom"},
            "custom requires",
        ),
        (
            "get_financial_overview",
            {"period": "current_month", "start_date": "2026-08-01"},
            "only valid with custom",
        ),
        (
            "get_financial_overview",
            {
                "period": "custom",
                "start_date": "2026-08-31",
                "end_date": "2026-08-01",
            },
            "must be ordered",
        ),
    ):
        invalid = _mcp_tool_call(client, access_token, name, arguments)
        assert invalid["isError"] is True
        assert message in invalid["content"][0]["text"]

    deleted_transaction = _confirmed_mcp_write(
        client,
        access_token,
        "delete_transaction",
        {
            "transaction_id": transaction_id,
            "idempotency_key": f"transaction-delete-{unique}",
        },
    )
    assert deleted_transaction["deleted"] is True
    deleted_budget = _confirmed_mcp_write(
        client,
        access_token,
        "delete_budget",
        {
            "budget_id": budget_id,
            "idempotency_key": f"budget-delete-{unique}",
        },
    )
    assert deleted_budget["deleted"] is True
    for category_id, label in ((child_id, "child"), (root_id, "root")):
        deleted_category = _confirmed_mcp_write(
            client,
            access_token,
            "delete_category",
            {
                "category_id": category_id,
                "idempotency_key": f"category-delete-{label}-{unique}",
            },
        )
        assert deleted_category["deleted"] is True

    connections_response = client.get(
        f"{settings.API_V1_STR}/ai-connections/",
        headers=superuser_token_headers,
    )
    assert connections_response.status_code == 200
    full_scope_connection = next(
        item
        for item in connections_response.json()["data"]
        if item["client_name"] == "Codex Full Scope Test"
    )
    revoke_response = client.delete(
        f"{settings.API_V1_STR}/ai-connections/{full_scope_connection['id']}",
        headers=superuser_token_headers,
    )
    assert revoke_response.status_code == 200
    repeated_revoke = client.delete(
        f"{settings.API_V1_STR}/ai-connections/{full_scope_connection['id']}",
        headers=superuser_token_headers,
    )
    assert repeated_revoke.status_code == 200
    missing_revoke = client.delete(
        f"{settings.API_V1_STR}/ai-connections/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert missing_revoke.status_code == 404
