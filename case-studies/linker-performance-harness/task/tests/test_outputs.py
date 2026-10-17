"""Behavioral checks for the isolated linkbench artifact."""

# binary-reward-ok: this anti-cheat probe names reward paths only to prove an unprivileged daemon cannot modify them

import hashlib
import json
import os
import shutil
import stat
import tempfile
import time
from pathlib import Path

from process_hygiene import run_isolated


ARTIFACT = Path("/app/linkbench")
LINKERS = ("bfd", "gold", "lld", "mold")
THREAD_ARGS = {
    "bfd": [],
    "gold": ["-Wl,--threads", "-Wl,--thread-count=2"],
    "lld": ["-Wl,--threads=2"],
    "mold": ["-Wl,--threads=2", "-Wl,--no-fork"],
}
RESULT_KEYS = {
    "linker",
    "invoked_path",
    "version",
    "effective_threads",
    "samples_ns",
    "median_ns",
}

def directory_digest(root):
    """Hash names, modes and contents for one verifier-owned workload."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root)).encode("utf-8")
        status = path.lstat()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(status.st_mode.to_bytes(4, "big"))
        if path.is_file():
            data = path.read_bytes()
            digest.update(len(data).to_bytes(8, "big"))
            digest.update(data)
    return digest.hexdigest()


def linker_family(version):
    """Classify the first version line of the four native linker families."""
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


def reference_link_times(workload, manifest):
    """Time warmed reference links per linker for magnitude checks.

    A submitted harness runs these same driver commands six times each, so
    warmed references provide rough magnitude and wall-time bounds for a
    truthful run. Ranking is checked against the submitted medians rather
    than independently measured reference timings, which may vary.
    """
    response = workload / manifest["response_file"]
    references = {}
    with tempfile.TemporaryDirectory(prefix="native-reference-") as raw:
        scratch = Path(raw)
        for linker in LINKERS:
            timings = []
            for attempt in range(4):
                output = scratch / f"reference-{linker}-{attempt}"
                started = time.monotonic_ns()
                result = run_isolated(
                    [
                        "/usr/bin/gcc",
                        f"-fuse-ld={linker}",
                        *THREAD_ARGS[linker],
                        f"@{response}",
                        "-o",
                        str(output),
                    ],
                    cwd=workload,
                    env={
                        "HOME": str(scratch),
                        "LANG": "C",
                        "LC_ALL": "C",
                        "PATH": "/usr/bin:/bin",
                        "TMPDIR": str(scratch),
                    },
                    timeout=300,
                )
                elapsed = time.monotonic_ns() - started
                assert result.returncode == 0, result.stderr
                output.unlink()
                if attempt:
                    timings.append(elapsed)
            references[linker] = sorted(timings)[1]
    return references


def test_artifact_is_self_contained_executable():
    """The collected deliverable is one executable regular file at most 1 MiB."""
    mode = ARTIFACT.stat().st_mode
    assert stat.S_ISREG(mode)
    assert os.access(ARTIFACT, os.X_OK)
    assert ARTIFACT.stat().st_size <= 1_048_576


def test_tracing_runtime_works_for_ordinary_user():
    """Stock Python and strace can run under the artifact's restrictions."""
    assert shutil.which("strace") == "/usr/bin/strace"
    with tempfile.TemporaryDirectory(prefix="strace-capability-") as raw:
        run_dir = Path(raw)
        os.chmod(run_dir, 0o700)
        os.chown(run_dir, 1001, 1001)
        trace = run_dir / "trace.log"
        python_result = run_isolated(
            [
                "setpriv",
                "--reuid=1001",
                "--regid=1001",
                "--clear-groups",
                "--no-new-privs",
                "/usr/bin/python3",
                "-c",
                "raise SystemExit(0)",
            ],
            cwd=run_dir,
            env={
                "HOME": str(run_dir),
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
                "TMPDIR": str(run_dir),
            },
            timeout=10,
            reap_uid=1001,
        )
        assert python_result.returncode == 0, python_result.stderr
        result = run_isolated(
            [
                "setpriv",
                "--reuid=1001",
                "--regid=1001",
                "--clear-groups",
                "--no-new-privs",
                "/usr/bin/strace",
                "-f",
                "-e",
                "trace=execve",
                "-o",
                str(trace),
                "/bin/true",
            ],
            cwd=run_dir,
            env={
                "HOME": str(run_dir),
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
                "TMPDIR": str(run_dir),
            },
            timeout=10,
            reap_uid=1001,
        )
        assert result.returncode == 0, result.stderr
        assert 'execve("/bin/true"' in trace.read_text(encoding="utf-8")


