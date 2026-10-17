# Independent AI Evaluation for Specific Business Tasks

I design controlled experiments to investigate how selected AI models perform on your task: what they get right, how they fail, and where human verification remains necessary. My work includes alternative and lower-cost models, not only frontier systems.

You receive an evidence-backed report of tested capabilities, failure patterns, costs, and limitations—not a guarantee of production performance.

## What this portfolio demonstrates

| Project | Consulting capability it demonstrates |
| --- | --- |
| [AI Conversation Review](case-studies/conversation-quality-comparison/) | Checking professional analysis against source records and assessing the reliability of AI-assisted review. |
| [Broadcast Conform](case-studies/broadcast-conform/) | Turning detailed deliverable requirements into objective acceptance checks. |
| [Clip Provenance](case-studies/clip-provenance-comparison/) | Comparing accuracy, uncertainty handling, coverage, and remaining review work. |
| [Linker Performance Harness](case-studies/linker-performance-harness/) | Detecting misleading measurements and verifying the evidence behind a performance claim. |
| [Agent Engineering Loops](case-studies/agent-engineering-loops/) | Examining whether completion claims are supported by actual acceptance evidence. |

## How I work

I turn ambiguous claims about model capability into evidence that can be checked: explicit tasks, controlled runs, objective or structured evaluation, failure analysis, and conclusions that stay inside the limits of the data.

This repository contains four completed evaluations and one observational engineering study. The work covers terminal benchmarks, model comparisons, verification design, synthetic evaluation data, run isolation, cost and runtime analysis, and review of agent claims during software development.

## Completed evaluations

| Case study | Problem | Method | Recorded result | Evidence |
| --- | --- | --- | --- | --- |
| [Broadcast Conform](case-studies/broadcast-conform/) | Can an agent deliver a technically valid broadcast-conform package rather than a file that only looks plausible? | A Harbor task with synthetic footage, a reference solution, 15 binary verifier checks, and 20 scored trials across four model routes. | The four routes scored 0/5, 4/5, 5/5, and 5/5. The failures differed in mechanism, elapsed time, token use, and cost. | Runnable task package, model trials, Oracle run, task-quality checks, verifier results, and failure analysis. |
| [Linker Performance Harness](case-studies/linker-performance-harness/) | Can an agent build a harness that follows an authenticated controlled protocol instead of producing a convincing but invalid benchmark? | A Harbor task with native workloads, hidden verification, 15 balanced trials across three model routes, and two separate exploratory trials. | The balanced routes scored 3/5, 2/5, and 0/5. Every failed balanced submission broke the controlled protocol, but for different implementation reasons. | Runnable task package, balanced and exploratory trials, Oracle evidence, check history, and protocol-level failure analysis. |
| [Clip Provenance Workflow Comparison](case-studies/clip-provenance-comparison/) | How do independently developed agent workflows differ when matching transformed clips to source media? | Three isolated OpenCode v2 instances received the same brief and the same set of 45 masters and 200 clips. Their work products were evaluated against withheld construction records. | The agents produced materially different visual and audio pipelines, confidence schemes, validation practices, and stopping behavior. | Shared context and prompt, per-run work products, evaluator records, representative evidence, and a cross-workflow comparison. |
| [AI Conversation Review](case-studies/conversation-quality-comparison/) | Can lower-tier models produce a defensible professional review of a 100-conversation synthetic dataset? | Three isolated OpenCode v2 instances received the same context and prompt. Their reports were checked against a fixed answer key and then reviewed for evaluator error. | Each report contained useful analysis, but the models differed in factual accuracy, grading judgment, evidence use, and the amount of oversight needed. | Synthetic context, exact prompt, answer key, three primary reports, evaluator reports, and final comparison. |

## Observational engineering study

| Case study | Question | Method | Supported finding | Evidence treatment |
| --- | --- | --- | --- | --- |
| [Evaluating Agent Engineering Loops](case-studies/agent-engineering-loops/) | How well did several agent runs carry bounded engineering tasks through implementation, verification, review, and recovery? | Three episodes reconstructed from contemporaneous private records, with agent claims separated from verified outcomes and human interventions marked explicitly. | The selected runs include premature completion, incomplete verification, correction after challenge, and deliberate scope control. Conclusions apply to these runs, not to the models in general. | Product-abstracted narrative and opaque evidence references. The private application, code, prompts, conversations, and source crosswalk are not published. |

## How the evaluations were run

The two terminal benchmarks use [Harbor](https://docs.harborframework.com/). Their published task directories include the instruction, task configuration, environment definition and inputs, reference solution, and verifier. Model trials, Oracle runs, and task-quality checks are separate evidence categories.

The two model comparisons use [OpenCode v2](https://opencode.ai/v2/docs/). Every compared model ran in a separate OpenCode instance against its own copy of the same context and the same prompt. One model's working state was not imported into another model's run.

This repository does not distribute Harbor, OpenCode, API credentials, provider configuration, or a copy of my computer environment. Reviewers install the relevant application, provide their own hardware and API access, and run the published task or context package. See [Reproducing the evaluations](docs/reproducing-the-evaluations.md).

## How to read the results

- A passing artifact is not automatically a good process, and a polished report is not automatically correct.
- Model, provider route, configuration, caching, pricing, and the execution environment can affect cost and runtime.
- Oracle runs and task-quality checks validate an evaluation; they are not included in model pass-rate denominators.
- Small trial sets support findings about these tasks and runs. They do not establish universal model rankings.
- The AI Conversation Review intentionally examines lower-tier options. A frontier-model comparison is outside that study's question.
- Synthetic data and generated workloads are labeled. The Clip Provenance source media has a documented public-domain provenance chain.

## Documentation

- [Evaluation methodology](docs/evaluation-methodology.md)
- [Evidence and claim policy](docs/evidence-and-claim-policy.md)
- [Model, provider, cost, and runtime notes](docs/model-and-provider-notes.md)
- [Reproducing the evaluations](docs/reproducing-the-evaluations.md)

## Publication status

The writing in this repository is a working draft. The evidence packages are being copied from a private source archive, sanitized, checked against their original records, and added case by case. A page describes planned evidence only when that evidence has already been located and classified; it does not mean the public package has passed its final release audit.

