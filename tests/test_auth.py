import json
import secrets
import time
import unittest
from unittest.mock import Mock, patch

from tests._support import install_keyring_stub

install_keyring_stub()

from codex_meter import auth


def credentials(access_token="access", refresh_token="refresh"):
    return auth.Credentials(
        access_token=access_token,
        refresh_token=refresh_token,
        id_token=None,
        account_id="account",
        email="user@example.com",
        plan_type="plus",
        refreshed_at=time.time(),
    )


class AuthTests(unittest.TestCase):
    @patch("codex_meter.auth.keyring.set_password")
    @patch("codex_meter.auth.keyring.get_password", return_value=None)
    def test_save_credentials_replaces_complete_record(self, _get_password, set_password):
        value = credentials("new-access", "rotated-refresh")

        auth.save_credentials(value)

        packed = set_password.call_args.args[2]
        self.assertTrue(packed.startswith("z1:"))
        with patch("codex_meter.auth.keyring.get_password", return_value=packed):
            stored = auth.load_credentials()
        self.assertEqual(stored, value)

    @patch("codex_meter.auth.keyring.delete_password")
    @patch("codex_meter.auth.keyring.get_password", return_value=None)
    @patch("codex_meter.auth.keyring.set_password")
    def test_large_credentials_commit_with_chunk_manifest(
        self, set_password, _get_password, _delete_password
    ):
        value = credentials(secrets.token_urlsafe(3000), secrets.token_urlsafe(3000))

        auth.save_credentials(value)

        manifest_call = set_password.call_args_list[-1]
        self.assertEqual(manifest_call.args[:2], (auth.KEYRING_SERVICE, auth.KEYRING_ACCOUNT))
        self.assertTrue(manifest_call.args[2].startswith("m1:"))
        self.assertGreater(set_password.call_count, 2)

    def test_request_device_code_uses_public_codex_client(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "user_code": "ABCD-EFGH",
            "device_auth_id": "device-id",
            "interval": 3,
        }
        session = Mock()
        session.post.return_value = response

        result = auth.request_device_code(session)

        self.assertEqual(result.user_code, "ABCD-EFGH")
        self.assertEqual(result.interval, 3)
        self.assertEqual(session.post.call_args.kwargs["json"], {"client_id": auth.CLIENT_ID})

    def test_refresh_uses_json_and_saves_rotated_token(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "access_token": "new-access",
            "refresh_token": "rotated-refresh",
        }
        session = Mock()
        session.post.return_value = response

        with patch("codex_meter.auth.save_credentials") as save:
            updated = auth.refresh_credentials(credentials(), session=session)

        self.assertEqual(updated.refresh_token, "rotated-refresh")
        self.assertNotIn("data", session.post.call_args.kwargs)
        self.assertEqual(session.post.call_args.kwargs["json"]["refresh_token"], "refresh")
        save.assert_called_once_with(updated)

    @patch("codex_meter.auth.keyring.get_password", return_value='{"access_token":""}')
    def test_invalid_stored_record_is_rejected(self, _get_password):
        with self.assertRaises(auth.AuthError):
            auth.load_credentials()


if __name__ == "__main__":
    unittest.main()
