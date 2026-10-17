# Controlled workload

This verifier-only workload has the same public manifest and response-file interface as the native workload. Its compiler driver and linkers are authenticated native test doubles.

The response inputs are synthetic. The controlled driver records the requested linker, validates linker-specific thread arguments, executes the corresponding controlled linker, brackets it with a link-dependent number of argument-free processes that report the link's own version banner, and then runs a linker-shaped helper that is not a linker. Fault scenarios can route an alias to the wrong family or change the family behind an unchanged path. Each output is bound to a fresh verifier-issued nonce, and the manifest probe records independent evidence.
