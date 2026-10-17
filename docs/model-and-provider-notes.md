# Model, Provider, Cost, and Runtime Notes

A model name is only part of a run's identity. The provider route, model revision or alias, reasoning settings, context limits, caching behavior, tool interface, execution environment, and date can all affect the observed result.

## Model route versus model family

The case studies report the route used in the recorded run when that information survives and is safe to publish. A result should be read as evidence about that route under the recorded conditions, not as a timeless property of every deployment carrying a similar model name.

Provider aliases can move. Hosted models can change behind an alias. Two providers may expose different defaults, tool-call behavior, context handling, or revisions. For this reason, the trial metadata is part of the evidence rather than a footnote.

## Cost

Recorded cost can depend on:

- provider pricing at the time of the run;
- whether cached input received a different rate;
- how the provider counted input, output, reasoning, or tool tokens;
- retries and failed requests;
- execution-layer accounting; and
- whether a run ended early.

The case studies report observed cost and explain the available accounting fields. They do not retroactively price every run under a new rate card.

Cost per successful deliverable can be more useful than cost per attempt when failures are common, but both figures need the same clearly defined trial boundary.

## Runtime

Elapsed workflow time includes more than model generation. Tool execution, container startup, file processing, retries, network delay, provider queues, and verification can all contribute.

These projects do not claim to benchmark inference latency or hardware throughput. They report end-to-end workflow time where it helps explain the practical result. Hardware specifications are intentionally outside the publication package.

## Execution environment and configuration effects

Harbor supplies the controlled task execution and verification path for the terminal benchmarks. OpenCode v2 supplied the working environment for the two model-comparison studies. A different runner, tool policy, timeout, reasoning setting, or provider configuration may produce a different result even when the prompt and nominal model name match.

The reproduction goal is procedural: use the published task or context, preserve the stated controls, record the new configuration, and compare the new evidence with the original evidence. An exact duplicate output is not expected.

## Why one study uses lower-tier models

The AI Conversation Review intentionally asks whether lower-tier options can produce defensible professional analysis and where oversight remains necessary. It is not a frontier-model shootout, and the absence of a frontier route is not missing data. Changing that comparison set would answer a different question.

The other three completed evaluations use frontier-model routes because their questions and original run designs called for them. The repository preserves those original boundaries instead of rerunning models to make the projects look symmetrical.
