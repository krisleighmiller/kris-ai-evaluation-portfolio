# Episode C — Verification Challenge and Recovery

## Assigned task

An agent was asked to finish a bounded interface and initial-workspace milestone, verify both behavior and appearance, preserve existing safety boundaries, and stop before the next migration stage. [C-E01]

## Initial completion claim

The agent inspected the implementation, fixed three visible duplication problems, ran automated checks, captured the application at multiple widths, and used an independent reviewer. It then declared the milestone complete. The report distinguished tested behavior, live visual checks, and a small set of implemented-but-untested items. [C-E02]

That was better than an unsupported one-line sign-off, but it still overstated two facts.

## Stronger verification

I asked for a second pass that inspected the target workspace at three widths and exercised its actions with mocks. [C-E03]

The resulting report said the repeated identity issue was fixed and treated two intermediate states as sufficient evidence:

- an already-approved item was used to stand in for a successful approval action; and
- reaching an authorization card was used to stand in for completed generation after authorization.

I challenged both claims. The repeated heading was still visible in the supplied screenshots. A disabled action proves only the disabled state. An authorization card proves that the workflow stopped for authorization. Neither proves a successful approval or a completed operation. I also pointed out that a frozen browser bridge prevented one mocking technique, not mocking at the external-service boundary. [C-E04]

## What the challenge exposed

The stronger test found more than a cosmetic defect.

The visual defect had a concrete cause: stored text already contained an identity prefix, and the interface added the same prefix again. A small selector change and regression test fixed it.

The completed-operation check was more consequential. During the attempt to exercise the full path, the agent discovered that the running application was using a stale binary rather than the newly built host. One verification attempt crossed the intended test boundary and reached a live service. The incident was retained in the private record rather than edited out.

After the environment was corrected, a local provider stub exposed a real workflow regression: the authorization replay could download an output and update one record while leaving the associated workflow job pending and failing to register the expected downstream result. Reopening did not repair the state. A second authorization event could also be lost while the first dialog was unresolved. [C-E05]

These findings invalidated the earlier completion claim.

## My intervention

I converted the findings into a bounded repair assignment. It required:

- proof that the running binary matched the source under test;
- an isolated profile, dummy credentials, and a fail-closed local provider stub;
- successful completion, downstream registration, approval, persistence, and reopening;
- recovery of an already-downloaded result without a second submission;
- explicit handling of concurrent, canceled, stale, duplicate, failed, and uncertain requests; and
- independent review of both the repair and the test isolation. [C-E06]

When the first repair pass still relied on a mocked state transition for concurrency and gave users a recovery instruction for an action that did not exist, I intervened again. The follow-up required a stateful two-operation application test, accurate instructions, content validation for recovered files, terminal-failure handling, and proof that test hooks could not redirect an ordinary release build. [C-E07]

## Repair and recovery

The repair restored the missing post-authorization state transition and added idempotent recovery during load and re-import. Invalid output content was rejected instead of being registered. Terminal external-service failures stopped polling and left charges unverified rather than converting them into a false success.

The authorization handler changed from silent dropping to a bounded, deduplicated queue. Each request was revalidated before dispatch. The application-level concurrency test showed why this mattered: completing one operation changed shared state and made an earlier quote stale. The stale request was rejected without submission, the independently queued request completed, and a fresh quote could then be used for a new run. Responses and outputs did not cross requests.

The test seam was moved behind an off-by-default test build. The mock build failed closed unless it was pointed at a validated loopback destination, identified itself at runtime, and prevented external downloads. The restored ordinary binary reported that the test feature was off.

The final application checks used an isolated profile and local stub. One authorized operation completed with exactly one submission, registered the expected result, survived reopen, and passed the normal approval transition. The concurrency scenario produced two completed operations from two submissions, with no submission for the stale request. Host, interface, desktop-shell, type, and release-build checks passed. [C-E08]

Independent review returned “approve with findings.” Its main actionable finding was that two distinct requests created at the same shared-state revision could collide in the queue's deduplication key. The agent corrected the key, added regression coverage, resolved smaller recovery and documentation findings, reran the suites, and requested follow-up review. The follow-up verified the corrections and found only a stale count in one note; that note was corrected. [C-E09]

The entire repaired state, tests, and retained evidence were then saved in a clean checkpoint. [C-E10]

## Final supported status

**Supported:** the original completion claim was premature; stronger verification reproduced material failures; the bounded repair passed application-level mock verification, regression checks, and independent review; the corrected state was saved.

**Still limited:** one failed-provider application scenario was covered by a lower-level post-fix test rather than rerun end to end. The application as a whole remained unfinished.

## What this episode shows

The key intervention was asking what each piece of evidence actually proved.

The repeated heading was visible in the evidence that accompanied the “fixed” claim. The authorization card was real, but it proved a stop, not a completion. The green suite was real, but the running binary was not the binary believed to be under test. Each problem came from treating an intermediate signal as the final outcome.

Recovery was possible because the failures were preserved, turned into explicit acceptance criteria, and rechecked at the boundary where the original claim failed.

