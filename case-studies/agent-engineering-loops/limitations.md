# Limitations

## Observational, not controlled

The episodes were selected from real engineering work. They used different models, prompts, starting states, tools, and task sizes. They do not support a model ranking or a causal claim that one model would behave the same way on another task.

## Private primary evidence

The application repository, prompts, conversations, source paths, screenshots, and exact crosswalk remain private. Public readers can inspect the claim structure, evidence labels, disclosed sequence, and evaluation method, but they cannot independently audit the primary records or recreate the application.

## Historical reconstruction

Historical claims were tied to contemporaneous records and saved checkpoints where available. Current code was not used by itself to prove earlier state. Some details that were not material to the evaluation were omitted rather than reconstructed from memory.

## Uneven verification depth

Not every finding was verified at the same level. The central successful and concurrent workflows received application-level mock verification. One terminal-failure behavior was verified after repair at a lower level rather than repeated through the entire application. That difference is disclosed rather than flattened into a single “tested” label.

## Unfinished application

The application was unfinished during all three episodes. The study evaluates bounded engineering loops and the quality of their evidence. It does not establish overall product readiness or completion.

