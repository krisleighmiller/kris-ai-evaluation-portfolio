# Trial Evidence

The evidence is divided into a balanced comparison, two exploratory trials, and validation history.

## Balanced comparison

[`balanced/`](balanced/) contains 15 trials: five each for Astra, DeepSeek, and Kimi. Every trial directory entry includes:

- the exact submitted `linkbench` executable script; and
- the CTRF verifier report produced for that artifact.

All 15 trial locks recorded the shared task digest `sha256:44a28ec01f8faecf4bb0a706e1b841fb6f2ffcb33daeaa1d3d416a1db09e9763`, OpenCode `1.19.0`, Docker execution, no trajectory resume, and a separate verifier environment.

## Exploratory trials

[`exploratory/`](exploratory/) contains one Qwen3.7 Plus trial and one earlier DeepSeek V4 Pro trial. They used the same recorded task digest but are excluded from balanced rates because there is only one trial in each exploratory route set.

## Validation

[`validation/`](validation/) contains four structured task-quality reports, the minimal record of an earlier malformed check response, the reconstructed historical Oracle record, and the fresh public-package Oracle verification. None enters the model-performance denominator.

## Sanitization

Random local trial slugs were replaced with stable public IDs. Raw trajectories, local OpenCode databases, provider configuration, credentials, caches, duplicated fixtures, and machine paths are excluded. Scores, test traces, timestamps, route names, usage, cost, artifact bytes, and artifact hashes remain intact.

[`../results/trial-summary.csv`](../results/trial-summary.csv) maps every public ID to its category and recorded outcome without exposing its local slug.
