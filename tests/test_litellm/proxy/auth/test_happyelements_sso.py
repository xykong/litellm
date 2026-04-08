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
    async def _call_login(self, key=None, preferred_team_id=None):
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
            await happyelements_login(request=mock_request, key=key, preferred_team_id=preferred_team_id)

        return mock_sso_client.generate_login_url

    async def test_no_key_uses_default_callback(self):
        generate_login_url = await self._call_login(key=None)
        generate_login_url.assert_called_once_with(client_ip="1.2.3.4", callback_url_override=None)

    async def test_valid_cli_key_embeds_key_in_callback(self):
        generate_login_url = await self._call_login(key="sk-mykey123")
        override = generate_login_url.call_args[1].get("callback_url_override")
        assert override is not None
        assert "cli_key=sk-mykey123" in override

    async def test_non_sk_key_ignored(self):
        generate_login_url = await self._call_login(key="notakey")
        _, kwargs = generate_login_url.call_args
        assert kwargs.get("callback_url_override") is None

    async def test_preferred_team_id_embedded_in_callback(self):
        generate_login_url = await self._call_login(key="sk-mykey123", preferred_team_id="team-abc")
        override = generate_login_url.call_args[1].get("callback_url_override")
        assert override is not None
        assert "cli_key=sk-mykey123" in override
        assert "preferred_team_id=team-abc" in override

    async def test_preferred_team_id_without_key_not_embedded(self):
        generate_login_url = await self._call_login(key=None, preferred_team_id="team-abc")
        _, kwargs = generate_login_url.call_args
        assert kwargs.get("callback_url_override") is None


@pytest.mark.asyncio
class TestGetOrCreateCliVirtualKey:
    def _make_prisma(self, existing_token=None):
        mock_prisma = MagicMock()
        mock_prisma.db.litellm_verificationtoken.find_first = AsyncMock(
            return_value=MagicMock(token="hashed-token-abc") if existing_token else None
        )
        mock_prisma.db.litellm_verificationtoken.delete = AsyncMock()
        return mock_prisma

    def _make_user_data(self, teams=None, user_role="internal_user"):
        user_data = MagicMock()
        user_data.user_role = user_role
        user_data.teams = teams or []
        return user_data

    async def test_creates_new_key_when_none_exists(self):
        from litellm.proxy.management_endpoints.sso.happyelements_endpoints import (
            _get_or_create_cli_virtual_key,
        )

        mock_prisma = self._make_prisma(existing_token=False)
        user_data = self._make_user_data(teams=["team-1"])

        with patch(
            "litellm.proxy.management_endpoints.sso.happyelements_endpoints.generate_key_helper_fn",
            new_callable=AsyncMock,
            return_value={"token": "sk-newkey123", "key_alias": "cli-sso-user1"},
        ) as mock_gen:
            result = await _get_or_create_cli_virtual_key(
                user_id="user1",
                user_email="user1@test.com",
                user_data=user_data,
                prisma_client=mock_prisma,
            )

        assert result == "sk-newkey123"
        mock_prisma.db.litellm_verificationtoken.delete.assert_not_called()
        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["key_alias"] == "cli-sso-user1"
        assert call_kwargs["team_id"] == "team-1"

    async def test_deletes_old_key_and_regenerates_when_exists(self):
        from litellm.proxy.management_endpoints.sso.happyelements_endpoints import (
            _get_or_create_cli_virtual_key,
        )

        mock_prisma = self._make_prisma(existing_token=True)
        user_data = self._make_user_data(teams=["team-1"])

        with patch(
            "litellm.proxy.management_endpoints.sso.happyelements_endpoints.generate_key_helper_fn",
            new_callable=AsyncMock,
            return_value={"token": "sk-regenerated456", "key_alias": "cli-sso-user1"},
        ) as mock_gen:
            result = await _get_or_create_cli_virtual_key(
                user_id="user1",
                user_email="user1@test.com",
                user_data=user_data,
                prisma_client=mock_prisma,
            )

        assert result == "sk-regenerated456"
        mock_prisma.db.litellm_verificationtoken.delete.assert_called_once_with(where={"token": "hashed-token-abc"})
        mock_gen.assert_called_once()

    async def test_preferred_team_id_used_when_valid(self):
        from litellm.proxy.management_endpoints.sso.happyelements_endpoints import (
            _get_or_create_cli_virtual_key,
        )

        mock_prisma = self._make_prisma(existing_token=False)
        user_data = self._make_user_data(teams=["team-1", "team-2", "team-3"])

        with patch(
            "litellm.proxy.management_endpoints.sso.happyelements_endpoints.generate_key_helper_fn",
            new_callable=AsyncMock,
            return_value={"token": "sk-teamkey", "key_alias": "cli-sso-user1"},
        ) as mock_gen:
            await _get_or_create_cli_virtual_key(
                user_id="user1",
                user_email="user1@test.com",
                user_data=user_data,
                prisma_client=mock_prisma,
                preferred_team_id="team-2",
            )

        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["team_id"] == "team-2"

    async def test_preferred_team_id_ignored_when_not_in_user_teams(self):
        from litellm.proxy.management_endpoints.sso.happyelements_endpoints import (
            _get_or_create_cli_virtual_key,
        )

        mock_prisma = self._make_prisma(existing_token=False)
        user_data = self._make_user_data(teams=["team-1", "team-2"])

        with patch(
            "litellm.proxy.management_endpoints.sso.happyelements_endpoints.generate_key_helper_fn",
            new_callable=AsyncMock,
            return_value={"token": "sk-fallback", "key_alias": "cli-sso-user1"},
        ) as mock_gen:
            await _get_or_create_cli_virtual_key(
                user_id="user1",
                user_email="user1@test.com",
                user_data=user_data,
                prisma_client=mock_prisma,
                preferred_team_id="team-999",
            )

        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["team_id"] == "team-1"

    async def test_no_teams_results_in_none_team_id(self):
        from litellm.proxy.management_endpoints.sso.happyelements_endpoints import (
            _get_or_create_cli_virtual_key,
        )

        mock_prisma = self._make_prisma(existing_token=False)
        user_data = self._make_user_data(teams=[])

        with patch(
            "litellm.proxy.management_endpoints.sso.happyelements_endpoints.generate_key_helper_fn",
            new_callable=AsyncMock,
            return_value={"token": "sk-notable", "key_alias": "cli-sso-user1"},
        ) as mock_gen:
            await _get_or_create_cli_virtual_key(
                user_id="user1",
                user_email="user1@test.com",
                user_data=user_data,
                prisma_client=mock_prisma,
            )

        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["team_id"] is None


