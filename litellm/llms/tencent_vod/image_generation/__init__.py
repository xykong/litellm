from litellm.llms.base_llm.image_generation.transformation import (
    BaseImageGenerationConfig,
)

from .transformation import TencentVODImageGenerationConfig

__all__ = ["TencentVODImageGenerationConfig"]


def get_tencent_vod_image_generation_config(model: str) -> BaseImageGenerationConfig:
    return TencentVODImageGenerationConfig()
