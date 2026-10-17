# Validation History

These records test the benchmark, not the compared model routes.

## Oracle validation

- Purpose: confirm that the published reference solution can satisfy the verifier.
- Agent: Harbor Oracle `1.0.0`.
- Recorded window: 2026-10-14 22:41:38–22:44:58 UTC.
- Outcome: reward `1`; 15/15 tests passed.
- Submitted master: 3,744,335 bytes; SHA-256 `f826181a9082d6d1c8624c016db8bc872bacd96fcd1137a3af92440804b26742`.
- Evidence: [`oracle-verifier.json`](oracle-verifier.json).

## Completed task-quality check

- Purpose: independently inspect task clarity, coverage, anti-cheating separation, dependencies, and solution quality.
- Agent: OpenCode `1.19.0` using `openrouter/deepseek/deepseek-v4-pro`.
- Recorded window: 2026-10-14 22:38:14–22:40:29 UTC.
- Outcome: reward `1`; all 11 task-quality criteria passed.
- Recorded cost: $0.0268035168.
- Evidence: [`task-quality-check.json`](task-quality-check.json).

## Authentication-aborted check attempt

- Purpose: the same class of task-quality validation, attempted before the completed check.
- Agent: Claude Code `2.1.300` configured for `anthropic/claude-sonnet-4-6`.
- Recorded window: 2026-10-14 22:33:30–22:34:42 UTC.
- Outcome: stopped before task evaluation because the runner was not logged in.
- Usage: zero input tokens, zero output tokens, and zero recorded cost.
- Evidence: the sanitized operational record in [`validation-summary.json`](validation-summary.json).

The aborted attempt is included for a complete check history. Its recorded reward of `0` is an execution artifact, not evidence that the task failed review.

## Public-package verification

On October 16, 2026, I ran Harbor `0.24.0` against a clean copy of the public task directory. Harbor's dry run recognized one Oracle trial. The full Oracle execution then completed without exceptions, earned reward `1`, and passed 15/15 tests in 145 seconds. The regenerated master was byte-identical to the original Oracle artifact by size and SHA-256.

The verification record is [`public-package-verification.json`](public-package-verification.json). Harbor `0.24.0` did not expose the `harbor lint` command described by the documentation, so that specific static check is recorded as unavailable rather than claimed as complete.
