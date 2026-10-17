#!/usr/bin/env python3
"""Reference implementation for the trustworthy multi-linker benchmark."""

from __future__ import annotations

import ctypes
import errno
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path


LINKERS = ("bfd", "gold", "lld", "mold")
SELECTOR_ARGS = {
    "bfd": ["-fuse-ld=bfd"],
    "gold": ["-fuse-ld=gold"],
    "lld": ["-fuse-ld=lld"],
    "mold": ["-fuse-ld=mold"],
}
THREAD_ARGS = {
    "bfd": [],
    "gold": ["-Wl,--threads", "-Wl,--thread-count=2"],
    "lld": ["-Wl,--threads=2"],
    "mold": ["-Wl,--threads=2", "-Wl,--no-fork"],
}
EFFECTIVE_THREADS = {"bfd": 1, "gold": 2, "lld": 2, "mold": 2}
TIE_BREAK = {linker: index for index, linker in enumerate(LINKERS)}

PTRACE_TRACEME = 0
PTRACE_CONT = 7
PTRACE_SETOPTIONS = 0x4200
PTRACE_GETEVENTMSG = 0x4201
PTRACE_O_TRACEFORK = 0x00000002
PTRACE_O_TRACEVFORK = 0x00000004
PTRACE_O_TRACEEXEC = 0x00000010
PTRACE_O_EXITKILL = 0x00100000
PTRACE_EVENT_FORK = 1
PTRACE_EVENT_VFORK = 2
PTRACE_EVENT_EXEC = 4
WAIT_ALL = 0x40000000
TRACE_OPTIONS = (
    PTRACE_O_TRACEFORK
    | PTRACE_O_TRACEVFORK
    | PTRACE_O_TRACEEXEC
    | PTRACE_O_EXITKILL
)

LIBC = ctypes.CDLL(None, use_errno=True)
LIBC.ptrace.restype = ctypes.c_long


class BenchError(RuntimeError):
    """The benchmark contract could not be satisfied."""


def ptrace(request: int, pid: int, address: int = 0, data: int = 0) -> int:
    """Call ptrace and convert errno into a useful exception."""
    ctypes.set_errno(0)
    result = LIBC.ptrace(
        ctypes.c_uint(request),
        ctypes.c_uint(pid),
        ctypes.c_void_p(address),
        ctypes.c_void_p(data),
    )
    if result == -1:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return int(result)


def ptrace_event_pid(pid: int) -> int:
    """Read the child PID attached by a fork or vfork event."""
    message = ctypes.c_ulong()
    ctypes.set_errno(0)
    result = LIBC.ptrace(
        ctypes.c_uint(PTRACE_GETEVENTMSG),
        ctypes.c_uint(pid),
        ctypes.c_void_p(),
        ctypes.byref(message),
    )
    if result == -1:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return int(message.value)


def first_nonempty_line(text: str) -> str:
    """Return the first nonempty output line without its terminator."""
    for line in text.splitlines():
        if line.strip():
            return line
    return ""


def family_from_version(version: str) -> str | None:
    """Classify the four supported linker version formats."""
    lower = version.lower()
    if "mold" in lower:
        return "mold"
    if "gnu gold" in lower:
        return "gold"
    if "lld" in lower:
        return "lld"
    if "gnu ld" in lower:
        return "bfd"
    return None


def linker_shaped(path: str) -> bool:
    """Reject compiler helpers even when their version resembles a linker."""
    name = Path(path).name.lower()
    return (
        name == "ld"
        or name == "mold"
        or "ld.bfd" in name
        or "ld.gold" in name
        or "ld.lld" in name
        or "ld.mold" in name
    )


def read_exec(pid: int) -> dict[str, object] | None:
    """Capture the flavor-preserving argv and canonical executable target."""
    try:
        command_line = Path(f"/proc/{pid}/cmdline").read_bytes()
        arguments = [
            os.fsdecode(item) for item in command_line.split(b"\0") if item
        ]
    except (FileNotFoundError, PermissionError, OSError):
        return None
    if not arguments:
        return None
    try:
        canonical_target = os.readlink(f"/proc/{pid}/exe")
    except (FileNotFoundError, PermissionError, OSError):
        canonical_target = ""
    return {
        "argv0": arguments[0],
        "argv": arguments,
        "canonical_target": canonical_target,
    }


