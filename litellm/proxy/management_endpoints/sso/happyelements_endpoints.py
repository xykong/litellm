"""
HappyElements SSO Endpoints for LiteLLM Proxy

This module provides SSO authentication endpoints for HappyElements integration.

Endpoints:
- GET /sso/happyelements/login - Initiates SSO login by redirecting to HappyElements
- GET /sso/happyelements/callback - Handles SSO callback and creates/updates user

Configuration required in general_settings:
    happyelements_sso:
      app_key: "he_vv5c1vjc08e0rbux"
      app_secret: "bf2cf9809d5047499607f1cb46c98471"
      callback_url: "https://animal-gateway.kxxxl.com/sso/happyelements/callback"  # Auto-detected if not set
      default_team: "animal-ai"  # Optional: default team for new users
      auto_create_users: true    # Optional: automatically create users (default: true)
"""

import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from litellm._logging import verbose_proxy_logger
from litellm.proxy._types import (
    CommonProxyErrors,
    LiteLLM_UserTable,
    LitellmUserRoles,
    NewUserRequest,
    ProxyException,
    UserAPIKeyAuth,
)
from litellm.proxy.auth.auth_checks import get_user_object
from litellm.proxy.management_endpoints.sso.happyelements_sso import HappyElementsSSO
from litellm.proxy.management_endpoints.internal_user_endpoints import new_user
from litellm.proxy.utils import PrismaClient


router = APIRouter()


def get_happyelements_sso_client(
    prisma_client: Optional[PrismaClient] = None,
) -> HappyElementsSSO:
    """
    Get or create HappyElements SSO client from configuration.
    
    Args:
        prisma_client: Optional Prisma client for database operations
        
    Returns:
        HappyElementsSSO client instance
        
    Raises:
        HTTPException: If configuration is missing or invalid
    """
    # Import here to avoid circular dependency
    from litellm.proxy.proxy_server import general_settings, proxy_config
    
    # Check if HappyElements SSO is configured
    if not general_settings:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LiteLLM proxy general_settings not configured",
        )
    
    sso_config = general_settings.get("happyelements_sso")
    
    if not sso_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HappyElements SSO not configured. Please add 'happyelements_sso' to general_settings in config.yaml",
        )
    
    # Validate required fields
    app_key = sso_config.get("app_key") or os.getenv("HAPPYELEMENTS_APP_KEY")
    app_secret = sso_config.get("app_secret") or os.getenv("HAPPYELEMENTS_APP_SECRET")
    
    if not app_key or not app_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="HappyElements SSO configuration incomplete. Required: app_key, app_secret",
        )
    
    # Get callback URL (auto-detect from proxy base URL if not set)
    callback_url = sso_config.get("callback_url")
    
    if not callback_url:
        # Auto-detect from PROXY_BASE_URL or request
        proxy_base_url = os.getenv("PROXY_BASE_URL")
        
        if proxy_base_url:
            # Remove trailing slash
            proxy_base_url = proxy_base_url.rstrip("/")
            callback_url = f"{proxy_base_url}/sso/happyelements/callback"
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="callback_url not configured and PROXY_BASE_URL not set. Please set either in config.yaml or environment.",
            )
    
    verbose_proxy_logger.info(
        f"Initializing HappyElements SSO client with app_key={app_key}, callback_url={callback_url}"
    )
    
    return HappyElementsSSO(
        app_key=app_key,
        app_secret=app_secret,
        callback_url=callback_url,
    )


