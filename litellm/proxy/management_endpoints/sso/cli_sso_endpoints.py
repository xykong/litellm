"""
Provider-neutral CLI SSO utilities for LiteLLM Proxy.

This module contains reusable CLI SSO functions extracted from the legacy
HappyElements SSO module. These utilities work with any SSO provider and
handle:

- Department-based team assignment
- User-to-team membership management
- CLI virtual key creation and reuse
- Team switching for CLI tokens

These functions are used by both the OIDC SSO flow and the legacy HE SSO flow.
"""

import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, status

from litellm._logging import verbose_proxy_logger
from litellm.constants import LENGTH_OF_LITELLM_GENERATED_KEY
from litellm.proxy._types import (
    LiteLLM_UserTable,
    LitellmUserRoles,
    Member,
    NewTeamRequest,
    SpecialModelNames,
    TeamMemberAddRequest,
    UserAPIKeyAuth,
)
from litellm.proxy.management_endpoints.internal_user_endpoints import new_user
from litellm.proxy.management_endpoints.team_endpoints import new_team, team_member_add


# Organization ID for 开心消消乐 project in LiteLLM
_DEFAULT_ORG_ID = "9661420d-7813-4ae9-a843-7b75ea7f2cb6"
# Department API base URL
_DEPT_API_URL = "https://ale.kxxxl.com/server/department.action"


router = APIRouter()


async def _get_department_team_alias(sso: str) -> Optional[str]:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                _DEPT_API_URL,
                params={"method": "getBySso", "sso": sso},
            )
        data = resp.json()
        if data.get("code") != 0:
            verbose_proxy_logger.warning(
                f"[CLI SSO] Department API returned non-zero code for sso={sso}: {data.get('code')}"
            )
            return None
        result = data.get("result") or {}
        parts = [
            d
            for d in [
                result.get("一级部门"),
                result.get("二级部门"),
                result.get("三级部门"),
            ]
            if d
        ]
        if not parts:
            verbose_proxy_logger.warning(
                f"[CLI SSO] All department levels empty for sso={sso}, skipping team assignment"
            )
            return None
        return "-".join(parts)
    except Exception as e:
        verbose_proxy_logger.warning(
            f"[CLI SSO] Failed to fetch department info for sso={sso}: {e}"
        )
        return None


async def _ensure_user_in_team(
    user_id: str,
    user_teams: list,
    team_alias: str,
    prisma_client: object,
) -> None:
    try:
        existing_team = await prisma_client.db.litellm_teamtable.find_first(
            where={"team_alias": team_alias}
        )
        if existing_team is None:
            admin_auth = UserAPIKeyAuth(user_role=LitellmUserRoles.PROXY_ADMIN)
            from fastapi import Request as FastAPIRequest

            created = await new_team(
                data=NewTeamRequest(
                    team_alias=team_alias,
                    organization_id=_DEFAULT_ORG_ID,
                    team_member_permissions=["/key/generate"],
                    models=[SpecialModelNames.all_proxy_models.value],
                ),
                http_request=FastAPIRequest(
                    scope={"type": "http", "path": "/sso/callback"}
                ),
                user_api_key_dict=admin_auth,
            )
            team_id = created["team_id"]
            verbose_proxy_logger.info(
                f"[CLI SSO] Created team team_alias={team_alias}, team_id={team_id}"
            )
        else:
            team_id = existing_team.team_id

        if team_id not in (user_teams or []):
            await team_member_add(
                data=TeamMemberAddRequest(
                    team_id=team_id,
                    member=Member(user_id=user_id, role="user"),
                ),
                user_api_key_dict=UserAPIKeyAuth(
                    user_role=LitellmUserRoles.PROXY_ADMIN
                ),
            )
            verbose_proxy_logger.info(
                f"[CLI SSO] Added user={user_id} to team={team_alias} ({team_id})"
            )
        else:
            verbose_proxy_logger.debug(
                f"[CLI SSO] User={user_id} already in team={team_alias}, skipping"
            )
    except Exception as e:
        verbose_proxy_logger.warning(
            f"[CLI SSO] Failed to ensure user={user_id} in team={team_alias}: {e}"
        )