def received_arguments(event: dict[str, object]) -> bool:
    """Report whether an execution was handed the link's arguments.

    A real compiler driver may pass the linker its arguments directly or spill
    them into an `@response` file, so the arguments themselves cannot be
    matched by content. What holds either way is that the process performing
    the link is given something, while the bracketing decoys are given nothing.
    """
    arguments = event.get("argv")
    return isinstance(arguments, list) and len(arguments) > 1


def child_exec(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    stdout_fd: int,
    stderr_fd: int,
) -> None:
    """Enter tracing and replace the forked process with the compiler driver."""
    try:
        os.chdir(cwd)
        os.dup2(stdout_fd, 1)
        os.dup2(stderr_fd, 2)
        os.close(stdout_fd)
        os.close(stderr_fd)
        devnull = os.open(os.devnull, os.O_RDONLY)
        os.dup2(devnull, 0)
        os.close(devnull)
        ptrace(PTRACE_TRACEME, 0)
        os.execve(command[0], command, environment)
    except BaseException as exc:
        try:
            os.write(2, f"child launch failed: {exc}\n".encode())
        finally:
            os._exit(127)


def traced_process(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    scratch: Path,
    label: str,
) -> tuple[int, int, str, str, list[dict[str, object]]]:
    """Run one driver process while observing descendant executable events."""
    stdout_path = scratch / f"{label}.stdout"
    stderr_path = scratch / f"{label}.stderr"
    stdout_fd = os.open(
        stdout_path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    stderr_fd = os.open(
        stderr_path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    started = time.monotonic_ns()
    root_pid = os.fork()
    if root_pid == 0:
        child_exec(
            command,
            cwd=cwd,
            environment=environment,
            stdout_fd=stdout_fd,
            stderr_fd=stderr_fd,
        )
    os.close(stdout_fd)
    os.close(stderr_fd)

    active = {root_pid}
    root_returncode = None
    root_finished_ns = None
    initial_stop = True
    executions: list[dict[str, object]] = []
    try:
        while active:
            try:
                pid, status = os.waitpid(-1, WAIT_ALL)
            except ChildProcessError:
                break
            if os.WIFEXITED(status):
                active.discard(pid)
                if pid == root_pid:
                    root_returncode = os.WEXITSTATUS(status)
                    root_finished_ns = time.monotonic_ns()
                continue
            if os.WIFSIGNALED(status):
                active.discard(pid)
                if pid == root_pid:
                    root_returncode = 128 + os.WTERMSIG(status)
                    root_finished_ns = time.monotonic_ns()
                continue
            if not os.WIFSTOPPED(status):
                continue

            stop_signal = os.WSTOPSIG(status)
            event = status >> 16
            if pid == root_pid and initial_stop:
                ptrace(PTRACE_SETOPTIONS, pid, 0, TRACE_OPTIONS)
                observed = read_exec(pid)
                if observed:
                    executions.append(observed)
                initial_stop = False
            elif event in (PTRACE_EVENT_FORK, PTRACE_EVENT_VFORK):
                active.add(ptrace_event_pid(pid))
            elif event == PTRACE_EVENT_EXEC:
                observed = read_exec(pid)
                if observed:
                    executions.append(observed)

            delivered_signal = 0
            if stop_signal not in (signal.SIGTRAP, signal.SIGSTOP):
                delivered_signal = stop_signal
            try:
                ptrace(PTRACE_CONT, pid, 0, delivered_signal)
            except OSError as exc:
                if exc.errno != errno.ESRCH:
                    raise
    except BaseException:
        for pid in active:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        while True:
            try:
                os.waitpid(-1, WAIT_ALL)
            except ChildProcessError:
                break
        raise

    if root_returncode is None or root_finished_ns is None:
        raise BenchError("compiler-driver trace ended without a root exit status")
    elapsed = root_finished_ns - started
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    return root_returncode, elapsed, stdout, stderr, executions


def run_capture(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    """Run a non-timed probe or version command."""
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            timeout=timeout,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        raise BenchError(f"command timed out: {command!r}") from exc


def validate_order(value: object, label: str) -> list[str]:
    """Validate one supplied linker order."""
    if (
        not isinstance(value, list)
        or len(value) != len(LINKERS)
        or any(not isinstance(item, str) for item in value)
        or sorted(value) != sorted(LINKERS)
    ):
        raise BenchError(f"{label} must name each linker exactly once")
    return value


def load_workload(workload: Path) -> tuple[dict, Path, Path]:
    """Read and validate the public workload fields used by the oracle."""
    if not workload.is_dir():
        raise BenchError(f"workload is not a directory: {workload}")
    try:
        manifest = json.loads(
            (workload / "workload.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchError(f"cannot read workload.json: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise BenchError("unsupported workload manifest")
    workload_id = manifest.get("workload_id")
    if not isinstance(workload_id, str) or not workload_id:
        raise BenchError("workload_id must be a nonempty string")
    driver_value = manifest.get("driver")
    if not isinstance(driver_value, str) or not os.path.isabs(driver_value):
        raise BenchError("driver must be an absolute string")
    driver = Path(driver_value)
    if not driver.is_file() or not os.access(driver, os.X_OK):
        raise BenchError(f"driver is not executable: {driver}")
    response_value = manifest.get("response_file")
    if not isinstance(response_value, str) or not response_value:
        raise BenchError("response_file must be a nonempty string")
    response_relative = Path(response_value)
    if response_relative.is_absolute() or ".." in response_relative.parts:
        raise BenchError("response_file must be a safe relative path")
    response = workload / response_relative
    if not response.is_file():
        raise BenchError(f"response file does not exist: {response}")
    manifest["warmup_order"] = validate_order(
        manifest.get("warmup_order"),
        "warmup_order",
    )
    rounds = manifest.get("timed_rounds")
    if not isinstance(rounds, list) or len(rounds) != 5:
        raise BenchError("timed_rounds must contain five rounds")
    manifest["timed_rounds"] = [
        validate_order(order, f"timed_rounds[{index}]")
        for index, order in enumerate(rounds)
    ]
    probe = manifest.get("probe")
    if not isinstance(probe, dict):
        raise BenchError("probe must be an object")
    argv = probe.get("argv")
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(item, str) for item in argv)
        or "{output}" not in argv
    ):
        raise BenchError("probe.argv must be a string array containing {output}")
    expected_returncode = probe.get("expected_returncode")
    if isinstance(expected_returncode, bool) or not isinstance(
        expected_returncode, int
    ):
        raise BenchError("probe.expected_returncode must be an integer")
    for field in ("expected_stdout", "expected_stderr"):
        if not isinstance(probe.get(field), str):
            raise BenchError(f"probe.{field} must be a string")
    return manifest, driver, response.resolve()


def identify_linker(
    executions: list[dict[str, object]],
    *,
    expected: str,
    workload: Path,
    environment: dict[str, str],
) -> tuple[str, str]:
    """Select and classify the execution that performed this link.

    One link can execute several linker-shaped processes whose versions all
    name the expected family, so neither the first nor the last such event is
    reliable. Only the process handed this link's arguments performed the link.
    """
    linker_events = [
        event
        for event in executions
        if linker_shaped(str(event["argv0"])) and received_arguments(event)
    ]
    matches = []
    for event in linker_events:
        invoked_path = str(event["argv0"])
        if not os.path.isabs(invoked_path):
            continue
        if not os.path.isfile(invoked_path) or not os.access(
            invoked_path,
            os.X_OK,
        ):
            continue
        version_result = run_capture(
            [invoked_path, "--version"],
            cwd=workload,
            environment=environment,
            timeout=20.0,
        )
        if version_result.returncode:
            continue
        version = first_nonempty_line(version_result.stdout)
        if version and family_from_version(version) == expected:
            matches.append((invoked_path, version))
    if len(matches) != 1:
        raise BenchError(
            f"requested {expected}, observed matching linker events: "
            f"{matches!r} from {linker_events!r}"
        )
    return matches[0]


def validate_output(
    output: Path,
    *,
    manifest: dict,
    workload: Path,
    environment: dict[str, str],
) -> None:
    """Require a fresh regular output which passes the workload probe."""
    try:
        mode = output.lstat().st_mode
    except FileNotFoundError as exc:
        raise BenchError(f"link produced no output: {output}") from exc
    if not stat.S_ISREG(mode):
        raise BenchError(f"link output is not regular: {output}")
    command = [
        str(output) if argument == "{output}" else argument
        for argument in manifest["probe"]["argv"]
    ]
    probe = run_capture(
        command,
        cwd=workload,
        environment=environment,
    )
    expected = manifest["probe"]
    actual_values = (probe.returncode, probe.stdout, probe.stderr)
    expected_values = (
        expected["expected_returncode"],
        expected["expected_stdout"],
        expected["expected_stderr"],
    )
    if actual_values != expected_values:
        raise BenchError(
            f"semantic probe mismatch: got {actual_values!r}, "
            f"expected {expected_values!r}"
        )


def execute_link(
    linker: str,
    *,
    invocation_index: int,
    output: Path,
    manifest: dict,
    driver: Path,
    response: Path,
    workload: Path,
    environment: dict[str, str],
    scratch: Path,
) -> tuple[int, str, str]:
    """Execute, identify and validate one compiler-driver link."""
    output.unlink(missing_ok=True)
    command = [
        str(driver),
        *SELECTOR_ARGS[linker],
        *THREAD_ARGS[linker],
        f"@{response}",
        "-o",
        str(output),
    ]
    returncode, elapsed, stdout, stderr, executions = traced_process(
        command,
        cwd=workload,
        environment=environment,
        scratch=scratch,
        label=f"{invocation_index:02d}-{linker}",
    )
    if returncode:
        raise BenchError(
            f"{linker} link failed ({returncode})\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        )
    if "ignoring --threads" in stderr.lower():
        raise BenchError(f"{linker} ignored its thread controls")
    invoked_path, version = identify_linker(
        executions,
        expected=linker,
        workload=workload,
        environment=environment,
    )
    validate_output(
        output,
        manifest=manifest,
        workload=workload,
        environment=environment,
    )
    if elapsed <= 0:
        raise BenchError(f"{linker} produced a nonpositive duration")
    return elapsed, invoked_path, version


def benchmark(workload: Path, report: Path) -> None:
    """Run the frozen protocol and write its exact successful report."""
    report.unlink(missing_ok=True)
    workload = workload.resolve()
    manifest, driver, response = load_workload(workload)

    with tempfile.TemporaryDirectory(prefix="linkbench-") as temp:
        scratch = Path(temp)
        temp_files = scratch / "tmp"
        temp_files.mkdir()
        environment = os.environ.copy()
        environment.update(
            {
                "TMPDIR": str(temp_files),
                "TMP": str(temp_files),
                "TEMP": str(temp_files),
                "LC_ALL": "C",
                "LANG": "C",
            }
        )
        outputs = {
            linker: scratch / f"output-{linker}" for linker in LINKERS
        }
        samples = {linker: [] for linker in LINKERS}
        identities: dict[str, tuple[str, str]] = {}
        invocation_index = 0

        def invoke(linker: str, measured: bool) -> None:
            nonlocal invocation_index
            invocation_index += 1
            elapsed, invoked_path, version = execute_link(
                linker,
                invocation_index=invocation_index,
                output=outputs[linker],
                manifest=manifest,
                driver=driver,
                response=response,
                workload=workload,
                environment=environment,
                scratch=scratch,
            )
            identity = (invoked_path, version)
            previous = identities.setdefault(linker, identity)
            if previous != identity:
                raise BenchError(
                    f"{linker} identity changed from {previous!r} "
                    f"to {identity!r}"
                )
            if measured:
                samples[linker].append(elapsed)

        for linker in manifest["warmup_order"]:
            invoke(linker, False)
        for order in manifest["timed_rounds"]:
            for linker in order:
                invoke(linker, True)

    medians = {
        linker: sorted(values)[2] for linker, values in samples.items()
    }
    results = []
    for linker in LINKERS:
        invoked_path, version = identities[linker]
        results.append(
            {
                "linker": linker,
                "invoked_path": invoked_path,
                "version": version,
                "effective_threads": EFFECTIVE_THREADS[linker],
                "samples_ns": samples[linker],
                "median_ns": medians[linker],
            }
        )
    ranking = sorted(
        LINKERS,
        key=lambda linker: (medians[linker], TIE_BREAK[linker]),
    )
    successful_report = {
        "schema_version": 1,
        "workload_id": manifest["workload_id"],
        "results": results,
        "ranking": ranking,
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    temporary_report = report.with_name(f".{report.name}.{os.getpid()}.tmp")
    try:
        temporary_report.write_text(
            json.dumps(successful_report, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_report, report)
    finally:
        temporary_report.unlink(missing_ok=True)


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: /app/linkbench <workload-directory> <report-json>",
            file=sys.stderr,
        )
        return 2
    workload = Path(sys.argv[1])
    report = Path(sys.argv[2])
    try:
        benchmark(workload, report)
    except (BenchError, OSError, ValueError, KeyError, TypeError) as exc:
        report.unlink(missing_ok=True)
        print(f"linkbench: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
