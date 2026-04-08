import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from litellm.proxy.management_endpoints.sso.happyelements_sso import HappyElementsSSO


def make_sso_client(callback_url="https://gw.example.com/sso/happyelements/callback"):
    return HappyElementsSSO(
        app_key="he_test_key",
        app_secret="a" * 32,
        callback_url=callback_url,
    )


class TestGenerateLoginUrl:
    def test_default_uses_instance_callback(self):
        client = make_sso_client("https://gw.example.com/sso/happyelements/callback")
        with patch(
            "litellm.proxy.management_endpoints.sso.happyelements_sso.create_request_token",
            return_value="tok",
        ) as mock_create:
            client.generate_login_url(client_ip="1.2.3.4")
            _, kwargs = mock_create.call_args
            assert kwargs["callback_url"] == "https://gw.example.com/sso/happyelements/callback"

    def test_override_uses_provided_callback(self):
        client = make_sso_client("https://gw.example.com/sso/happyelements/callback")
        override = "https://gw.example.com/sso/happyelements/callback?cli_key=sk-abc"
        with patch(
            "litellm.proxy.management_endpoints.sso.happyelements_sso.create_request_token",
            return_value="tok",
        ) as mock_create:
            client.generate_login_url(client_ip="1.2.3.4", callback_url_override=override)
            _, kwargs = mock_create.call_args
            assert kwargs["callback_url"] == override

    def test_none_override_falls_back_to_instance_callback(self):
        client = make_sso_client("https://gw.example.com/sso/happyelements/callback")
        with patch(
            "litellm.proxy.management_endpoints.sso.happyelements_sso.create_request_token",
            return_value="tok",
        ) as mock_create:
            client.generate_login_url(client_ip="1.2.3.4", callback_url_override=None)
            _, kwargs = mock_create.call_args
            assert kwargs["callback_url"] == "https://gw.example.com/sso/happyelements/callback"


@pytest.mark.asyncio
class TestHappyelementsLogin:
    async def _call_login(self, key=None):
        from litellm.proxy.management_endpoints.sso.happyelements_endpoints import (
            happyelements_login,
        )

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client = MagicMock(host="1.2.3.4")

        mock_sso_client = MagicMock()
        mock_sso_client.callback_url = "https://gw.example.com/sso/happyelements/callback"
        mock_sso_client.generate_login_url = MagicMock(return_value="https://he-sso.example.com/login?...")

        with patch(
            "litellm.proxy.management_endpoints.sso.happyelements_endpoints.get_happyelements_sso_client",
            return_value=mock_sso_client,
        ):
            await happyelements_login(request=mock_request, key=key)

        return mock_sso_client.generate_login_url

    async def test_no_key_uses_default_callback(self):
        generate_login_url = await self._call_login(key=None)
        generate_login_url.assert_called_once_with(client_ip="1.2.3.4", callback_url_override=None)

    async def test_valid_cli_key_embeds_key_in_callback(self):
        generate_login_url = await self._call_login(key="sk-mykey123")
        _, kwargs = generate_login_url.call_args
        override = (
            kwargs.get("callback_url_override") or generate_login_url.call_args[0][1]
            if len(generate_login_url.call_args[0]) > 1
            else None
        )
        override = generate_login_url.call_args[1].get("callback_url_override")
        assert override is not None
        assert "cli_key=sk-mykey123" in override

    async def test_non_sk_key_ignored(self):
        generate_login_url = await self._call_login(key="notakey")
        _, kwargs = generate_login_url.call_args
        assert kwargs.get("callback_url_override") is None


