# Failure Analysis

All ten failed balanced submissions failed `test_authenticated_controlled_protocol`, but the retained verifier traces show different implementation failures.

## Astra: traced-string handling

`LPH-AS-02` treated an unreadable or truncated traced string as fatal. `LPH-AS-05` failed on the related unreadable-string case. Both passed the hidden native workload and the other three verifier layers.

The controlled protocol intentionally permits these trace edge cases. A trustworthy harness must avoid turning an irrelevant or unreadable traced pointer into a false conclusion about the actual linker process.

## Kimi: incomplete version-probe sequence

`LPH-KI-01`, `LPH-KI-03`, and `LPH-KI-04` each omitted or produced the wrong required `--version` probe at controlled invocation 4. The other two Kimi trials passed all tests.

This repeated failure is narrow: the failed artifacts otherwise passed basic artifact, ordinary-user tracing, hidden native workload, and reward-channel checks. They failed because the signed protocol evidence was incomplete.

## DeepSeek: several identity and schema failures

The five balanced DeepSeek artifacts did not converge on one failure mechanism:

- `LPH-DS-01` could not locate the BFD linker process in its `strace` evidence.
- `LPH-DS-02` classified the controlled `ld.gold-helper` as no linker family when gold was expected.
- `LPH-DS-03` likewise could not classify `ld.gold-helper` from its version output.
- `LPH-DS-04` failed the hidden native report schema by using `path` where `invoked_path` was required, then also exited unsuccessfully in the controlled protocol.
- `LPH-DS-05` tried to classify the post-link `ld.gold-helper` as the measured linker and rejected its `post-link helper 1.0` version line.

The earlier exploratory DeepSeek artifact, `LPH-EX-DS-01`, is the run that missed the required version probe at invocation 0. It is not part of the five-trial balanced set.

## Shared test, distinct causes

The controlled protocol is the central discriminator because it joins several requirements that simpler testing separates poorly:

- requested linker versus executed process;
- normalized identity versus verbatim invocation path;
- actual linker versus decoy or post-link helper;
- correct process family at every invocation;
- required schedule and version probes;
- measured durations versus signed observer intervals; and
- success reporting versus cleanup on any failure.

Publishing the exact submitted scripts and CTRF traces makes these distinctions independently inspectable. The conclusions describe these artifacts and runs, not permanent model traits.
