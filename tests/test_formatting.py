from datetime import datetime, timedelta, timezone
import os
import unittest
from unittest.mock import patch

from tests._support import install_keyring_stub, install_pystray_stub

install_keyring_stub()
install_pystray_stub()

from codex_meter import api, i18n, tray


class FormattingTests(unittest.TestCase):
    def test_duration_formats_days_hours_and_minutes(self):
        with patch.dict(os.environ, {"CODEX_METER_LANG": "ko"}):
            self.assertEqual(
                tray._fmt_duration(6 * 86400 + 12 * 3600 + 3 * 60),
                "6일 12시간 3분",
            )
        with patch.dict(os.environ, {"CODEX_METER_LANG": "en"}):
            self.assertEqual(tray._fmt_duration(3720), "1h 2m")

    def test_weekly_line_combines_used_percent_and_local_countdown(self):
        app = object.__new__(tray.CodexMeterApp)
        app.usage = api.UsageData(
            weekly=api.UsageWindow(
                used_percent=5,
                reset_at=datetime.now(timezone.utc) + timedelta(days=6, hours=12, minutes=4),
                window_seconds=604800,
            )
        )

        with patch.dict(os.environ, {"CODEX_METER_LANG": "ko"}):
            text = app._weekly_line()

        self.assertTrue(text.startswith("주간: 5% 사용 · "))
        self.assertIn("후 초기화", text)
        self.assertNotIn("남음", text)

    def test_available_credit_includes_expiration_countdown(self):
        now = datetime(2026, 8, 12, 22, tzinfo=timezone.utc)
        credit = api.ResetCredit(
            id="one",
            reset_type="full_reset",
            status="available",
            title="Full reset",
            description=None,
            expires_at=now + timedelta(hours=2),
        )

        with patch.dict(os.environ, {"CODEX_METER_LANG": "en"}):
            text = tray._format_credit(credit, now=now)

        self.assertIn("Full reset · Available", text)
        self.assertIn("in 2h 0m", text)

    def test_expired_credit_is_marked_expired(self):
        now = datetime(2026, 8, 13, tzinfo=timezone.utc)
        credit = api.ResetCredit(
            id="one",
            reset_type="full_reset",
            status="expired",
            title=None,
            description=None,
            expires_at=now - timedelta(minutes=1),
        )

        with patch.dict(os.environ, {"CODEX_METER_LANG": "ko"}):
            text = tray._format_credit(credit, now=now)

        self.assertIn("만료됨", text)
        self.assertIn("만료", text)

    @patch("codex_meter.tray.webbrowser.open")
    def test_usage_and_analytics_open_different_pages(self, open_browser):
        app = object.__new__(tray.CodexMeterApp)

        app._open_usage_page()
        app._open_analytics_page()

        self.assertEqual(
            open_browser.call_args_list[0].args[0],
            "https://chatgpt.com/#settings/Usage",
        )
        self.assertEqual(
            open_browser.call_args_list[1].args[0],
            "https://chatgpt.com/codex/cloud/settings/analytics",
        )


if __name__ == "__main__":
    unittest.main()
