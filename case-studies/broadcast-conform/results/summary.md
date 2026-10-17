# Results

## Primary outcome

The 20 primary trials produced 14 successful deliverables.

| Recorded route | Passes | Input tokens | Cache-read tokens | Output tokens | Recorded cost | Cost per success | Agent time range |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `openai/gpt-6-astra` | 5/5 | 3,387,018 | 3,386,643 | 45,332 | $9.753843 | $1.950769 | 275–517 s |
| `openrouter/qwen/qwen3.8-max-0902` | 5/5 | 36,148,859 | 35,035,136 | 150,923 | $14.176826 | $2.835365 | 2,091–6,343 s |
| `openrouter/moonshotai/kimi-k3` | 4/5 | 59,231,858 | 56,349,952 | 210,108 | $38.102688 | $9.525672 | 1,929–4,633 s |
| `openrouter/deepseek/deepseek-v4-pro` | 0/5 | 11,515,270 | 10,203,583 | 87,804 | $0.725185 | Not defined | 1,067–1,974 s |

`Cost per success` is total recorded route cost divided by successful trials. It is intentionally undefined where there were no successes. Cost and token fields are the execution layer's recorded values and are not normalized across providers.

## Failure matrix

The table shows the number of trials on each route that failed each test. Omitted verifier tests passed in all 20 trials.

| Failed verifier test | Astra | Qwen | Kimi | DeepSeek |
| --- | ---: | ---: | ---: | ---: |
| Decoded limited-range levels | 0 | 0 | 0 | 5 |
| Decoded patch colorimetry | 0 | 0 | 0 | 5 |
| Segment content and cuts | 0 | 0 | 0 | 5 |
| A/V sync | 0 | 0 | 1 | 5 |
| Beep spacing | 0 | 0 | 1 | 5 |
| Segment loudness | 0 | 0 | 0 | 2 |

The row-level source is [`trial-summary.csv`](trial-summary.csv); every public trial ID links conceptually to one CTRF verifier report under [`../trials/models/`](../trials/models/).

## Interpretation

The strongest result is not simply the 5/5 versus 0/5 spread. Every DeepSeek-route output passed deliverable presence, input integrity, basic stream properties, frame-rate and duration, keyframe interval, padding, no-synthesized-frames, audio provenance, and program loudness. Yet all five failed the decoded signal, edit, and timing checks listed above. A surface-level acceptance test would have missed that distinction.

The retained records support a narrower causal statement: unsuccessful runs did not correctly recover and conform all hidden source properties. They do not support claiming that every failed run used one identical command or made one identical reasoning error.

## Checksum note

The historical `recorded_task_checksum` values in the CSV are preserved because Harbor wrote them into each run. They are not suitable as a stable task-version identifier for this archive. The source task had its `jobs/` output directory nested below the task root, and the installed Harbor implementation hashed the full directory, so the value changed as job artifacts accumulated—even among trials in the same batch.

Use [`../task/CHECKSUMS.sha256`](../task/CHECKSUMS.sha256) as the identity of the published task files. This corrects the earlier working interpretation that route-level checksum differences represented simple metadata variants.

## Validation is not performance data

The Oracle passed 15/15 tests. The completed task-quality check passed 11/11 criteria. Those records establish that the reference solution can satisfy the verifier and that a separate check found the task design sound; they are not added to the 20-trial model denominator.

## Closing assessment

### What worked under the tested conditions

Fourteen of the 20 primary trials produced deliverables that passed all 15 verifier checks. Astra and Qwen passed five of five trials, and Kimi passed four of five. The Oracle and completed task-quality check also supported the evaluation design under the published task conditions.

### What failed

All five DeepSeek-route deliverables failed decoded-signal, edit, and timing checks despite passing several surface-level requirements. One Kimi deliverable failed A/V sync and beep spacing. These failures show that file presence, plausible metadata, and basic stream properties were not sufficient evidence of conformance.

### What required human verification

Human review was required to define the hidden truth, decide which decoded properties represented acceptance, interpret failure patterns, keep validation runs out of model pass rates, and correct the task-checksum interpretation. The automated verifier established whether a submission met the encoded requirements; it did not determine how broadly the findings should be applied.

### What remains untested

The study does not cover other broadcast specifications, source problems, program lengths, model revisions, provider routes, or repeated batches beyond five trials per route. It also does not establish how the same workflows would perform after model, application, dependency, or hardware changes.

### What these findings could inform

The findings could inform acceptance-test design for generated media, selection of AI-assisted conform workflows, budgeting for failed attempts, and decisions about which deliverable properties require decoded artifact checks before human sign-off.
