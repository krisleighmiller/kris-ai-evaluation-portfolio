# Evaluation Methodology

The projects in this repository ask different questions, but they follow the same basic discipline: define the task, control what can reasonably be controlled, preserve the run record, verify the deliverable, and limit the conclusion to the evidence collected.

## Start with the decision being tested

Each evaluation begins with a concrete question. The unit of analysis may be a submitted artifact, a complete agent workflow, or a bounded engineering episode. The scoring method must match that unit.

A terminal benchmark can often use executable checks. A professional report may require a structured answer key and a separate factual review. An observational case study needs a chronological evidence chain and clear labels for what was observed, reported, inferred, or left unverified.

## Define the comparison set before calculating results

Primary trials, exploratory trials, validation runs, and aborted attempts answer different questions. They remain separate in the published record.

- **Primary model trials** form the stated comparison set.
- **Exploratory trials** may inform later work but do not enter balanced pass rates.
- **Oracle runs** test whether the reference solution can satisfy the verifier.
- **Task-quality checks** assess the task definition and grading design.
- **Operationally aborted attempts** document execution history but do not count as model or task failures when evaluation never began.

This prevents a convenient denominator from replacing the actual experiment.

## Repeat trials when the question concerns reliability

The Harbor case studies use repeated trials because one success or failure does not show how reliably a route handles the task. Results report the observed trial count and do not inflate a small sample into a population-wide claim.

The OpenCode studies compare complete work products produced by isolated instances. Those runs are expensive and artifact-heavy, so the analysis emphasizes methods, factual accuracy, evidence quality, and failure modes rather than pretending a few workflows establish a stable ranking.

## Keep model-comparison runs isolated

Every run in the two OpenCode comparisons used a separate OpenCode v2 instance and a separate copy of the same supplied context. Each instance received the same project prompt. No compared model received another model's working state or output.

The evaluator-facing answer key and scoring material remain separate from the model-visible context. Published directory layouts preserve that separation.

## Verify the deliverable, not its appearance

The evaluation target is the requested outcome. A file can exist, a program can run, or a report can sound confident while still failing the task.

The Harbor tasks therefore use executable verifiers and controlled task environments. Where a binary score hides useful information, the case study also records which criterion failed and why. The model-comparison studies check claims against withheld construction records, a fixed answer key, or both.

## Investigate failure mechanisms

Two submissions can fail the same test for different reasons. The analysis preserves those differences when the evidence supports them. Examples include an invalid implementation strategy, a broken protocol, insufficient validation, a factual error, an incomplete report, or a correct observation paired with an unsupported conclusion.

Failure analysis is kept separate from speculation. If the available record cannot establish a cause, the cause remains unverified.

## Record configuration and execution context

Each released case study should identify the task or context version, model route, relevant execution settings, trial category, date, result, runtime, token counts, and recorded cost when those fields exist and are safe to publish.

Hardware inventories and machine-specific state are excluded because these projects evaluate task performance rather than hardware performance. A future inference-performance project would require a different standard, including a full configuration fingerprint and hardware telemetry.

## Preserve corrections

The public narrative may correct a working report, but it does not silently rewrite a model artifact into a better answer. Original outputs are preserved as trial evidence after sanitization. Corrections, evaluator disagreements, and later findings appear in separate review material.

## State what the evidence does not prove

Each case study has a limitations page. Common limits include small samples, provider and route effects, incomplete historical records, manual review judgment, external software versions, and the difference between reproducing an evaluation procedure and reproducing an identical output.
