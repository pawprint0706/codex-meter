from datetime import datetime, timezone
import time
import unittest
from unittest.mock import Mock, patch

from tests._support import install_keyring_stub

install_keyring_stub()

from codex_meter import api, auth


def credentials(access_token="access", refresh_token="refresh"):
    return auth.Credentials(
        access_token=access_token,
        refresh_token=refresh_token,
        id_token=None,
        account_id="account",
        email=None,
        plan_type="plus",
        refreshed_at=time.time(),
    )


class ParsingTests(unittest.TestCase):
    def test_longest_rate_limit_window_is_weekly(self):
        payload = {
            "plan_type": "plus",
            "rate_limit": {
                "primary_window": {
                    "used_percent": 10,
                    "reset_at": 1_800_000_000,
                    "limit_window_seconds": 18_000,
                },
                "secondary_window": {
                    "used_percent": 5,
                    "reset_at": 1_800_100_000,
                    "limit_window_seconds": 604_800,
                },
            },
        }

        weekly, plan = api.parse_usage(payload)

        self.assertEqual(weekly.window_seconds, 604_800)
        self.assertEqual(weekly.remaining_percent, 95)
        self.assertEqual(plan, "plus")

    def test_reset_credit_fallback_counts_only_available(self):
        credits, count = api.parse_reset_credits({
            "credits": [
                {"id": "one", "reset_type": "full_reset", "status": "available"},
                {"id": "two", "reset_type": "full_reset", "status": "used"},
            ]
        })

        self.assertEqual(len(credits), 2)
        self.assertEqual(count, 1)

    def test_iso_expiration_is_timezone_aware(self):
        credits, _ = api.parse_reset_credits({
            "credits": [{
                "id": "one",
                "status": "available",
                "expires_at": "2026-08-13T00:00:00Z",
            }]
        })

        self.assertEqual(credits[0].expires_at, datetime(2026, 8, 13, tzinfo=timezone.utc))


class RetryTests(unittest.TestCase):
    @patch("codex_meter.api.auth.valid_credentials")
    @patch("codex_meter.api.fetch_usage")
    def test_unauthorized_refreshes_and_retries_once(self, fetch_usage, valid_credentials):
        old = credentials("old-access")
        new = credentials("new-access", "new-refresh")
        valid_credentials.side_effect = [old, new]
        expected = Mock(spec=api.UsageData)
        fetch_usage.side_effect = [api.UnauthorizedError("HTTP 401"), expected]

        result = api.fetch_with_refresh(session=Mock())

        self.assertIs(result, expected)
        self.assertEqual(fetch_usage.call_count, 2)
        self.assertEqual(valid_credentials.call_args_list[1].kwargs, {"force_refresh": True})

    @patch("codex_meter.api.auth.valid_credentials")
    @patch("codex_meter.api.fetch_usage")
    def test_second_unauthorized_is_not_retried(self, fetch_usage, valid_credentials):
        valid_credentials.side_effect = [credentials("old"), credentials("new")]
        fetch_usage.side_effect = api.UnauthorizedError("HTTP 403")

        with self.assertRaises(api.UnauthorizedError):
            api.fetch_with_refresh()

        self.assertEqual(fetch_usage.call_count, 2)


if __name__ == "__main__":
    unittest.main()
