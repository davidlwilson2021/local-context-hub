from __future__ import annotations

from typing import Optional
from urllib.parse import quote

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
    """Read API token from query string, Bearer header, or X-Context-Hub-Token."""
    query_token = request.query_params.get("token")
    if query_token:
        return query_token.strip()
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

    provided = token_from_request(request) or _extract_token(authorization, x_context_hub_token)
    if not validate_token(provided):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def auth_template_context(request: Request) -> dict[str, Optional[str]]:
    """Context for Jinja templates to preserve token in links and forms."""
    config = load_config()
    if not config.api_token:
        return {"auth_token": None, "auth_suffix": ""}
    token = token_from_request(request)
    suffix = f"&token={quote(token, safe='')}" if token else ""
    return {"auth_token": token, "auth_suffix": suffix}


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
    provided = query_token or _extract_token(authorization, x_context_hub_token)
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
    provided = query_token or _extract_token(authorization, x_context_hub_token)
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
                        "<p>Add your API token to the URL:</p>"
                        "<pre>http://127.0.0.1:8000/?token=YOUR_TOKEN</pre>"
                        "<p>Generate or reset a token:</p>"
                        "<pre>python -m context_hub.cli config token-generate</pre>"
                        "<p>Then restart <code>serve</code> and use the URL it prints.</p>"
                    ),
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or missing API token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)