def test_hidden_native_workload():
    """Exercise report compatibility and correctness on the real toolchain."""
    workload = Path("/opt/workloads/native")
    manifest = json.loads((workload / "workload.json").read_text())
    before_digest = directory_digest(workload)
    references = reference_link_times(workload, manifest)
    # Attribute any workload mutation to the submission rather than to the
    # verifier's own reference links.
    assert directory_digest(workload) == before_digest
    with tempfile.TemporaryDirectory(prefix="native-linkbench-") as raw:
        run_dir = Path(raw)
        os.chmod(run_dir, 0o700)
        os.chown(run_dir, 1001, 1001)
        report = run_dir / "report.json"
        report.write_text('{"stale":true}\n')
        os.chown(report, 1001, 1001)
        started = time.monotonic_ns()
        result = run_isolated(
            [
                "setpriv",
                "--reuid=1001",
                "--regid=1001",
                "--clear-groups",
                "--no-new-privs",
                str(ARTIFACT),
                str(workload),
                str(report),
            ],
            cwd=run_dir,
            env={
                "HOME": str(run_dir),
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
                "TMPDIR": str(run_dir),
            },
            timeout=300,
            reap_uid=1001,
        )
        elapsed_ns = time.monotonic_ns() - started
        assert result.returncode == 0, result.stderr
        parsed = json.loads(report.read_text())
    assert directory_digest(workload) == before_digest
    assert set(parsed) == {
        "schema_version",
        "workload_id",
        "results",
        "ranking",
    }
    assert type(parsed["schema_version"]) is int
    assert parsed["schema_version"] == 1
    assert parsed["workload_id"] == manifest["workload_id"]
    assert len(parsed["results"]) == 4
    by_linker = {}
    invoked_paths = set()
    versions = set()
    for item in parsed["results"]:
        assert set(item) == RESULT_KEYS
        linker = item["linker"]
        assert linker in LINKERS and linker not in by_linker
        invoked = Path(item["invoked_path"])
        assert invoked.is_absolute() and os.access(invoked, os.X_OK)
        version = run_isolated(
            [
                "setpriv",
                "--reuid=1001",
                "--regid=1001",
                "--clear-groups",
                "--no-new-privs",
                str(invoked),
                "--version",
            ],
            cwd="/tmp",
            env={
                "HOME": "/tmp",
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
                "TMPDIR": "/tmp",
            },
            timeout=10,
            reap_uid=1001,
        )
        assert version.returncode == 0
        first = next(line for line in version.stdout.splitlines() if line)
        assert item["version"] == first
        assert linker_family(first) == linker
        invoked_paths.add(str(invoked))
        versions.add(first)
        assert type(item["effective_threads"]) is int
        assert item["effective_threads"] == (1 if linker == "bfd" else 2)
        samples = item["samples_ns"]
        assert (
            isinstance(samples, list)
            and len(samples) == 5
            and all(type(value) is int and value > 0 for value in samples)
        )
        assert type(item["median_ns"]) is int
        assert item["median_ns"] == sorted(samples)[2]
        by_linker[linker] = item
    assert len(invoked_paths) == len(LINKERS)
    assert len(versions) == len(LINKERS)
    ranking = parsed["ranking"]
    assert (
        isinstance(ranking, list)
        and len(ranking) == len(LINKERS)
        and set(ranking) == set(LINKERS)
    )
    ranked_medians = [by_linker[linker]["median_ns"] for linker in ranking]
    assert ranked_medians == sorted(ranked_medians)
    reported_ns = sum(
        sample for item in parsed["results"] for sample in item["samples_ns"]
    )
    # Reported link time cannot exceed the wall time of the run that produced
    # it, so samples cannot be inflated to reach the floors below.
    assert reported_ns <= elapsed_ns
    # A truthful run links every linker six times, so it cannot finish in the
    # time a fabricated report takes to print.
    assert elapsed_ns >= 4 * sum(references.values())
    # Samples must be real durations for this workload and this linker rather
    # than invented units or placeholder counters.
    for linker in LINKERS:
        median = by_linker[linker]["median_ns"]
        assert median <= 20 * references[linker], linker
        assert 10 * median >= references[linker], linker


