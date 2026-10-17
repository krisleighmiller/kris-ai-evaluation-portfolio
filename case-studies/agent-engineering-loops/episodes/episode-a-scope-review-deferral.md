# Episode A — Scope, Review, and Deliberate Deferral

## Assigned task

An agent was asked to finish the remaining work in a broad engineering milestone involving authorization-sensitive state, operational disclosures, job records, and recovery. It was told to verify the existing implementation rather than accept prior findings as fact, preserve unrelated work, use a separate branch, and stop short of later roadmap scope. [A-E01]

## Starting state

The application already contained a substantial partial implementation. The problem was not a blank feature. It was a mixed state of working behavior, placeholder assumptions, incomplete enforcement, and tests that covered some pieces more strongly than others.

That starting condition matters. A productive run could make several real corrections and still leave the larger milestone incomplete.

## Agent actions and claimed outcome

The first run reviewed the existing behavior, corrected several inconsistencies, rewrote affected tests, and saved the changes. Its report described concrete fixes and a green regression suite. Those claims are supported for the bounded changes. [A-E02]

What the report did not establish was completion of the wider milestone. The milestone required consistent behavior across every relevant authorization-sensitive path, not only the paths covered by the corrected tests.

## Review findings

I commissioned an independent audit with an explicit instruction not to accept the earlier implementation report as proof of completion. The audit found the milestone partial. Among the abstracted findings:

- some external-service paths did not share the same preflight boundary;
- interface state and host policy could disagree;
- some operational assumptions were not verified bounds;
- recovery and retry lineage were incomplete; and
- passing tests did not establish coverage of every required path. [A-E03]

The reviewer continued with bounded repairs and verified them, but its final report still said the milestone was not acceptance-ready. The saved checkpoint and test record support the repairs; they also preserve the refusal to call the milestone complete. [A-E04]

## My intervention

At that point I made a product-scope decision: stop the milestone, preserve the advanced work in a recoverable checkpoint, and prepare a safe baseline for the nearer release. The instruction was explicit that deferral was not completion. [A-E05]

That intervention changed the engineering objective. The task was no longer “finish every advanced guarantee.” It became “retain truthful disclosures and authorization safeguards, remove incomplete machinery from the critical path, preserve recovery information, and stop.”

The revised candidate went through repeated read-only review. Early review rounds found blocking truthfulness problems in how uncertain outcomes were described. Those findings were corrected and reviewed again. The final baseline checkpoint passed the bounded acceptance gate while the deferred milestone remained labeled partial. [A-E06]

## Final supported status

**Supported:** several implementation and verification improvements were real; the safe baseline was saved and reviewed; advanced scope was deliberately deferred.

**Not supported:** the broader milestone was complete.

## What this episode shows

The useful behavior was not blind persistence toward the original checklist. It was the combination of independent audit, honest status language, recoverable checkpoints, and a human scope decision.

The failure mode to avoid is subtle: a long list of fixes plus a green suite can create the feeling of completion even when the acceptance boundary is wider than the tested boundary. The corrective practice is to keep scope status separate from implementation progress.

