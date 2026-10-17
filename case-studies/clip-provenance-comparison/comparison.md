# Comparing the three workflows

## Evaluation question

How well did each recorded workflow carry a difficult media-provenance task through method design, implementation, validation, uncertainty handling, and delivery?

The comparison is not a single accuracy leaderboard. The workflows defined confidence differently and made different tradeoffs between coverage and restraint. The evaluator therefore preserves each native tier, then applies shared source and timing checks to the saved artifacts.

## Shared task and ground truth

All three workflows received the same [client brief](prompt.md), 45 masters, and 200 transformed clips. Of those clips, 160 came from the supplied master library and 40 came from held-out material. The transformations included crop, resize, re-encoding, overlays, color changes, modest speed changes, and removed or replaced audio.

The answer key came from the deterministic corpus generator. It was not inferred from majority agreement between models and was not visible during the trials. The evaluator requires exact clip coverage, checks source identity, applies a 1.5-second inclusive start-time tolerance, and treats foreign rejection separately from genuine-clip matching.

## Method differences

| Workflow | Core retrieval and alignment | Independent or supporting checks | Confidence design |
| --- | --- | --- | --- |
| DeepSeek | Multi-feature perceptual frame fingerprints, sequence alignment, and a search over playback ratios | Audio-spectrum correlation; generated positive and foreign controls | `confident`, `likely`, `uncertain`, `not-identified` based on visual uniqueness and audio evidence |
| Astra | RootSIFT/FLANN retrieval, affine geometric verification, sequence support, and dense local clock refinement | Development controls, held-out controls, source-withheld negatives, input decode/hash audit, selected visual review | Separate source and timing gates; `confident`, `uncertain`, `unidentified` |
| Kimi | Perceptual-hash voting, luma template verification, ORB recovery, then temporal refinement | Generated controls, audio check, and visual spot checks were developed during the run | `confident`, `uncertain`, `unidentified`; thresholds and recovery logic continued changing before the stop |

These are materially different implementations. DeepSeek used audio as corroboration. Astra excluded audio so that missing or replaced tracks could not influence a match. Kimi broadened visual recovery iteratively and had not finished reconciling the consequences when the run stopped.

## Verified outcomes

| Measure | DeepSeek completed | Astra completed | Kimi round 2 refined | Kimi round 3 checkpoint |
| --- | ---: | ---: | ---: | ---: |
| Accepted rows | 151 | 137 | 134 | 136 |
| Correct accepted sources | 151 | 137 | 134 | 134 |
| Correct accepted source + time | 151 | 137 | 133 | 132 |
| Accepted source precision | 100.0% | 100.0% | 100.0% | 98.5% |
| Accepted source + time precision | 100.0% | 100.0% | 99.3% | 97.1% |
| Genuine source + time recall from accepted rows | 94.4% | 85.6% | 83.1% | 82.5% |
| Correct proposed genuine sources | 160/160 | 160/160 | 140/160 | 144/160 |
| Correct proposed genuine source + time | 160/160 | 159/160 | 139/160 | 141/160 |
| Explicit foreign rejection | 22/40 | 40/40 | 34/40 | 14/40 |
| Uncertain queue | 27 | 23 | 13 | 40 |
| Genuine clips unidentified | 0 | 0 | 19 | 10 |

The complete canonical row-level evidence is in [verification-results.json](results/verification-results.json). The original evaluator output is retained separately in [all-trial-scoring.json](evaluator/all-trial-scoring.json). The table can be regenerated from the included scorer rather than trusted as prose.

## Findings

### DeepSeek: broad genuine coverage with uncertainty concentrated on foreign clips

Every genuine clip had the correct proposed source and a start within tolerance. The accepted set was also clean: all 151 accepted rows had the correct source and time. The remaining nine genuine clips were held as uncertain rather than accepted.

The weaker side of the result was foreign rejection. Twenty-two of 40 foreign clips were explicitly rejected, while the other 18 appeared in the uncertain queue with unsupported candidate sources. That is not the same as a false accepted match, but it leaves more manual review work and makes the meaning of “uncertain” important.

### Astra: strongest foreign rejection and a deliberately narrower accepted set

Astra explicitly rejected all 40 foreign clips and proposed the correct source for every genuine clip. Its accepted set contained 137 rows, all with the correct source and time. Of 23 uncertain genuine rows, 22 were also within the timing tolerance; one source was correct but the start estimate missed by 8.509 seconds.

