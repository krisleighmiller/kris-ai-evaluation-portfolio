# Broadcast Conform

A video can play normally and still be wrong. This benchmark asks an agent to diagnose seven deliberately messy source files, assemble a 60-second promo, and deliver a master that meets exact picture, audio, timing, and packaging requirements.

I designed the task, synthetic footage, hidden truth, reference solution, and 15-test verifier. The verifier decodes the submitted `master.mp4`; it does not accept tags or an agent's completion claim as proof of conformance.

## Result at a glance

| Recorded model route | Successful trials | Observed pass rate | Recorded cost | Cost per success |
| --- | ---: | ---: | ---: | ---: |
| `openai/gpt-6-astra` | 5/5 | 100% | $9.7538 | $1.9508 |
| `openrouter/qwen/qwen3.8-max-0902` | 5/5 | 100% | $14.1768 | $2.8354 |
| `openrouter/moonshotai/kimi-k3` | 4/5 | 80% | $38.1027 | $9.5257 |
| `openrouter/deepseek/deepseek-v4-pro` | 0/5 | 0% | $0.7252 | Not defined |

The comparison set is 20 model trials: five per route. Oracle and task-quality runs are validation evidence and never enter these pass rates.

## What the benchmark exposed

All five DeepSeek-route trials produced a file with the expected basic structure, but every one failed five decoded-signal checks: limited-range levels, patch colorimetry, segment content and cuts, A/V sync, and beep spacing. Two also failed segment loudness. The repeated pattern matters because it shows why artifact inspection is stronger than checking whether a file exists or carries plausible metadata.

Kimi passed four trials. Its one failed trial missed A/V sync and beep-spacing requirements. Astra and Qwen passed all 15 tests in all five recorded trials.

These are observations about the named routes, task version, and run conditions—not a permanent ranking of model families. See the [full result summary](results/summary.md) and [failure analysis](results/failure-analysis.md).

## What is included

- [`task/`](task/) — the complete Harbor task: instruction, configuration, Docker environment, seven synthetic inputs, reference solution, verifier, hidden truth, and checksums.
- [`trials/models/`](trials/models/) — the 20 sanitized verifier reports, organized by route.
- [`trials/validation/`](trials/validation/) — separate Oracle and task-quality-check evidence, including the operationally aborted check attempt.
- [`results/trial-summary.csv`](results/trial-summary.csv) — one auditable row per primary trial, with reward, failed tests, usage, cost, runtime, and output hash.
- [`methodology.md`](methodology.md) — controls, evidence flow, and reproduction procedure.
- [`limitations.md`](limitations.md) — small-sample, route, accounting, and archive caveats.

Harbor, OpenCode, credentials, provider configuration, local databases, caches, and machine specifications are not included. Reviewers bring their own installation, hardware, and API keys, then compare new verifier results with the recorded evidence.

## Why this belongs in the portfolio

The work is not just an FFmpeg exercise. It demonstrates how I turn an ambiguous professional requirement into a controlled evaluation: synthetic source design, withheld ground truth, a working Oracle, decoded artifact checks, repeated trials, failure analysis, cost accounting, and bounded conclusions.

Start with the [methodology](methodology.md), then inspect the [published task](task/) or [trial evidence](trials/README.md).
