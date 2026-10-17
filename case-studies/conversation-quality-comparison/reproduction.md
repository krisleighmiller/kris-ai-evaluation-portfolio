# Reproducing the AI Conversation Review

You supply OpenCode, your hardware, and your own provider credentials. This repository supplies the task files and recorded outputs for comparison.

## Produce a new report

1. Install OpenCode v2.
2. Create a new empty project directory.
3. Copy [`context`](context/) into that directory as `context/`.
4. Copy [`prompt.md`](prompt.md) to the project root.
5. Verify the 15 context-file hashes against [`manifest/context-manifest.json`](manifest/context-manifest.json).
6. Start a fresh OpenCode instance in the project directory and select the model route you want to test.
7. Submit the text of `prompt.md` exactly as written.
8. Preserve the resulting report before making corrections or exposing the instance to the answer key.
9. Compare the report with the corresponding artifact under [`trials`](trials/) and with [`analysis/model-trial-comparison.md`](analysis/model-trial-comparison.md).

The prompt asks the model to create its final document in the work directory. A Markdown or Word result can satisfy that instruction. File format differences should not be treated as substantive model differences unless they affect readability or required content.

## Evaluate a report

Use a different fresh OpenCode instance. Give that instance the completed report, the same 15 context files, and [`answer-key/answer-key.md`](answer-key/answer-key.md). Ask it to evaluate the report against the key and verify material assertions against the supplied records. Do not reuse the report-producing instance.

The archived evaluations used `openrouter/z-ai/glm-5.3` with the `high` variant in OpenCode 2.0.29. Reproduction with another OpenCode version, provider route, model revision, tool policy, or reasoning setting may differ.

## Compare results responsibly

The public context is semantically equivalent to the private run input, but not byte-identical: the public EML files use reserved domains, and PDF metadata was scrubbed. PDF page text, CSV contents, dates, case IDs, session IDs, and member IDs are unchanged.

One run per primary route cannot establish a stable model ranking. Record your OpenCode version, provider/model route, date, and relevant run settings so differences can be interpreted.
