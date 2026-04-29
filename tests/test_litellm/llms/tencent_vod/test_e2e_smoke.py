from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import litellm
from litellm.types.utils import ImageResponse


def _make_httpx_response(body: dict, status_code: int = 200) -> httpx.Response:
    content = json.dumps(body).encode()
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "https://vod.tencentcloudapi.com"),
    )


class TestTencentVODE2ESmoke:

    @pytest.mark.asyncio
    async def test_full_pipeline_produces_image_response(self):
        call_count = 0

        async def mock_post(self_client, url, **kwargs):
            nonlocal call_count
            call_count += 1

            headers = kwargs.get("headers", {})
            action = headers.get("X-TC-Action", "")

            if action == "CreateAigcImageTask":
                return _make_httpx_response(
                    {
                        "Response": {
                            "RequestId": "req123",
                            "TaskId": "task-abc",
                        }
                    }
                )
            elif action == "DescribeTaskDetail":
                return _make_httpx_response(
                    {
                        "Response": {
                            "RequestId": "req456",
                            "TaskType": "AigcImageTask",
                            "AigcImageTask": {
                                "TaskId": "task-abc",
                                "Status": "SUCCESS",
                                "Output": {
                                    "FileInfos": [
                                        {
                                            "FileUrl": "https://cdn.example.com/img.png",
                                            "FileId": "file-001",
                                            "StorageMode": "Temporary",
                                            "ExpireTime": "2026-05-01T00:00:00Z",
                                        }
                                    ]
                                },
                            },
                        }
                    }
                )
            else:
                raise AssertionError(f"Unexpected VOD action: {action!r}")

        env_vars = {
            "TENCENTCLOUD_SECRET_ID": "test-secret-id",
            "TENCENTCLOUD_SECRET_KEY": "test-secret-key",
            "VOD_SUB_APP_ID": "1500055513",
        }

        with patch.dict("os.environ", env_vars):
            with patch("httpx.AsyncClient.post", new=mock_post):
                response = await litellm.aimage_generation(
                    model="tencent_vod/og-image2_low",
                    prompt="a cute cat",
                )

        assert isinstance(response, ImageResponse)
        assert response.data is not None
        assert len(response.data) == 1
        assert response.data[0].url == "https://cdn.example.com/img.png"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_full_pipeline_multiple_images(self):
        call_count = 0

        async def mock_post(self_client, url, **kwargs):
            nonlocal call_count
            call_count += 1

            headers = kwargs.get("headers", {})
            action = headers.get("X-TC-Action", "")

            if action == "CreateAigcImageTask":
                return _make_httpx_response(
                    {
                        "Response": {
                            "RequestId": "req-multi",
                            "TaskId": "task-multi",
                        }
                    }
                )
            elif action == "DescribeTaskDetail":
                return _make_httpx_response(
                    {
                        "Response": {
                            "RequestId": "req-multi-poll",
                            "TaskType": "AigcImageTask",
                            "AigcImageTask": {
                                "TaskId": "task-multi",
                                "Status": "FINISH",
                                "Output": {
                                    "FileInfos": [
                                        {
                                            "FileUrl": "https://cdn.example.com/img1.png",
                                            "FileId": "file-a",
                                        },
                                        {
                                            "FileUrl": "https://cdn.example.com/img2.png",
                                            "FileId": "file-b",
                                        },
                                    ]
                                },
                            },
                        }
                    }
                )
            else:
                raise AssertionError(f"Unexpected VOD action: {action!r}")

        env_vars = {
            "TENCENTCLOUD_SECRET_ID": "test-secret-id",
            "TENCENTCLOUD_SECRET_KEY": "test-secret-key",
            "VOD_SUB_APP_ID": "1500055513",
        }

        with patch.dict("os.environ", env_vars):
            with patch("httpx.AsyncClient.post", new=mock_post):
                response = await litellm.aimage_generation(
                    model="tencent_vod/og-image2_low",
                    prompt="two cute cats",
                )

        assert isinstance(response, ImageResponse)
        assert len(response.data) == 2
        assert response.data[0].url == "https://cdn.example.com/img1.png"
        assert response.data[1].url == "https://cdn.example.com/img2.png"

    @pytest.mark.asyncio
    async def test_full_pipeline_with_polling_delay(self):
        call_count = 0
        poll_count = 0

        async def mock_post(self_client, url, **kwargs):
            nonlocal call_count, poll_count
            call_count += 1

            headers = kwargs.get("headers", {})
            action = headers.get("X-TC-Action", "")

            if action == "CreateAigcImageTask":
                return _make_httpx_response(
                    {
                        "Response": {
                            "RequestId": "req-delay",
                            "TaskId": "task-delay",
                        }
                    }
                )
            elif action == "DescribeTaskDetail":
                poll_count += 1
                if poll_count == 1:
                    return _make_httpx_response(
                        {
                            "Response": {
                                "RequestId": "req-poll1",
                                "TaskType": "AigcImageTask",
                                "AigcImageTask": {
                                    "TaskId": "task-delay",
                                    "Status": "PROCESSING",
                                },
                            }
                        }
                    )
                else:
                    return _make_httpx_response(
                        {
                            "Response": {
                                "RequestId": "req-poll2",
                                "TaskType": "AigcImageTask",
                                "AigcImageTask": {
                                    "TaskId": "task-delay",
                                    "Status": "SUCCESS",
                                    "Output": {
                                        "FileInfos": [
                                            {
                                                "FileUrl": "https://cdn.example.com/delayed.png",
                                                "FileId": "file-delayed",
                                            }
                                        ]
                                    },
                                },
                            }
                        }
                    )
            else:
                raise AssertionError(f"Unexpected VOD action: {action!r}")

        env_vars = {
            "TENCENTCLOUD_SECRET_ID": "test-secret-id",
            "TENCENTCLOUD_SECRET_KEY": "test-secret-key",
            "VOD_SUB_APP_ID": "1500055513",
        }

        with patch.dict("os.environ", env_vars):
            with patch("httpx.AsyncClient.post", new=mock_post):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    response = await litellm.aimage_generation(
                        model="tencent_vod/og-image2_low",
                        prompt="a delayed cat",
                    )

        assert isinstance(response, ImageResponse)
        assert len(response.data) == 1
        assert response.data[0].url == "https://cdn.example.com/delayed.png"
        assert call_count == 3
        assert poll_count == 2
