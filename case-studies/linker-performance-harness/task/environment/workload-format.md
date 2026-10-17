# Linker Replay Workload Format

A workload directory contains one captured final compiler-driver link. Compilation has already happened. The benchmark may read the directory but must not write to it.

## Required files

`workload.json` is the manifest. The file named by `response_file` contains the captured common link arguments. The remaining regular files are the main object and static archives named by that response file.

## Manifest

The manifest is a JSON object with these fields:

```json
{
  "schema_version": 1,
  "workload_id": "visible-001",
  "driver": "/usr/bin/gcc",
  "response_file": "link.rsp",
  "warmup_order": ["bfd", "gold", "lld", "mold"],
  "timed_rounds": [
    ["gold", "lld", "mold", "bfd"],
    ["lld", "mold", "bfd", "gold"],
    ["mold", "bfd", "gold", "lld"],
    ["bfd", "gold", "lld", "mold"],
    ["gold", "lld", "mold", "bfd"]
  ],
  "probe": {
    "argv": ["{output}", "--verify", "workload-token"],
    "expected_returncode": 0,
    "expected_stdout": "workload-token:12345\n",
    "expected_stderr": ""
  }
}
```

`schema_version` is the integer `1`.

`workload_id` is an opaque nonempty string copied verbatim into the benchmark report.

`driver` is the absolute compiler-driver path.

`response_file` is a safe relative path within the workload directory. It contains the already captured common link arguments. It does not contain a linker selector, linker thread controls or an output path.

`warmup_order` contains each of `bfd`, `gold`, `lld` and `mold` exactly once.

`timed_rounds` contains exactly five arrays. Each array contains all four linker IDs exactly once. Preserve both the supplied round order and each order within a round.

`probe.argv` is an argument array, not a shell command. Replace every exact `{output}` element with the absolute path of the new linked executable. Run the resulting array directly and require its exit status, standard output and standard error to equal the three expected fields. Inability to start that array is a probe failure.

Additional manifest fields are diagnostic metadata and do not change benchmark behavior.

## Link invocation

Run the compiler driver with `-fuse-ld=<id>`, that linker's thread controls, `@` followed by the absolute response-file path, and `-o` followed by an absolute output path outside the workload. Use the workload directory as the compiler driver's working directory and keep temporary files outside it.

The supplied response file contains an archive group. Removing the group causes unresolved references by design.

## Correctness

Before every warm-up or timed link, remove that invocation's output path. A successful invocation must exit zero and create a new regular file at that path, not a symlink to another file. Run the manifest probe immediately afterward. Any link or probe failure invalidates the complete benchmark.

Different linkers are expected to produce different output bytes and file sizes.
