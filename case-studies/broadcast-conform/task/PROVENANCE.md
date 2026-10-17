# Task Provenance

## Authorship and source classification

The task instruction, configuration, Dockerfiles, delivery specification, timeline, reference solution, verifier, hidden truth, and all seven footage files were created for this evaluation. The footage is owner-generated synthetic media, not client material or a derivative of third-party footage.

The published A–G media files are byte-identical to the files produced by the private authoring generator and used in the recorded trials. Their hashes appear in [`tests/input_hashes.json`](tests/input_hashes.json) and in the package-level [`CHECKSUMS.sha256`](CHECKSUMS.sha256).

## Visible versus withheld material

During a model trial, the agent environment receives:

- the seven footage files;
- `delivery_spec.json`;
- `timeline.json`; and
- the instruction.

The reference solution and verifier-facing ground truth remain outside the agent image. Harbor supplies them only to the Oracle or separate verifier stage. This separation is part of the benchmark design, not a publication omission.

## Redistribution boundary

This directory is the benchmark package. It includes the Dockerfiles because they define the agent and verifier environments. It does not include Harbor, OpenCode, container images, system packages, provider software, credentials, or local application state. Those are independently supplied execution tools.

The approved publication plan applies MIT terms to authored code and configuration and CC BY 4.0 terms to authored documentation, synthetic data, and evidence. The repository-level license and notice files still need to be added before public release. Software installed by the Dockerfiles retains its own upstream licensing.
