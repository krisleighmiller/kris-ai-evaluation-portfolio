# Kimi manually stopped trial

## Run card

- OpenCode version: 2.0.29
- OpenCode agent: `build`
- Provider route: OpenRouter
- Model route recorded by OpenCode: `moonshotai/kimi-k3`
- Started: 2026-10-15 19:41:28 UTC
- Last session update: 2026-10-15 22:52:25 UTC
- Status: manually stopped before a finished report was produced

This was a separate OpenCode instance with its own byte-identical copy of the shared context. The model did not receive the answer key or another trial's work.

## Why two checkpoints are published

The trial built a three-stage visual pipeline using perceptual-hash voting, luma template matching, and ORB retrieval, followed by refinement and supporting checks. It produced a usable refined round-two report, then continued broadening recovery in round three. The session was manually stopped before it reconciled the later changes into a final report.

Round three recovered more genuine clips, but evaluator scoring shows that it also moved two foreign clips into the accepted tier and reduced explicit foreign rejection from 34/40 to 14/40. Publishing only the terminal checkpoint would hide that regression; publishing only round two would hide the later work. Both are therefore labeled as checkpoints from one stopped run.

The top-level draft report from the private workspace is not published as a deliverable because it says its numbers remain to be finalized and leaves the final-results section unfilled. The public package instead includes:

- `round-2-report.json` and `.csv`: refined round-two output;
- `round-2-decisions.json` and `round-2-refined.json`: supporting round-two state;
- `round-3-decisions.json`: terminal saved decision checkpoint;
- `synthetic-validation-results.json`: saved generated-control results; and
- `pipeline/`: trial-generated implementation scripts.

Large signatures, indexes, inspection montages, raw process logs, repeated media, caches, and unfinished draft prose were excluded.
