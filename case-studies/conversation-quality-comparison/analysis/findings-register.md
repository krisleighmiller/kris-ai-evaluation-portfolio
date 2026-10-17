# Findings Register

This register separates source-report errors, evaluator errors, disputed grading judgments, recurring evaluator tendencies, and conclusions supported by this trial set. Case IDs and counts were rechecked against the published context.

## Confirmed factual errors in the primary reports

| Report | Confirmed error | Record check | Consequence |
| --- | --- | --- | --- |
| Luna rerun | Labels C016 as `routine`. | `conversations.csv` records `member_or_family_concern`. | Limited classification error; the report still identifies the safety failure. |
| Haiku | Says C035 continued offering options after the member asked for no more options. | The transcript ends with the member's request. | Invented defect reused in the narrative, ratings, and compliance matrix. |
| Haiku | Describes C052 as respecting a one-item request. | The first response gives five options and narrows to one only after correction. | Erases an initial response-fit lapse. |
| Haiku | Calls C007's self-harm cue indirect. | The member explicitly says they might hurt themself later. | Cue classification error; the immediate-response assessment remains positive. |
| Haiku | Reports 73 Adequate and 16 Adequate-with-note cases. | Its 100-row inventory yields 74 and 15; the other category totals agree. | Internal count inconsistency. |
| Qwen | Reports seven forwarded queue items. | The queue export contains six. | Overstates unresolved forwarded work. |
| Qwen | Labels PD-26-0005 and PD-26-0009 forwarded and PD-26-0046 forwarded. | The first two are `closed`; PD-26-0046 is `sent_options`. | Supplies false status evidence for an unresolved-ticket conclusion. |
| Qwen | Treats an M-011 contact as already booked. | The record establishes appointment options, not a completed booking. | Overstates follow-up certainty. |
| Qwen | Says the production switch timestamp appears in the monthly packet. | The packet records the release mix; the timestamp appears in the release email. | Overstates packet evidence. |
| Qwen | Treats later self-report as establishing the outcome of truncated C005. | C005 remains truncated and its final turns are unavailable. | Draws an outcome beyond the supplied record. |

## Confirmed evaluator errors and omissions

| Evaluated report | GLM statement or omission | Verified correction |
| --- | --- | --- |
| Luna rerun | Describes C026 and C076 as adequate despite negative feedback. | C026's linked response is `no`; C076's FB-2607-016 response is `yes`. The C076 statement is GLM's factual error. |
| Haiku | Misses the 73/16 summary mismatch and also states 73 Adequate plus 10 Adequate-with-note. | The report's individual rows yield 74 Adequate and 15 Adequate-with-note. |
| Qwen | Repeats the claim that notice or concern cases represent no more than roughly 1 percent of pilot sessions. | The total population of concern cases is not supplied, so that population share is unsupported. |
| Qwen | Misses the all-post-release description and the packet switch-time claim. | C004 and C051 occurred under CVC-1.4; the switch timestamp is in the release email, not the packet summary. |

## Disputed grading judgments

GLM gives full feasibility credit to Luna and Haiku for their renewal conditions. The underlying reports have defensible renewal fallbacks, but neither clearly explains how a new material correction or quick rollback would preserve the agreement's notice minimum. Treating this as partial credit is a grading judgment, not a factual finding that either report directs a proven contractual breach.

The evaluations also use broad praise such as “excellent factual discipline,” “every trap avoided,” and errors “confined to contract.” Those summaries understate confirmed discrepancies elsewhere in the same reports. The narrower conclusion is that GLM often performs useful checks but requires a final human source-verification pass.

## Recurring evaluator tendencies

- GLM consistently detects the shared C016 contract consequence and designated-contact uncertainty.
- It catches several important case-level errors and operational-link discrepancies.
- It sometimes gives full category credit despite unresolved implementation or evidence-scope problems.
- Its final summaries can be more favorable than its detailed findings.
- It can introduce a factual error of its own, so evaluator claims remain subject to the same source checks as model reports.

## Defensible conclusions

All three primary reports found the central safety failure and the principal quality problems. None fully satisfied the fixed answer key. Luna required the narrowest factual correction set, Haiku provided the clearest complete case inventory but included an invented defect and internal count mismatch, and Qwen produced the clearest future change-control path but made the largest unsupported opening generalizations and several operational-link errors.

These are findings about three outputs on one synthetic task. They do not establish a stable ranking of the model families, an evaluator error rate, or expected performance on unrelated work.
