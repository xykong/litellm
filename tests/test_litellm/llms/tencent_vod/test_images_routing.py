"""Tests for TENCENT_VOD routing in litellm images/main.py."""

import pytest
from unittest.mock import AsyncMock, patch

from litellm.types.utils import ImageObject, ImageResponse


class TestTencentVODImagesRouting:
    """Verify that tencent_vod models are routed to TencentVODImageGenerationConfig.aimage_generation."""

    @pytest.mark.asyncio
    async def test_aimage_generation_routes_to_tencent_vod(self):
        """aimage_generation with tencent_vod model calls TencentVODImageGenerationConfig.aimage_generation"""
        import litellm

        expected_response = ImageResponse(
            created=1234567890,
            data=[ImageObject(url="https://cdn.example.com/result.png")],
        )

        with patch(
            "litellm.llms.tencent_vod.image_generation.transformation.TencentVODImageGenerationConfig.aimage_generation",
            new_callable=AsyncMock,
            return_value=expected_response,
        ) as mock_aimage_gen:
            with patch.dict(
                "os.environ",
                {
                    "TENCENTCLOUD_SECRET_ID": "test_id",
                    "TENCENTCLOUD_SECRET_KEY": "test_key",
                },
            ):
                response = await litellm.aimage_generation(
                    model="tencent_vod/og-image2_low",
                    prompt="a cute cat",
                )

        mock_aimage_gen.assert_called_once()
        call_kwargs = mock_aimage_gen.call_args
        # Check that model was passed correctly (could be positional or keyword)
        if call_kwargs.kwargs.get("model"):
            assert "og-image2_low" in call_kwargs.kwargs["model"]
        else:
            assert "og-image2_low" in call_kwargs.args[0]
        assert len(response.data) == 1
        assert response.data[0].url == "https://cdn.example.com/result.png"
