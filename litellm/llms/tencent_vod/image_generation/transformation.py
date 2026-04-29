from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, List, Optional, Union

import httpx

from litellm.llms.base_llm.image_generation.transformation import (
    BaseImageGenerationConfig,
)
from litellm.llms.tencent_vod.client import TencentVODClient
from litellm.types.llms.openai import (
    AllMessageValues,
    OpenAIImageGenerationOptionalParams,
)
from litellm.types.utils import ImageObject, ImageResponse

if TYPE_CHECKING:
    from litellm.litellm_core_utils.litellm_logging import Logging as _LiteLLMLoggingObj

    LiteLLMLoggingObj = _LiteLLMLoggingObj
else:
    LiteLLMLoggingObj = Any

# Model name prefix → VOD ModelName mapping
_MODEL_NAME_MAP = {
    "og": "OG",
    "kling": "Kling",
    "gem": "Gem",
    "vidu": "Vidu",
    "seedance": "Seedance",
}


def _parse_vod_model(model: str) -> tuple[str, str]:
    """
    Parse a litellm model string into (ModelName, ModelVersion).

    Examples:
      "tencent_vod/og-image2_low"  → ("OG", "image2_low")
      "vod/og-image2_low"          → ("OG", "image2_low")
    """
    raw = re.sub(r"^(tencent_vod|vod)/", "", model)

    for prefix, model_name in sorted(_MODEL_NAME_MAP.items(), key=lambda x: -len(x[0])):
        if raw.startswith(prefix + "-"):
            version = raw[len(prefix) + 1 :]
            return model_name, version
        if raw == prefix:
            return model_name, ""

    raise ValueError(
        f"Cannot parse tencent_vod model {model!r}. "
        f"Expected format: tencent_vod/<prefix>-<version>. "
        f"Known prefixes: {list(_MODEL_NAME_MAP.keys())}"
    )


class TencentVODImageGenerationConfig(BaseImageGenerationConfig):
    """
    LiteLLM image generation config for Tencent VOD AIGC.

    Supports /v1/images/generations with model="tencent_vod/og-image2_low" etc.
    Internally submits a CreateAigcImageTask and polls until FINISH.
    """

    def get_supported_openai_params(
        self, model: str
    ) -> List[OpenAIImageGenerationOptionalParams]:
        return ["n", "size"]  # type: ignore[return-value]

    def map_openai_params(
        self,
        non_default_params: dict,
        optional_params: dict,
        model: str,
        drop_params: bool,
    ) -> dict:
        supported = self.get_supported_openai_params(model)
        for k, v in non_default_params.items():
            if k in optional_params:
                continue
            if k == "size":
                optional_params["resolution"] = v
            elif k in supported:
                optional_params[k] = v
            elif drop_params:
                pass
            else:
                raise ValueError(
                    f"Parameter {k!r} is not supported for model {model!r}. "
                    f"Supported: {supported}. Set drop_params=True to ignore."
                )
        return optional_params

    def get_complete_url(
        self,
        api_base: Optional[str],
        api_key: Optional[str],
        model: str,
        optional_params: dict,
        litellm_params: dict,
        stream: Optional[bool] = None,
    ) -> str:
        return "https://vod.tencentcloudapi.com"

    def validate_environment(
        self,
        headers: dict,
        model: str,
        messages: List[AllMessageValues],
        optional_params: dict,
        litellm_params: dict,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ) -> dict:
        return headers

    def transform_image_generation_request(
        self,
        model: str,
        prompt: str,
        optional_params: dict,
        litellm_params: dict,
        headers: dict,
    ) -> dict:
        """Build the CreateAigcImageTask payload."""
        model_name, model_version = _parse_vod_model(model)

        payload: dict[str, Any] = {
            "ModelName": model_name,
            "ModelVersion": model_version,
            "Prompt": prompt,
        }

        if optional_params.get("negative_prompt"):
            payload["NegativePrompt"] = optional_params["negative_prompt"]

        output: dict[str, Any] = {
            "StorageMode": optional_params.get("storage_mode", "Temporary")
        }
        if optional_params.get("resolution"):
            output["Resolution"] = optional_params["resolution"]
        if optional_params.get("aspect_ratio"):
            output["AspectRatio"] = optional_params["aspect_ratio"]
        payload["OutputConfig"] = output

        return payload

    def transform_image_generation_response(
        self,
        model: str,
        raw_response: httpx.Response,
        model_response: ImageResponse,
        logging_obj: LiteLLMLoggingObj,
        request_data: dict,
        optional_params: dict,
        litellm_params: dict,
        encoding: Any,
        api_key: Optional[str] = None,
        json_mode: Optional[bool] = None,
    ) -> ImageResponse:
        # Not called for tencent_vod — we override aimage_generation instead
        return model_response

    async def aimage_generation(
        self,
        model: str,
        prompt: str,
        optional_params: dict,
        litellm_params: dict,
        logging_obj: LiteLLMLoggingObj,
        model_response: ImageResponse,
        timeout: Union[float, int],
        client: Optional[Any] = None,
    ) -> ImageResponse:
        """
        Submit CreateAigcImageTask → poll DescribeTaskDetail → return ImageResponse.
        """
        if client is not None and hasattr(client, "call_vod"):
            vod_client = client
        else:
            vod_client = TencentVODClient()

        payload = self.transform_image_generation_request(
            model=model,
            prompt=prompt,
            optional_params=optional_params,
            litellm_params=litellm_params,
            headers={},
        )

        result = await vod_client.call_vod("CreateAigcImageTask", payload)
        task_id = result.get("TaskId")
        if not task_id:
            raise RuntimeError(f"VOD did not return TaskId: {result}")

        poll_result = await vod_client.poll_until_done(
            task_id,
            poll_interval=5.0,
            timeout=float(timeout) if timeout else 600.0,
        )

        if not model_response.data:
            model_response.data = []

        for fi in poll_result.get("file_infos", []):
            url = fi.get("url") or fi.get("file_url")
            if url:
                model_response.data.append(ImageObject(url=url))

        return model_response
