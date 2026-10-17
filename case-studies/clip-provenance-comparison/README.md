# Clip Provenance Workflow Comparison

Three frontier-model workflows received the same bounded assignment: match 200 transformed clips against 45 possible source videos, report the source and start time where supported, reject clips from outside the library, and explain how the result was validated.

This is an evaluation of end-to-end technical work, not a chat-answer comparison. Each workflow had to inspect media, design and implement a pipeline, establish confidence rules, validate the method, and leave an auditable result.

## What was controlled

- Each trial ran in a separate OpenCode 2.0.29 instance.
- Each instance received a byte-identical copy of the 45 masters and 200 clips.
- Each instance received the same [client brief](prompt.md). The only run-specific addition directed the agent to keep its work inside its assigned trial directory.
- The agents did not receive the generator records, answer key, another trial's output, or another trial's working state.
- The media corpus was generated deterministically from documented public-domain source material.

The exact OpenCode model and provider routes are recorded in each trial directory. OpenCode, provider accounts, credentials, caches, local databases, and machine details are not part of this repository.

## Verified outcomes

The scorer uses 160 genuine clips and 40 clips from outside the supplied master library. A genuine result is jointly correct when it names the correct master and places the start within the 1.5-second inclusive tolerance.

| Saved snapshot | Accepted correct source + time | Correct proposed source + time across genuine clips | Explicit foreign rejection | Genuine clips unidentified |
| --- | ---: | ---: | ---: | ---: |
| DeepSeek completed | 151/151 | 160/160 | 22/40 | 0 |
| Astra completed | 137/137 | 159/160 | 40/40 | 0 |
| Kimi round 2 refined | 133/134 | 139/160 | 34/40 | 19 |
| Kimi round 3 checkpoint | 132/136 | 141/160 | 14/40 | 10 |

“Accepted” follows each workflow's own published labels: DeepSeek's `confident` and `likely` tiers, and the `confident` tier for Astra and Kimi. “Proposed” additionally includes uncertain candidates. The terminology is normalized only for scoring; the native labels remain in every saved result.

The useful tradeoff is visible in the full evidence. DeepSeek proposed the correct source and time for every genuine clip but left 18 foreign clips in its uncertain queue. Astra rejected every foreign clip and proposed the correct source for all genuine clips, while one uncertain timing estimate missed the evaluator tolerance. Kimi's later checkpoint recovered more genuine clips than round two, but it also admitted two foreign clips into the accepted tier and rejected fewer foreign clips. The two Kimi checkpoints are therefore evidence of a changed, unfinished workflow—not two independent trials.

See the [comparison report](comparison.md) for the complete interpretation and [verification summary](results/verification-summary.md) for the metric definitions.

## Evidence map

| Evidence | Location |
| --- | --- |
| Exact shared brief | [prompt.md](prompt.md) |
| Context asset, hashes, and retrieval instructions | [context/README.md](context/README.md) |
| Source and rights provenance | [context/SOURCE_PROVENANCE.md](context/SOURCE_PROVENANCE.md) |
| Portable answer key | [answer-key/README.md](answer-key/README.md) |
| Evaluator rules and raw aggregate scoring | [evaluator/README.md](evaluator/README.md) |
| Reproducible scorer and regression tests | [verification/README.md](verification/README.md) |
| DeepSeek report, results, scripts, and run card | [trials/deepseek/README.md](trials/deepseek/README.md) |
| Astra report, results, validation records, selected panels, scripts, and run card | [trials/astra/README.md](trials/astra/README.md) |
| Kimi stopped-run checkpoints, scripts, and run card | [trials/kimi/README.md](trials/kimi/README.md) |
| Row-level verified results | [results/verification-results.json](results/verification-results.json) |

## Recreate the evaluation

1. Download `clip-provenance-context-v1.0.0.zip` from the repository's `v1.0.0` GitHub Release.
2. Verify the archive and extracted files using [context/README.md](context/README.md).
3. Create a clean trial directory containing only the extracted `masters/` and `clips/` folders.
4. Start a fresh OpenCode instance in that directory with your own provider credentials.
5. Submit [prompt.md](prompt.md), adding only an instruction to keep work inside the current trial directory if needed.
6. Preserve the resulting report, scripts, and machine-readable decisions. Do not expose the answer key until the run is finished.
7. Add a format adapter to the standalone scorer or convert the result into one of the documented native schemas, then compare the new output with the recorded trials.

Exact numerical reproduction is not guaranteed across different model snapshots, provider routes, OpenCode versions, or hardware. The repository supplies the original input package, prompt, saved work products, truth, and evaluation logic so those differences can be measured rather than hidden.

## Claim boundary

This case study supports conclusions about three recorded workflows on one constructed corpus. It does not establish a universal ranking of model families. Current model names are factual run metadata, and all findings remain attached to the saved artifacts evaluated here.
