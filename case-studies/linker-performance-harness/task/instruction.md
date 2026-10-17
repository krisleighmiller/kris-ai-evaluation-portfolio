Fix `/app/linkbench`, run as `/app/linkbench <workload-directory> <report-json>`, to compare GNU BFD `ld`, GNU `gold`, LLVM `lld` and `mold` over the captured final compiler-driver link documented in `/app/workload/README.md`. Follow the manifest's warm-up order once and its five timed round orders exactly: 24 links, no extra links or retries. Before every link remove its output, keep all outputs and temporary files outside the possibly read-only workload, and time the complete driver process from launch through exit with a monotonic wall clock in nanoseconds. Select with `-fuse-ld=<id>` and use only this control policy: no thread argument for BFD; separate `-Wl,--threads` and `-Wl,--thread-count=2` arguments for gold; `-Wl,--threads=2` for LLD; and `-Wl,--threads=2` plus `-Wl,--no-fork` for mold. Required `<invoked_path> --version` metadata probes are neither links nor samples.

For every scheduled link, determine which linker ran from the `execve` events the driver actually performs, not from the selector. A link may execute more than one linker-shaped process; the one to report is the process that performed that link. The supplied drivers execute linkers by absolute path, possibly containing `.` or `..`; record the path each linker was executed with, verbatim, without resolving or normalizing it. Every link for an ID must use the same path, and the linker executed at that path must belong to the ID's family at every link. Classify a `--version` probe's first nonempty stdout line case-insensitively by the first marker it contains, tested in this order: `mold` is mold, `GNU gold` is gold, `LLD` is LLD, `GNU ld` is BFD. Apply these checks to warm-ups and samples. Also require each newly created output itself, without following symlinks, to be a regular file that exactly passes the manifest probe; inability to start the probe is failure. Remove any existing report before linking. Any identity, link, output or probe failure must exit nonzero and leave no report.

On success, write one complete JSON object with exactly the four top-level keys and six result keys shown below—no extras. Copy `workload_id` verbatim; include one result per linker in any order; preserve each linker's observed path and first nonempty version line; report `effective_threads` as 1 for BFD and 2 otherwise; keep each linker's five actual measured, positive integer driver durations in execution order (not estimates, placeholders, or values derived from the manifest); use their third-smallest value as `median_ns`; and rank by increasing median, allowing either order only for exact ties. The example ranking is illustrative. The native verifier checks measurement plausibility against its own warmed reference links of the same workload and thread settings: it runs each linker once to warm up and three more times to take the middle reference duration. The submitted run must take at least four times the sum of those four reference durations in total wall time; the sum of its 20 reported samples must not exceed that wall time; and each reported linker median must be between one tenth and twenty times its corresponding reference duration. These checks do not prescribe a reference ranking: rank only by the submitted medians. `/app/linkbench` must exit zero and be one self-contained executable regular file no larger than one mebibyte. It is copied out alone and run directly, without an external tracer, as an ordinary user from a writable working directory that does not contain it, with stock Python 3 and `strace` available.

```json
{
  "schema_version": 1,
  "workload_id": "string",
  "results": [
    {
      "linker": "bfd | gold | lld | mold",
      "invoked_path": "absolute string",
      "version": "nonempty string",
      "effective_threads": 1,
      "samples_ns": [1, 2, 3, 4, 5],
      "median_ns": 3
    }
  ],
  "ranking": ["mold", "lld", "gold", "bfd"]
}
```

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
