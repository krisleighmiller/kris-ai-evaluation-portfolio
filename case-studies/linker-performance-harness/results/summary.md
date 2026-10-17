# Results

## Balanced comparison

The 15 primary trials produced five successful submissions.

| Recorded route | Passes | Input tokens | Cache-read tokens | Output tokens | Recorded cost | Cost per success | Agent time range |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `openai/gpt-6-astra` | 3/5 | 1,660,816 | 1,660,525 | 46,073 | $6.742785 | $2.247595 | 285–429 s |
| `openrouter/moonshotai/kimi-k3` | 2/5 | 21,087,748 | 19,901,760 | 86,928 | $17.014213 | $8.507107 | 911–1,607 s |
| `openrouter/deepseek/deepseek-v4-pro` | 0/5 | 5,020,295 | 4,322,176 | 46,957 | $0.280306 | Not defined | 226–748 s |

Cost per success is total recorded route cost divided by passing submissions. It is undefined when a route produced no success. These are execution-layer observations, not normalized provider prices or inference benchmarks.

## Failure distribution

| Verifier test | Astra failures | Kimi failures | DeepSeek failures |
| --- | ---: | ---: | ---: |
| Authenticated controlled protocol | 2/5 | 3/5 | 5/5 |
| Hidden native workload | 0/5 | 0/5 | 1/5 |

The other three tests passed in every balanced trial. See the [failure analysis](failure-analysis.md) for the mechanisms hidden by this compact table.

## Exploratory observations

The Qwen3.7 Plus exploratory trial and the earlier DeepSeek exploratory trial both scored 0/1 after failing the authenticated controlled protocol. Qwen missed a required version probe at invocation 4; the earlier DeepSeek trial missed one at invocation 0.

They are useful engineering observations but do not enter the balanced rates or route totals above.

## Task identity

All 17 model trials—15 balanced and two exploratory—recorded the same lock digest:

`sha256:44a28ec01f8faecf4bb0a706e1b841fb6f2ffcb33daeaa1d3d416a1db09e9763`

The sanitized public package has its own per-file checksum manifest because one private runtime-name comment was rewritten. The historical digest identifies the recorded comparison set; [`../task/CHECKSUMS.sha256`](../task/CHECKSUMS.sha256) identifies the public files.

## Corrections to the working report

The private working report said no separate Oracle execution existed. A contemporaneous record establishes a successful development Oracle run; its temporary raw directory was not retained, so the public record is explicitly labeled reconstructed.

The working report also assigned the invocation-0 missing-probe failure to the five balanced DeepSeek trials. The underlying verifier reports show that failure belongs to the earlier exploratory DeepSeek run. The balanced DeepSeek failures are corrected in the [failure analysis](failure-analysis.md).
