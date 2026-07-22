"""Cross-platform tray application."""

import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from typing import Optional

import pystray
import requests

from . import api, auth, autostart, config, icon
from .i18n import tr

logger = logging.getLogger(__name__)

REFRESH_OPTIONS = (5, 10, 30, 60)
UI_TICK_SECONDS = 60
THEME_TICK_SECONDS = 5


def _fmt_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return tr("1분 미만", "<1m")
    minutes = seconds // 60
    if minutes < 60:
        return tr(f"{minutes}분", f"{minutes}m")
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return tr(f"{hours}시간 {minutes}분", f"{hours}h {minutes}m")
    days, hours = divmod(hours, 24)
    return tr(
        f"{days}일 {hours}시간 {minutes}분",
        f"{days}d {hours}h {minutes}m",
    )


def _fmt_datetime(value: datetime) -> str:
    local = value.astimezone()
    if tr("ko", "en") == "ko":
        period = "오전" if local.hour < 12 else "오후"
        hour = local.hour % 12 or 12
        return f"{local.year}. {local.month}. {local.day}. {period} {hour}:{local.minute:02d}"
    return local.strftime("%Y-%m-%d %H:%M")


def _credit_status(status: str) -> str:
    labels = {
        "available": tr("사용 가능", "Available"),
        "used": tr("사용됨", "Used"),
        "expired": tr("만료됨", "Expired"),
    }
    return labels.get(status.lower(), status.replace("_", " ").title())


def _format_credit(credit: api.ResetCredit, now: Optional[datetime] = None) -> str:
    title = credit.title or credit.reset_type.replace("_", " ").title()
    title += f" · {_credit_status(credit.status)}"
    if not credit.expires_at:
        return title
    current = now or datetime.now(credit.expires_at.tzinfo)
    remaining_seconds = (credit.expires_at - current).total_seconds()
    if remaining_seconds > 0:
        remaining = _fmt_duration(remaining_seconds)
        return title + tr(
            f" · {_fmt_datetime(credit.expires_at)} 만료 ({remaining} 후)",
            f" · expires {_fmt_datetime(credit.expires_at)} (in {remaining})",
        )
    return title + tr(
        f" · {_fmt_datetime(credit.expires_at)} 만료",
        f" · expired {_fmt_datetime(credit.expires_at)}",
    )


def _hide_dock_icon() -> None:
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApplication

        NSApplication.sharedApplication().setActivationPolicy_(1)
    except Exception:
        logger.debug("Could not hide Dock icon", exc_info=True)


