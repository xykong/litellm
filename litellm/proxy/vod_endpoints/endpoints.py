from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from litellm._logging import verbose_proxy_logger
from litellm.llms.tencent_vod.client import (
    TencentVODClient,
    _TASK_TYPE_KEY,
    _normalize_file_infos,
)
from litellm.proxy.auth.user_api_key_auth import UserAPIKeyAuth, user_api_key_auth

router = APIRouter()

_vod_client = TencentVODClient()


def _normalize_file_infos_input(file_infos: list[dict]) -> list[dict]:
    """Normalize user-supplied file_infos (snake_case) to PascalCase for VOD API."""
    result = []
    for fi in file_infos:
        normalized: dict[str, Any] = {}
        if "FileUrl" in fi:
            normalized["FileUrl"] = fi["FileUrl"]
        elif "file_url" in fi:
            normalized["FileUrl"] = fi["file_url"]

        if "FileId" in fi:
            normalized["FileId"] = fi["FileId"]
        elif "file_id" in fi:
            normalized["FileId"] = fi["file_id"]

        if "Type" in fi:
            normalized["Type"] = fi["Type"]
        elif "type" in fi:
            normalized["Type"] = fi["type"]

        if "StorageMode" in fi:
            normalized["StorageMode"] = fi["StorageMode"]
        elif "storage_mode" in fi:
            normalized["StorageMode"] = fi["storage_mode"]

        if "Url" in fi:
            normalized["Url"] = fi["Url"]
        elif "url" in fi:
            normalized["Url"] = fi["url"]

        for k, v in fi.items():
            if k not in (
                "FileUrl",
                "file_url",
                "FileId",
                "file_id",
                "Type",
                "type",
                "StorageMode",
                "storage_mode",
                "Url",
                "url",
            ):
                normalized[k] = v
        result.append(normalized)
    return result


async def _call_vod(action: str, payload: dict) -> dict:
    """Delegate to the shared TencentVODClient, translating errors to HTTPException."""
    try:
        return await _vod_client.call_vod(action, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except RuntimeError as e:
        verbose_proxy_logger.error(f"[VOD] Action={action} Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )


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
        payload["FileInfos"] = _normalize_file_infos_input(body["file_infos"])

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
        raise HTTPException(
            status_code=502, detail=f"VOD did not return TaskId: {result}"
        )
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
        payload["FileInfos"] = _normalize_file_infos_input(body["file_infos"])
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
        raise HTTPException(
            status_code=502, detail=f"VOD did not return TaskId: {result}"
        )
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

    result_key = _TASK_TYPE_KEY.get(task_type)
    aigc = result.get(result_key, result) if result_key else result

    status_val = (
        aigc.get("Status", "PROCESSING") if isinstance(aigc, dict) else "PROCESSING"
    )
    task_result = aigc.get("Output", aigc) if isinstance(aigc, dict) else aigc
    message = (
        (aigc.get("ErrCodeExt") or aigc.get("ErrMsg") or "")
        if isinstance(aigc, dict)
        else ""
    )

    if (
        isinstance(task_result, dict)
        and "FileInfos" in task_result
        and "file_infos" not in task_result
    ):
        file_infos_norm = _normalize_file_infos(task_result)
        task_result = dict(task_result)
        task_result["file_infos"] = file_infos_norm

    if status_val in ("FINISH", "SUCCESS"):
        norm_status = "FINISH"
    elif status_val in ("FAIL", "ERROR", "SUBMIT_FAILED"):
        norm_status = "FAIL"
    else:
        norm_status = "PROCESSING"

    return JSONResponse(
        {
            "status": norm_status,
            "result": task_result,
            "message": message,
            "raw": result,
        }
    )


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
    result = await _call_vod(
        "DescribeAiAnalysisTaskResult", {"FileInfos": body["file_infos"]}
    )
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
        raise HTTPException(
            status_code=502, detail=f"VOD did not return PersonId: {result}"
        )
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
        raise HTTPException(
            status_code=502, detail=f"VOD did not return TaskId: {result}"
        )
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
        "MediaProcessTask": {
            "TranscodeTaskSet": [{"Definition": body.get("template_id", 101540)}]
        },
    }
    result = await _call_vod("ProcessMedia", payload)
    task_id = result.get("TaskId")
    if not task_id:
        raise HTTPException(
            status_code=502, detail=f"VOD did not return TaskId: {result}"
        )
    return JSONResponse({"task_id": task_id})
