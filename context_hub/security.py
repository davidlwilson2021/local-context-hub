from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, JSONResponse, Response

from .db import load_config


def _extract_token(
    authorization: Optional[str],
    x_context_hub_token: Optional[str],
) -> Optional[str]:
    if x_context_hub_token:
        return x_context_hub_token.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def token_from_request(request: Request) -> Optional[str]:
    """Read API token from Authorization: Bearer or X-Context-Hub-Token header.

    Note: ?token= query-string auth is intentionally NOT supported.
    Tokens in URLs appear in web-server access logs, browser history,
    and Referer headers. Use request headers only.
    """
    return _extract_token(
        request.headers.get("authorization"),
        request.headers.get("x-context-hub-token"),
    )


def validate_token(provided: Optional[str]) -> bool:
    config = load_config()
    if not config.api_token:
        return True
    return bool(provided and provided == config.api_token)


def require_api_auth(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_context_hub_token: Optional[str] = Header(default=None, alias="X-Context-Hub-Token"),
) -> None:
    """Enforce bearer token when api_token is configured."""
    config = load_config()
    if not config.api_token:
        return

    provided = _extract_token(authorization, x_context_hub_token)
    if not validate_token(provided):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def auth_template_context(request: Request) -> dict[str, Optional[str]]:
    """Context for Jinja templates.

    auth_suffix is always empty — query-string token passing is no longer
    supported to prevent token leakage into server logs and browser history.
    """
    return {"auth_token": None, "auth_suffix": ""}


def may_expose_raw_paths(
    authorization: Optional[str] = None,
    x_context_hub_token: Optional[str] = None,
    *,
    query_token: Optional[str] = None,
) -> bool:
    """Whether raw filesystem paths may appear in responses."""
    config = load_config()
    if config.expose_raw_paths:
        return True
    if not config.api_token:
        return False
    # query_token param kept for call-site compatibility but ignored (see L-1 fix)
    provided = _extract_token(authorization, x_context_hub_token)
    return validate_token(provided)


def may_expose_metadata(
    authorization: Optional[str] = None,
    x_context_hub_token: Optional[str] = None,
    *,
    query_token: Optional[str] = None,
) -> bool:
    """Whether full activity metadata may appear in API responses."""
    config = load_config()
    if config.expose_metadata:
        return True
    if not config.api_token:
        return False
    # query_token param kept for call-site compatibility but ignored (see L-1 fix)
    provided = _extract_token(authorization, x_context_hub_token)
    return validate_token(provided)


class ApiAuthMiddleware(BaseHTTPMiddleware):
    """Require api_token on all routes when configured."""

    async def dispatch(self, request: Request, call_next) -> Response:
        config = load_config()
        if not config.api_token:
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        if not validate_token(token_from_request(request)):
            accept = request.headers.get("accept", "")
            if "text/html" in accept:
                return HTMLResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content=(
                        "<h1>Context Hub — authentication required</h1>"
                        "<p>Include your API token as a request header:</p>"
                        "<pre>Authorization: Bearer YOUR_TOKEN</pre>"
                        "<p>Or:</p>"
                        "<pre>X-Context-Hub-Token: YOUR_TOKEN</pre>"
                        "<p>For browser access, use a header-injection extension "
                        "(e.g. ModHeader for Chrome/Firefox).</p>"
                        "<p>Generate or reset a token:</p>"
                        "<pre>python -m context_hub.cli config token-generate</pre>"
                    ),
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or missing API token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)
