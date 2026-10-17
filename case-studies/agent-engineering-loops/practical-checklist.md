# Practical Checklist for Agent Engineering Loops

This checklist is the main operational result of the study.

## Before implementation

- Define the user-visible outcome and the boundary that must be crossed.
- Record the starting branch or checkpoint and preserve inherited work.
- Separate required behavior from later roadmap scope.
- Decide which external boundaries will be mocked and how the running binary will prove its identity.

## Before accepting a completion claim

- Treat “complete” as a claim, not a status transition.
- Ask what each test actually reaches.
- Distinguish component coverage from a connected workflow.
- Distinguish an intermediate state—queued, authorized, downloaded—from the required final state.
- Inspect visual evidence for the defect the report says is fixed.
- Confirm that the running application uses the source, build, profile, and configuration believed to be under test.

## For external-service and authorization paths

- Establish isolation before approving an operation.
- Make the mock configuration fail closed rather than falling back to a real service.
- Use dummy credentials and an isolated profile.
- Count submissions, not just successful responses.
- Verify that stale, duplicate, canceled, failed, and uncertain requests cannot become false successes.
- Test two concurrent operations against real shared state; a queue-only unit test may miss quote or revision invalidation.
- Prove that recovery does not resubmit an external operation.

## For review and repair

- Give the reviewer the original acceptance criteria, not only the final diff.
- Ask the reviewer to identify unsupported claims as well as code defects.
- Convert findings into bounded repair tasks.
- Rerun the connected scenario after each material correction.
- Request follow-up review when the fix changes the behavior that was reviewed.
- Keep the first failure and the correction in the record.

## At the stopping point

- Separate implemented, verified, deferred, and unverified scope.
- Save a recoverable checkpoint.
- Reconcile documentation with the actual final test counts and limitations.
- Do not rename deferral as completion.
- Keep conclusions attached to the observed run rather than generalizing to the model.

