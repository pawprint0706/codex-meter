"""Best-effort Windows left-click tray menu support."""

import ctypes
import logging
from ctypes import wintypes

logger = logging.getLogger(__name__)


def enable_left_click_menu(tray_icon) -> None:
    try:
        from pystray._util import win32

        def show_menu():
            menu_handle = getattr(tray_icon, "_menu_handle", None)
            if not menu_handle:
                return
            win32.SetForegroundWindow(tray_icon._hwnd)
            point = wintypes.POINT()
            win32.GetCursorPos(ctypes.byref(point))
            menu, descriptors = menu_handle
            index = win32.TrackPopupMenuEx(
                menu,
                win32.TPM_RIGHTALIGN | win32.TPM_BOTTOMALIGN | win32.TPM_RETURNCMD,
                point.x,
                point.y,
                tray_icon._menu_hwnd,
                None,
            )
            if index > 0:
                descriptors[index - 1](tray_icon)

        def on_notify(_wparam, lparam):
            if lparam in (win32.WM_LBUTTONUP, win32.WM_RBUTTONUP):
                show_menu()
            return 0

        tray_icon._message_handlers[win32.WM_NOTIFY] = on_notify
    except Exception:
        logger.debug("Could not enable the left-click menu", exc_info=True)
