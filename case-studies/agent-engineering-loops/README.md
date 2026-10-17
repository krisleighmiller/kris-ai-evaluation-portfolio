# Evaluating Agent Engineering Loops

**Status:** Approved for private staging. Product details and primary records remain private.

## The question

I wanted to know whether an AI agent could carry a bounded engineering task through implementation, verification, review, and recovery—not merely produce a convincing completion report.

This is an observational study of three engineering episodes from an unfinished private desktop application. The application is not the subject of the study. The subject is the work loop: what the agent was assigned, what it did, what it claimed, what review found, how I intervened, and what the retained evidence finally supports.

## What this demonstrates

This study demonstrates how I examine whether an agent's completion claims are supported by acceptance evidence, separate reported status from verified outcomes, and document human intervention without disclosing the private product under development.

## What I found

The strongest signal was not whether an agent wrote working code. All three episodes produced useful implementation work. The stronger discriminator was whether the run could establish that the intended behavior worked across the real boundary under review.

- A passing test suite did not prove that a wider milestone was complete.
- Component coverage did not prove a connected workflow.
- Reaching an authorization step did not prove successful completion after authorization.
- Independent review improved the work only when its findings were converted into bounded repair tasks and re-verified.
- Human intervention was most valuable when it challenged the evidence behind a claim, not when it prescribed every implementation detail.

The final result is not “one model won.” It is a record of three particular runs, with different models, prompts, starting states, and review conditions.

## Episode map

| Episode | Run metadata | Evaluation focus | Final supported status |
| --- | --- | --- | --- |
| [A — Scope, review, and deliberate deferral](episodes/episode-a-scope-review-deferral.md) | DeepSeek V4 Pro, GPT-6 Sol, GPT-5.6 Sol, plus delegated reviewers | Whether implementation progress supported completion of a larger milestone | Useful work was retained; the larger milestone remained incomplete and advanced scope was deliberately deferred. |
| [B — Integration and acceptance verification](episodes/episode-b-integration-acceptance.md) | Qwen3.8 Flash plus delegated reviewers | Whether criterion-level work and component tests established one connected workflow | A connected verification path and missing host-level checks were added; final acceptance was supported for the bounded scope. |
| [C — Verification challenge and recovery](episodes/episode-c-verification-recovery.md) | GLM-5.3, Kimi K3, plus delegated reviewers | Whether a completion claim survived stronger visual and behavioral verification | The first sign-off did not survive review. Reproduced failures were repaired, re-tested, independently reviewed, and saved in a clean checkpoint. |

## How to read the evidence

Every material statement is tied to an opaque evidence ID. The public [evidence index](evidence-index.md) describes what kind of record supports the statement and how strong that support is. The private crosswalk maps those IDs to exact messages, saved changes, test output, and artifacts.

The raw repository, conversations, screenshots, prompts, and crosswalk are intentionally excluded because they would disclose the private application. This is therefore an audit of evaluation method and claim discipline, not a reproducibility package for the application itself.

Read next:

- [Methodology and claim labels](methodology.md)
- [Public evidence index](evidence-index.md)
- [Practical checklist for agent engineering loops](practical-checklist.md)
- [Limitations](limitations.md)

## Closing assessment

### What worked under the tested conditions

All three episodes produced useful implementation work. In the bounded scopes that reached acceptance, review findings were converted into specific repair tasks and followed by stronger verification. Deliberate deferral also worked when the retained evidence did not support claiming completion of the larger milestone.

### What failed

Initial completion claims did not always survive review. The episodes include a passing test suite that did not establish a wider milestone, component-level checks that did not prove a connected workflow, and a sign-off that stopped at an authorization boundary before the full behavior had been verified.

### What required human verification

Human verification was required to challenge the evidence behind completion claims, reproduce failures, distinguish implemented components from accepted workflows, direct bounded repair work, and decide when the supported outcome was completion, correction, or deferral.

### What remains untested

This is an observational study of three selected episodes, not a controlled comparison of models or prompting strategies. It does not test unattended long-duration operation, generalize to other products or engineering domains, or publish enough of the private application for an independent full replay.

### What these findings could inform

The findings could inform definitions of done for agent work, acceptance gates for delegated engineering tasks, evidence-retention practices, reviewer handoffs, and decisions about when an autonomous workflow still requires human challenge or recovery.

