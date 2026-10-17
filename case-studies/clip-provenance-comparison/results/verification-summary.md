# Verified outcome summary

The public scorer evaluates four saved artifacts against the generator-derived truth for 160 genuine clips and 40 clips from outside the supplied master library. A genuine result is jointly correct when it names the correct master and places the start within 1.5 seconds of the generated start time.

| Measure | DeepSeek completed | Astra completed | Kimi round 2 refined | Kimi round 3 checkpoint |
| --- | ---: | ---: | ---: | ---: |
| Accepted rows | 151 | 137 | 134 | 136 |
| Correct accepted sources | 151 | 137 | 134 | 134 |
| Correct accepted source + time | 151 | 137 | 133 | 132 |
| Accepted source precision | 100.0% | 100.0% | 100.0% | 98.5% |
| Accepted source + time precision | 100.0% | 100.0% | 99.3% | 97.1% |
| Genuine source + time recall from accepted rows | 94.4% | 85.6% | 83.1% | 82.5% |
| Correct proposed genuine sources | 160/160 | 160/160 | 140/160 | 144/160 |
| Correct proposed genuine source + time | 160/160 | 159/160 | 139/160 | 141/160 |
| Explicit foreign rejection | 22/40 | 40/40 | 34/40 | 14/40 |
| Uncertain queue | 27 | 23 | 13 | 40 |
| Genuine clips unidentified | 0 | 0 | 19 | 10 |

## Reading the table

Accepted rows are the results each workflow labeled ready to rely on. DeepSeek used both `confident` and `likely`; the other workflows used `confident`. Proposed results additionally count uncertain candidates. An unidentified result is an explicit foreign rejection only when the answer key also identifies that clip as outside the library.

These distinctions matter. Astra rejected every foreign clip while leaving 23 genuine results uncertain. DeepSeek proposed the correct source and time for every genuine clip but left 18 foreign clips in its uncertain queue. Kimi's later checkpoint proposed more genuine results than round two, yet its accepted set gained two foreign clips and lost timing accuracy. The stopped Kimi run therefore requires both checkpoints to show what changed.

The figures can be regenerated with `python3 verification/score_trials.py` and checked with `python3 -m unittest discover -s verification/tests -v` from the case-study directory.
