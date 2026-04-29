import pytest
from unittest.mock import AsyncMock, patch

from litellm.types.utils import ImageObject, ImageResponse
from litellm.llms.tencent_vod.image_generation.transformation import (
    TencentVODImageGenerationConfig,
    _parse_vod_model,
)


class TestParseVodModel:
    def test_og_image2_low(self):
        assert _parse_vod_model("tencent_vod/og-image2_low") == ("OG", "image2_low")

    def test_og_image2_high(self):
        assert _parse_vod_model("tencent_vod/og-image2_high") == ("OG", "image2_high")

    def test_vod_prefix_also_works(self):
        assert _parse_vod_model("vod/og-image2_low") == ("OG", "image2_low")

    def test_unknown_prefix_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            _parse_vod_model("tencent_vod/unknown-xyz")


class TestTencentVODImageGenerationConfig:
    def setup_method(self):
        self.config = TencentVODImageGenerationConfig()

    def test_get_supported_openai_params(self):
        params = self.config.get_supported_openai_params("tencent_vod/og-image2_low")
        assert "size" in params
        assert "n" in params

    def test_map_openai_params_size_to_resolution(self):
        result = self.config.map_openai_params(
            non_default_params={"size": "1024x1024"},
            optional_params={},
            model="tencent_vod/og-image2_low",
            drop_params=False,
        )
        assert result.get("resolution") == "1024x1024"

    def test_map_openai_params_unsupported_raises(self):
        with pytest.raises(ValueError, match="not supported"):
            self.config.map_openai_params(
                non_default_params={"quality": "hd"},
                optional_params={},
                model="tencent_vod/og-image2_low",
                drop_params=False,
            )

    def test_map_openai_params_unsupported_dropped_with_flag(self):
        result = self.config.map_openai_params(
            non_default_params={"quality": "hd"},
            optional_params={},
            model="tencent_vod/og-image2_low",
            drop_params=True,
        )
        assert "quality" not in result

    def test_transform_request_basic(self):
        body = self.config.transform_image_generation_request(
            model="tencent_vod/og-image2_low",
            prompt="a cute cat",
            optional_params={},
            litellm_params={},
            headers={},
        )
        assert body["ModelName"] == "OG"
        assert body["ModelVersion"] == "image2_low"
        assert body["Prompt"] == "a cute cat"
        assert body["OutputConfig"]["StorageMode"] == "Temporary"

    def test_transform_request_with_resolution(self):
        body = self.config.transform_image_generation_request(
            model="tencent_vod/og-image2_low",
            prompt="test",
            optional_params={"resolution": "1280x720"},
            litellm_params={},
            headers={},
        )
        assert body["OutputConfig"]["Resolution"] == "1280x720"

    def test_transform_request_with_negative_prompt(self):
        body = self.config.transform_image_generation_request(
            model="tencent_vod/og-image2_low",
            prompt="test",
            optional_params={"negative_prompt": "ugly"},
            litellm_params={},
            headers={},
        )
        assert body["NegativePrompt"] == "ugly"

    def test_transform_request_unknown_model_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            self.config.transform_image_generation_request(
                model="tencent_vod/unknown-xyz",
                prompt="test",
                optional_params={},
                litellm_params={},
                headers={},
            )

    def test_validate_environment_returns_dict(self):
        headers = self.config.validate_environment(
            headers={},
            model="tencent_vod/og-image2_low",
            messages=[],
            optional_params={},
            litellm_params={},
        )
        assert isinstance(headers, dict)

    @pytest.mark.asyncio
    async def test_aimage_generation_returns_image_response(self):
        poll_result = {
            "status": "FINISH",
            "file_infos": [{"url": "https://cdn.example.com/img.png", "file_id": "fid1"}],
            "message": "",
            "raw": {},
        }
        mock_client = AsyncMock()
        mock_client.call_vod = AsyncMock(return_value={"TaskId": "task123"})
        mock_client.poll_until_done = AsyncMock(return_value=poll_result)

        with patch(
            "litellm.llms.tencent_vod.image_generation.transformation.TencentVODClient",
            return_value=mock_client,
        ):
            response = await self.config.aimage_generation(
                model="tencent_vod/og-image2_low",
                prompt="a cute cat",
                optional_params={},
                litellm_params={},
                logging_obj=None,
                model_response=ImageResponse(created=0, data=[]),
                timeout=600,
                client=None,
            )

        assert len(response.data) == 1
        assert response.data[0].url == "https://cdn.example.com/img.png"
