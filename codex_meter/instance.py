"""Single-instance lock and targeted stop support."""

import os
import signal
import subprocess
import sys
import time


def _paths() -> tuple[str, str]:
    from . import config

    root = config.config_dir()
    return os.path.join(root, "app.lock"), os.path.join(root, "app.pid")


def _try_lock():
    lock_path, _ = _paths()
    handle = open(lock_path, "a+")
    try:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def _release(handle) -> None:
    try:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    handle.close()


def acquire_lock():
    handle = _try_lock()
    if handle is None:
        return None
    _, pid_path = _paths()
    with open(pid_path, "w", encoding="ascii") as pid_file:
        pid_file.write(str(os.getpid()))
    return handle


def stop_running(timeout: float = 10.0) -> bool:
    probe = _try_lock()
    if probe is not None:
        _release(probe)
        return True
    _, pid_path = _paths()
    try:
        with open(pid_path, "r", encoding="ascii") as pid_file:
            pid = int(pid_file.read().strip())
    except (OSError, ValueError):
        return False
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        probe = _try_lock()
        if probe is not None:
            _release(probe)
            return True
        time.sleep(0.2)
    return False
