#!/usr/bin/env python3
"""Benchmark four installed ELF linkers over one captured final link."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path


LINKERS = ("bfd", "gold", "lld", "mold")
PROGRAM_NAMES = {
    "bfd": "ld.bfd",
    "gold": "ld.gold",
    "lld": "ld.lld",
    "mold": "ld.mold",
}
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
_cached_selection = None


class HarnessError(RuntimeError):
    """The starter harness could not complete its comparison."""


def log(message: str) -> None:
    print(f"linkbench: {message}", file=sys.stderr)


def first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line
    return ""


def run(command, *, cwd, environment, timeout=120.0):
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
        raise HarnessError(f"command timed out: {command!r}") from exc


def validate_order(value, label):
    if (
        not isinstance(value, list)
        or len(value) != 4
        or sorted(value) != sorted(LINKERS)
    ):
        raise HarnessError(f"{label} must contain the four linker IDs")
    return value


def load_workload(workload):
    try:
        manifest = json.loads(
            (workload / "workload.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessError(f"cannot read workload: {exc}") from exc
    if manifest.get("schema_version") != 1:
        raise HarnessError("unsupported workload schema")
    if not isinstance(manifest.get("workload_id"), str):
        raise HarnessError("workload_id is missing")
    validate_order(manifest.get("warmup_order"), "warmup_order")
    rounds = manifest.get("timed_rounds")
    if not isinstance(rounds, list) or len(rounds) != 5:
        raise HarnessError("timed_rounds must contain five rounds")
    for index, order in enumerate(rounds):
        validate_order(order, f"timed_rounds[{index}]")
    response_value = manifest.get("response_file")
    if not isinstance(response_value, str):
        raise HarnessError("response_file is missing")
    response = workload / response_value
    if not response.is_file():
        raise HarnessError(f"response file does not exist: {response}")
    return manifest, response.resolve()


def discover_tools(workload, environment):
    discovered = {}
    for linker in LINKERS:
        selected = shutil.which(PROGRAM_NAMES[linker])
        if not selected:
            raise HarnessError(f"{PROGRAM_NAMES[linker]} is not installed")
        invoked_path = str(Path(selected).absolute())
        version_result = run(
            [invoked_path, "--version"],
            cwd=workload,
            environment=environment,
            timeout=20.0,
        )
        if version_result.returncode:
            raise HarnessError(
                f"{invoked_path} --version failed: {version_result.stderr}"
            )
        version = first_nonempty_line(version_result.stdout)
        if not version:
            raise HarnessError(f"{invoked_path} has no version output")
        discovered[linker] = {
            "invoked_path": invoked_path,
            "canonical_target": str(Path(invoked_path).resolve()),
            "version": version,
        }
        log(
            f"selected {linker}: {invoked_path} "
            f"({discovered[linker]['canonical_target']})"
        )
    return discovered


def driver_command(manifest, response, linker, output):
    global _cached_selection
    requested_arguments = [
        *SELECTOR_ARGS[linker],
        *THREAD_ARGS[linker],
    ]
    log(
        f"requesting {linker} with "
        f"{' '.join(requested_arguments) if requested_arguments else '(defaults)'}"
    )
    if _cached_selection is None:
        _cached_selection = requested_arguments
    command = [
        manifest["driver"],
        *_cached_selection,
        f"@{response}",
        "-o",
        str(output),
    ]
    return command


def probe_output(output, manifest, *, workload, environment):
    try:
        mode = output.stat().st_mode
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(mode):
        return False
    probe_command = [
        str(output) if argument == "{output}" else argument
        for argument in manifest["probe"]["argv"]
    ]
    result = run(
        probe_command,
        cwd=workload,
        environment=environment,
        timeout=30.0,
    )
    return result.returncode == manifest["probe"]["expected_returncode"]


def execute_link(
    manifest,
    response,
    linker,
    output,
    *,
    workload,
    environment,
):
    command = driver_command(manifest, response, linker, output)
    started = time.time_ns()
    result = run(
        command,
        cwd=workload,
        environment=environment,
    )
    elapsed = time.time_ns() - started
    if result.returncode:
        if output.exists():
            log(
                f"{linker} exited {result.returncode}; "
                "keeping the existing output for comparison"
            )
        else:
            raise HarnessError(
                f"{linker} failed before producing output: {result.stderr}"
            )
    if not probe_output(
        output,
        manifest,
        workload=workload,
        environment=environment,
    ):
        raise HarnessError(f"{linker} output failed its smoke test")
    if elapsed <= 0:
        elapsed = 1
    return elapsed


def benchmark(workload, report_path):
    workload = workload.resolve()
    manifest, response = load_workload(workload)
    with tempfile.TemporaryDirectory(prefix="linkbench-starter-") as temp:
        scratch = Path(temp)
        temporary_files = scratch / "tmp"
        temporary_files.mkdir()
        environment = os.environ.copy()
        environment.update(
            {
                "TMPDIR": str(temporary_files),
                "TMP": str(temporary_files),
                "TEMP": str(temporary_files),
                "LC_ALL": "C",
                "LANG": "C",
            }
        )
        discovered = discover_tools(workload, environment)
        outputs = {
            linker: scratch / f"benchmark-output-{linker}"
            for linker in LINKERS
        }
        samples = {linker: [] for linker in LINKERS}
        for linker in LINKERS:
            log(f"warming {linker}")
            execute_link(
                manifest,
                response,
                linker,
                outputs[linker],
                workload=workload,
                environment=environment,
            )
            for repetition in range(5):
                log(f"measuring {linker} repetition {repetition + 1}/5")
                samples[linker].append(
                    execute_link(
                        manifest,
                        response,
                        linker,
                        outputs[linker],
                        workload=workload,
                        environment=environment,
                    )
                )
    medians = {
        linker: sorted(values)[2] for linker, values in samples.items()
    }
    results = []
    for linker in LINKERS:
        results.append(
            {
                "linker": linker,
                "invoked_path": discovered[linker]["invoked_path"],
                "version": discovered[linker]["version"],
                "effective_threads": EFFECTIVE_THREADS[linker],
                "samples_ns": samples[linker],
                "median_ns": medians[linker],
            }
        )
    ranking = sorted(LINKERS, key=lambda linker: (medians[linker], linker))
    report = {
        "schema_version": 1,
        "workload_id": manifest["workload_id"],
        "results": results,
        "ranking": ranking,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    log(f"wrote report to {report_path}")


def main():
    if len(sys.argv) != 3:
        print(
            "usage: /app/linkbench <workload-directory> <report-json>",
            file=sys.stderr,
        )
        return 2
    try:
        benchmark(Path(sys.argv[1]), Path(sys.argv[2]))
    except (HarnessError, OSError, KeyError, TypeError, ValueError) as exc:
        log(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
