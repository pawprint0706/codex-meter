#!/bin/bash
# Uninstall Codex Meter (macOS / Linux): stop the app, remove the autostart
# entry, saved OAuth credentials, app data, and the virtualenv.
set -e
cd "$(dirname "$0")"

echo "This will stop Codex Meter and remove:"
echo "  - the Start-at-Login entry (LaunchAgent / autostart)"
echo "  - the OAuth login from macOS Keychain"
echo "  - app data in ~/.codex-meter"
echo "  - the .venv folder in this project"
read -p "Continue? [y/N] " CONFIRM
case "$CONFIRM" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "Cancelled."; exit 0 ;;
esac

echo ""
echo "Stopping any running instance and removing login and autostart..."
if [ -x .venv/bin/python ]; then
    .venv/bin/python launch.py --stop >/dev/null 2>&1 || true
    .venv/bin/python -c "from codex_meter import auth, autostart; auth.delete_credentials(); autostart.disable()" >/dev/null 2>&1 || true
fi

# Fallback: remove the LaunchAgent directly if the virtualenv is gone.
LABEL="local.codex-meter"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
if [ -f "$PLIST" ]; then
    launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
    rm -f "$PLIST"
fi

echo "Removing app data (~/.codex-meter) and .venv..."
rm -rf "$HOME/.codex-meter"
rm -rf .venv

echo ""
echo "Done. Codex Meter has been removed."
echo "You can now delete this project folder if you want: $(pwd)"
read -p "Press Enter to close this window..."
