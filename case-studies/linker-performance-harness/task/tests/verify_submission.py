#!/usr/bin/env python3
"""Run a submitted harness through authenticated controlled scenarios."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from pathlib import Path

from process_hygiene import run_isolated


LINKERS = ("bfd", "gold", "lld", "mold")
THREAD_MASKS = {"bfd": 0, "gold": 3, "lld": 4, "mold": 12}
TOP_KEYS = {"schema_version", "workload_id", "results", "ranking"}
RESULT_KEYS = {
    "linker",
    "invoked_path",
    "version",
    "effective_threads",
    "samples_ns",
    "median_ns",
}
VERSIONS = {
    "bfd": "GNU ld controlled 1.0",
    "gold": "GNU gold controlled 1.0",
    "lld": "LLD controlled 1.0",
    "mold": "mold controlled 1.0",
}
FAULT_INDEX = {
    "identity_mismatch": 1,
    "identity_mismatch_timed": 9,
    "identity_path_change": 13,
    "identity_family_spoof": 0,
    "identity_family_change": 13,
    "late_failure": 21,
    "no_output": 5,
    "corrupt_output": 5,
    "non_regular_output": 5,
    "probe_failure": 5,
    "probe_stdout_mismatch": 5,
    "probe_stderr_mismatch": 5,
}
FAULT_ACTION = {
    "late_failure": "fail",
    "no_output": "no_output",
    "corrupt_output": "corrupt",
    "non_regular_output": "non_regular",
    "probe_failure": "probe_fail",
}
ALL_SCENARIOS = (
    "success",
    "identity_mismatch",
    "identity_mismatch_timed",
    "identity_path_change",
    "identity_family_spoof",
    "identity_family_change",
    "late_failure",
    "no_output",
    "corrupt_output",
    "non_regular_output",
    "probe_failure",
    "probe_stdout_mismatch",
    "probe_stderr_mismatch",
)


class VerificationError(RuntimeError):
    pass


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def signed_records(evidence, secret):
    key = secret.read_bytes()
    records = []
    for line_number, line in enumerate(evidence.read_text().splitlines(), 1):
        envelope = json.loads(line)
        record = envelope["record"]
        canonical = json.dumps(
            record, sort_keys=True, separators=(",", ":")
        ).encode()
        expected = hmac.new(key, canonical, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, envelope["signature"]):
            raise VerificationError("observer evidence signature is invalid")
        if record.get("sequence") != line_number:
            raise VerificationError("observer evidence sequence is invalid")
        records.append(record)
    if not records:
        raise VerificationError("observer produced no evidence")
    return records


def events(records, name):
    return [record for record in records if record.get("event") == name]


def schedule(manifest):
    return [
        *manifest["warmup_order"],
        *[
            linker
            for order in manifest["timed_rounds"]
            for linker in order
        ],
    ]


def validate_report(report, manifest, tool_dir):
    if not isinstance(report, dict) or set(report) != TOP_KEYS:
        raise VerificationError("incorrect report keys")
    if not integer(report["schema_version"]) or report["schema_version"] != 1:
        raise VerificationError("incorrect schema_version")
    if report["workload_id"] != manifest["workload_id"]:
        raise VerificationError("incorrect workload_id")
    if not isinstance(report["results"], list) or len(report["results"]) != 4:
        raise VerificationError("incorrect result count")
    by_linker = {}
    for result in report["results"]:
        if not isinstance(result, dict) or set(result) != RESULT_KEYS:
            raise VerificationError("incorrect result keys")
        linker = result["linker"]
        if linker not in LINKERS or linker in by_linker:
            raise VerificationError("invalid or duplicate linker result")
        expected_path = tool_dir / ".." / "bin" / f"ld.{linker}"
        if result["invoked_path"] != str(expected_path):
            raise VerificationError(f"{linker} invoked_path is incorrect")
        if result["version"] != VERSIONS[linker]:
            raise VerificationError(f"{linker} version is incorrect")
        expected_threads = 1 if linker == "bfd" else 2
        if (
            not integer(result["effective_threads"])
            or result["effective_threads"] != expected_threads
        ):
            raise VerificationError(f"{linker} effective_threads is incorrect")
        samples = result["samples_ns"]
        if (
            not isinstance(samples, list)
            or len(samples) != 5
            or any(not integer(sample) or sample <= 0 for sample in samples)
        ):
            raise VerificationError(f"{linker} samples are invalid")
        if (
            not integer(result["median_ns"])
            or result["median_ns"] != sorted(samples)[2]
        ):
            raise VerificationError(f"{linker} median is incorrect")
        by_linker[linker] = result
    ranking = report["ranking"]
    if (
        not isinstance(ranking, list)
        or len(ranking) != len(LINKERS)
        or set(ranking) != set(LINKERS)
    ):
        raise VerificationError("ranking is not a linker permutation")
    ranked_medians = [
        by_linker[linker]["median_ns"] for linker in ranking
    ]
    if ranked_medians != sorted(ranked_medians):
        raise VerificationError("ranking is not ordered by median")
    return by_linker, ranking


def validate_success(records, manifest, by_linker, ranking, run_uid):
    if events(records, "violation"):
        raise VerificationError("observer recorded a protocol violation")
    sequence = schedule(manifest)
    routes = events(records, "route")
    starts = events(records, "link_start")
    completions = events(records, "link_done")
    probes = events(records, "probe")
    versions = events(records, "version")
    if any(len(group) != 24 for group in (routes, starts, completions, probes)):
        raise VerificationError("success did not complete 24 links and probes")
    starts = {record["index"]: record for record in starts}
    completions = {record["index"]: record for record in completions}
    probes = {record["index"]: record for record in probes}
    durations = {linker: [] for linker in LINKERS}
    for index, linker in enumerate(sequence):
        route = routes[index]
        start = starts.get(index)
        done = completions.get(index)
        probe = probes.get(index)
        if (
            route["requested"] != linker
            or route["actual"] != linker
            or not start
            or start["requested"] != linker
            or start["actual"] != linker
            or start["thread_mask"] != THREAD_MASKS[linker]
            or start["output_preexisting"] != 0
            or start["unexpected_thread_control"] != 0
            or start["uid"] != run_uid
            or start["action"] != "success"
            or not done
            or done["nonce"] != start["nonce"]
            or not probe
            or probe["nonce"] != start["nonce"]
            or probe["uid"] != run_uid
            or probe["returncode"] != manifest["probe"]["expected_returncode"]
            or probe["stdout"] != manifest["probe"]["expected_stdout"]
            or probe["stderr"] != manifest["probe"]["expected_stderr"]
        ):
            raise VerificationError(f"invalid evidence at invocation {index}")
        # The version request must come from the real linker for this link,
        # after it starts and before the next scheduled driver invocation.
        next_route_ns = routes[index + 1]["server_ns"] if index + 1 < len(sequence) else float("inf")
        if not any(
            version["index"] == index
            and version["uid"] == run_uid
            and version["linker"] == linker
            and version["family"] == linker
            and start["server_ns"] < version["server_ns"] < next_route_ns
            for version in versions
        ):
            raise VerificationError(f"missing or incorrect --version probe at invocation {index}")
        if index >= 4:
            durations[linker].append(done["server_ns"] - start["server_ns"])
    for linker in LINKERS:
        samples = by_linker[linker]["samples_ns"]
        for sample, observed in zip(samples, durations[linker]):
            if sample + 2_000_000 < observed:
                raise VerificationError(f"{linker} sample is too short")
            if sample - observed > 200_000_000:
                raise VerificationError(f"{linker} sample is not correlated")
    observed_medians = {
        linker: sorted(values)[2] for linker, values in durations.items()
    }
    observed_ranking = sorted(
        LINKERS,
        key=lambda linker: observed_medians[linker],
    )
    if ranking != observed_ranking:
        raise VerificationError(
            "ranking does not match observer timing evidence"
        )
    stops = events(records, "observer_stop")
    if len(stops) != 1:
        raise VerificationError("observer did not stop cleanly")
    state = stops[0]["state"]
    if state["next_index"] != 24 or state["probe_invocations"] != 24:
        raise VerificationError("observer ended with incomplete state")


def validate_fault(records, scenario, run_uid, manifest):
    at_fault = [
        record
        for record in events(records, "link_start")
        if record["index"] == FAULT_INDEX[scenario]
    ]
    if len(at_fault) != 1 or at_fault[0]["uid"] != run_uid:
        raise VerificationError(f"{scenario} did not reach its fault")
    if scenario in (
        "identity_mismatch",
        "identity_mismatch_timed",
        "identity_path_change",
        "identity_family_spoof",
    ):
        if at_fault[0]["requested"] == at_fault[0]["actual"]:
            raise VerificationError("identity mismatch was not injected")
    elif scenario == "identity_family_change":
        # The family behind the LLD path only changes once the fault link has
        # completed, so any such record is evidence the harness re-probed and
        # saw it. Pinning the index instead would reject a harness that probes
        # on a different but equally valid cadence.
        changed_versions = [
            record
            for record in events(records, "version")
            if record["index"] >= FAULT_INDEX[scenario]
            and record["linker"] == "lld"
            and record["family"] == "bfd"
        ]
        if not changed_versions:
            raise VerificationError("family change was not observed")
    elif scenario in ("probe_stdout_mismatch", "probe_stderr_mismatch"):
        injected = [
            record for record in events(records, "probe")
            if record["index"] == FAULT_INDEX[scenario]
            and record["uid"] == run_uid
        ]
        field = "stdout" if scenario == "probe_stdout_mismatch" else "stderr"
        if (
            len(injected) != 1
            or injected[0]["returncode"] != manifest["probe"]["expected_returncode"]
            or injected[0][field] == manifest["probe"][f"expected_{field}"]
        ):
            raise VerificationError(f"{scenario} did not inject its output mismatch")
    elif at_fault[0]["action"] != FAULT_ACTION[scenario]:
        raise VerificationError(f"{scenario} action was not injected")
    if events(records, "violation"):
        raise VerificationError(f"{scenario} caused a protocol violation")


def wait_for_socket(path, observer):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if path.exists():
            return
        if observer.poll() is not None:
            break
        time.sleep(0.01)
    raise VerificationError("observer did not create its socket")


def run_scenario(args, scenario):
    with tempfile.TemporaryDirectory(prefix=f"linkbench-{scenario}-") as raw:
        root = Path(raw)
        os.chmod(root, 0o755)
        run_dir = root / "run"
        run_dir.mkdir()
        os.chown(run_dir, args.run_uid, args.run_gid)
        artifact = root / "submission"
        shutil.copy2(args.artifact, artifact)
        os.chmod(artifact, 0o755)
        report = run_dir / "report.json"
        report.write_text('{"stale":true}\n')
        os.chown(report, args.run_uid, args.run_gid)
        control_dir = Path("/run/linkbench-control")
        shutil.rmtree(control_dir, ignore_errors=True)
        control_dir.mkdir(mode=0o711)
        socket_path = control_dir / "observer.sock"
        evidence = root / "evidence.jsonl"
        secret = root / "secret"
        observer_err = root / "observer.stderr"
        with observer_err.open("w") as error_handle:
            observer = subprocess.Popen(
                [
                    "python3",
                    str(args.observer),
                    "--scenario",
                    scenario,
                    "--workload",
                    str(args.workload),
                    "--tool-dir",
                    str(args.tool_dir),
                    "--socket",
                    str(socket_path),
                    "--evidence",
                    str(evidence),
                    "--secret",
                    str(secret),
                    "--report",
                    str(report),
                ],
                stdout=subprocess.DEVNULL,
                stderr=error_handle,
            )
            wait_for_socket(socket_path, observer)
            environment = {
                "HOME": str(run_dir),
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": f"{args.tool_dir}:/usr/bin:/bin",
                "TMPDIR": str(run_dir),
            }
            try:
                harness = run_isolated(
                    [
                        "setpriv",
                        f"--reuid={args.run_uid}",
                        f"--regid={args.run_gid}",
                        "--clear-groups",
                        "--no-new-privs",
                        str(artifact),
                        str(args.workload),
                        str(report),
                    ],
                    cwd=run_dir,
                    env=environment,
                    timeout=30,
                    reap_uid=args.run_uid,
                )
            finally:
                observer.send_signal(signal.SIGTERM)
                observer.wait(timeout=5)
        if observer.returncode:
            raise VerificationError(observer_err.read_text())
        records = signed_records(evidence, secret)
        manifest = json.loads((args.workload / "workload.json").read_text())
        if scenario == "success":
            if harness.returncode:
                raise VerificationError(
                    f"success exited {harness.returncode}: {harness.stderr}"
                )
            by_linker, ranking = validate_report(
                json.loads(report.read_text()),
                manifest,
                args.tool_dir,
            )
            validate_success(
                records,
                manifest,
                by_linker,
                ranking,
                args.run_uid,
            )
        else:
            if harness.returncode == 0:
                raise VerificationError(f"{scenario} exited zero")
            if report.exists():
                raise VerificationError(f"{scenario} left a report")
            validate_fault(records, scenario, args.run_uid, manifest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--workload", type=Path, required=True)
    parser.add_argument("--tool-dir", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--run-uid", type=int, default=1001)
    parser.add_argument("--run-gid", type=int, default=1001)
    args = parser.parse_args()
    args.artifact = args.artifact.resolve()
    args.workload = args.workload.resolve()
    args.tool_dir = args.tool_dir.resolve()
    args.observer = args.observer.resolve()
    mode = args.artifact.stat().st_mode
    if (
        not stat.S_ISREG(mode)
        or not os.access(args.artifact, os.X_OK)
        or args.artifact.stat().st_size > 1_048_576
    ):
        raise SystemExit("artifact must be executable, regular, and at most 1 MiB")
    for scenario in ALL_SCENARIOS:
        run_scenario(args, scenario)
    print(f"accepted: {args.artifact} passed {len(ALL_SCENARIOS)} scenarios")


if __name__ == "__main__":
    main()
