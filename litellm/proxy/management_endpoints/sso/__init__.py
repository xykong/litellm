"""
SSO (Single Sign-On) related modules for LiteLLM Proxy.

This package contains custom SSO implementations and utilities.
"""

from litellm.proxy.management_endpoints.sso.custom_microsoft_sso import (
    CustomMicrosoftSSO,
)
from litellm.proxy.management_endpoints.sso.cli_sso_endpoints import (
    router as cli_sso_router,
)

__all__ = ["CustomMicrosoftSSO", "cli_sso_router"]
