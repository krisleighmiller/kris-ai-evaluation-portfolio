# Context release asset

The model-visible media is distributed as a GitHub Release asset rather than ordinary Git.

| Field | Value |
| --- | --- |
| Repository release | `v1.0.0` |
| Asset | `clip-provenance-context-v1.0.0.zip` |
| Archive size | 439,756,510 bytes (approximately 420 MiB) |
| Archive SHA-256 | `443485fd0fec0f18b7eb52d1f0765d4ed7b12ff2cd3c1a021708c98c1899840d` |
| Extracted media | 45 masters, 200 clips |
| Extracted media bytes | 439,700,250 |
| Master-set aggregate SHA-256 | `3c6d9999d0dab1e5a62de2336cf87f31f1dba561cbfde6ffd71caebe296cc37d` |
| Clip-set aggregate SHA-256 | `31ad405df9948ec2b6bffff39d5765a65f0ec23effa5057164ed3f3f240a3cb4` |

The archive contains one top-level folder, `clip-provenance-context-v1.0.0/`, with only `masters/` and `clips/` beneath it. The shared prompt, provenance, answer key, and evaluator remain outside the model-visible archive so the original information boundary can be reproduced.

## Download

From a clone of the repository after the `v1.0.0` release exists:

```bash
gh release download v1.0.0 --pattern 'clip-provenance-context-v1.0.0.zip'
```

The same asset can be downloaded from the release page in a browser. GitHub and OpenCode are external tools; they are not bundled here.

## Verify the archive

```bash
echo '443485fd0fec0f18b7eb52d1f0765d4ed7b12ff2cd3c1a021708c98c1899840d  clip-provenance-context-v1.0.0.zip' | sha256sum -c -
```

## Extract and verify every media file

```bash
unzip clip-provenance-context-v1.0.0.zip
cd clip-provenance-context-v1.0.0
sha256sum -c ../path/to/repository/case-studies/clip-provenance-comparison/context/files.sha256
```

The check must report all 245 files as `OK`. `context-files.tsv` adds the byte size for each file, and `context-manifest.json` records the package summary.

## Information boundary

For a fresh comparison run, place only the extracted `masters/` and `clips/` directories in the new trial directory and submit the repository's [shared prompt](../prompt.md). Do not place `answer-key/`, `evaluator/`, `verification/`, prior trial outputs, or `SOURCE_PROVENANCE.md` in the model's working directory until the run is complete.

See [SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md) for the public-domain source and transformation record.
