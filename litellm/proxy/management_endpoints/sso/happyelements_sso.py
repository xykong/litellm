"""
HappyElements SSO Client

This module provides the SSO client for HappyElements authentication integration.
It handles the OAuth2-like flow with custom DES encryption as specified in the
HappyElements SSO documentation.

SSO Flow:
1. User initiates login -> redirect to HappyElements SSO login page with RequestToken
2. User authenticates on HappyElements SSO
3. SSO redirects back to callback URL with RspToken and ResponseExtra
4. Callback handler decrypts tokens and creates/updates user
"""

import time
from typing import Optional, Dict, Any
from litellm._logging import verbose_proxy_logger
from litellm.proxy.management_endpoints.sso.happyelements_crypto import (
    create_request_token,
    decrypt_response_token,
    decrypt_response_extra,
)


class HappyElementsSSO:
    """
    HappyElements SSO Client.
    
    Handles generation of SSO login URLs and processing of SSO callbacks.
    """
    
    # HappyElements SSO domain
    SSO_DOMAIN = "https://he-sso.happyelements.com"
    SSO_LOGIN_PATH = "/sso/login"
    
    def __init__(
        self,
        app_key: str,
        app_secret: str,
        callback_url: str,
    ):
        """
        Initialize HappyElements SSO client.
        
        Args:
            app_key: HappyElements App Key (e.g., "he_vv5c1vjc08e0rbux")
            app_secret: HappyElements App Secret (32 character hex string)
            callback_url: Callback URL for SSO to redirect to after authentication
        """
        self.app_key = app_key
        self.app_secret = app_secret
        self.callback_url = callback_url
    
    def generate_login_url(self, client_ip: str) -> str:
        """
        Generate HappyElements SSO login URL.
        
        According to the documentation, the login URL format is:
        https://he-sso.happyelements.com/sso/login?appid=AppKey&reqtoken=RequestToken
        
        RequestToken is generated from:
        1. Current timestamp (seconds)
        2. Client IP address
        3. Callback URL
        
        Args:
            client_ip: Client IP address (used for security validation)
            
        Returns:
            Complete SSO login URL
        """
        # Get current timestamp in seconds
        timestamp = int(time.time())
        
        verbose_proxy_logger.debug(
            f"Generating HappyElements SSO login URL: timestamp={timestamp}, ip={client_ip}, callback={self.callback_url}"
        )
        
        # Generate encrypted RequestToken
        request_token = create_request_token(
            app_secret=self.app_secret,
            timestamp=timestamp,
            client_ip=client_ip,
            callback_url=self.callback_url,
        )
        
        # Construct login URL
        login_url = f"{self.SSO_DOMAIN}{self.SSO_LOGIN_PATH}?appid={self.app_key}&reqtoken={request_token}"
        
        verbose_proxy_logger.debug(f"Generated SSO login URL (token truncated): {login_url[:100]}...")
        
        return login_url
    
    def process_callback(
        self,
        appid: str,
        rsptoken: str,
        response_extra: Optional[str] = None,
        lang: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process HappyElements SSO callback.
        
        According to the documentation, the callback URL format is:
        http://callback_url?appid=AppKey&rsptoken=RspToken&response_extra=ResponseExtra&lang=Lang
        
        RspToken decrypts to: timestamp,ip,username
        ResponseExtra decrypts to: JSON with detailed user info
        
        Args:
            appid: App Key (should match self.app_key)
            rsptoken: Encrypted response token
            response_extra: Encrypted response extra (optional, but recommended)
            lang: Language code (zh/en/ja/ko)
            
        Returns:
            Dict containing user information:
            {
                "username": "san.zhang",
                "email": "san.zhang@example.com",
                "unique_id": "C251234",
                "mobile": "13800138000",
                "mobile_area_code": "+86",
                "account_type": "employee",
                "login_channel": "feishu_qr_code",
                "timestamp": 1734567890,
                "client_ip": "192.168.1.100",
                "lang": "zh"
            }
            
        Raises:
            ValueError: If appid doesn't match or decryption fails
        """
        # Validate appid
        if appid != self.app_key:
            raise ValueError(f"AppID mismatch: expected {self.app_key}, got {appid}")
        
        verbose_proxy_logger.info(f"Processing HappyElements SSO callback for appid={appid}")
        
        # Decrypt RspToken
        timestamp, client_ip, username = decrypt_response_token(
            app_secret=self.app_secret,
            rsp_token=rsptoken,
        )
        
        verbose_proxy_logger.debug(
            f"Decrypted RspToken: username={username}, ip={client_ip}, timestamp={timestamp}"
        )
        
        # Validate timestamp (optional: check if within reasonable time window, e.g., 5 minutes)
        current_time = int(time.time())
        time_diff = abs(current_time - timestamp)
        
        if time_diff > 300:  # 5 minutes
            verbose_proxy_logger.warning(
                f"SSO callback timestamp is {time_diff} seconds old (threshold: 300s)"
            )
        
        # Prepare result with basic info from RspToken
        result = {
            "username": username,
            "timestamp": timestamp,
            "client_ip": client_ip,
            "lang": lang or "zh",
        }
        
        # Decrypt ResponseExtra if available (recommended)
        if response_extra:
            try:
                verbose_proxy_logger.warning(
                    f"[HappyElements SSO] Decrypting ResponseExtra (length: {len(response_extra)})"
                )
                
                extra_data = decrypt_response_extra(
                    app_secret=self.app_secret,
                    response_extra=response_extra,
                )
                
                verbose_proxy_logger.warning(
                    f"[HappyElements SSO] ✅ ResponseExtra decrypted. User: {extra_data.get('username')}, "
                    f"Email: {extra_data.get('email')}, UniqueID: {extra_data.get('unique_id')}"
                )
                
                # Merge extra data into result
                result.update({
                    "email": extra_data.get("email"),
                    "unique_id": extra_data.get("unique_id"),
                    "mobile": extra_data.get("mobile"),
                    "mobile_area_code": extra_data.get("mobile_area_code"),
                    "account_type": extra_data.get("account_type"),
                    "login_channel": extra_data.get("login_channel"),
                    # Override timestamp and client_ip from ResponseExtra if available
                    "timestamp": extra_data.get("timestamp", timestamp),
                    "client_ip": extra_data.get("client_ip", client_ip),
                })
            except Exception as e:
                verbose_proxy_logger.error(
                    f"❌ Failed to decrypt ResponseExtra: {type(e).__name__}: {e}. "
                    f"Falling back to RspToken data only."
                )
        else:
            verbose_proxy_logger.warning(
                "ResponseExtra not provided. User info will be limited to username, timestamp, and IP."
            )
        
        return result
    
    @staticmethod
    def get_user_display_name(user_info: Dict[str, Any]) -> str:
        """
        Get user display name from SSO user info.
        
        Args:
            user_info: User information from process_callback
            
        Returns:
            User display name (email or username)
        """
        return user_info.get("email") or user_info.get("username") or "unknown"
    
    @staticmethod
    def get_user_id(user_info: Dict[str, Any]) -> str:
        """
        Get unique user ID from SSO user info.
        
        Args:
            user_info: User information from process_callback
            
        Returns:
            Unique user ID (unique_id or username)
        """
        return user_info.get("unique_id") or user_info.get("username") or "unknown"
