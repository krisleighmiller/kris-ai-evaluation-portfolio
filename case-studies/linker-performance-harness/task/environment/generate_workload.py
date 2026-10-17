#!/usr/bin/env python3
"""Generate a deterministic final-link replay workload."""

import argparse
import concurrent.futures
import hashlib
import json
import random
import shutil
import subprocess
from pathlib import Path


LINKERS = ["bfd", "gold", "lld", "mold"]
COMPILE_FLAGS = [
    "-std=c11",
    "-O0",
    "-gdwarf-4",
    "-ffunction-sections",
    "-fdata-sections",
    "-fno-inline",
    "-fno-omit-frame-pointer",
    "-fno-optimize-sibling-calls",
]


def run(command, *, cwd=None, check=True):
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )
    if check and result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {command!r}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def c_u64(value):
    return f"UINT64_C({value & ((1 << 64) - 1)})"


def write_unit(path, prefix, unit, functions, seed, has_next):
    rng = random.Random((seed << 20) ^ unit)
    payload = [rng.getrandbits(64) for _ in range(32)]
    constants = [
        (rng.getrandbits(64), rng.getrandbits(64))
        for _ in range(functions)
    ]
    entry = f"{prefix}_entry_{unit:05d}"
    next_entry = f"{prefix}_entry_{unit + 1:05d}"
    lines = [
        "#include <stddef.h>",
        "#include <stdint.h>",
        "typedef uint64_t (*work_fn)(uint64_t);",
        f"static const uint64_t {prefix}_payload_{unit:05d}[32] = {{",
        "    " + ",\n    ".join(c_u64(value) for value in payload),
        "};",
    ]
    if has_next:
        lines.append(f"uint64_t {next_entry}(uint64_t value);")
    names = []
    for index, (left, right) in enumerate(constants):
        name = f"{prefix}_fn_{unit:05d}_{index:03d}"
        names.append(name)
        lines.extend(
            [
                "__attribute__((noinline, used))",
                f"uint64_t {name}(uint64_t value) {{",
                (
                    f" return ((value ^ {c_u64(left)}) + {c_u64(right)}) "
                    f"^ {prefix}_payload_{unit:05d}[{index % 32}];"
                ),
                "}",
            ]
        )
    table = f"{prefix}_table_{unit:05d}"
    lines.extend(
        [
            f"static work_fn const {table}[{functions}] = {{",
            "    " + ",\n    ".join(names),
            "};",
            "__attribute__((noinline, used))",
            f"uint64_t {entry}(uint64_t value) {{",
            f" for (size_t i = 0; i < {functions}; ++i) value = {table}[i](value);",
        ]
    )
    if has_next:
        lines.append(
            f" return {next_entry}(value ^ {c_u64(rng.getrandbits(64))});"
        )
    else:
        lines.append(f" return value ^ {c_u64(rng.getrandbits(64))};")
    lines.extend(["}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_main(path, prefix, token, initial):
    path.write_text(
        f"""#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
uint64_t {prefix}_entry_00000(uint64_t value);
int main(int argc, char **argv) {{
 if (argc != 3 || strcmp(argv[1], "--verify") != 0 ||
     strcmp(argv[2], "{token}") != 0) return 64;
 uint64_t result = {prefix}_entry_00000({c_u64(initial)});
 printf("%s:%" PRIu64 "\\n", argv[2], result);
 return 0;
}}
""",
        encoding="utf-8",
    )


def compile_one(source, output, root, random_seed):
    run(
        [
            "gcc",
            *COMPILE_FLAGS,
            f"-fdebug-prefix-map={root}=/workload",
            f"-frandom-seed={random_seed}",
            "-c",
            str(source),
            "-o",
            str(output),
        ]
    )


def write_response(path, arguments, layout):
    if layout == "one-per-line":
        text = "\n".join(arguments) + "\n"
    else:
        widths = (2, 5, 3, 4)
        lines = []
        offset = 0
        while offset < len(arguments):
            width = widths[len(lines) % len(widths)]
            lines.append(" ".join(arguments[offset : offset + width]))
            offset += width
        text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")


def payload_digest(output):
    digest = hashlib.sha256()
    for path in sorted(output.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.name == "workload.json":
            continue
        name = path.name.encode()
        data = path.read_bytes()
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def make_schedule(seed):
    rng = random.Random(seed ^ 0x5C4EDA7A)
    warmup = list(LINKERS)
    rng.shuffle(warmup)
    rounds = []
    previous = None
    for _ in range(5):
        order = list(LINKERS)
        while True:
            rng.shuffle(order)
            if order != previous:
                break
        rounds.append(list(order))
        previous = list(order)
    return warmup, rounds


def generate(args):
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    sources = output / ".sources"
    objects_dir = output / ".objects"
    sources.mkdir(parents=True)
    objects_dir.mkdir()
    rng = random.Random(args.seed)
    prefix = f"w_{rng.getrandbits(48):012x}"
    token = f"probe-{rng.getrandbits(64):016x}"
    initial = rng.getrandbits(64)
    object_names = [
        f"{prefix}_{unit:05d}_{rng.getrandbits(32):08x}.o"
        for unit in range(args.units)
    ]
    source_paths = []
    object_paths = []
    for unit, name in enumerate(object_names):
        source = sources / f"source_{unit:05d}.c"
        obj = objects_dir / name
        write_unit(
            source,
            prefix,
            unit,
            args.functions,
            args.seed,
            unit + 1 < args.units,
        )
        source_paths.append(source)
        object_paths.append(obj)
    main_name = f"{prefix}_root_{rng.getrandbits(32):08x}.o"
    main_source = sources / "root.c"
    main_object = objects_dir / main_name
    write_main(main_source, prefix, token, initial)
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.compile_jobs
    ) as executor:
        jobs = [
            executor.submit(
                compile_one,
                source,
                obj,
                output,
                f"{args.seed}-{unit}",
            )
            for unit, (source, obj) in enumerate(
                zip(source_paths, object_paths)
            )
        ]
        jobs.append(
            executor.submit(
                compile_one,
                main_source,
                main_object,
                output,
                f"{args.seed}-main",
            )
        )
        for job in jobs:
            job.result()
    members = [[] for _ in range(args.archives)]
    for unit, obj in enumerate(object_paths):
        members[unit % args.archives].append(obj)
    archives = []
    for index, archive_members in enumerate(members):
        archive = output / (
            f"lib{prefix}_{index:02d}_{rng.getrandbits(32):08x}.a"
        )
        run(["ar", "rcsD", str(archive), *map(str, archive_members)])
        archives.append(archive)
    shutil.move(main_object, output / main_name)
    response_name = (
        "link.rsp"
        if args.response_layout == "one-per-line"
        else f"replay-{rng.getrandbits(32):08x}.rsp"
    )
    response = output / response_name
    common = [
        main_name,
        "-Wl,--build-id=none",
        "-Wl,--start-group",
        *(path.name for path in archives),
        "-Wl,--end-group",
    ]
    write_response(response, common, args.response_layout)
    failed_output = output / ".without-group"
    failed = run(
        [
            "gcc",
            "-fuse-ld=bfd",
            main_name,
            "-Wl,--build-id=none",
            *(path.name for path in archives),
            "-o",
            str(failed_output),
        ],
        cwd=output,
        check=False,
    )
    failed_output.unlink(missing_ok=True)
    if failed.returncode == 0:
        raise RuntimeError("workload links without its archive group")
    baseline = output / ".baseline"
    run(
        ["gcc", "-fuse-ld=bfd", f"@{response}", "-o", str(baseline)],
        cwd=output,
    )
    probe = run([str(baseline), "--verify", token], cwd=output)
    baseline.unlink()
    shutil.copyfile(args.format_doc, output / "README.md")
    shutil.rmtree(sources)
    shutil.rmtree(objects_dir)
    input_bytes = (output / main_name).stat().st_size + sum(
        path.stat().st_size for path in archives
    )
    warmup, rounds = make_schedule(args.seed)
    manifest = {
        "schema_version": 1,
        "workload_id": args.workload_id,
        "driver": "/usr/bin/gcc",
        "response_file": response_name,
        "warmup_order": warmup,
        "timed_rounds": rounds,
        "probe": {
            "argv": ["{output}", "--verify", token],
            "expected_returncode": probe.returncode,
            "expected_stdout": probe.stdout,
            "expected_stderr": probe.stderr,
        },
        "input_summary": {
            "translation_units": args.units + 1,
            "functions_per_unit": args.functions,
            "archives": args.archives,
            "input_bytes": input_bytes,
            "defined_functions": args.units * (args.functions + 1) + 1,
            "minimum_relocations": args.units * (args.functions + 1) + 1,
            "archive_group_required": True,
            "response_layout": args.response_layout,
        },
        "payload_sha256": payload_digest(output),
    }
    (output / "workload.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workload-id", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--units", type=int, required=True)
    parser.add_argument("--functions", type=int, required=True)
    parser.add_argument("--archives", type=int, required=True)
    parser.add_argument("--compile-jobs", type=int, default=2)
    parser.add_argument(
        "--response-layout",
        choices=("one-per-line", "wrapped"),
        required=True,
    )
    parser.add_argument("--format-doc", type=Path, required=True)
    args = parser.parse_args()
    if args.units < args.archives:
        parser.error("units must be greater than or equal to archives")
    generate(args)


if __name__ == "__main__":
    main()
