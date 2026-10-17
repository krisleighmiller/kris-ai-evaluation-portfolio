# Luna Calibration History

The primary Luna artifact in this case study is the rerun in [`trials/luna-rerun`](../trials/luna-rerun/). An earlier Luna attempt is retained privately and is not a fourth primary trial.

The first attempt correctly identified the central C016 safety failure but introduced a nonexistent C038 numbering defect. Its GLM evaluation also applied an informal A-minus or roughly 90 percent judgment before the answer key explicitly prohibited numerical aggregation without an agreed scoring scheme. Those two issues prompted calibration revision 1 and a new Luna run.

Both the initial attempt and its evaluator ran in separate OpenCode 2.0.29 instances on 15 October 2026. The initial report used `openrouter/openai/gpt-6-luna`; its evaluator used `openrouter/z-ai/glm-5.3` with the `high` variant. The rerun did not repeat the C038 error, and all three primary reports were evaluated under the same qualitative revision of the answer key.

The private source archive preserves the initial report and evaluation. They are summarized here because their role is methodological: they explain the calibration change and the decision to use the rerun as Luna's primary result.
