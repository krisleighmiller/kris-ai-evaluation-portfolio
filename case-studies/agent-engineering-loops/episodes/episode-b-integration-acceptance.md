# Episode B — Integration and Acceptance Verification

## Assigned task

An agent was asked to audit a bounded integration milestone criterion by criterion, implement the smallest coherent missing work, preserve established safety boundaries, and convert the remaining gaps into an acceptance-ready state. [B-E01]

## Starting state

Several components already existed and had tests. The open question was whether those components formed the connected workflow required by the acceptance criteria.

The first audit was appropriately mixed rather than binary. It classified some criteria as satisfied and others as partial. The remaining gaps included missing population tests, thin integration seams, and an unproven transition from an approved plan through the external boundary to a reviewable local result. [B-E02]

## Agent actions and claimed outcome

The run added tests and implementation work across the state, integration, and interface layers. It also used delegated reviewers to inspect separate criteria. An early closeout report accurately retained several limitations, but the work later moved toward a broader acceptance claim after more checks passed. [B-E03]

The critical problem was evidence shape. Many individual components were tested, but the named workflow still had not been exercised as one chain. A collection of green component tests can leave the handoff between components untested.

## My intervention

I issued a narrower follow-up: prove one connected workflow from an approved plan through a mocked external boundary, reconciliation, local output construction, review handoff, and final status. The task explicitly rejected substituting disconnected component tests for that chain. It required real local fixture files, a mocked external boundary, the actual host path, failure-path coverage, and independent review. [B-E04]

## Correction and verification

The agent mapped the full dispatch path and built the connected test. The first executions failed. Those failures were useful: they identified incorrect assumptions in the fixture and gaps in the test itself. The agent corrected the setup rather than weakening the assertions.

The completed verification exercised the real application host code with only the external service replaced by a local stub. It processed real local fixture files, passed through authorization and state reconciliation, produced a reviewable local artifact, checked output classification, and verified the final workflow state. A companion test covered the failure path. [B-E05]

Independent review then identified one overbroad statement: a public boundary was described as host-tested when the existing check stopped earlier in the chain. The review also found two fidelity differences between the test and the application path. [B-E06]

The agent responded by adding the missing boundary test and aligning the connected scenario with the application route and approved request. It reran the relevant host and interface suites. The reviewer reproduced the final counts and accepted the bounded claims. [B-E07]

The connected test, acceptance record, and later saved checkpoint preserve the final state. [B-E08]

## Final supported status

**Supported:** the bounded integration milestone had a connected, repeatable local verification path; the final claims were corrected to match the tests; the relevant regression suites passed.

**Separately supported:** a human had observed playback in the application. That observation was retained as human evidence, not substituted for the automated chain.

**Not supported:** that every future workflow, provider, or application state was covered.

## What this episode shows

The strongest contribution was the move from component confidence to connected evidence.

A useful acceptance test does more than mention each component. It demonstrates the handoffs between them and fails when those handoffs are wrong. Independent review was especially valuable here because it checked not only the code, but whether the written claim accurately described what the test reached.

