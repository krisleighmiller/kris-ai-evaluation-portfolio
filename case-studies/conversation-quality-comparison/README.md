# AI Conversation Review

This case study compares three lower-tier model routes on one synthetic professional-review task. Each model received the same 15-file context and exact prompt in a separate OpenCode v2 instance, then a separate GLM instance evaluated the completed report against a fixed qualitative answer key.

**All people, organizations, conversations, identifiers, contracts, service records, and events in the context are synthetic. No client or real member data appears in this package.**

## Research question

Can lower-tier models produce a defensible clinical-quality and contract review of 100 synthetic AI-user conversations, and where does human verification remain necessary?

The comparison intentionally does not include a frontier model. Adding one would change the question rather than complete a missing trial.

## Primary trials

| Trial | Report route | Report | GLM evaluation |
| --- | --- | --- | --- |
| Luna rerun | `openrouter/openai/gpt-6-luna` | [Report](trials/luna-rerun/report.md) | [Evaluation](trials/luna-rerun/evaluation.md) |
| Haiku 5.5 | `openrouter/anthropic/claude-haiku-5.5` | [Report](trials/haiku-5-5/report.md) | [Evaluation](trials/haiku-5-5/evaluation.md) |
| Qwen3.8 Flash | `openrouter/qwen/qwen3.8-flash` | [Report](trials/qwen-3-8-flash/report.md) | [Evaluation](trials/qwen-3-8-flash/evaluation.md) |

All six primary report/evaluation instances used OpenCode 2.0.29 on 15 October 2026. The GLM route was `openrouter/z-ai/glm-5.3` with the `high` variant. Each trial directory contains a sanitized `metadata.json` record; no OpenCode configuration or state is published.

The Luna rerun is the primary Luna artifact. An earlier Luna attempt informed calibration and is described separately in [calibration history](analysis/calibration-history.md).

## Findings

All three reports found the central C016 safety failure and the principal quality problems. None fully satisfied the answer key.

- Luna's rerun required the narrowest factual correction set, but it mislabeled C016's selection route and omitted important member-level sampling limitations.
- Haiku provided a complete 100-case inventory, but it invented a C035 defect, misread other cases, and reported summary counts that do not match its own inventory.
- Qwen produced the clearest future change-control plan, but it made unsupported population claims and several false operational-link assertions.

GLM caught important errors and the shared contractual omissions, but it also missed overclaims, sometimes awarded more credit than its own detailed findings supported, and introduced a factual error about C076 feedback. The result supports GLM as an assisted reviewer with human source verification, not as the sole final grader.

See the [final model comparison](analysis/model-trial-comparison.md), [GLM evaluation review](analysis/glm-evaluation-review.md), and [findings register](analysis/findings-register.md).

## Package map

- [`prompt.md`](prompt.md) is the exact prompt submitted to each report model.
- [`context/`](context/) contains the 15-file sanitized synthetic context.
- [`answer-key/`](answer-key/) contains the fixed qualitative key and calibration explanation. It was not model-visible during report generation.
- [`trials/`](trials/) separates primary model reports, GLM evaluations, and run metadata.
- [`analysis/`](analysis/) contains Kris's final synthesis, evaluator review, calibration history, and verified findings register.
- [`methodology.md`](methodology.md) explains the run design and evidence layers.
- [`reproduction.md`](reproduction.md) gives a clean-room OpenCode procedure.
- [`limitations.md`](limitations.md) defines what the trial can and cannot establish.
- [`PROVENANCE.md`](PROVENANCE.md) records sanitization and document conversion.
- [`manifest/`](manifest/) contains context and package checksums.

## Claim boundary

The results describe three outputs on one constructed task. They do not establish a stable ranking of the model families, a general error rate for GLM, or expected performance on unrelated work. A reproduction may differ with another OpenCode version, provider route, model revision, reasoning setting, tool policy, or run.

See the repository-wide [evidence and claim policy](../../docs/evidence-and-claim-policy.md) and [model and provider notes](../../docs/model-and-provider-notes.md).
