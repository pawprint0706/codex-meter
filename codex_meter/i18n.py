"""Small Korean/English localization helper."""

import os
import sys

_detected = None


def _detect() -> str:
    if sys.platform == "darwin":
        try:
            from Foundation import NSLocale

            languages = NSLocale.preferredLanguages()
            if languages:
                return "ko" if str(languages[0]).lower().startswith("ko") else "en"
        except Exception:
            pass
    if sys.platform == "win32":
        try:
            import ctypes

            language_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "ko" if (language_id & 0x3FF) == 0x12 else "en"
        except Exception:
            pass
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(name)
        if value:
            return "ko" if value.lower().startswith("ko") else "en"
    return "en"


def current_lang() -> str:
    override = os.environ.get("CODEX_METER_LANG")
    if override in ("ko", "en"):
        return override
    global _detected
    if _detected is None:
        _detected = _detect()
    return _detected


def tr(ko: str, en: str) -> str:
    return ko if current_lang() == "ko" else en
