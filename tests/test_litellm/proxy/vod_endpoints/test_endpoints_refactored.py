"""
Tests for vod_endpoints/endpoints.py — verifying:
1. Endpoints delegate to TencentVODClient (no inline TC3 signing)
2. FileInfos are normalized (snake_case → PascalCase) before sending to VOD API
3. TaskType is resolved correctly via _TASK_TYPE_KEY mapping
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient
from fastapi import FastAPI

from litellm.proxy.vod_endpoints.endpoints import router


@pytest.fixture
def app():
    """Create a test app with the VOD router, bypassing auth."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture(autouse=True)
def bypass_auth():
    """Bypass user_api_key_auth for all tests."""
    with patch(
        "litellm.proxy.vod_endpoints.endpoints.user_api_key_auth",
        return_value=MagicMock(),
    ):
        yield


class TestEndpointsUseTencentVODClient:
    """Verify endpoints delegate to TencentVODClient.call_vod instead of inline signing."""

    @pytest.mark.asyncio
    async def test_vod_image_uses_client_call_vod(self, client):
        """POST /vod/v1/image should call TencentVODClient.call_vod with action=CreateAigcImageTask."""
        with patch("litellm.proxy.vod_endpoints.endpoints._vod_client") as mock_client:
            mock_client.call_vod = AsyncMock(return_value={"TaskId": "task_123"})

            response = client.post(
                "/vod/v1/image",
                json={
                    "model_name": "seedream-3.0",
                    "model_version": "seedream-3.0-t2i-turbo",
                    "prompt": "a cat",
                },
            )

            assert response.status_code == 200
            assert response.json() == {"task_id": "task_123"}
            mock_client.call_vod.assert_called_once()
            call_args = mock_client.call_vod.call_args
            assert call_args[0][0] == "CreateAigcImageTask"

    @pytest.mark.asyncio
    async def test_vod_video_uses_client_call_vod(self, client):
        """POST /vod/v1/video should call TencentVODClient.call_vod with action=CreateAigcVideoTask."""
        with patch("litellm.proxy.vod_endpoints.endpoints._vod_client") as mock_client:
            mock_client.call_vod = AsyncMock(return_value={"TaskId": "vtask_456"})

            response = client.post(
                "/vod/v1/video",
                json={
                    "model_name": "seedance-1.0",
                    "model_version": "seedance-1.0-t2v",
                    "prompt": "a running dog",
                },
            )

            assert response.status_code == 200
            assert response.json() == {"task_id": "vtask_456"}
            mock_client.call_vod.assert_called_once()
            call_args = mock_client.call_vod.call_args
            assert call_args[0][0] == "CreateAigcVideoTask"

    @pytest.mark.asyncio
    async def test_vod_task_uses_client_call_vod(self, client):
        """GET /vod/v1/task/{task_id} should call TencentVODClient.call_vod with action=DescribeTaskDetail."""
        with patch("litellm.proxy.vod_endpoints.endpoints._vod_client") as mock_client:
            mock_client.call_vod = AsyncMock(
                return_value={
                    "TaskType": "AigcImageTask",
                    "AigcImageTask": {
                        "Status": "FINISH",
                        "Output": {
                            "FileInfos": [
                                {
                                    "FileUrl": "https://example.com/img.png",
                                    "FileId": "f1",
                                }
                            ]
                        },
                    },
                }
            )

            response = client.get("/vod/v1/task/task_123")

            assert response.status_code == 200
            mock_client.call_vod.assert_called_once_with(
                "DescribeTaskDetail", {"TaskId": "task_123"}
            )

    @pytest.mark.asyncio
    async def test_vod_element_uses_client_call_vod(self, client):
        """POST /vod/v1/element should call TencentVODClient.call_vod."""
        with patch("litellm.proxy.vod_endpoints.endpoints._vod_client") as mock_client:
            mock_client.call_vod = AsyncMock(
                return_value={"Person": {"PersonId": "pid_001"}}
            )

            response = client.post(
                "/vod/v1/element",
                json={
                    "element_name": "Test Person",
                    "element_frontal_image": "https://example.com/face.jpg",
                },
            )

            assert response.status_code == 200
            assert response.json() == {"element_id": "pid_001"}
            mock_client.call_vod.assert_called_once()
            call_args = mock_client.call_vod.call_args
            assert call_args[0][0] == "CreatePersonSample"


