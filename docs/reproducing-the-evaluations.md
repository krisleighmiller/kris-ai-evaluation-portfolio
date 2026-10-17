# Reproducing the Evaluations

The public packages are designed so another person can rerun the evaluations without receiving my computer environment, credentials, or local application state.

## What this repository provides

For each Harbor benchmark:

- the task instruction and `task.toml`;
- the complete required `environment/`, including its Dockerfile and task inputs;
- the `tests/` verifier;
- the reference `solution/` used for Oracle validation;
- sanitized model, Oracle, and task-quality-check records; and
- results, limitations, and checksums.

This follows Harbor's task layout. Harbor describes a task as an instruction, environment, solution, and tests packaged as an independent directory. See the official [Harbor task overview](https://docs.harborframework.com/tasks/overview).

For each OpenCode comparison:

- one canonical sanitized context package;
- the exact published prompt;
- the answer key or evaluation method, kept outside the model-visible context;
- sanitized work products from each isolated run;
- compact run metadata; and
- the cross-run comparison and limitations.

OpenCode v2 is an external open-source application with its own installation and provider setup. See the official [OpenCode v2 documentation](https://opencode.ai/v2/docs/).

## What the reviewer provides

- their own hardware;
- a current Harbor or OpenCode installation;
- Docker or another environment runtime required by the selected task;
- their own API keys or local-model access; and
- a record of the model route, provider, configuration, date, runtime, tokens, cost, and any deviation from the published procedure.

The repository does not include application binaries, provider accounts, credentials, auth files, local databases, caches, or a hardware image.

## Harbor procedure

1. Install Harbor from its official documentation.
2. Copy the selected published task directory into a clean working location.
3. Verify the published checksums.
4. Inspect the task instruction, environment, verifier, and reference solution.
5. Configure a reviewer-owned model route and credentials.
6. Run the Oracle validation and task-quality checks separately from model trials.
7. Run the desired model trials without changing the published task package.
8. Record any local configuration differences.
9. Compare the new artifacts, verifier results, failure mechanisms, tokens, cost, and elapsed time with the published trials.

Do not add Oracle or check runs to the model-trial denominator.

## OpenCode procedure

1. Install OpenCode v2 from its official documentation.
2. Verify the context bundle and prompt checksums.
3. Create a fresh project directory and OpenCode instance for each model route.
4. Place an independent copy of the same context in each directory.
5. Provide the same published prompt to every instance.
6. Do not copy another model's state, report, working files, or evaluator material into the run.
7. Save the resulting report, scripts, tables, and evidence files.
8. Record the model route, provider, relevant configuration, OpenCode version, date, and execution totals.
9. Evaluate the new output against the published answer key or scoring method after the run is complete.

## Expected differences

Reproduction means repeating the procedure and comparing evidence. It does not guarantee byte-identical output. Hosted model aliases, provider implementations, prices, caches, service load, software versions, and nondeterministic generation can change.

If a new result differs, record the difference before interpreting it. A changed route or tool version may explain the outcome; it may also expose a useful reliability issue. The comparison is strongest when configuration differences are visible rather than smoothed away.

## Synthetic and public-domain material

Evaluation scenarios, generated workloads, structured records, transformations, labels, and ground truth are synthetic. Broadcast Conform's footage is owner-generated synthetic media. Clip Provenance uses a documented public-domain source chain for its seed media and synthetic transformations for the evaluation corpus. Each staged release package includes its specific provenance and checksum record.
