"""Run subprocesses without pipe inheritance or surviving process groups."""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path


def _kill_process_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _kill_processes_owned_by(uid: int) -> None:
    """Kill untrusted processes that escaped the original process group."""
    for _ in range(3):
        found = False
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                if entry.stat().st_uid != uid:
                    continue
                os.kill(int(entry.name), signal.SIGKILL)
                found = True
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
        if not found:
            return
        time.sleep(0.01)


def run_isolated(
    command,
    *,
    cwd,
    env,
    timeout,
    reap_uid=None,
) -> subprocess.CompletedProcess[str]:
    """Capture through root-owned files and terminate all untrusted children."""
    with tempfile.TemporaryDirectory(prefix="verifier-capture-") as raw:
        capture_dir = Path(raw)
        stdout_path = capture_dir / "stdout"
        stderr_path = capture_dir / "stderr"
        with stdout_path.open("w+b") as stdout_handle, stderr_path.open(
            "w+b"
        ) as stderr_handle:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                start_new_session=True,
            )
            timed_out = False
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                _kill_process_group(process)
                if reap_uid is not None:
                    _kill_processes_owned_by(reap_uid)
            stdout_handle.flush()
            stderr_handle.flush()
            stdout_handle.seek(0)
            stderr_handle.seek(0)
            stdout = stdout_handle.read().decode("utf-8", errors="replace")
            stderr = stderr_handle.read().decode("utf-8", errors="replace")
        if timed_out:
            raise subprocess.TimeoutExpired(
                command,
                timeout,
                output=stdout,
                stderr=stderr,
            )
        return subprocess.CompletedProcess(
            command,
            process.returncode,
            stdout,
            stderr,
        )
