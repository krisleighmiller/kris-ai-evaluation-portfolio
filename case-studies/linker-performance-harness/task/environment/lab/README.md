# Linkbench audit lab

Run:

```bash
python3 /app/lab/audit_run.py
```

The audit executes `/app/linkbench` directly against a small visible controlled workload. Its compiler-driver and linker entry points are symlinks to one controlled executable, just as multiple tool names can select one dispatcher in a real toolchain. A link may involve more than one process. The controlled tools record routing events, executable paths, invocation order, thread controls, semantic probes and timing intervals.

The audit prints those raw events and the generated report without interpreting them. The log records what happened, not whether it was correct: no event states which linker a link should have used, or whether the harness attributed it, timed it or probed it correctly. Compare the evidence with the copied workload manifest and the task contract yourself.

The harness is deliberately not placed under an external process tracer, so implementations may observe their own descendant `execve` events. The controlled workload directory supplied to the harness is read-only.

This is a diagnostic aid, not the verifier. Its evidence is intentionally visible and unauthenticated. It does not disclose hidden workloads, authenticated verifier evidence, fault scenarios or expected solution code.
