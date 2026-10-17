# Failure Analysis

## Repeated DeepSeek-route pattern

All five DeepSeek-route trials failed the same five verifier checks:

- limited-range pixel levels;
- color-patch conversion;
- segment content and cut placement;
- flash-to-beep A/V sync; and
- beep spacing, which detects residual timing drift.

Two of the five also failed per-segment loudness. All five passed the basic packaging and stream tests.

This is direct verifier evidence that the outputs looked structurally plausible but were not fully conformed when decoded. The instruction warned that some metadata was unreliable and that measurements must take priority over tags. The failure pattern is consistent with incomplete source interpretation and timing correction. Because the five retained implementations were not identical, the public conclusion stops there rather than assigning every failure to one command or one reasoning step.

## Single Kimi-route failure

Four Kimi-route trials passed. `BC-KI-04` failed only A/V sync and beep spacing. Its picture, edit structure, padding, audio provenance, and loudness checks passed. This isolates the unsuccessful result to the audio timing correction rather than a general inability to build the deliverable.

## Why the multi-test verifier matters

A binary reward tells us which trials succeeded. The individual tests tell us what kind of work remained unreliable:

- existence and format checks distinguish a missing or malformed deliverable;
- decoded pixel checks distinguish real color/range conversion from plausible tags;
- cut and no-blend checks distinguish correct edit timing from frame synthesis or boundary errors;
- flash/beep measurements separate fixed sync offset from clock drift;
- program and segment loudness checks distinguish a globally plausible mix from uneven segments.

That diagnostic resolution makes the benchmark useful for engineering review, not just ranking.

## Evidence boundary

This analysis is derived from the published CTRF verifier reports and the unchanged private run archive. Raw agent trajectories and machine logs are excluded because they contain local application state and add privacy surface without being necessary to reproduce the scores. Output videos are represented by byte size and SHA-256 digest in [`trial-summary.csv`](trial-summary.csv); the task can be rerun to produce new comparison artifacts.
