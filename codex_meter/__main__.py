"""Codex Meter entry point."""

import argparse
import logging
import os
import shutil
import sys

from . import auth, autostart, config, instance
from .tray import CodexMeterApp


def _handlers():
    handlers = []
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    try:
        handlers.append(
            logging.FileHandler(os.path.join(config.config_dir(), "app.log"), encoding="utf-8")
        )
    except OSError:
        pass
    return handlers


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor ChatGPT Codex usage in the system tray.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--stop", action="store_true")
    actions.add_argument("--replace", action="store_true")
    actions.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    if args.uninstall:
        if not instance.stop_running():
            parser.error("could not stop the running Codex Meter instance")
        autostart.disable()
        auth.delete_credentials()
        shutil.rmtree(config.config_dir(), ignore_errors=True)
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=_handlers(),
    )
    if args.stop:
        sys.exit(0 if instance.stop_running() else 1)
    if args.replace and not instance.stop_running():
        sys.exit(1)
    lock = instance.acquire_lock()
    if lock is None:
        logging.getLogger(__name__).warning("Codex Meter is already running")
        return
    app = CodexMeterApp()
    try:
        app.run()
    except KeyboardInterrupt:
        app.stop()