class TestFileInfosNormalization:
    """Verify FileInfos are normalized from snake_case to PascalCase before VOD API call."""

    @pytest.mark.asyncio
    async def test_vod_image_normalizes_file_infos_to_pascal_case(self, client):
        """When user sends snake_case file_infos, they should be converted to PascalCase."""
        with patch("litellm.proxy.vod_endpoints.endpoints._vod_client") as mock_client:
            mock_client.call_vod = AsyncMock(return_value={"TaskId": "task_789"})

            response = client.post(
                "/vod/v1/image",
                json={
                    "model_name": "seedream-3.0",
                    "model_version": "seedream-3.0-i2i",
                    "prompt": "enhance this",
                    "file_infos": [
                        {
                            "file_url": "https://example.com/input.png",
                            "file_id": "fid_001",
                            "type": "image",
                        }
                    ],
                },
            )

            assert response.status_code == 200
            call_args = mock_client.call_vod.call_args
            payload = call_args[0][1]
            # FileInfos should have PascalCase keys for VOD API
            file_infos = payload["FileInfos"]
            assert len(file_infos) == 1
            fi = file_infos[0]
            assert fi.get("FileUrl") == "https://example.com/input.png"
            assert fi.get("FileId") == "fid_001"

    @pytest.mark.asyncio
    async def test_vod_image_passes_pascal_case_file_infos_unchanged(self, client):
        """When user sends PascalCase FileInfos, they should pass through unchanged."""
        with patch("litellm.proxy.vod_endpoints.endpoints._vod_client") as mock_client:
            mock_client.call_vod = AsyncMock(return_value={"TaskId": "task_aaa"})

            response = client.post(
                "/vod/v1/image",
                json={
                    "model_name": "seedream-3.0",
                    "model_version": "seedream-3.0-i2i",
                    "prompt": "enhance this",
                    "file_infos": [
                        {
                            "FileUrl": "https://example.com/input.png",
                            "FileId": "fid_002",
                            "Type": "image",
                        }
                    ],
                },
            )

            assert response.status_code == 200
            call_args = mock_client.call_vod.call_args
            payload = call_args[0][1]
            file_infos = payload["FileInfos"]
            assert file_infos[0].get("FileUrl") == "https://example.com/input.png"
            assert file_infos[0].get("FileId") == "fid_002"

    @pytest.mark.asyncio
    async def test_vod_video_normalizes_file_infos_to_pascal_case(self, client):
        """Video endpoint should also normalize snake_case file_infos."""
        with patch("litellm.proxy.vod_endpoints.endpoints._vod_client") as mock_client:
            mock_client.call_vod = AsyncMock(return_value={"TaskId": "vtask_bbb"})

            response = client.post(
                "/vod/v1/video",
                json={
                    "model_name": "seedance-1.0",
                    "model_version": "seedance-1.0-i2v",
                    "file_infos": [
                        {"file_url": "https://example.com/frame.png", "type": "image"}
                    ],
                },
            )

            assert response.status_code == 200
            call_args = mock_client.call_vod.call_args
            payload = call_args[0][1]
            file_infos = payload["FileInfos"]
            assert file_infos[0].get("FileUrl") == "https://example.com/frame.png"


