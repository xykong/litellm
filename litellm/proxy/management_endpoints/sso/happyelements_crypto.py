"""
HappyElements SSO Encryption/Decryption Utilities

This module provides encryption and decryption functions for HappyElements SSO integration.
Based on the HappyElements SSO documentation, it implements:
1. MD5 hash for DES key generation
2. DES encryption/decryption for request and response tokens
"""

import base64
import hashlib
from typing import Tuple
from Crypto.Cipher import DES
from Crypto.Util.Padding import pad, unpad


def md5_hash(text: str) -> bytes:
    """
    Generate MD5 hash of input text.
    
    Args:
        text: Input string to hash
        
    Returns:
        MD5 hash bytes
    """
    return hashlib.md5(text.encode('utf-8')).digest()


def hex_to_bytes(hex_str: str) -> bytes:
    """
    Convert hex string to bytes.
    
    Args:
        hex_str: Hex string (e.g., "0A1B2C")
        
    Returns:
        Bytes representation
    """
    return bytes.fromhex(hex_str)


class HappyElementsCrypto:
    """
    HappyElements SSO encryption/decryption handler.
    
    Implements the DES encryption/decryption algorithm specified in the
    HappyElements SSO documentation.
    """
    
    def __init__(self, app_secret: str):
        """
        Initialize crypto handler with app secret.
        
        Args:
            app_secret: HappyElements App Secret (32 character hex string)
        """
        self.app_secret = app_secret
        self._des_key, self._des_iv = self._generate_des_context(app_secret)
    
    def _generate_des_context(self, app_secret: str) -> Tuple[bytes, bytes]:
        """
        Generate DES key and IV from app secret.
        
        According to HappyElements implementation (Jenkins SSO Plugin):
        - app_secret is a 32-character hex string (e.g., "bf2cf9809d5047499607f1cb46c98471")
        - First 16 hex chars → 8 bytes for DES key
        - Last 16 hex chars → 8 bytes for DES IV
        - NO MD5 hashing! Direct hex parsing.
        
        Args:
            app_secret: HappyElements App Secret (32+ hex chars)
            
        Returns:
            Tuple of (des_key, des_iv)
        """
        if len(app_secret) < 32:
            raise ValueError(f"app_secret must be at least 32 characters, got {len(app_secret)}")
        
        # Extract hex strings (NO MD5!)
        key_hex = app_secret[:16]    # First 16 hex chars
        iv_hex = app_secret[16:32]   # Next 16 hex chars
        
        # Convert hex to bytes
        des_key = bytes.fromhex(key_hex)   # 8 bytes
        des_iv = bytes.fromhex(iv_hex)     # 8 bytes
        
        return des_key, des_iv
    
    def encrypt(self, plaintext: bytes) -> bytes:
        """
        Encrypt plaintext using DES CBC mode.
        
        Args:
            plaintext: Data to encrypt
            
        Returns:
            Encrypted ciphertext
        """
        cipher = DES.new(self._des_key, DES.MODE_CBC, self._des_iv)
        
        # DES requires data to be multiple of 8 bytes
        padded_data = pad(plaintext, DES.block_size)
        
        return cipher.encrypt(padded_data)
    
    def decrypt(self, ciphertext: bytes) -> bytes:
        """
        Decrypt ciphertext using DES CBC mode.
        
        Args:
            ciphertext: Encrypted data
            
        Returns:
            Decrypted plaintext
        """
        cipher = DES.new(self._des_key, DES.MODE_CBC, self._des_iv)
        
        decrypted_padded = cipher.decrypt(ciphertext)
        
        # Remove PKCS7 padding
        return unpad(decrypted_padded, DES.block_size)
    
    def hash_and_des_encrypt(self, data: bytes) -> str:
        """
        Hash data with MD5 and encrypt with DES, then Base64 encode.
        
        According to Jenkins SSO Plugin implementation:
        1. MD5 hash the input data (16 bytes)
        2. Concatenate: md5_hash + original_data (ORDER CRITICAL!)
        3. DES encrypt
        4. Base64 encode (NOT hex!)
        
        Args:
            data: Data to encrypt (e.g., "timestamp,ip,callback_url")
            
        Returns:
            Base64-encoded encrypted string
        """
        md5_result = md5_hash(data.decode('utf-8') if isinstance(data, bytes) else data)
        
        data_bytes = data if isinstance(data, bytes) else data.encode('utf-8')
        combined = md5_result + data_bytes
        
        encrypted = self.encrypt(combined)
        
        return base64.b64encode(encrypted).decode('utf-8')
    
    def des_decrypt_and_verify(self, b64_data: str) -> str:
        """
        Decrypt Base64-encoded data and verify MD5 hash.
        
        According to Jenkins SSO Plugin implementation:
        1. Clean whitespace/newlines from Base64 string
        2. Base64 decode
        3. DES decrypt
        4. Split: first 16 bytes = MD5 hash, rest = data
        5. Verify MD5(data) == hash
        6. Return data
        
        Args:
            b64_data: Base64-encoded encrypted string (may contain newlines)
            
        Returns:
            Decrypted and verified data string
            
        Raises:
            ValueError: If MD5 verification fails
        """
        cleaned_b64 = ''.join(b64_data.split())
        
        encrypted_bytes = base64.b64decode(cleaned_b64)
        
        decrypted = self.decrypt(encrypted_bytes)
        
        if len(decrypted) < 16:
            raise ValueError("Decrypted data too short")
        
        hash_part = decrypted[:16]
        data_part = decrypted[16:]
        
        calculated_hash = md5_hash(data_part.decode('utf-8'))
        
        if calculated_hash != hash_part:
            raise ValueError("MD5 verification failed - data may be corrupted or tampered")
        
        return data_part.decode('utf-8')


