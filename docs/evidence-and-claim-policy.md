# Evidence and Claim Policy

This repository distinguishes an agent's statement from a verified outcome. A completion message is evidence that the agent claimed completion. It is not proof that the work met the requirements.

## Evidence labels

| Label | Meaning |
| --- | --- |
| **Directly observed** | Preserved output, verifier result, test result, artifact, or behavior observed during the recorded run. |
| **Contemporaneously supported** | Supported by records created at the time, such as a saved change, run log, or review note, even when the full raw environment no longer exists. |
| **Inferred** | The available evidence supports the interpretation, but no single record proves it directly. |
| **Reported** | A person or agent described the event, but the underlying evidence is incomplete. |
| **Unverified** | The claim could not be confirmed from the retained record. |

## Source priority

When records disagree, the closest primary evidence takes priority:

1. Task inputs, produced artifacts, verifier output, tests, and saved changes.
2. Contemporaneous run records and review notes.
3. Later summaries and working reports.
4. Memory or unsupported completion statements.

Search tools may locate evidence, but a search result is not substituted for the underlying record when that record is available.

## Trial categories stay separate

Model trials, exploratory runs, Oracle runs, task-quality checks, reruns, stopped runs, and authentication failures are labeled separately. Validation activity does not enter model pass-rate denominators. A run stopped before evaluation is not relabeled as a task failure.

## Original output and later evaluation stay separate

Sanitized model outputs are kept as generated. Factual corrections and scoring judgments belong in evaluator material, not inside a cleaned-up version of the model's report.

The same rule applies to evaluator mistakes. When an evaluator makes an incorrect claim, the correction is recorded without hiding the original error. This is especially important in the AI Conversation Review, where source-report errors and second-order evaluation errors are different findings.

## Historical and current-state claims stay separate

Current code can show what exists now. It cannot, by itself, prove what existed before a review, repair, or scope decision. Historical claims require contemporaneous records or remain labeled as inference, report, or unverified.

## Claim limits

Results are attached to the task version, run set, model route, provider path, configuration, and evaluation method that produced them. The repository does not turn a few trials into a general leaderboard or a permanent judgment about a model family.

Cost and runtime are reported as observed values. They are not treated as stable model properties because pricing, caching, provider behavior, harness configuration, and service conditions can change.

## Sanitization does not erase technical evidence

Public trial records remove credentials, personal identity, private slugs, host paths, and unrelated machine state. They retain the task-relative paths, container paths, commands, errors, scores, timings, model labels, and artifacts needed to understand the result unless a specific value creates a privacy or security risk.

The private originals remain unchanged so the sanitized copies can be checked against them.