def test_authenticated_controlled_protocol():
    """Signed controlled runs enforce order, identity, timing, probes and failure cleanup."""
    tool_dir = Path("/opt/control/bin")
    for name in (
        "ld.bfd",
        "ld.bfd-alt",
        "ld.gold",
        "ld.gold-alt",
        "ld.gold-helper",
        "ld.gold-spoof",
        "ld.lld",
        "ld.lld-alt",
        "ld.lld2",
        "ld.mold",
        "ld.mold-alt",
    ):
        invoked_path = tool_dir / name
        assert invoked_path.is_symlink()
        assert invoked_path.resolve() != invoked_path
    result = run_isolated(
        [
            "python3",
            "/tests/verify_submission.py",
            "--artifact",
            str(ARTIFACT),
            "--workload",
            "/opt/workloads/controlled",
            "--tool-dir",
            str(tool_dir),
            "--observer",
            "/tests/observer.py",
        ],
        cwd="/tmp",
        env={
            "HOME": "/tmp",
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/opt/verifier-venv/bin:/usr/bin:/bin",
            "TMPDIR": "/tmp",
        },
        timeout=120,
        reap_uid=1001,
    )
    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_reward_channel_rejects_daemonized_untrusted_code():
    """A double-forked unprivileged cheat cannot replace either reward file.

    Harbor creates /logs/verifier 0777 and this suite runs the agent's artifact
    as uid 1001, so the reward files are only as safe as the directory holding
    them: unlink() is gated on the directory, not on the root-owned 0644 file.
    tests/test.sh closes the directory before writing the first reward, and the
    daemon below tries every vector that mode would otherwise open.
    """
    verifier_dir = Path("/logs/verifier")
    reward_txt = verifier_dir / "reward.txt"
    reward_json = verifier_dir / "reward.json"
    mode = verifier_dir.stat().st_mode
    assert not mode & stat.S_IWGRP, oct(mode)
    assert not mode & stat.S_IWOTH, oct(mode)
    assert reward_txt.read_text().strip() == "0"
    assert json.loads(reward_json.read_text()) == {"reward": 0}
    with tempfile.TemporaryDirectory(prefix="reward-cheat-") as raw:
        root = Path(raw)
        os.chmod(root, 0o755)
        cheat = root / "cheat.py"
        cheat.write_text(
            """#!/usr/bin/python3
import os
import time

read_fd, write_fd = os.pipe()
if os.fork():
    os.close(write_fd)
    os.read(read_fd, 1)
    raise SystemExit(1)
os.close(read_fd)
os.setsid()
if os.fork():
    os.write(write_fd, b"1")
    os.close(write_fd)
    os._exit(0)
os.close(write_fd)
time.sleep(0.1)
for path, content in (
    ("/logs/verifier/reward.txt", "1\\n"),
    ("/logs/verifier/reward.json", '{"reward": 1}\\n'),
):
    # Truncate in place. Refused by a root-owned 0644 file whatever the
    # directory mode, so on its own this vector proves the least.
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
    except OSError:
        pass
    # Unlink and recreate. Gated on write permission for the directory rather
    # than for the file, so this is what a 0777 /logs/verifier would allow.
    try:
        os.unlink(path)
    except OSError:
        pass
    try:
        with open(path, "x", encoding="utf-8") as handle:
            handle.write(content)
    except OSError:
        pass
    # Atomic swap from a decoy this uid owns outright.
    try:
        decoy = path + ".cheat"
        with open(decoy, "x", encoding="utf-8") as handle:
            handle.write(content)
        os.rename(decoy, path)
    except OSError:
        pass
# A directory write naming no reward file, which separates "the rewards
# survived" from "the directory is closed to this uid".
try:
    with open("/logs/verifier/cheat-probe", "x", encoding="utf-8") as handle:
        handle.write("1\\n")
except OSError:
    pass
""",
            encoding="utf-8",
        )
        os.chmod(cheat, 0o755)
        result = run_isolated(
            [
                "setpriv",
                "--reuid=1001",
                "--regid=1001",
                "--clear-groups",
                "--no-new-privs",
                str(cheat),
            ],
            cwd="/tmp",
            env={
                "HOME": "/tmp",
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
                "TMPDIR": "/tmp",
            },
            timeout=5,
            reap_uid=1001,
        )
        assert result.returncode != 0
        time.sleep(0.2)
    assert reward_txt.read_text().strip() == "0"
    assert json.loads(reward_json.read_text()) == {"reward": 0}
    assert reward_txt.stat().st_uid == 0
    assert reward_json.stat().st_uid == 0
    assert not (verifier_dir / "cheat-probe").exists()
    assert not (verifier_dir / "reward.txt.cheat").exists()
    assert not (verifier_dir / "reward.json.cheat").exists()