async def _get_or_create_cli_virtual_key(
    user_id: str,
    user_email: Optional[str],
    user_data: object,
    prisma_client: object,
    preferred_team_id: Optional[str] = None,
    sso_username: Optional[str] = None,
    usage: str = "cli-sso",
) -> str:
    from litellm.proxy.management_endpoints.key_management_endpoints import (
        generate_key_helper_fn,
    )
    from litellm.proxy._types import LitellmUserRoles
    from litellm.proxy.common_utils.encrypt_decrypt_utils import (
        decrypt_value_helper,
        encrypt_value_helper,
    )
    from datetime import datetime, timezone
    from litellm.constants import LENGTH_OF_LITELLM_GENERATED_KEY
    import secrets
    import uuid

    name = sso_username or user_id
    alias_prefix = f"{usage}-{name}-"

    user_role = getattr(user_data, "user_role", None) or LitellmUserRoles.INTERNAL_USER
    teams = getattr(user_data, "teams", None) or []

    if preferred_team_id and preferred_team_id in teams:
        team_id = preferred_team_id
    else:
        team_id = teams[0] if teams else None

    existing_key_row = None
    try:
        now = datetime.now(timezone.utc)
        where_clause: dict = {
            "user_id": user_id,
            "key_alias": {"startsWith": alias_prefix},
            "OR": [
                {"expires": None},
                {"expires": {"gt": now}},
            ],
        }
        if team_id:
            where_clause["team_id"] = team_id

        existing_key_row = await prisma_client.db.litellm_verificationtoken.find_first(
            where=where_clause,
            order={"created_at": "desc"},
        )
    except Exception as e:
        verbose_proxy_logger.warning(
            f"[CLI SSO] Failed to query existing CLI key for user={user_id}, alias_prefix={alias_prefix}: {e}"
        )

    if existing_key_row is not None:
        cli_token: Optional[str] = None
        try:
            meta = existing_key_row.metadata or {}
            if isinstance(meta, dict):
                encrypted = meta.get("cli_token")
                if encrypted:
                    cli_token = decrypt_value_helper(
                        value=encrypted,
                        key="cli_token",
                        exception_type="debug",
                        return_original_value=False,
                    )
        except Exception:
            cli_token = None

        if cli_token:
            verbose_proxy_logger.info(
                f"[CLI SSO] Reusing existing CLI key for user={user_id}, alias={existing_key_row.key_alias}, team={team_id}"
            )
            return cli_token

    cli_key_alias = f"{alias_prefix}{uuid.uuid4().hex[:6]}"
    virtual_key = f"sk-{secrets.token_urlsafe(LENGTH_OF_LITELLM_GENERATED_KEY)}"
    encrypted_token = encrypt_value_helper(virtual_key)

    await generate_key_helper_fn(
        request_type="key",
        token=virtual_key,
        user_id=user_id,
        user_email=user_email,
        user_role=str(user_role),
        team_id=team_id,
        key_alias=cli_key_alias,
        duration=None,
        models=[SpecialModelNames.all_team_models.value],
        inherit_user_models=False,
        metadata={"cli_token": encrypted_token},
        created_by=user_id,
        updated_by=user_id,
    )

    verbose_proxy_logger.info(
        f"[CLI SSO] CLI virtual key created for user={user_id}, alias={cli_key_alias}, team={team_id}"
    )
    return virtual_key


@router.post(
    "/sso/cli/switch-team",
    tags=["sso"],
    include_in_schema=False,
)
async def cli_switch_team(request: Request):
    """
    Switch the team associated with the caller's CLI virtual key.

    Accepts JSON body: {"team_id": "<target-team-id>"}
    Authorization: Bearer <current-cli-token>

    Re-generates the caller's CLI virtual key bound to the requested team
    and returns the new key. No browser interaction required.
    """
    from litellm.proxy.proxy_server import prisma_client, user_api_key_cache
    from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
    from litellm.proxy._types import UserAPIKeyAuth

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    current_token = auth_header[len("Bearer "):]

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    target_team_id: Optional[str] = body.get("team_id")
    if not target_team_id:
        raise HTTPException(status_code=400, detail="team_id is required")
    target_usage: str = body.get("usage") or "sso"

    if not prisma_client:
        raise HTTPException(status_code=500, detail="Database not configured")

    token_hash = prisma_client.hash_token(token=current_token)
    key_row = await prisma_client.db.litellm_verificationtoken.find_unique(
        where={"token": token_hash}
    )
    if not key_row:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id: str = key_row.user_id or ""
    if not user_id:
        raise HTTPException(status_code=401, detail="Token has no associated user")

    user_data = await prisma_client.db.litellm_usertable.find_unique(
        where={"user_id": user_id}
    )
    if not user_data:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    user_teams: list = getattr(user_data, "teams", None) or []
    if target_team_id not in user_teams:
        raise HTTPException(
            status_code=403,
            detail=f"User does not belong to team {target_team_id}. Available: {user_teams}",
        )

    user_email = getattr(user_data, "user_email", None)
    sso_username = user_email.split("@")[0] if user_email else None
    new_key = await _get_or_create_cli_virtual_key(
        user_id=user_id,
        user_email=user_email,
        user_data=user_data,
        prisma_client=prisma_client,
        preferred_team_id=target_team_id,
        sso_username=sso_username,
        usage=target_usage,
    )

    team_alias: Optional[str] = None
    try:
        team_row = await prisma_client.db.litellm_teamtable.find_unique(
            where={"team_id": target_team_id}
        )
        if team_row:
            team_alias = team_row.team_alias
    except Exception:
        pass

    verbose_proxy_logger.info(
        f"[CLI SSO] CLI team switch: user={user_id}, new_team={target_team_id}"
    )
    return {
        "status": "ready",
        "key": new_key,
        "user_id": user_id,
        "team_id": target_team_id,
        "team_alias": team_alias,
        "teams": user_teams,
    }
