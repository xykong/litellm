"""
SSO (Single Sign-On) related modules for LiteLLM Proxy.

This package contains custom SSO implementations and utilities.
"""

from litellm.proxy.management_endpoints.sso.custom_microsoft_sso import (
    CustomMicrosoftSSO,
)
from litellm.proxy.management_endpoints.sso.happyelements_endpoints import (
    router as happyelements_router,
)

__all__ = ["CustomMicrosoftSSO", "happyelements_router"]
