# Task Provenance

The task instruction, configuration, Dockerfiles, workload generators, diagnostic lab, starter harness, reference solution, verifier, and controlled tools were created for this evaluation.

The visible and hidden workloads are deterministic synthetic C link graphs generated during image construction. Their archive cycles, relocation-heavy objects, response files, and correctness probes reproduce the integrity problems of captured production links without distributing proprietary source code or client data.

## Agent-visible material

The runtime image contains the visible generated workload, its format documentation, a deliberately incomplete starter harness, and a diagnostic lab. The lab exposes raw controlled events for development; it does not include the verifier's interpretation or answer.

## Withheld verifier material

The separate verifier image contains:

- a different generated native workload;
- authenticated controlled driver and linker programs;
- signed observer evidence;
- adversarial identity, ordering, timing, path, output, and cleanup scenarios; and
- the executable scoring tests.

The reference solution and verifier materials are not copied into the agent image.

## Publication boundary

This directory is the runnable Harbor task package. It includes Dockerfiles because they define the evaluation environments. It does not include Harbor, OpenCode, built images, installed system packages, credentials, provider configuration, or local application state.

The approved publication plan applies MIT terms to authored code and configuration and CC BY 4.0 terms to authored documentation, synthetic data, and evidence. Repository-level license and third-party-notice files still need to be added before public release. Dependencies installed by the Dockerfiles retain their upstream licenses.
