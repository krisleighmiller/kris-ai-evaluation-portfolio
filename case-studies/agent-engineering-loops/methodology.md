# Methodology and Claim Labels

## Case selection

I selected three episodes because each contained more than a final answer. The retained record included an assignment, an agent claim, review activity, human intervention, correction work, and a supported stopping point. The central episode also contained a reproduced failure after an earlier completion claim.

The episodes were not designed as a controlled model comparison. They involved different tasks, models, prompts, starting states, and amounts of delegated work. Model names are included as run metadata only.

## Reconstruction method

Search was used to locate candidate records. The narrative was then checked against the underlying contemporaneous conversations, agent-run records, saved source checkpoints, test results, and artifacts. Search results were navigation aids, not historical sources.

For each episode I reconstructed the same sequence:

1. assigned task;
2. starting condition;
3. agent actions;
4. claimed outcome;
5. review findings;
6. my intervention;
7. correction or recovery;
8. final supported status.

Current code was used only to establish present state. Historical statements required a contemporaneous record or saved checkpoint from the relevant point in the sequence.

## Claim labels

| Label | Meaning in this study |
| --- | --- |
| **Directly observed** | Preserved output, test result, saved checkpoint, or artifact directly demonstrates the claim. |
| **Contemporaneously supported** | A record created during the work describes the event and is consistent with the retained implementation evidence. |
| **Inferred** | The conclusion follows from multiple records but was not directly recorded at the time. |
| **Reported** | A participant stated the claim, but the retained evidence does not independently establish it. |
| **Unverified** | The available record is insufficient to decide. |

An agent's completion statement is treated as a claim until the evidence supports it. A test's existence is not treated as proof that it exercised the behavior its name suggests. A current implementation is not treated as proof that the same behavior existed earlier.

## Review standard

The review asked five questions:

- Did the verification exercise the actual boundary named in the acceptance criterion?
- Could the test pass while the user-visible outcome still failed?
- Did the running application use the source and binary believed to be under test?
- Were mocked external boundaries isolated from real services and credentials?
- Did the final status preserve unresolved scope instead of converting it into a completion claim?

## Confidentiality method

This document was written from private evidence into a new public narrative. It is not a redacted transcript.

Product names, purpose, domain vocabulary, screen and feature names, source paths, symbols, repository identifiers, branch and commit identifiers, screenshots, prompts, provider integrations, and exact product-specific acceptance criteria were omitted. Engineering meaning was retained through stable terms such as *the target workflow*, *the affected interface state*, *the external-service boundary*, and *the authorization-sensitive state transition*.

