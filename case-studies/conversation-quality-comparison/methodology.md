# AI Conversation Review Methodology

## Research question

This study asks whether three lower-tier model routes can produce a defensible professional review of 100 synthetic AI-user conversations and related operational records. A frontier model is intentionally outside the comparison. Adding one would answer a different question.

## Controlled inputs

Each primary report used the same prompt and a byte-identical private copy of the same 15 source files. The source archive's relative-path-and-content aggregate SHA-256 is `41bfe58c56a28d58f9814d6186e24f6e5ba635b5bdaa01ad65c644840ed9ff73`. The public context makes only two publication transformations: synthetic email domains were moved to reserved `.example` domains, and PDF document metadata was removed. CSV values and PDF page content are unchanged.

The answer key and evaluator materials were not model-visible inputs. They appear in separate directories so a reviewer does not accidentally give the key to a report-producing model.

## Isolated OpenCode instances

Archived OpenCode records confirm separate OpenCode 2.0.29 instances for every primary report and every GLM evaluation. The records also establish the following routes. Session IDs, local paths, provider configuration, credentials, token totals, cost records, and OpenCode state are not published.

| Public trial | Role | Provider and model route | OpenCode | Local run date |
| --- | --- | --- | --- | --- |
| `cq-luna-rerun` | Primary report | `openrouter/openai/gpt-6-luna` | 2.0.29 | 2026-10-15 |
| `cq-luna-rerun-eval` | Report evaluation | `openrouter/z-ai/glm-5.3`, `high` variant | 2.0.29 | 2026-10-15 |
| `cq-haiku-5-5` | Primary report | `openrouter/anthropic/claude-haiku-5.5` | 2.0.29 | 2026-10-15 |
| `cq-haiku-5-5-eval` | Report evaluation | `openrouter/z-ai/glm-5.3`, `high` variant | 2.0.29 | 2026-10-15 |
| `cq-qwen-3-8-flash` | Primary report | `openrouter/qwen/qwen3.8-flash` | 2.0.29 | 2026-10-15 |
| `cq-qwen-3-8-flash-eval` | Report evaluation | `openrouter/z-ai/glm-5.3`, `high` variant | 2.0.29 | 2026-10-15 |

The initial Luna report and its evaluation also used separate OpenCode 2.0.29 instances and the same two Luna/GLM routes. They are calibration history, not primary comparison trials.

## Evaluation sequence

1. Start a separate OpenCode instance with one clean copy of the context and the exact prompt.
2. Run one assigned report model without the answer key or any other model's work.
3. Preserve the completed report as the model artifact.
4. Start a separate GLM instance with the report, context, and fixed answer key.
5. Preserve the GLM evaluation without editing its claims.
6. Verify material claims against the source files and record evaluator errors separately from report errors.
7. Compare the three primary reports qualitatively. Do not calculate an aggregate score or model-family ranking from one output per route.

## Evidence layers

The package keeps four layers distinct:

- `trials/*/report.md` contains the three primary model outputs.
- `trials/*/evaluation.md` contains the three GLM evaluations.
- `analysis/glm-evaluation-review.md` and `analysis/findings-register.md` review evaluator accuracy.
- `analysis/model-trial-comparison.md` is Kris's final cross-model synthesis.

Corrections are never inserted into a primary report or evaluator output. They appear in the analysis layer, where the reader can compare a claim with the original artifact and the fixed source record.