def create_request_token(app_secret: str, timestamp: int, client_ip: str, callback_url: str) -> str:
    """
    Create HappyElements SSO RequestToken.
    
    Args:
        app_secret: HappyElements App Secret
        timestamp: Current Unix timestamp (seconds)
        client_ip: Client IP address
        callback_url: Callback URL after SSO login
        
    Returns:
        URL-encoded RequestToken
    """
    import urllib.parse
    
    crypto = HappyElementsCrypto(app_secret)
    
    # Format: timestamp,ip,callback_url
    data_str = f"{timestamp},{client_ip},{callback_url}"
    
    # Encrypt and hex encode
    request_token = crypto.hash_and_des_encrypt(data_str.encode('utf-8'))
    
    # URL encode
    return urllib.parse.quote(request_token, safe='')


def decrypt_response_token(app_secret: str, rsp_token: str) -> Tuple[int, str, str]:
    """
    Decrypt HappyElements SSO RspToken.
    
    Args:
        app_secret: HappyElements App Secret
        rsp_token: URL-encoded RspToken from SSO callback
        
    Returns:
        Tuple of (timestamp, ip, username)
        
    Raises:
        ValueError: If decryption or verification fails
    """
    import urllib.parse
    
    crypto = HappyElementsCrypto(app_secret)
    
    # URL decode
    decoded_token = urllib.parse.unquote(rsp_token)
    
    # Decrypt and verify
    decrypted_data = crypto.des_decrypt_and_verify(decoded_token)
    
    # Parse: timestamp,ip,username
    parts = decrypted_data.split(',')
    
    if len(parts) != 3:
        raise ValueError(f"Invalid RspToken format: expected 3 parts, got {len(parts)}")
    
    timestamp = int(parts[0])
    ip = parts[1]
    username = parts[2]
    
    return timestamp, ip, username


def decrypt_response_extra(app_secret: str, response_extra: str) -> dict:
    """
    Decrypt HappyElements SSO ResponseExtra.
    
    Args:
        app_secret: HappyElements App Secret
        response_extra: URL-encoded ResponseExtra from SSO callback
        
    Returns:
        Dict containing user information:
        {
            "timestamp": 1734567890123,
            "client_ip": "192.168.1.100",
            "username": "san.zhang",
            "unique_id": "C251234",
            "email": "san.zhang@example.com",
            "mobile": "13800138000",
            "mobile_area_code": "+86",
            "account_type": "employee|customer|employee,customer",
            "login_channel": "feishu_qr_code|feishu_free_login|token|username|mobile|email|wechat_qr_code"
        }
        
    Raises:
        ValueError: If decryption or JSON parsing fails
    """
    import json
    import urllib.parse
    
    crypto = HappyElementsCrypto(app_secret)
    
    # URL decode
    decoded_extra = urllib.parse.unquote(response_extra)
    
    from litellm._logging import verbose_proxy_logger
    
    decrypted_json = crypto.des_decrypt_and_verify(decoded_extra)
    
    verbose_proxy_logger.warning(
        f"[HappyElements SSO] Raw decrypted ResponseExtra JSON: {decrypted_json}"
    )
    
    result = json.loads(decrypted_json)
    verbose_proxy_logger.warning(
        f"[HappyElements SSO] Parsed ResponseExtra fields: {list(result.keys())}"
    )
    return result
