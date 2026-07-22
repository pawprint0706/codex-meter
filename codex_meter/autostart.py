"""Start-at-login registration for macOS and Windows."""

import logging
import os
import platform
import subprocess
import sys

logger = logging.getLogger(__name__)

APP_LABEL = "local.codex-meter"
_SYSTEM = platform.system()
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE = "CodexMeter"


def _project_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _launcher() -> str:
    return os.path.join(_project_dir(), "launch.py")


def _python() -> str:
    executable = sys.executable
    if _SYSTEM == "Windows":
        pythonw = os.path.join(os.path.dirname(executable), "pythonw.exe")
        if os.path.exists(pythonw):
            return pythonw
    return executable


def _command() -> list[str]:
    return [_python(), _launcher()]


def _plist_path() -> str:
    return os.path.expanduser(f"~/Library/LaunchAgents/{APP_LABEL}.plist")


def _registry_command() -> str:
    python, launcher = _command()
    return f'"{python}" "{launcher}"'


def _read_registry():
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as key:
            return winreg.QueryValueEx(key, _RUN_VALUE)[0]
    except FileNotFoundError:
        return None


def is_enabled() -> bool:
    try:
        if _SYSTEM == "Darwin":
            return os.path.exists(_plist_path())
        if _SYSTEM == "Windows":
            return _read_registry() is not None
        return False
    except Exception:
        logger.exception("Could not check start-at-login state")
        return False


def enable() -> None:
    if _SYSTEM == "Darwin":
        import plistlib

        from . import config

        path = _plist_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {
            "Label": APP_LABEL,
            "ProgramArguments": _command(),
            "RunAtLoad": True,
            "WorkingDirectory": _project_dir(),
            "StandardOutPath": os.path.join(config.config_dir(), "launchd.log"),
            "StandardErrorPath": os.path.join(config.config_dir(), "launchd.log"),
        }
        with open(path, "wb") as handle:
            plistlib.dump(payload, handle)
    elif _SYSTEM == "Windows":
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, _RUN_VALUE, 0, winreg.REG_SZ, _registry_command())


def disable() -> None:
    if _SYSTEM == "Darwin":
        try:
            os.unlink(_plist_path())
        except FileNotFoundError:
            pass
        try:
            subprocess.run(
                ["launchctl", "bootout", f"gui/{os.getuid()}/{APP_LABEL}"],
                capture_output=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    elif _SYSTEM == "Windows":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, _RUN_VALUE)
        except FileNotFoundError:
            pass


def refresh_if_stale() -> None:
    if not is_enabled():
        return
    try:
        if _SYSTEM == "Windows" and _read_registry() != _registry_command():
            enable()
        elif _SYSTEM == "Darwin":
            import plistlib

            with open(_plist_path(), "rb") as handle:
                current = plistlib.load(handle).get("ProgramArguments")
            if current != _command():
                enable()
    except Exception:
        logger.exception("Could not refresh start-at-login registration")