@pytest.mark.asyncio
class TestHappyelementsCallback:
    def _make_mock_sso_client(self, user_info):
        mock_sso_client = MagicMock()
        mock_sso_client.process_callback = MagicMock(return_value=user_info)
        mock_sso_client.get_user_id = MagicMock(return_value=user_info.get("unique_id", "testuser"))
        mock_sso_client.get_user_display_name = MagicMock(return_value="Test User")
        return mock_sso_client

    async def test_cli_key_routes_to_cli_sso_callback(self):
        from litellm.proxy.management_endpoints.sso.happyelements_endpoints import (
            happyelements_callback,
        )

        user_info = {
            "username": "test.user",
            "unique_id": "C123456",
            "email": "test.user@happyelements.com",
        }

        mock_request = MagicMock()
        mock_prisma = MagicMock()
        mock_existing_user = MagicMock()
        mock_existing_user.user_email = "test.user@happyelements.com"
        mock_prisma.db.litellm_usertable.find_unique = AsyncMock(return_value=mock_existing_user)

        mock_sso_client = self._make_mock_sso_client(user_info)

        with (
            patch(
                "litellm.proxy.management_endpoints.sso.happyelements_endpoints.get_happyelements_sso_client",
                return_value=mock_sso_client,
            ),
            patch(
                "litellm.proxy.management_endpoints.sso.happyelements_endpoints.prisma_client",
                mock_prisma,
            ),
            patch(
                "litellm.proxy.management_endpoints.sso.happyelements_endpoints.general_settings",
                {},
            ),
            patch(
                "litellm.proxy.management_endpoints.sso.happyelements_endpoints.user_api_key_cache",
                MagicMock(),
            ),
            patch(
                "litellm.proxy.management_endpoints.sso.happyelements_endpoints.cli_sso_callback",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ) as mock_cli_cb,
            patch(
                "litellm.proxy.management_endpoints.sso.happyelements_endpoints.SSOAuthenticationHandler",
            ) as mock_sso_handler,
        ):
            await happyelements_callback(
                request=mock_request,
                appid="he_test_key",
                rsptoken="dummytoken",
                cli_key="sk-clikey123",
            )

        mock_cli_cb.assert_called_once()
        call_kwargs = mock_cli_cb.call_args[1]
        assert call_kwargs["key"] == "sk-clikey123"
        assert call_kwargs["existing_key"] is None
        mock_sso_handler.get_redirect_response_from_openid.assert_not_called()

    async def test_no_cli_key_routes_to_browser_flow(self):
        from litellm.proxy.management_endpoints.sso.happyelements_endpoints import (
            happyelements_callback,
        )

        user_info = {
            "username": "test.user",
            "unique_id": "C123456",
            "email": "test.user@happyelements.com",
        }

        mock_request = MagicMock()
        mock_prisma = MagicMock()
        mock_existing_user = MagicMock()
        mock_existing_user.user_email = "test.user@happyelements.com"
        mock_prisma.db.litellm_usertable.find_unique = AsyncMock(return_value=mock_existing_user)

        mock_sso_client = self._make_mock_sso_client(user_info)

        with (
            patch(
                "litellm.proxy.management_endpoints.sso.happyelements_endpoints.get_happyelements_sso_client",
                return_value=mock_sso_client,
            ),
            patch(
                "litellm.proxy.management_endpoints.sso.happyelements_endpoints.prisma_client",
                mock_prisma,
            ),
            patch(
                "litellm.proxy.management_endpoints.sso.happyelements_endpoints.general_settings",
                {},
            ),
            patch(
                "litellm.proxy.management_endpoints.sso.happyelements_endpoints.user_api_key_cache",
                MagicMock(),
            ),
            patch(
                "litellm.proxy.management_endpoints.sso.happyelements_endpoints.cli_sso_callback",
                new_callable=AsyncMock,
            ) as mock_cli_cb,
            patch(
                "litellm.proxy.management_endpoints.sso.happyelements_endpoints.SSOAuthenticationHandler"
            ) as mock_sso_handler,
        ):
            mock_sso_handler.get_redirect_response_from_openid = AsyncMock(return_value=MagicMock())
            await happyelements_callback(
                request=mock_request,
                appid="he_test_key",
                rsptoken="dummytoken",
                cli_key=None,
            )

        mock_cli_cb.assert_not_called()
        mock_sso_handler.get_redirect_response_from_openid.assert_called_once()