The trial's validation package was the most structured of the three: it separated development controls from held-out controls, used source-withheld negatives to test forced matching, and recorded input integrity and timeline-boundary checks. Those controls do not prove accuracy on unseen corpora, but they make the reasoning behind the conservative confidence boundary easier to audit.

### Kimi: useful engineering work, but the later checkpoint shows why completion state matters

Round two accepted 134 rows and had one accepted timing miss. It explicitly rejected 34 foreign clips but left 19 genuine clips unidentified. Round three recovered some genuine coverage, yet it also accepted two foreign clips, increased the uncertain queue from 13 to 40, and reduced explicit foreign rejection to 14/40.

That change is the central Kimi finding. More recovery activity did not translate cleanly into a stronger deliverable. The run was still modifying retrieval and decision thresholds and never produced a reconciled final report. Its scripts and checkpoints remain valuable engineering evidence, but “latest file” cannot be treated as “finished result.”

## Representative evidence

The Astra package contains paired clip/source panels for every row in its 23-item review queue, plus one accepted and one unidentified example. These panels make the confidence boundary visible:

- [accepted transformed match: clip 000](trials/astra/report/evidence/clip_000.jpg)
- [source match with weaker timing evidence: clip 080](trials/astra/report/evidence/clip_080.jpg)
- [unidentified foreign clip: clip 002](trials/astra/report/evidence/clip_002.jpg)

The panels are supporting review evidence, not the evaluator truth. The source and timing metrics come from the generator-derived answer key.

## What Kris designed and verified

Kris designed the shared task and deterministic corpus, ran the isolated OpenCode trials, preserved the work products, selected the canonical checkpoints, adapted the terminal-benchmark verification logic to the three native schemas, and checked the reported comparisons against row-level truth. Model-generated methods and reports remain identified as trial artifacts; the cross-run interpretation and claim boundaries are the portfolio owner's work.

## Limits

- This is one constructed corpus, not a representative sample of all video-provenance work.
- Model routes identify the recorded runs, not immutable model families. Provider behavior and model snapshots can change.
- The timing tolerance is an evaluation rule, not a claim of frame-accurate forensic certainty.
- Confidence labels are not calibrated probabilities and are not directly interchangeable across workflows.
- The Kimi checkpoints come from one manually stopped run, not two independent observations.
- Generated controls test known transformations but do not cover every possible edit, montage, reversal, rotation, nonlinear time warp, or missing-source condition.
- A fresh replay may differ because OpenCode, provider routes, and models can change. The package is designed to expose those differences.

## Reproduction

Use [context/README.md](context/README.md) to retrieve and verify the exact media. Run the [shared prompt](prompt.md) in a fresh isolated directory, preserve the resulting work products, and keep the [answer key](answer-key/README.md) unavailable until the run is complete. Then use [verification/README.md](verification/README.md) to score and compare the new result.

## Closing assessment

### What worked under the tested conditions

All three workflows produced useful matching systems from the same brief and media. DeepSeek proposed the correct source and time for all 160 genuine clips, while Astra explicitly rejected all 40 foreign clips and maintained a clean accepted set. The shared scorer made the different confidence schemes comparable without replacing their native labels.

### What failed

No workflow dominated every measure. DeepSeek left 18 foreign clips in its uncertain queue, Astra had one uncertain timing estimate outside tolerance, and Kimi's unfinished recovery work reduced foreign rejection and introduced two accepted foreign clips in its later checkpoint. Greater recovery activity did not automatically produce a stronger deliverable.

### What required human verification

Human verification was required to select the appropriate saved checkpoints, adapt the three output schemas to one scorer, inspect row-level disagreements, distinguish foreign rejection from uncertain matching, and interpret the review burden behind each confidence label. Representative panels supported review but did not replace generator-derived truth.

### What remains untested

The comparison does not cover unseen media collections, every possible transformation, repeated independent runs, additional model routes, or later versions of the models and OpenCode. The confidence labels are not calibrated probabilities, and the timing rule does not establish frame-accurate forensic certainty.

### What these findings could inform

The findings could inform model and workflow selection for media-provenance work, confidence-threshold design, staffing for manual review queues, and evaluation plans that measure accepted accuracy, coverage, foreign rejection, and unresolved work separately.
