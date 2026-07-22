import sys
import types
from unittest.mock import Mock


def install_keyring_stub():
    try:
        import keyring  # noqa: F401
    except ModuleNotFoundError:
        keyring = types.ModuleType("keyring")
        keyring.errors = types.SimpleNamespace(
            KeyringError=type("KeyringError", (Exception,), {}),
            PasswordDeleteError=type("PasswordDeleteError", (Exception,), {}),
        )
        keyring.get_password = Mock()
        keyring.set_password = Mock()
        keyring.delete_password = Mock()
        sys.modules["keyring"] = keyring


def install_pystray_stub():
    try:
        import pystray  # noqa: F401
    except ModuleNotFoundError:
        pystray = types.ModuleType("pystray")
        pystray.Icon = type("Icon", (), {})
        pystray.Menu = type("Menu", (), {"SEPARATOR": object()})
        pystray.MenuItem = type("MenuItem", (), {})
        sys.modules["pystray"] = pystray