def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request.
    
    Checks X-Forwarded-For header first (for proxied requests),
    then falls back to direct client IP.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Client IP address
    """
    # Check X-Forwarded-For header (for proxied requests)
    forwarded_for = request.headers.get("X-Forwarded-For")
    
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        # Fall back to direct client IP
        client_ip = request.client.host if request.client else "127.0.0.1"
    
    verbose_proxy_logger.debug(f"Detected client IP: {client_ip}")
    
    return client_ip


@router.get(
    "/sso/happyelements/login",
    tags=["sso"],
    summary="HappyElements SSO Login",
    description="Initiates HappyElements SSO authentication by redirecting to HappyElements login page",
    include_in_schema=True,
)
async def happyelements_login(request: Request):
    """
    Initiate HappyElements SSO login.
    
    This endpoint redirects the user to the HappyElements SSO login page.
    After successful authentication, HappyElements will redirect back to the callback endpoint.
    
    Query Parameters:
        None required (all handled automatically)
        
    Returns:
        RedirectResponse to HappyElements SSO login page
    """
    verbose_proxy_logger.info("HappyElements SSO login initiated")
    
    # Get SSO client
    sso_client = get_happyelements_sso_client()
    
    # Get client IP
    client_ip = get_client_ip(request)
    
    # Generate login URL
    login_url = sso_client.generate_login_url(client_ip=client_ip)
    
    verbose_proxy_logger.info(f"Redirecting to HappyElements SSO: {login_url[:80]}...")
    
    # Redirect to HappyElements SSO
    return RedirectResponse(url=login_url)


@router.get(
    "/sso/happyelements/callback",
    tags=["sso"],
    summary="HappyElements SSO Callback",
    description="Handles HappyElements SSO callback after user authentication",
    include_in_schema=True,
)
async def happyelements_callback(
    request: Request,
    appid: str,
    rsptoken: str,
    response_extra: Optional[str] = None,
    lang: Optional[str] = None,
):
    """
    Handle HappyElements SSO callback.
    
    This endpoint is called by HappyElements after successful user authentication.
    It processes the encrypted tokens, creates/updates the user, and returns a JWT
    that can be used to access the LiteLLM UI and API.
    
    Query Parameters:
        appid: HappyElements App Key (validated)
        rsptoken: Encrypted response token containing user info
        response_extra: Encrypted detailed user info (optional but recommended)
        lang: Language code (zh/en/ja/ko)
        
    Returns:
        RedirectResponse to LiteLLM UI with JWT token
        
    Raises:
        HTTPException: If authentication fails or user creation fails
    """
    from litellm.proxy.proxy_server import (
        general_settings,
        prisma_client,
        user_api_key_cache,
    )
    
    verbose_proxy_logger.warning(
        f"[HappyElements SSO] Callback received: appid={appid}, lang={lang}, has_response_extra={response_extra is not None}"
    )
    verbose_proxy_logger.warning(
        f"[HappyElements SSO] Callback params: rsptoken_len={len(rsptoken) if rsptoken else 0}, "
        f"response_extra_len={len(response_extra) if response_extra else 0}"
    )
    
    try:
        # Get SSO client
        sso_client = get_happyelements_sso_client(prisma_client=prisma_client)
        
        # Process callback and decrypt user info
        user_info = sso_client.process_callback(
            appid=appid,
            rsptoken=rsptoken,
            response_extra=response_extra,
            lang=lang,
        )
        
        verbose_proxy_logger.warning(
            f"[HappyElements SSO] ✅ Callback processed. User: {user_info.get('username')}, "
            f"Email: {user_info.get('email')}, UniqueID: {user_info.get('unique_id')}"
        )
        
        # Get or create user
        if not prisma_client:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database not configured",
            )
        
        # Extract user information
        username = user_info["username"]
        user_id = sso_client.get_user_id(user_info)
        user_email = user_info.get("email")
        
        # If email is empty, construct it from username
        # Employee emails are in format: firstname.lastname@happyelements.com
        if not user_email and username:
            user_email = f"{username}@happyelements.com"
            verbose_proxy_logger.info(
                f"[HappyElements SSO] Email not provided by SSO, constructed from username: {user_email}"
            )
        
        # Check if user exists
        existing_user = await prisma_client.db.litellm_usertable.find_unique(
            where={"user_id": user_id}
        )
        
        if existing_user:
            verbose_proxy_logger.info(f"Existing user found: {user_id}")
            
            # Update user information if needed
            update_data = {}
            
            if user_email and existing_user.user_email != user_email:
                update_data["user_email"] = user_email
            
            if update_data:
                await prisma_client.db.litellm_usertable.update(
                    where={"user_id": user_id},
                    data=update_data,
                )
                verbose_proxy_logger.info(f"Updated user {user_id} with new data: {update_data}")
            
            user_data = existing_user
        else:
            # Auto-create user if enabled
            sso_config = general_settings.get("happyelements_sso", {})
            auto_create = sso_config.get("auto_create_users", True)
            
            if not auto_create:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User {user_id} does not exist and auto_create_users is disabled",
                )
            
            verbose_proxy_logger.info(f"Creating new user: {user_id}")
            
            default_role_config = sso_config.get("default_user_role", "internal_user")
            
            if default_role_config.lower() == "proxy_admin":
                user_role = LitellmUserRoles.PROXY_ADMIN
            elif default_role_config.lower() == "internal_user_viewer":
                user_role = LitellmUserRoles.INTERNAL_USER_VIEW_ONLY
            else:
                user_role = LitellmUserRoles.INTERNAL_USER
            
            user_count = await prisma_client.db.litellm_usertable.count()
            if user_count == 0:
                verbose_proxy_logger.info(f"First user detected, setting as proxy_admin: {user_id}")
                user_role = LitellmUserRoles.PROXY_ADMIN
            
            verbose_proxy_logger.info(f"Setting user role: {user_role}")
            
            # Get default team (if configured)
            default_team = sso_config.get("default_team")
            
            # Create new user
            new_user_request = NewUserRequest(
                user_id=user_id,
                user_email=user_email,
                user_role=user_role,
                teams=([default_team] if default_team else None),
                auto_create_key=False,
            )
            
            # Create admin auth for creating user
            admin_auth = UserAPIKeyAuth(
                user_role=LitellmUserRoles.PROXY_ADMIN
            )
            
            # Create user via internal endpoint
            user_response = await new_user(
                data=new_user_request,
                user_api_key_dict=admin_auth,
            )
            
            verbose_proxy_logger.info(f"Created new user: {user_id}")
            
            # Fetch the created user
            user_data = await prisma_client.db.litellm_usertable.find_unique(
                where={"user_id": user_id}
            )
            
            if not user_data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="User creation failed",
                )
        
        # Generate JWT token for UI access
        from litellm.proxy.auth.handle_jwt import JWTHandler
        from litellm.proxy.management_endpoints.ui_sso import SSOAuthenticationHandler
        
        jwt_handler = JWTHandler()
        
        display_name = sso_client.get_user_display_name(user_info)
        
        openid_result = {
            "id": user_id,
            "email": user_email or user_id,
            "display_name": display_name,
            "first_name": user_info.get("username"),
            "last_name": "",
            "provider": "happyelements",
        }
        
        verbose_proxy_logger.info(
            f"[HappyElements SSO] Creating openid_result: id={user_id}, email={user_email}, "
            f"display_name={display_name}, username={user_info.get('username')}"
        )
        
        redirect_response = await SSOAuthenticationHandler.get_redirect_response_from_openid(
            result=openid_result,
            request=request,
            received_response=None,
            generic_client_id=None,
            ui_access_mode=general_settings.get("ui_access_mode"),
        )
        
        verbose_proxy_logger.info(f"SSO login successful for user: {user_id}")
        
        return redirect_response
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        verbose_proxy_logger.error(f"HappyElements SSO callback error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SSO authentication failed: {str(e)}",
        )
