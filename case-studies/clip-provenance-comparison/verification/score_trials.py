#!/usr/bin/env python3
"""Score Clip Provenance trial artifacts against generator-derived truth.

This is a comparison scorer, not the original Harbor pass/fail verifier. It
keeps each workflow's native confidence label while mapping equivalent labels
to a small shared vocabulary for aggregate reporting.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable


TOLERANCE_SECONDS = 1.5


def _canonical_clip(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"clip name must be a non-empty string, got {value!r}")
    name = Path(value).name
    return name if name.endswith(".mp4") else f"{name}.mp4"


def _canonical_master(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError(f"master must not be boolean: {value!r}")
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
        return f"master_{int(value):02d}.mp4"
    if isinstance(value, str):
        name = Path(value).name
        if name.startswith("master_") and name.endswith(".mp4"):
            return name
    raise ValueError(f"unrecognized master value: {value!r}")


def _number_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"offset must be a JSON number or null, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"offset must be finite, got {value!r}")
    return number


def _first_number(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if row.get(key) is not None:
            return _number_or_none(row[key])
    return None


def adapt_deepseek(row: dict[str, Any]) -> dict[str, Any]:
    native_tier = row.get("classification")
    tier = "unidentified" if native_tier == "not-identified" else native_tier
    native_master = _canonical_master(row.get("source_master"))
    native_offset = _number_or_none(row.get("begin_time_s"))
    return {
        "clip": _canonical_clip(row.get("clip")),
        "native_tier": native_tier,
        "tier": tier,
        "candidate_master": None if tier == "unidentified" else native_master,
        "candidate_offset": None if tier == "unidentified" else native_offset,
        "diagnostic_master": native_master if tier == "unidentified" else None,
        "diagnostic_offset": native_offset if tier == "unidentified" else None,
    }


def adapt_astra(row: dict[str, Any]) -> dict[str, Any]:
    tier = row.get("status")
    return {
        "clip": _canonical_clip(row.get("clip")),
        "native_tier": tier,
        "tier": tier,
        "candidate_master": _canonical_master(row.get("source_video")),
        "candidate_offset": _number_or_none(row.get("source_start_seconds")),
    }


def adapt_kimi_round2(row: dict[str, Any]) -> dict[str, Any]:
    tier = row.get("tier")
    return {
        "clip": _canonical_clip(row.get("clip")),
        "native_tier": tier,
        "tier": tier,
        "candidate_master": _canonical_master(row.get("master")),
        "candidate_offset": _first_number(row, "master_start_s", "t0_refined", "t0"),
    }


def adapt_kimi_round3(row: dict[str, Any]) -> dict[str, Any]:
    tier = row.get("tier")
    return {
        "clip": _canonical_clip(row.get("clip")),
        "native_tier": tier,
        "tier": tier,
        "candidate_master": _canonical_master(row.get("master")),
        "candidate_offset": _number_or_none(row.get("t0")),
    }


ADAPTERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "deepseek": adapt_deepseek,
    "astra": adapt_astra,
    "kimi-round2": adapt_kimi_round2,
    "kimi-round3": adapt_kimi_round3,
}

ACCEPTED_TIERS = {
    "deepseek": {"confident", "likely"},
    "astra": {"confident"},
    "kimi-round2": {"confident"},
    "kimi-round3": {"confident"},
}

DISPLAY_NAMES = {
    "deepseek": "DeepSeek completed",
    "astra": "Astra completed",
    "kimi-round2": "Kimi stopped — round 2 refined",
    "kimi-round3": "Kimi stopped — round 3 checkpoint",
}

DEFAULT_TRIALS = {
    "deepseek": "trials/deepseek/results.json",
    "astra": "trials/astra/results.json",
    "kimi-round2": "trials/kimi/round-2-report.json",
    "kimi-round3": "trials/kimi/round-3-decisions.json",
}


def load_truth(path: Path) -> dict[str, dict[str, Any]]:
    raw = json.loads(path.read_text())
    if not isinstance(raw, list):
        raise ValueError("answer key must be a JSON array")
    truth: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(raw):
        if not isinstance(row, dict):
            raise ValueError(f"answer-key row {index} is not an object")
        clip = _canonical_clip(row.get("clip"))
        if clip in truth:
            raise ValueError(f"answer key contains duplicate clip {clip}")
        master = _canonical_master(row.get("master"))
        offset = _number_or_none(row.get("offset_sec"))
        if (master is None) != (offset is None):
            raise ValueError(f"answer key {clip}: master and offset must both be set or null")
        truth[clip] = {"clip": clip, "master": master, "offset_sec": offset}
    return truth


def load_trial(path: Path, adapter_name: str) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text())
    if not isinstance(raw, list):
        raise ValueError(f"{path}: trial artifact must be a JSON array")
    adapter = ADAPTERS[adapter_name]
    rows = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"{path}: row {index} is not an object")
        row = adapter(item)
        if row["tier"] not in {"confident", "likely", "uncertain", "unidentified"}:
            raise ValueError(f"{path}: row {index} has unknown tier {row['tier']!r}")
        if (row["candidate_master"] is None) != (row["candidate_offset"] is None):
            raise ValueError(
                f"{path}: {row['clip']} candidate master and offset must both be set or null"
            )
        rows.append(row)
    return rows


def validate_coverage(rows: list[dict[str, Any]], truth: dict[str, dict[str, Any]]) -> None:
    names = [row["clip"] for row in rows]
    counts = Counter(names)
    duplicates = sorted(name for name, count in counts.items() if count > 1)
    missing = sorted(set(truth) - set(names))
    unknown = sorted(set(names) - set(truth))
    problems = []
    if duplicates:
        problems.append(f"duplicate clips: {duplicates[:10]}")
    if missing:
        problems.append(f"missing clips: {missing[:10]}")
    if unknown:
        problems.append(f"unknown clips: {unknown[:10]}")
    if problems:
        raise ValueError("; ".join(problems))


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _tier_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors = [
        row["offset_error_seconds"]
        for row in rows
        if row["truth_kind"] == "genuine"
        and row["source_correct"]
        and row["offset_error_seconds"] is not None
    ]
    return {
        "count": len(rows),
        "genuine": sum(row["truth_kind"] == "genuine" for row in rows),
        "foreign": sum(row["truth_kind"] == "foreign" for row in rows),
        "correct_genuine_sources": sum(
            row["truth_kind"] == "genuine" and row["source_correct"] for row in rows
        ),
        "joint_correct": sum(row["joint_correct"] for row in rows),
        "median_offset_error_seconds": statistics.median(errors) if errors else None,
        "max_offset_error_seconds": max(errors) if errors else None,
    }


def score_trial(
    trial_rows: list[dict[str, Any]],
    truth: dict[str, dict[str, Any]],
    adapter_name: str,
    tolerance_seconds: float = TOLERANCE_SECONDS,
) -> dict[str, Any]:
    validate_coverage(trial_rows, truth)
    accepted_tiers = ACCEPTED_TIERS[adapter_name]
    scored_rows = []
    for row in trial_rows:
        expected = truth[row["clip"]]
        truth_kind = "foreign" if expected["master"] is None else "genuine"
        source_correct = row["candidate_master"] == expected["master"]
        offset_error = None
        if truth_kind == "genuine" and source_correct and row["candidate_offset"] is not None:
            offset_error = abs(row["candidate_offset"] - expected["offset_sec"])
        if truth_kind == "foreign":
            joint_correct = row["candidate_master"] is None and row["candidate_offset"] is None
        else:
            joint_correct = source_correct and offset_error is not None and offset_error <= tolerance_seconds
        scored_rows.append(
            {
                **row,
                "truth_kind": truth_kind,
                "truth_master": expected["master"],
                "truth_offset": expected["offset_sec"],
                "source_correct": source_correct,
                "offset_error_seconds": offset_error,
                "joint_correct": joint_correct,
                "accepted_match": row["tier"] in accepted_tiers,
            }
        )

    genuine_total = sum(row["truth_kind"] == "genuine" for row in scored_rows)
    foreign_total = len(scored_rows) - genuine_total
    accepted = [row for row in scored_rows if row["accepted_match"]]
    proposed = [row for row in scored_rows if row["tier"] != "unidentified"]
    uncertain = [row for row in scored_rows if row["tier"] == "uncertain"]
    unidentified = [row for row in scored_rows if row["tier"] == "unidentified"]
    accepted_source_correct = sum(
        row["truth_kind"] == "genuine" and row["source_correct"] for row in accepted
    )
    accepted_joint_correct = sum(
        row["truth_kind"] == "genuine" and row["joint_correct"] for row in accepted
    )
    proposed_source_correct = sum(
        row["truth_kind"] == "genuine" and row["source_correct"] for row in proposed
    )
    proposed_joint_correct = sum(
        row["truth_kind"] == "genuine" and row["joint_correct"] for row in proposed
    )
    explicit_foreign_rejections = sum(
        row["truth_kind"] == "foreign" for row in unidentified
    )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scored_rows:
        grouped[row["tier"]].append(row)

    return {
        "adapter": adapter_name,
        "display_name": DISPLAY_NAMES[adapter_name],
        "accepted_tiers": sorted(accepted_tiers),
        "metrics": {
            "rows": len(scored_rows),
            "genuine_clips": genuine_total,
            "foreign_clips": foreign_total,
            "accepted_matches": len(accepted),
            "accepted_correct_sources": accepted_source_correct,
            "accepted_correct_source_and_time": accepted_joint_correct,
            "accepted_source_precision": _ratio(accepted_source_correct, len(accepted)),
            "accepted_joint_precision": _ratio(accepted_joint_correct, len(accepted)),
            "accepted_source_recall": _ratio(accepted_source_correct, genuine_total),
            "accepted_joint_recall": _ratio(accepted_joint_correct, genuine_total),
            "proposed_correct_genuine_sources": proposed_source_correct,
            "proposed_correct_genuine_source_and_time": proposed_joint_correct,
            "explicit_foreign_rejections": explicit_foreign_rejections,
            "foreign_rejection_recall": _ratio(explicit_foreign_rejections, foreign_total),
            "genuine_unidentified": sum(
                row["truth_kind"] == "genuine" for row in unidentified
            ),
            "uncertain_rows": len(uncertain),
            "uncertain_genuine": sum(row["truth_kind"] == "genuine" for row in uncertain),
            "uncertain_foreign": sum(row["truth_kind"] == "foreign" for row in uncertain),
            "all_rows_joint_correct": sum(row["joint_correct"] for row in scored_rows),
        },
        "tiers": {tier: _tier_metrics(rows) for tier, rows in sorted(grouped.items())},
        "rows": sorted(scored_rows, key=lambda row: row["clip"]),
    }


def score_suite(root: Path, tolerance_seconds: float = TOLERANCE_SECONDS) -> dict[str, Any]:
    truth = load_truth(root / "answer-key/ground-truth.json")
    trials = {}
    for adapter_name, relative_path in DEFAULT_TRIALS.items():
        rows = load_trial(root / relative_path, adapter_name)
        trials[adapter_name] = score_trial(rows, truth, adapter_name, tolerance_seconds)
    return {
        "schema_version": 1,
        "tolerance_seconds": tolerance_seconds,
        "truth_summary": {
            "rows": len(truth),
            "genuine": sum(row["master"] is not None for row in truth.values()),
            "foreign": sum(row["master"] is None for row in truth.values()),
        },
        "trials": trials,
    }


def main() -> None:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_root, help="case-study directory")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="write JSON here; defaults to results/verification-results.json under --root",
    )
    parser.add_argument("--tolerance", type=float, default=TOLERANCE_SECONDS)
    args = parser.parse_args()
    if args.tolerance < 0:
        parser.error("--tolerance must be non-negative")
    root = args.root.resolve()
    output = args.output or root / "results/verification-results.json"
    result = score_suite(root, args.tolerance)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"Scored {len(result['trials'])} saved snapshots against {result['truth_summary']['rows']} clips")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
