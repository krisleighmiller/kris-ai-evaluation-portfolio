#!/usr/bin/env python3
"""Generate a verifier-only native linker workload."""

import argparse
import json
import random
import shutil
import subprocess
from pathlib import Path


def run(command, cwd=None, check=True):
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise RuntimeError(f"{command!r}\n{result.stderr}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    shutil.rmtree(output, ignore_errors=True)
    source = output / ".source"
    objects = output / ".objects"
    source.mkdir(parents=True)
    objects.mkdir()
    rng = random.Random(8675309)
    token = f"hidden-{rng.getrandbits(64):016x}"
    units = 128
    functions = 24
    names = []
    for unit in range(units):
        name = f"unit_{unit:04d}_{rng.getrandbits(32):08x}"
        names.append(name)
        values = [rng.getrandbits(64) for _ in range(functions)]
        lines = [
            "#include <stdint.h>",
            f"uint64_t {name}(uint64_t);",
            f"uint64_t {name}_next(uint64_t);",
        ]
        for index, value in enumerate(values):
            lines.extend(
                [
                    "__attribute__((noinline,used))",
                    f"static uint64_t f_{unit}_{index}(uint64_t x) "
                    f"{{ return (x ^ UINT64_C({value})) + {index + 1}; }}",
                ]
            )
        next_unit = (unit + 1) % units
        next_name = f"unit_{next_unit:04d}_PLACEHOLDER"
        lines.extend(
            [
                f"extern uint64_t {next_name}(uint64_t);",
                f"uint64_t {name}(uint64_t x) {{",
                *[
                    f" x = f_{unit}_{index}(x);"
                    for index in range(functions)
                ],
                (
                    f" return {next_name}(x);"
                    if unit + 1 < units
                    else " return x;"
                ),
                "}",
            ]
        )
        (source / f"{unit:04d}.c").write_text("\n".join(lines))
    for unit in range(units - 1):
        path = source / f"{unit:04d}.c"
        text = path.read_text().replace(
            f"unit_{unit + 1:04d}_PLACEHOLDER", names[unit + 1]
        )
        path.write_text(text)
    last = source / f"{units - 1:04d}.c"
    last.write_text(last.read_text().replace("unit_0000_PLACEHOLDER", names[0]))
    main_source = source / "main.c"
    main_source.write_text(
        f"""#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
uint64_t {names[0]}(uint64_t);
int main(int argc, char **argv) {{
 if (argc != 3 || strcmp(argv[1], "--verify") ||
     strcmp(argv[2], "{token}")) return 64;
 printf("%s:%" PRIu64 "\\n", argv[2], {names[0]}(UINT64_C(1234567)));
 return 0;
}}
"""
    )
    flags = [
        "-O0",
        "-gdwarf-4",
        "-ffunction-sections",
        "-fdata-sections",
        "-fdebug-prefix-map=" + str(output) + "=/hidden",
    ]
    for unit in range(units):
        run(
            [
                "gcc",
                *flags,
                "-c",
                str(source / f"{unit:04d}.c"),
                "-o",
                str(objects / f"{unit:04d}.o"),
            ]
        )
    run(["gcc", *flags, "-c", str(main_source), "-o", str(output / "main.o")])
    archives = []
    for bucket in range(8):
        archive = output / f"libhidden-{bucket}.a"
        members = [
            str(objects / f"{unit:04d}.o")
            for unit in range(bucket, units, 8)
        ]
        run(["ar", "rcsD", str(archive), *members])
        archives.append(archive)
    response = output / "hidden.rsp"
    response.write_text(
        "\n".join(
            [
                "main.o",
                "-Wl,--build-id=none",
                "-Wl,--start-group",
                *(archive.name for archive in archives),
                "-Wl,--end-group",
            ]
        )
        + "\n"
    )
    baseline = output / ".baseline"
    run(["gcc", "-fuse-ld=bfd", f"@{response}", "-o", str(baseline)], output)
    probe = run([str(baseline), "--verify", token], output)
    baseline.unlink()
    manifest = {
        "schema_version": 1,
        "workload_id": "hidden-8675309",
        "driver": "/usr/bin/gcc",
        "response_file": response.name,
        "warmup_order": ["lld", "bfd", "mold", "gold"],
        "timed_rounds": [
            ["gold", "mold", "lld", "bfd"],
            ["bfd", "lld", "gold", "mold"],
            ["mold", "gold", "bfd", "lld"],
            ["lld", "mold", "bfd", "gold"],
            ["gold", "bfd", "mold", "lld"],
        ],
        "probe": {
            "argv": ["{output}", "--verify", token],
            "expected_returncode": 0,
            "expected_stdout": probe.stdout,
            "expected_stderr": probe.stderr,
        },
    }
    (output / "workload.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    (output / "README.md").write_text(
        "Verifier-only final-link replay workload.\n"
    )
    shutil.rmtree(source)
    shutil.rmtree(objects)


if __name__ == "__main__":
    main()
