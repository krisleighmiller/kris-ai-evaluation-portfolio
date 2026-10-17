# Validation History

Validation runs are evidence about task development and the reference solution. They are not part of the 15-trial balanced model comparison.

## Historical Oracle

A contemporaneous development record identifies one completed Oracle trial under the earlier `multi-linker-benchmark` name. It reported reward `1` with no error. The temporary raw job directory was not retained, so this is published as a reconstructed, contemporaneously supported record—not as surviving raw trial output.

The exact public summary is `LPH-VAL-ORACLE-HIST-01` in [`validation-summary.json`](validation-summary.json). A clean Oracle run against the finished public package provides separate direct evidence.

## Task-quality check progression

| Public ID | Task name at run | Outcome | What changed or was learned |
| --- | --- | --- | --- |
| `LPH-CHECK-01` | `multi-linker-benchmark` | Invalid response | A criterion name was misspelled, so the result could not be parsed as a valid check. |
| `LPH-CHECK-02` | `multi-linker-benchmark` | 10/11 | The check found that native proof-of-work constraints tested by the verifier were not yet stated in the instruction. |
| `LPH-CHECK-03` | `multi-linker-benchmark` | 10/11 | After the instruction changed, the check questioned whether required version-probe behavior was fully established by the tests. |
| `LPH-CHECK-04` | `multi-linker-benchmark` | 11/11 | All task-quality criteria passed after further revision. |
| `LPH-CHECK-05` | `linker-performance-harness` | 11/11 | All criteria passed under the final public task name. |

The changing digests are expected: these checks span task development. The balanced trial set later used one shared digest, recorded separately in [`../../results/trial-summary.csv`](../../results/trial-summary.csv).

The four valid check reports are retained here unchanged because they contain criterion-level explanations without private host paths or credentials. The malformed first response is represented by a minimal sanitized record in `validation-summary.json`.

## Public-package Oracle

On October 16, 2026, Harbor `0.24.0` recognized one Oracle trial in a dry run against the sanitized public task. A clean execution then completed in 36 seconds with no exceptions, earned reward `1`, and passed all five verifier tests. The produced `linkbench` was 20,453 bytes and matched the published reference implementation's SHA-256.

See [`public-package-verification.json`](public-package-verification.json) and [`public-package-oracle-verifier.json`](public-package-oracle-verifier.json). Harbor `0.24.0` did not expose the documented `harbor lint` command, so that check is marked unavailable rather than claimed as complete.
