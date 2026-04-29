import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from litellm.llms.tencent_vod.client import TencentVODClient, TencentVODCredentials


class TestTencentVODClient:
    def setup_method(self):
        self.creds = TencentVODCredentials(
            secret_id="test_id",
            secret_key="test_key",
            sub_app_id=1500055513,
        )
        self.client = TencentVODClient(credentials=self.creds)

    def test_credentials_from_env(self, monkeypatch):
        monkeypatch.setenv("TENCENTCLOUD_SECRET_ID", "env_id")
        monkeypatch.setenv("TENCENTCLOUD_SECRET_KEY", "env_key")
        monkeypatch.setenv("VOD_SUB_APP_ID", "1500055513")
        creds = TencentVODCredentials.from_env()
        assert creds.secret_id == "env_id"
        assert creds.secret_key == "env_key"
        assert creds.sub_app_id == 1500055513

    def test_credentials_from_env_missing_raises(self, monkeypatch):
        monkeypatch.delenv("TENCENTCLOUD_SECRET_ID", raising=False)
        monkeypatch.delenv("TENCENTCLOUD_SECRET_KEY", raising=False)
        with pytest.raises(ValueError, match="TENCENTCLOUD_SECRET_ID"):
            TencentVODCredentials.from_env()

    def test_sign_request_returns_required_headers(self):
        headers = self.client._sign_request("CreateAigcImageTask", {"Prompt": "test"})
        assert "Authorization" in headers
        assert "X-TC-Action" in headers
        assert headers["X-TC-Action"] == "CreateAigcImageTask"
        assert "TC3-HMAC-SHA256" in headers["Authorization"]

    @pytest.mark.asyncio
    async def test_call_vod_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"Response": {"TaskId": "abc123"}}
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            result = await self.client.call_vod("CreateAigcImageTask", {"Prompt": "test"})
        assert result["TaskId"] == "abc123"

    @pytest.mark.asyncio
    async def test_call_vod_api_error_raises(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Response": {"Error": {"Code": "InvalidParam", "Message": "bad input"}}
        }
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            with pytest.raises(RuntimeError, match="InvalidParam"):
                await self.client.call_vod("CreateAigcImageTask", {"Prompt": "test"})

    @pytest.mark.asyncio
    async def test_poll_until_done_returns_on_finish(self):
        finish_response = {
            "TaskType": "AigcImageTask",
            "AigcImageTask": {
                "Status": "FINISH",
                "Output": {
                    "FileInfos": [{"FileUrl": "https://example.com/img.png", "FileId": "fid1"}]
                },
            },
        }
        self.client.call_vod = AsyncMock(return_value=finish_response)
        result = await self.client.poll_until_done("task_abc", poll_interval=0, timeout=10)
        assert result["status"] == "FINISH"
        assert result["file_infos"][0]["url"] == "https://example.com/img.png"

    @pytest.mark.asyncio
    async def test_poll_until_done_raises_on_fail(self):
        fail_response = {
            "TaskType": "AigcImageTask",
            "AigcImageTask": {"Status": "FAIL", "ErrCodeExt": "InternalError", "Output": {}},
        }
        self.client.call_vod = AsyncMock(return_value=fail_response)
        with pytest.raises(RuntimeError, match="FAIL"):
            await self.client.poll_until_done("task_abc", poll_interval=0, timeout=10)

    @pytest.mark.asyncio
    async def test_poll_until_done_timeout(self):
        processing_response = {
            "TaskType": "AigcImageTask",
            "AigcImageTask": {"Status": "PROCESSING", "Output": {}},
        }
        self.client.call_vod = AsyncMock(return_value=processing_response)
        with pytest.raises(TimeoutError):
            await self.client.poll_until_done("task_abc", poll_interval=0, timeout=0.01)
