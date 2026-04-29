from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

_VOD_HOST = "vod.tencentcloudapi.com"
_VOD_ENDPOINT = f"https://{_VOD_HOST}"
_VOD_REGION = "ap-guangzhou"
_VOD_VERSION = "2018-07-17"
_VOD_SERVICE = "vod"

# Task type → result key mapping
_TASK_TYPE_KEY = {
    "AigcImage": "AigcImageTask",
    "AigcImageTask": "AigcImageTask",
    "AigcVideo": "AigcVideoTask",
    "AigcVideoTask": "AigcVideoTask",
    "AigcSceneImage": "AigcSceneImageTask",
    "AigcSceneImageTask": "AigcSceneImageTask",
}


@dataclass
class TencentVODCredentials:
    secret_id: str
    secret_key: str
    sub_app_id: int = 0

    @classmethod
    def from_env(cls) -> "TencentVODCredentials":
        secret_id = os.environ.get("TENCENTCLOUD_SECRET_ID", "")
        secret_key = os.environ.get("TENCENTCLOUD_SECRET_KEY", "")
        if not secret_id or not secret_key:
            raise ValueError(
                "VOD credentials not configured: TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY"
            )
        sub_app_id = int(os.environ.get("VOD_SUB_APP_ID", "0"))
        return cls(secret_id=secret_id, secret_key=secret_key, sub_app_id=sub_app_id)


class TencentVODClient:
    """Reusable Tencent VOD AIGC client — TC3 signing, task submission, polling."""

    def __init__(self, credentials: Optional[TencentVODCredentials] = None):
        self._creds: Optional[TencentVODCredentials] = credentials

    def _get_credentials(self) -> TencentVODCredentials:
        if self._creds is not None:
            return self._creds
        return TencentVODCredentials.from_env()

    def _sign_request(self, action: str, payload: dict) -> dict[str, str]:
        """TC3-HMAC-SHA256 signing per https://cloud.tencent.com/document/api/267/30661"""
        creds = self._get_credentials()
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
        timestamp = int(time.time())
        date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")

        canonical_headers = f"content-type:application/json\nhost:{_VOD_HOST}\nx-tc-action:{action.lower()}\n"
        signed_headers = "content-type;host;x-tc-action"
        hashed_payload = hashlib.sha256(body).hexdigest()
        canonical_request = "\n".join(
            ["POST", "/", "", canonical_headers, signed_headers, hashed_payload]
        )

        credential_scope = f"{date}/{_VOD_SERVICE}/tc3_request"
        hashed_canonical = hashlib.sha256(canonical_request.encode()).hexdigest()
        string_to_sign = "\n".join(
            ["TC3-HMAC-SHA256", str(timestamp), credential_scope, hashed_canonical]
        )

        def _hmac_sha256(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        secret_date = _hmac_sha256(("TC3" + creds.secret_key).encode(), date)
        secret_service = _hmac_sha256(secret_date, _VOD_SERVICE)
        secret_signing = _hmac_sha256(secret_service, "tc3_request")
        signature = hmac.new(
            secret_signing, string_to_sign.encode(), hashlib.sha256
        ).hexdigest()

        authorization = (
            f"TC3-HMAC-SHA256 "
            f"Credential={creds.secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )
        return {
            "Authorization": authorization,
            "Content-Type": "application/json",
            "Host": _VOD_HOST,
            "X-TC-Action": action,
            "X-TC-Version": _VOD_VERSION,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Region": _VOD_REGION,
        }

    async def call_vod(self, action: str, payload: dict) -> dict:
        """Submit one Tencent VOD API call and return the Response body."""
        creds = self._get_credentials()
        if creds.sub_app_id:
            payload = {**payload, "SubAppId": creds.sub_app_id}

        headers = self._sign_request(action, payload)
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(_VOD_ENDPOINT, headers=headers, content=body)

        try:
            data = resp.json()
        except Exception:
            raise RuntimeError(
                f"VOD API returned non-JSON (HTTP {resp.status_code}): {resp.text[:200]}"
            )

        response_body = data.get("Response", data)
        error = response_body.get("Error") if isinstance(response_body, dict) else None
        if error:
            code = error.get("Code", "Unknown")
            message = error.get("Message", "Unknown error")
            raise RuntimeError(f"VOD API error [{code}]: {message}")

        return response_body

    async def poll_until_done(
        self,
        task_id: str,
        poll_interval: float = 5.0,
        timeout: float = 600.0,
    ) -> dict:
        """
        Poll DescribeTaskDetail until FINISH/FAIL or timeout.

        Returns normalized dict:
          {
            "status": "FINISH" | "FAIL",
            "file_infos": [{"url": "...", "file_id": "...", ...}],
            "message": "",
            "raw": {...},
          }
        Raises TimeoutError on timeout, RuntimeError on FAIL.
        """
        deadline = time.monotonic() + timeout
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"VOD task {task_id!r} did not complete within {timeout}s"
                )

            result = await self.call_vod("DescribeTaskDetail", {"TaskId": task_id})
            task_type = result.get("TaskType", "")
            result_key = _TASK_TYPE_KEY.get(task_type)
            aigc = result.get(result_key, result) if result_key else result

            status_val = (
                aigc.get("Status", "PROCESSING")
                if isinstance(aigc, dict)
                else "PROCESSING"
            )
            task_output = aigc.get("Output", aigc) if isinstance(aigc, dict) else aigc
            message = (
                (aigc.get("ErrCodeExt") or aigc.get("ErrMsg") or "")
                if isinstance(aigc, dict)
                else ""
            )

            if status_val in ("FINISH", "SUCCESS"):
                file_infos = _normalize_file_infos(task_output)
                return {
                    "status": "FINISH",
                    "file_infos": file_infos,
                    "message": message,
                    "raw": result,
                }
            elif status_val in ("FAIL", "ERROR", "SUBMIT_FAILED"):
                raise RuntimeError(
                    f"VOD task {task_id!r} failed with status={status_val}: {message}"
                )

            await asyncio.sleep(poll_interval)


def _normalize_file_infos(output: Any) -> list[dict]:
    """Convert FileInfos (PascalCase) → list of normalized dicts with snake_case keys."""
    if not isinstance(output, dict):
        return []
    raw = output.get("FileInfos") or output.get("file_infos") or []
    return [
        {
            "url": fi.get("FileUrl") or fi.get("url") or "",
            "file_url": fi.get("FileUrl") or fi.get("file_url") or "",
            "file_id": fi.get("FileId") or fi.get("file_id") or "",
            "storage_mode": fi.get("StorageMode") or fi.get("storage_mode") or "",
            "expire_time": fi.get("ExpireTime") or fi.get("expire_time") or "",
        }
        for fi in raw
    ]


# Module-level singleton for re-use (credentials loaded lazily from env)
default_client = TencentVODClient()
