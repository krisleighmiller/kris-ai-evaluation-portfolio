# Public Evidence Index

These references are intentionally opaque. The private crosswalk maps each ID to exact source records. It is retained for audit and is not part of the public repository.

## Episode A

| ID | Public description | Strength |
| --- | --- | --- |
| A-E01 | Original bounded implementation assignment and starting-state instructions | Contemporaneously supported |
| A-E02 | Implementation report, regression summary, and saved review-fix checkpoint | Directly observed |
| A-E03 | Independent gap audit concluding that the wider milestone remained incomplete | Contemporaneously supported |
| A-E04 | Repair record and saved checkpoint that explicitly did not claim milestone completion | Directly observed |
| A-E05 | Human scope decision to stop the milestone and defer advanced work without relabeling it complete | Contemporaneously supported |
| A-E06 | Final review sequence and saved safe-baseline checkpoint | Directly observed |

## Episode B

| ID | Public description | Strength |
| --- | --- | --- |
| B-E01 | Criterion-level audit assignment and recorded starting state | Contemporaneously supported |
| B-E02 | Audit report separating satisfied, partial, and unverified criteria | Contemporaneously supported |
| B-E03 | First repair and review pass, including remaining verification limits | Contemporaneously supported |
| B-E04 | Human-issued follow-up requiring one connected workflow rather than disconnected component evidence | Contemporaneously supported |
| B-E05 | Connected local-fixture and mocked-boundary verification record | Directly observed |
| B-E06 | Independent review identifying an overbroad host-test claim and two fidelity gaps | Contemporaneously supported |
| B-E07 | Added boundary tests, corrected assertions, and reproduced final test results | Directly observed |
| B-E08 | Saved checkpoint containing the connected verification and acceptance record | Directly observed |

## Episode C

| ID | Public description | Strength |
| --- | --- | --- |
| C-E01 | Bounded interface-and-workflow completion assignment | Contemporaneously supported |
| C-E02 | Initial completion report with passing automated checks and visual claims | Reported |
| C-E03 | Follow-up request for multi-width inspection and action-level verification | Contemporaneously supported |
| C-E04 | Human challenge identifying a still-visible defect and two unsupported success claims | Directly observed |
| C-E05 | Stronger boundary test, reproduced failure, and discovery of test-environment contamination | Directly observed |
| C-E06 | Bounded repair assignment covering completion, recovery, request isolation, and safe mocking | Contemporaneously supported |
| C-E07 | Follow-up intervention requiring stateful concurrency, accurate recovery instructions, invalid-output rejection, and terminal-failure handling | Contemporaneously supported |
| C-E08 | Application-level mock results and final regression results | Directly observed |
| C-E09 | Independent review, correction of its actionable findings, and follow-up review | Contemporaneously supported |
| C-E10 | Final saved checkpoint containing repaired code, tests, and retained verification artifacts | Directly observed |

## Evidence availability

The public index exposes the claim structure without exposing the private application. It does not allow a reader to inspect the primary records. That limitation is deliberate and is discussed in [Limitations](limitations.md).

