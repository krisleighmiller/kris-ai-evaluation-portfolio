#!/usr/bin/env python3
"""Run linkbench directly and expose raw controlled-workload evidence."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> int:
    lab = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="linkbench-audit-") as raw_temp:
        temp = Path(raw_temp)
        workload = temp / "workload"
        shutil.copytree(lab / "workload", workload)
        event_log = temp / "events.jsonl"
        event_log.touch(mode=0o600)
        (workload / "link.rsp").write_text(
            str(event_log) + "\n",
            encoding="utf-8",
        )
        for child in workload.iterdir():
            child.chmod(0o444)
        workload.chmod(0o555)
        report = temp / "report.json"
        try:
            completed = subprocess.run(
                ["/app/linkbench", str(workload), str(report)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
        except subprocess.TimeoutExpired as exc:
            print("harness timed out after 60 seconds")
            if exc.stderr:
                print("\nharness stderr:")
                print(exc.stderr.rstrip())
            return 1

        print(f"harness exit status: {completed.returncode}")
        print("\nraw controlled events:")
        raw_events = event_log.read_text(encoding="utf-8").rstrip()
        print(raw_events or "(none)")
        print("\nraw report:")
        if report.exists():
            try:
                parsed = json.loads(report.read_text(encoding="utf-8"))
                print(json.dumps(parsed, indent=2, sort_keys=True))
            except json.JSONDecodeError:
                print(report.read_text(encoding="utf-8").rstrip())
        else:
            print("(none)")
        if completed.stdout:
            print("\nharness stdout:")
            print(completed.stdout.rstrip())
        if completed.stderr:
            print("\nharness stderr:")
            print(completed.stderr.rstrip())
        return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
