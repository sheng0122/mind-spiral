"""API 認證 — 簡單 Bearer token 驗證"""

from __future__ import annotations

import os
from typing import Literal

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

Role = Literal["owner", "agent", "viewer", "public"]

_security = HTTPBearer(auto_error=False)


def _load_tokens() -> dict[str, Role]:
    """從環境變數載入 token → role 映射。"""
    mapping: dict[str, Role] = {}

    owner_token = os.environ.get("MIND_SPIRAL_OWNER_TOKEN")
    if owner_token:
        mapping[owner_token] = "owner"

    agent_tokens = os.environ.get("MIND_SPIRAL_AGENT_TOKENS", "")
    for t in agent_tokens.split(","):
        t = t.strip()
        if t:
            mapping[t] = "agent"

    viewer_tokens = os.environ.get("MIND_SPIRAL_VIEWER_TOKENS", "")
    for t in viewer_tokens.split(","):
        t = t.strip()
        if t:
            mapping[t] = "viewer"

    return mapping


_tokens: dict[str, Role] | None = None


def _get_tokens() -> dict[str, Role]:
    global _tokens
    if _tokens is None:
        _tokens = _load_tokens()
    return _tokens


def reload_tokens():
    """重新載入 token（測試用）。"""
    global _tokens
    _tokens = None


def resolve_role(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> Role:
    """解析 Bearer token，回傳角色。無 token 時回傳 public。"""
    if credentials is None:
        return "public"
    token = credentials.credentials
    tokens = _get_tokens()
    return tokens.get(token, "public")


def require_owner(role: Role = Depends(resolve_role)) -> Role:
    """限制 owner 角色。"""
    if role != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    return role


def require_authenticated(role: Role = Depends(resolve_role)) -> Role:
    """限制已認證角色（owner / agent / viewer）。"""
    if role == "public":
        raise HTTPException(status_code=401, detail="Authentication required")
    return role