class TestTaskTypeResolution:
    """Verify TaskType is resolved correctly using _TASK_TYPE_KEY mapping."""

    @pytest.mark.asyncio
    async def test_task_resolves_aigc_image_task_type(self, client):
        """AigcImageTask type should extract data from AigcImageTask key."""
        with patch("litellm.proxy.vod_endpoints.endpoints._vod_client") as mock_client:
            mock_client.call_vod = AsyncMock(
                return_value={
                    "TaskType": "AigcImage",
                    "AigcImageTask": {
                        "Status": "FINISH",
                        "Output": {
                            "FileInfos": [
                                {
                                    "FileUrl": "https://cdn.example.com/result.png",
                                    "FileId": "f1",
                                }
                            ]
                        },
                    },
                }
            )

            response = client.get("/vod/v1/task/img_task_1")

            data = response.json()
            assert data["status"] == "FINISH"
            assert "file_infos" in data["result"]
            assert (
                data["result"]["file_infos"][0]["url"]
                == "https://cdn.example.com/result.png"
            )

    @pytest.mark.asyncio
    async def test_task_resolves_aigc_video_task_type(self, client):
        """AigcVideo type should extract data from AigcVideoTask key."""
        with patch("litellm.proxy.vod_endpoints.endpoints._vod_client") as mock_client:
            mock_client.call_vod = AsyncMock(
                return_value={
                    "TaskType": "AigcVideo",
                    "AigcVideoTask": {
                        "Status": "FINISH",
                        "Output": {
                            "FileInfos": [
                                {
                                    "FileUrl": "https://cdn.example.com/video.mp4",
                                    "FileId": "v1",
                                }
                            ]
                        },
                    },
                }
            )

            response = client.get("/vod/v1/task/vid_task_1")

            data = response.json()
            assert data["status"] == "FINISH"
            assert (
                data["result"]["file_infos"][0]["url"]
                == "https://cdn.example.com/video.mp4"
            )

    @pytest.mark.asyncio
    async def test_task_resolves_aigc_scene_image_task_type(self, client):
        """AigcSceneImage type should extract data from AigcSceneImageTask key."""
        with patch("litellm.proxy.vod_endpoints.endpoints._vod_client") as mock_client:
            mock_client.call_vod = AsyncMock(
                return_value={
                    "TaskType": "AigcSceneImage",
                    "AigcSceneImageTask": {
                        "Status": "FINISH",
                        "Output": {
                            "FileInfos": [
                                {
                                    "FileUrl": "https://cdn.example.com/scene.png",
                                    "FileId": "s1",
                                }
                            ]
                        },
                    },
                }
            )

            response = client.get("/vod/v1/task/scene_task_1")

            data = response.json()
            assert data["status"] == "FINISH"
            assert (
                data["result"]["file_infos"][0]["url"]
                == "https://cdn.example.com/scene.png"
            )

    @pytest.mark.asyncio
    async def test_task_fail_status_reported(self, client):
        """FAIL status should be normalized to FAIL."""
        with patch("litellm.proxy.vod_endpoints.endpoints._vod_client") as mock_client:
            mock_client.call_vod = AsyncMock(
                return_value={
                    "TaskType": "AigcImageTask",
                    "AigcImageTask": {
                        "Status": "FAIL",
                        "ErrCodeExt": "InternalError",
                        "Output": {},
                    },
                }
            )

            response = client.get("/vod/v1/task/fail_task")

            data = response.json()
            assert data["status"] == "FAIL"
            assert data["message"] == "InternalError"

    @pytest.mark.asyncio
    async def test_task_processing_status_reported(self, client):
        """PROCESSING status should be reported as PROCESSING."""
        with patch("litellm.proxy.vod_endpoints.endpoints._vod_client") as mock_client:
            mock_client.call_vod = AsyncMock(
                return_value={
                    "TaskType": "AigcImageTask",
                    "AigcImageTask": {
                        "Status": "PROCESSING",
                        "Output": {},
                    },
                }
            )

            response = client.get("/vod/v1/task/proc_task")

            data = response.json()
            assert data["status"] == "PROCESSING"
