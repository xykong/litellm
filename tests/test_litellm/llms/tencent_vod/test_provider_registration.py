import pytest
import litellm
from litellm import LlmProviders
from litellm.utils import ProviderConfigManager


class TestTencentVODProviderRegistration:
    def test_tencent_vod_in_llm_providers_enum(self):
        assert hasattr(LlmProviders, "TENCENT_VOD")
        assert LlmProviders.TENCENT_VOD.value == "tencent_vod"

    def test_get_llm_provider_parses_tencent_vod(self):
        model, provider, key, base = litellm.get_llm_provider("tencent_vod/og-image2_low")
        assert provider == "tencent_vod"

    def test_provider_config_manager_returns_image_gen_config(self):
        from litellm.llms.tencent_vod.image_generation.transformation import (
            TencentVODImageGenerationConfig,
        )

        config = ProviderConfigManager.get_provider_image_generation_config(
            model="tencent_vod/og-image2_low",
            provider=LlmProviders.TENCENT_VOD,
        )
        assert isinstance(config, TencentVODImageGenerationConfig)
