# Linker Performance Harness

A performance harness can print precise timings while measuring the wrong executable, using unfair thread settings, accepting stale output, or silently falling back to another linker. This benchmark asks an agent to repair a self-contained harness that compares GNU BFD, GNU gold, LLVM LLD, and mold over a captured compiler-driver link.

I designed the synthetic workloads, authenticated controlled protocol, reference solution, and five-test verifier. The central question is not whether the program produces a ranking. It is whether the evidence behind that ranking can be trusted.

## What this demonstrates

This project demonstrates how I detect misleading measurements, verify the evidence behind a performance claim, and distinguish a plausible-looking benchmark report from a run that followed the required protocol.

## Balanced result

| Recorded model route | Successful trials | Observed pass rate | Recorded cost | Cost per success |
| --- | ---: | ---: | ---: | ---: |
| `openai/gpt-6-astra` | 3/5 | 60% | $6.7428 | $2.2476 |
| `openrouter/moonshotai/kimi-k3` | 2/5 | 40% | $17.0142 | $8.5071 |
| `openrouter/deepseek/deepseek-v4-pro` | 0/5 | 0% | $0.2803 | Not defined |

Every one of the ten failed balanced submissions failed the authenticated controlled protocol. One DeepSeek submission also failed the hidden native workload. The common failed test did not imply one common cause: the artifacts failed through trace parsing, omitted probes, linker attribution, and report-schema handling.

Two single exploratory trials—Qwen3.7 Plus and an earlier DeepSeek run—are published separately and excluded from these rates.

## Why the protocol matters

The controlled verifier does not trust the requested linker label. It authenticates the executed tools and checks the exact link schedule, unresolved invocation paths, linker family, thread controls, fresh outputs, version probes, timing evidence, aggregation, ranking, and all-or-nothing cleanup behavior.

A submission can therefore pass basic execution and the native workload while still fail the benchmark because its measurement evidence is not trustworthy. That is the intended discriminator.

## Evidence package

- [`task/`](task/) — complete Harbor task, including environment, diagnostic lab, reference solution, hidden verifier, controlled tools, provenance, and checksums.
- [`trials/balanced/`](trials/balanced/) — all 15 submitted `linkbench` programs and their verifier reports.
- [`trials/exploratory/`](trials/exploratory/) — the two single-trial observations, kept outside the balanced denominator.
- [`trials/validation/`](trials/validation/) — reconstructed historical Oracle evidence, the five-stage check history, and fresh public-package verification.
- [`results/trial-summary.csv`](results/trial-summary.csv) — auditable row-level configuration, result, usage, cost, runtime, digest, and artifact hash.
- [`results/failure-analysis.md`](results/failure-analysis.md) — distinct trace-supported failure mechanisms.

Harbor, OpenCode, credentials, provider configuration, local databases, caches, and machine specifications are excluded. A reviewer supplies those independently and reruns the published task.

## Claim boundary

These are controlled observations from five trials per primary route on one demanding systems task. They demonstrate differences in observed reliability, failure mechanism, workflow time, and cost per successful deliverable. They do not establish a permanent ranking of the underlying model families.

Start with the [methodology](methodology.md), [results](results/summary.md), or [published task](task/).
