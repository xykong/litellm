from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from litellm._logging import verbose_proxy_logger
from litellm.proxy.auth.user_api_key_auth import UserAPIKeyAuth, user_api_key_auth

router = APIRouter()

_VOD_HOST = "vod.tencentcloudapi.com"
_VOD_ENDPOINT = f"https://{_VOD_HOST}"
_VOD_REGION = "ap-guangzhou"
_VOD_VERSION = "2018-07-17"
_VOD_SERVICE = "vod"


def _get_credentials() -> tuple[str, str, int]:
    secret_id = os.environ.get("TENCENTCLOUD_SECRET_ID", "")
    secret_key = os.environ.get("TENCENTCLOUD_SECRET_KEY", "")
    sub_app_id_str = os.environ.get("VOD_SUB_APP_ID", "0")
    if not secret_id or not secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VOD credentials not configured (TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY)",
        )
    return secret_id, secret_key, int(sub_app_id_str)


def _sign_request(secret_id: str, secret_key: str, action: str, payload: dict) -> dict[str, str]:
    # TC3-HMAC-SHA256 signature per https://cloud.tencent.com/document/api/267/30661
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    timestamp = int(time.time())
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")

    canonical_headers = f"content-type:application/json\nhost:{_VOD_HOST}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(body).hexdigest()
    canonical_request = "\n".join(
        [
            "POST",
            "/",
            "",
            canonical_headers,
            signed_headers,
            hashed_payload,
        ]
    )

    credential_scope = f"{date}/{_VOD_SERVICE}/tc3_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode()).hexdigest()
    string_to_sign = "\n".join(["TC3-HMAC-SHA256", str(timestamp), credential_scope, hashed_canonical])

    def _hmac(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    secret_date = _hmac(("TC3" + secret_key).encode(), date)
    secret_service = _hmac(secret_date, _VOD_SERVICE)
    secret_signing = _hmac(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

    authorization = (
        f"TC3-HMAC-SHA256 "
        f"Credential={secret_id}/{credential_scope}, "
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


async def _call_vod(action: str, payload: dict) -> dict:
    secret_id, secret_key, sub_app_id = _get_credentials()
    if sub_app_id:
        payload.setdefault("SubAppId", sub_app_id)

    headers = _sign_request(secret_id, secret_key, action, payload)
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(_VOD_ENDPOINT, headers=headers, content=body)

    try:
        data = resp.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"VOD API returned non-JSON (HTTP {resp.status_code}): {resp.text[:200]}",
        )

    response_body = data.get("Response", data)
    error = response_body.get("Error") if isinstance(response_body, dict) else None
    if error:
        code = error.get("Code", "Unknown")
        message = error.get("Message", "Unknown error")
        verbose_proxy_logger.error(f"[VOD] Action={action} Error: {code} - {message}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"VOD API error [{code}]: {message}",
        )

    return response_body


async def _parse_body(request: Request) -> dict:
    try:
        return await request.json()
    except Exception:
        return {}


@router.post(
    "/vod/v1/image",
    dependencies=[Depends(user_api_key_auth)],
    tags=["vod"],
)
async def vod_image(
    request: Request,
    _: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> JSONResponse:
    body = await _parse_body(request)

    payload: dict[str, Any] = {
        "ModelName": body["model_name"],
        "ModelVersion": body["model_version"],
    }
    if body.get("prompt"):
        payload["Prompt"] = body["prompt"]
    if body.get("negative_prompt"):
        payload["NegativePrompt"] = body["negative_prompt"]
    if body.get("file_infos"):
        payload["FileInfos"] = body["file_infos"]

    cfg = body.get("output_config", {})
    output: dict[str, Any] = {"StorageMode": cfg.get("storage_mode", "Temporary")}
    if cfg.get("resolution"):
        output["Resolution"] = cfg["resolution"]
    if cfg.get("aspect_ratio"):
        output["AspectRatio"] = cfg["aspect_ratio"]
    payload["OutputConfig"] = output

    result = await _call_vod("CreateAigcImageTask", payload)
    task_id = result.get("TaskId")
    if not task_id:
        raise HTTPException(status_code=502, detail=f"VOD did not return TaskId: {result}")
    return JSONResponse({"task_id": task_id})


@router.post(
    "/vod/v1/video",
    dependencies=[Depends(user_api_key_auth)],
    tags=["vod"],
)
async def vod_video(
    request: Request,
    _: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> JSONResponse:
    body = await _parse_body(request)

    payload: dict[str, Any] = {
        "ModelName": body["model_name"],
        "ModelVersion": body["model_version"],
    }
    if body.get("prompt"):
        payload["Prompt"] = body["prompt"]
    if body.get("file_infos"):
        payload["FileInfos"] = body["file_infos"]
    if body.get("last_frame_url"):
        payload["LastFrameUrl"] = body["last_frame_url"]
    if body.get("enhance_prompt"):
        payload["EnhancePrompt"] = body["enhance_prompt"]
    if body.get("scene_type"):
        payload["SceneType"] = body["scene_type"]
    if body.get("ext_info"):
        payload["ExtInfo"] = body["ext_info"]

    cfg = body.get("output_config", {})
    output: dict[str, Any] = {"StorageMode": cfg.get("storage_mode", "Temporary")}
    if cfg.get("resolution"):
        output["Resolution"] = cfg["resolution"]
    if cfg.get("duration") is not None:
        output["Duration"] = cfg["duration"]
    if cfg.get("aspect_ratio"):
        output["AspectRatio"] = cfg["aspect_ratio"]
    if cfg.get("audio_generation"):
        output["AudioGeneration"] = cfg["audio_generation"]
    if cfg.get("enhance_switch"):
        output["EnhanceSwitch"] = cfg["enhance_switch"]
    payload["OutputConfig"] = output

    result = await _call_vod("CreateAigcVideoTask", payload)
    task_id = result.get("TaskId")
    if not task_id:
        raise HTTPException(status_code=502, detail=f"VOD did not return TaskId: {result}")
    return JSONResponse({"task_id": task_id})


@router.get(
    "/vod/v1/task/{task_id}",
    dependencies=[Depends(user_api_key_auth)],
    tags=["vod"],
)
async def vod_task(
    task_id: str,
    _: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> JSONResponse:
    result = await _call_vod("DescribeTaskDetail", {"TaskId": task_id})
    task_type = result.get("TaskType", "")

    if task_type == "AigcImage":
        aigc = result.get("AigcImageTask", {})
    elif task_type == "AigcVideo":
        aigc = result.get("AigcVideoTask", {})
    elif task_type == "AigcSceneImage":
        aigc = result.get("AigcSceneImageTask", {})
    else:
        aigc = result

    status_val = aigc.get("Status", "PROCESSING") if isinstance(aigc, dict) else "PROCESSING"
    task_result = aigc.get("Output", aigc) if isinstance(aigc, dict) else aigc
    message = (aigc.get("ErrCodeExt") or aigc.get("ErrMsg") or "") if isinstance(aigc, dict) else ""

    if status_val in ("FINISH", "SUCCESS"):
        norm_status = "FINISH"
    elif status_val in ("FAIL", "ERROR", "SUBMIT_FAILED"):
        norm_status = "FAIL"
    else:
        norm_status = "PROCESSING"

    return JSONResponse({"status": norm_status, "result": task_result, "message": message, "raw": result})


@router.post(
    "/vod/v1/face-info",
    dependencies=[Depends(user_api_key_auth)],
    tags=["vod"],
)
async def vod_face_info(
    request: Request,
    _: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> JSONResponse:
    body = await _parse_body(request)
    result = await _call_vod("DescribeAiAnalysisTaskResult", {"FileInfos": body["file_infos"]})
    return JSONResponse(result)


@router.post(
    "/vod/v1/element",
    dependencies=[Depends(user_api_key_auth)],
    tags=["vod"],
)
async def vod_element(
    request: Request,
    _: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> JSONResponse:
    body = await _parse_body(request)
    payload = {
        "Name": body["element_name"],
        "Usages": ["AigcImage", "AigcVideo"],
        "FaceInfos": [{"FrontImageUrl": body["element_frontal_image"]}],
        "Description": body.get("element_description", ""),
    }
    result = await _call_vod("CreatePersonSample", payload)
    person_id = result.get("Person", {}).get("PersonId") or result.get("PersonId")
    if not person_id:
        raise HTTPException(status_code=502, detail=f"VOD did not return PersonId: {result}")
    return JSONResponse({"element_id": person_id})


@router.post(
    "/vod/v1/scene-image",
    dependencies=[Depends(user_api_key_auth)],
    tags=["vod"],
)
async def vod_scene_image(
    request: Request,
    _: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> JSONResponse:
    body = await _parse_body(request)

    payload: dict[str, Any] = {
        "ModelName": body["model_name"],
        "ModelVersion": body["model_version"],
        "Prompt": body.get("prompt", ""),
    }
    for k, v in body.items():
        if k not in ("model_name", "model_version", "prompt"):
            payload[k] = v

    result = await _call_vod("CreateAigcImageTask", payload)
    task_id = result.get("TaskId")
    if not task_id:
        raise HTTPException(status_code=502, detail=f"VOD did not return TaskId: {result}")
    return JSONResponse({"task_id": task_id})


@router.post(
    "/vod/v1/enhance",
    dependencies=[Depends(user_api_key_auth)],
    tags=["vod"],
)
async def vod_enhance(
    request: Request,
    _: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> JSONResponse:
    body = await _parse_body(request)
    payload = {
        "FileId": body["file_id"],
        "MediaProcessTask": {"TranscodeTaskSet": [{"Definition": body.get("template_id", 101540)}]},
    }
    result = await _call_vod("ProcessMedia", payload)
    task_id = result.get("TaskId")
    if not task_id:
        raise HTTPException(status_code=502, detail=f"VOD did not return TaskId: {result}")
    return JSONResponse({"task_id": task_id})