class CodexMeterApp:
    def __init__(self):
        self.cfg = config.load_config()
        self.usage: Optional[api.UsageData] = None
        self.status = tr("시작하는 중...", "Starting...")
        self.tray_icon: Optional[pystray.Icon] = None
        self._running = False
        self._fetching = threading.Lock()
        self._timer_lock = threading.Lock()
        self._refresh_timer: Optional[threading.Timer] = None
        self._ui_timer: Optional[threading.Timer] = None
        self._theme_timer: Optional[threading.Timer] = None
        self._icon_is_light: Optional[bool] = None
        self._login_in_progress = False
        self._device_code: Optional[str] = None

    @property
    def is_logged_in(self) -> bool:
        try:
            return auth.load_credentials() is not None
        except auth.AuthError:
            return False

    def run(self) -> None:
        self._running = True
        self.tray_icon = pystray.Icon(
            "codex_meter",
            icon.get_icon(),
            "Codex Meter",
            pystray.Menu(self._menu_items),
        )
        if sys.platform == "win32":
            self._icon_is_light = icon._is_light_theme()
        _hide_dock_icon()
        self.tray_icon.run(setup=self._on_ready)

    def _on_ready(self, tray_icon) -> None:
        tray_icon.visible = True
        icon.apply_macos_template(tray_icon)
        if sys.platform == "win32":
            from . import win_tray

            win_tray.enable_left_click_menu(tray_icon)
            self._schedule_theme_tick()
        threading.Thread(target=self._startup_worker, daemon=True).start()

    def _startup_worker(self) -> None:
        autostart.refresh_if_stale()
        if self.is_logged_in:
            self._refresh_usage()
        else:
            self.status = tr("로그인이 필요합니다", "Sign in required")
            self._update_ui()

    def stop(self, *_args) -> None:
        self._running = False
        with self._timer_lock:
            for timer in (self._refresh_timer, self._ui_timer, self._theme_timer):
                if timer:
                    timer.cancel()
            self._refresh_timer = None
            self._ui_timer = None
            self._theme_timer = None
        if self.tray_icon:
            self.tray_icon.stop()

    def _menu_items(self):
        items = []
        if self.is_logged_in:
            items.append(pystray.MenuItem(self._weekly_line(), self._open_usage_page))
            items.append(
                pystray.MenuItem(
                    self._reset_credit_summary(),
                    pystray.Menu(*self._reset_credit_items()),
                )
            )
        if self._device_code:
            items.append(pystray.MenuItem(f"Code: {self._device_code}", self._copy_device_code))
        if self.status:
            items.append(pystray.MenuItem(self.status, None))
        items.append(pystray.Menu.SEPARATOR)
        if self.is_logged_in:
            items.append(pystray.MenuItem(tr("지금 새로고침", "Refresh Now"), self._on_refresh))
            items.append(
                pystray.MenuItem(
                    tr("Codex 애널리틱스 페이지 열기", "Open Codex Analytics"),
                    self._open_analytics_page,
                )
            )
        items.append(
            pystray.MenuItem(
                tr("새로고침 주기", "Refresh Interval"),
                pystray.Menu(*[
                    pystray.MenuItem(
                        tr(f"{minutes}분", f"{minutes} min"),
                        self._interval_setter(minutes),
                        checked=lambda _item, m=minutes: self.cfg.refresh_interval == m,
                        radio=True,
                    )
                    for minutes in REFRESH_OPTIONS
                ]),
            )
        )
        items.append(
            pystray.MenuItem(
                tr("로그인 시 자동 시작", "Start at Login"),
                self._toggle_autostart,
                checked=lambda _item: autostart.is_enabled(),
            )
        )
        items.append(pystray.Menu.SEPARATOR)
        if self.is_logged_in:
            items.append(pystray.MenuItem(tr("로그아웃", "Sign Out"), self._on_logout))
        else:
            items.append(
                pystray.MenuItem(
                    tr("OpenAI로 로그인...", "Sign in with OpenAI..."),
                    self._on_login,
                    enabled=not self._login_in_progress,
                )
            )
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem(tr("종료", "Quit"), self.stop))
        return items

    def _weekly_line(self) -> str:
        if not self.usage:
            return tr("주간: ...", "Week: ...")
        weekly = self.usage.weekly
        remaining = _fmt_duration(
            (weekly.reset_at - datetime.now(weekly.reset_at.tzinfo)).total_seconds()
        )
        return tr(
            f"주간: {weekly.used_percent:.0f}% 사용 · {remaining} 후 초기화",
            f"Week: {weekly.used_percent:.0f}% used · resets in {remaining}",
        )

    def _reset_credit_summary(self) -> str:
        if not self.usage:
            return tr("사용량 한도 재설정: ...", "Usage limit resets: ...")
        if self.usage.reset_credits_error:
            return tr("사용량 한도 재설정: 조회 실패", "Usage limit resets: unavailable")
        count = self.usage.available_reset_count
        return tr(f"사용량 한도 재설정: {count}개", f"Usage limit resets: {count}")

    def _reset_credit_items(self):
        if not self.usage:
            return [pystray.MenuItem("...", None)]
        if self.usage.reset_credits_error:
            return [pystray.MenuItem(tr("조회하지 못했습니다", "Could not load"), None)]
        credits = self.usage.reset_credits
        if not credits:
            return [pystray.MenuItem(tr("보유한 재설정 없음", "No reset credits"), None)]
        output = []
        for credit in credits:
            output.append(pystray.MenuItem(_format_credit(credit), self._open_usage_page))
        return output

    def _tooltip(self) -> str:
        if not self.usage:
            return "Codex Meter"
        return tr(
            f"Codex 주간 {self.usage.weekly.used_percent:.0f}% 사용 | 재설정 {self.usage.available_reset_count}개",
            f"Codex weekly {self.usage.weekly.used_percent:.0f}% used | {self.usage.available_reset_count} resets",
        )

    def _update_ui(self) -> None:
        if not self.tray_icon:
            return
        try:
            self.tray_icon.title = self._tooltip()
            self.tray_icon.update_menu()
        except Exception:
            logger.exception("Tray UI update failed")

    def _notify(self, message: str) -> None:
        try:
            if self.tray_icon and self.tray_icon.HAS_NOTIFICATION:
                self.tray_icon.notify(message, "Codex Meter")
        except Exception:
            logger.debug("Notification failed", exc_info=True)

    def _open_usage_page(self, *_args) -> None:
        webbrowser.open("https://chatgpt.com/#settings/Usage", new=2)

    def _open_analytics_page(self, *_args) -> None:
        webbrowser.open("https://chatgpt.com/codex/cloud/settings/analytics", new=2)

    def _copy_device_code(self, *_args) -> None:
        if not self._device_code:
            return
        try:
            if sys.platform == "darwin":
                subprocess.run(["pbcopy"], input=self._device_code, text=True, timeout=5)
            elif sys.platform == "win32":
                subprocess.run(["clip"], input=self._device_code, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            logger.debug("Could not copy device code", exc_info=True)

    def _interval_setter(self, minutes: int):
        def setter(*_args):
            self.cfg.refresh_interval = minutes
            config.save_config(self.cfg)
            self._schedule_refresh()

        return setter

    def _toggle_autostart(self, *_args) -> None:
        try:
            autostart.disable() if autostart.is_enabled() else autostart.enable()
        except Exception as exc:
            logger.exception("Could not change start-at-login")
            self.status = tr("자동 시작 변경 실패", "Start-at-login change failed")
            self._notify(str(exc))
        self._update_ui()

    def _on_refresh(self, *_args) -> None:
        self._refresh_usage()

    def _on_logout(self, *_args) -> None:
        try:
            auth.delete_credentials()
        except auth.AuthError as exc:
            self.status = str(exc)
            self._update_ui()
            return
        self.usage = None
        self.status = tr("로그아웃됨", "Signed out")
        self._update_ui()

    def _on_login(self, *_args) -> None:
        if self._login_in_progress:
            return
        self._login_in_progress = True
        self.status = tr("로그인 준비 중...", "Preparing sign-in...")
        self._update_ui()
        threading.Thread(target=self._login_worker, daemon=True).start()

    def _login_worker(self) -> None:
        try:
            def on_code(code: auth.DeviceCode) -> None:
                self._device_code = code.user_code
                self._copy_device_code()
                self.status = tr(
                    f"브라우저에서 코드 {code.user_code}를 입력하세요 (클립보드에 복사됨)",
                    f"Enter code {code.user_code} in the browser (copied)",
                )
                self._update_ui()
                self._notify(self.status)

            auth.login(on_code, should_continue=lambda: self._running)
            self._device_code = None
            self.status = tr("로그인됨", "Signed in")
            self._update_ui()
            self._refresh_usage()
        except auth.LoginCancelled:
            pass
        except (auth.AuthError, requests.RequestException) as exc:
            logger.warning("Login failed: %s", exc)
            self.status = tr(f"로그인 실패: {exc}", f"Sign-in failed: {exc}")
            self._notify(self.status)
        finally:
            self._device_code = None
            self._login_in_progress = False
            self._update_ui()

    def _refresh_usage(self) -> None:
        if self.is_logged_in:
            threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self) -> None:
        if not self._fetching.acquire(blocking=False):
            return
        try:
            self.status = tr("가져오는 중...", "Fetching...")
            self._update_ui()
            self.usage = api.fetch_with_refresh()
            self.status = time.strftime(tr("%H:%M 업데이트됨", "Updated %H:%M"))
        except (auth.AuthError, api.UnauthorizedError) as exc:
            logger.warning("Authentication failed: %s", exc)
            self.status = tr("로그인이 만료되었습니다", "Sign-in expired")
            self._notify(tr("다시 로그인하세요.", "Please sign in again."))
        except requests.RequestException as exc:
            logger.warning("Network error: %s", exc)
            self.status = tr("네트워크 오류 · 재시도 예정", "Network error · will retry")
        except api.ResponseError as exc:
            logger.warning("API response error: %s", exc)
            self.status = tr("사용량 응답을 읽지 못했습니다", "Could not read usage response")
        except Exception:
            logger.exception("Unexpected refresh error")
            self.status = tr("예기치 않은 오류 · 로그 확인", "Unexpected error · see log")
        finally:
            self._fetching.release()
            self._schedule_refresh()
            self._schedule_ui_tick()
            self._update_ui()

    def _schedule_refresh(self) -> None:
        if not self._running or not self.is_logged_in:
            return
        with self._timer_lock:
            if self._refresh_timer:
                self._refresh_timer.cancel()
            self._refresh_timer = threading.Timer(
                self.cfg.refresh_interval * 60, self._refresh_usage
            )
            self._refresh_timer.daemon = True
            self._refresh_timer.start()

    def _schedule_ui_tick(self) -> None:
        if not self._running or not self.usage:
            return
        with self._timer_lock:
            if self._ui_timer:
                self._ui_timer.cancel()
            self._ui_timer = threading.Timer(UI_TICK_SECONDS, self._ui_tick)
            self._ui_timer.daemon = True
            self._ui_timer.start()

    def _ui_tick(self) -> None:
        self._update_ui()
        self._schedule_ui_tick()

    def _schedule_theme_tick(self) -> None:
        if not self._running or sys.platform != "win32":
            return
        with self._timer_lock:
            if self._theme_timer:
                self._theme_timer.cancel()
            self._theme_timer = threading.Timer(THEME_TICK_SECONDS, self._theme_tick)
            self._theme_timer.daemon = True
            self._theme_timer.start()

    def _theme_tick(self) -> None:
        self._refresh_icon_for_theme()
        self._schedule_theme_tick()

    def _refresh_icon_for_theme(self) -> None:
        if sys.platform != "win32" or not self.tray_icon:
            return
        light = icon._is_light_theme()
        if light == self._icon_is_light:
            return
        self._icon_is_light = light
        try:
            self.tray_icon.icon = icon.get_icon()
        except Exception:
            logger.debug("Tray icon theme refresh failed", exc_info=True)
