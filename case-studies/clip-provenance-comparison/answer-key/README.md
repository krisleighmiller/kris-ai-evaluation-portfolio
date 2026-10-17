# Answer key

`ground-truth.json` is the sanitized verification key for the 200-clip corpus. It was derived from the same deterministic generator record used by the Clip Provenance terminal benchmark.

Each row contains:

- `clip`: the portable clip filename;
- `master`: the expected master filename, or `null` for footage outside the supplied library; and
- `offset_sec`: the generated start time on the master clock, or `null` for outside-library footage.

The public copy removes Harbor's `/app/clips/` and `/app/masters/` container prefixes. The expected filenames and start values are unchanged. The comparison agents did not receive this file.

Corpus composition: **160 genuine clips and 40 outside-library clips**. Verification accepts a genuine start time when its absolute error is at most **1.5 seconds**.
