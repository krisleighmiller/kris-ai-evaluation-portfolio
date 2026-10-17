# Limitations

- **Small sample:** each route has five primary trials. The result is useful evidence about this run set, not an estimate precise enough for a universal leaderboard.
- **Route-specific identity:** provider path, hosted alias, tool interface, and date are part of the result. A similarly named model elsewhere may not behave identically.
- **Mutable hosted systems:** reruns can differ as providers change model aliases, service behavior, pricing, or caching.
- **Accounting is observed, not normalized:** token categories and cost were recorded by the execution layer. Cross-provider accounting may not be perfectly comparable.
- **Workflow time is not inference latency:** reported agent time includes tool use and media processing. This is not a hardware or throughput benchmark.
- **Compact public evidence:** raw trajectories, local logs, and the 20 generated masters are not published. Verifier reports, output hashes, sizes, and row-level metadata preserve the scoring evidence without distributing machine state or hundreds of megabytes of duplicated outputs.
- **Historical checksum contamination:** Harbor's historical task checksum covered the full source task directory while its `jobs/` directory was nested inside that root. The changing recorded values therefore include accumulating run output and must not be read as stable task versions. The published per-file checksum manifest is authoritative for this package.
- **Task scope:** success demonstrates conformance on this deliberately constructed corpus and specification. It does not prove general post-production competence on every codec, delivery standard, or source defect.
- **Causal restraint:** the verifier establishes what each artifact got wrong. A specific internal reasoning failure is claimed only when the retained trace supports it; repeated output failures alone do not prove identical reasoning across runs.
