# Verification suite

This standalone scorer adapts the Clip Provenance terminal-benchmark verifier for the model-comparison artifacts. It uses the same generator-derived answer key and the same **1.5-second inclusive timing tolerance**, but it does not impose the benchmark's `/app/matches.json` format on trials that were given a different client brief.

## What it checks

- Exactly 200 known clip names appear once in every scored snapshot.
- A genuine clip names the correct master.
- A genuine clip's proposed start is within 1.5 seconds of the generated start time.
- An out-of-library clip is explicitly rejected when the workflow labels it unidentified without a source or time.
- Accepted, uncertain, and unidentified results remain separate.

The answer key contains 160 genuine clips and 40 clips from outside the supplied master library. It was produced by the deterministic media generator, not estimated from the submitted results.

## Why the original Harbor tests were adapted

The Harbor task required one exact JSON schema and passed only when every row was correct. The OpenCode comparison instead requested a report containing confident, uncertain, and unidentified findings. The four saved snapshots also use different field names.

The adapters perform only structural normalization:

| Adapter | Native result fields | Shared interpretation |
| --- | --- | --- |
| `deepseek` | `classification`, `source_master`, `begin_time_s` | `not-identified` maps to `unidentified`; `confident` and `likely` are counted as accepted tiers. |
| `astra` | `status`, `source_video`, `source_start_seconds` | `confident` is the accepted tier. |
| `kimi-round2` | `tier`, `master`, `master_start_s` | `confident` is the accepted tier; this is the refined round-two report. |
| `kimi-round3` | `tier`, `master`, `t0` | `confident` is the accepted tier; this is the later saved checkpoint, not a finished report. |

The scorer preserves every native label in its row-level output. It does not convert an uncertain candidate into a confident match or treat an unidentified diagnostic candidate as an accepted answer.

## Run it

From this case-study directory:

```bash
python3 verification/score_trials.py
python3 -m unittest discover -s verification/tests -v
```

The first command regenerates `results/verification-results.json`. The second confirms corpus coverage, tolerance behavior, and the recorded aggregate values for all four snapshots.

From the case-study directory, `sha256sum -c verification/CHECKSUMS.sha256` verifies the answer key, scorer, regression checks, saved inputs, and generated results.

## Metrics

The output separates:

- accepted-match precision and genuine-clip recall;
- correct proposed sources and correct source-plus-time results across accepted and uncertain tiers;
- explicit foreign rejection;
- genuine clips left unidentified;
- uncertain-queue composition; and
- results broken down by each workflow's reported tier.

These are observations about the saved artifacts. They are not a universal ranking of the underlying model families.
