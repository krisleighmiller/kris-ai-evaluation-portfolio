# AI Conversation Review Provenance

## Source and rights

Kris created the synthetic conversations, operational records, agreement, quality standard, prompt, answer key, and evaluation package for this comparison. The files do not contain client records or real member data. Organization, person, member, session, case, ticket, note, feedback, alert, and release identifiers are fictional.

## Publication transformations

The private source archive remains unchanged. The public package applies the following transformations:

- publishes one canonical context instead of three redundant per-model copies;
- replaces ordinary-looking synthetic email domains and message-ID domains with reserved `.example` domains;
- removes author, title, creator, producer, and timestamp metadata from the three public PDFs while preserving their page content;
- converts the Haiku Word report, the final model comparison, and the final GLM evaluation review to Markdown;
- replaces absolute source paths in the two converted synthesis documents with repository-relative links; and
- excludes OpenCode state, configuration, local databases, caches, credentials, machine paths, token and cost records, and working-only scripts.

The PDF text-extraction hashes were compared before and after metadata removal and matched for all three files. The Haiku Word source rendered to 12 pages and was inspected before conversion. The two synthesis Word sources each rendered to five pages and were inspected before conversion. The private Word originals are retained in the source archive.

## Evidence identity

The exact prompt and answer key retain their original SHA-256 checksums. Luna and Qwen reports and all three GLM evaluations are byte-for-byte copies of the selected Markdown source artifacts. Haiku's report is a mechanical Word-to-Markdown conversion; its source and public checksums are both recorded in trial metadata.

The private run context had aggregate SHA-256 `41bfe58c56a28d58f9814d6186e24f6e5ba635b5bdaa01ad65c644840ed9ff73`. Public per-file checksums appear in [`manifest/context-manifest.json`](manifest/context-manifest.json), and repository-package checksums appear in [`manifest/checksums.sha256`](manifest/checksums.sha256).
