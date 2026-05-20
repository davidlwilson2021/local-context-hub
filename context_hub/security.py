from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, Request, status

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
    if not provided or provided != config.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def may_expose_raw_paths(
    authorization: Optional[str] = None,
    x_context_hub_token: Optional[str] = None,
) -> bool:
    """Whether raw filesystem paths may appear in responses."""
    config = load_config()
    if config.expose_raw_paths:
        return True
    if not config.api_token:
        return False
    provided = _extract_token(authorization, x_context_hub_token)
    return bool(provided and provided == config.api_token)
