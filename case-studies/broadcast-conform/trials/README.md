# Trial Evidence

This directory keeps performance trials and validation activity separate.

## Primary model trials

[`models/`](models/) contains 20 sanitized CTRF verifier reports: five each for Astra, DeepSeek, Kimi, and Qwen. The stable public IDs match [`../results/trial-summary.csv`](../results/trial-summary.csv).

The CSV preserves each trial's route, reward, test counts, failed-test names, recorded usage and cost, agent runtime, timestamps, historical task-checksum field, and submitted-master size and SHA-256 digest. Random local slugs were replaced with public IDs.

## Validation

[`validation/`](validation/) contains the Oracle verifier report, completed task-quality-check result, and a compact summary of both check attempts. Validation records do not enter model pass-rate calculations.

## Deliberate exclusions

The publication does not include raw agent trajectories, session identifiers, local runner logs, container state, credentials, provider configuration, caches, or duplicate copies of the task inputs. The 20 submitted masters are not duplicated into Git; their size and hash remain in the CSV, while the verifier reports preserve the auditable scoring outcome.

The untouched private archive remains available for checking the sanitized summaries against the source records.