@pytest.mark.asyncio
class TestHappyelementsCallback:
    def _make_mock_sso_client(self, user_info):
        mock_sso_client = MagicMock()
        mock_sso_client.process_callback = MagicMock(return_value=user_info)
        mock_sso_client.get_user_id = MagicMock(return_value=user_info.get("unique_id", "testuser"))
        mock_sso_client.get_user_display_name = MagicMock(return_value="Test User")
        return mock_sso_client

    def _make_mock_prisma(self, teams=None):
        mock_prisma = MagicMock()
        mock_existing_user = MagicMock()
        mock_existing_user.user_email = "test.user@happyelements.com"
        mock_existing_user.teams = teams or []
        mock_prisma.db.litellm_usertable.find_unique = AsyncMock(return_value=mock_existing_user)
        mock_prisma.db.litellm_verificationtoken.find_first = AsyncMock(return_value=None)
        mock_prisma.db.litellm_teamtable.find_unique = AsyncMock(return_value=None)
        mock_prisma.db.litellm_teamtable.find_many = AsyncMock(return_value=[])
        return mock_prisma

    async def test_cli_key_creates_virtual_key_and_stores_in_cache(self):
        from litellm.proxy.management_endpoints.sso.happyelements_endpoints import (
            happyelements_callback,
        )

        user_info = {
            "username": "test.user",
            "unique_id": "C123456",
            "email": "test.user@happyelements.com",
        }

        mock_request = MagicMock()
        mock_request.query_params = {}
        mock_prisma = self._make_mock_prisma(teams=["team-1"])
        mock_cache = MagicMock()
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
                mock_cache,
            ),
            patch(
                "litellm.proxy.management_endpoints.sso.happyelements_endpoints._get_or_create_cli_virtual_key",
                new_callable=AsyncMock,
                return_value="sk-virtualkey789",
            ) as mock_get_key,
            patch("litellm.proxy.management_endpoints.sso.happyelements_endpoints.SSOAuthenticationHandler"),
        ):
            await happyelements_callback(
                request=mock_request,
                appid="he_test_key",
                rsptoken="dummytoken",
                cli_key="sk-clikey123",
            )

        mock_get_key.assert_called_once()
        call_kwargs = mock_get_key.call_args[1]
        assert call_kwargs["user_id"] == "C123456"

        mock_cache.set_cache.assert_called_once()
        cache_call_kwargs = mock_cache.set_cache.call_args[1]
        stored = cache_call_kwargs["value"]
        assert stored["status"] == "ready"
        assert stored["key"] == "sk-virtualkey789"
        assert stored["user_id"] == "C123456"

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
        mock_prisma = self._make_mock_prisma()
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
                "litellm.proxy.management_endpoints.sso.happyelements_endpoints._get_or_create_cli_virtual_key",
                new_callable=AsyncMock,
            ) as mock_get_key,
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

        mock_get_key.assert_not_called()
        mock_sso_handler.get_redirect_response_from_openid.assert_called_once()
