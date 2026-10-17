# Video source identification report

## Findings

All **45 originals and 200 clips** were investigated. The final classifications are:

- **137 confident matches:** strong source evidence and well-constrained start/speed estimates.
- **23 matches requiring review:** 16 have high-confidence sources but uncertain timing; 7 have plausible sources that did not clear every verification threshold.
- **40 unidentified clips:** no defensible source assignment within the supplied library.

There are **153 high-confidence source identifications** when timing-only uncertainties are included. The 160 assigned candidates cover 45 of the 45 originals. No clip has two competing sources supported by three or more sequence-consistent geometric samples. Confidence categories are evidence rules, not numerical probabilities.

Inspect [all 200 results](report/matches.csv), [confident results](report/confident.csv), [the review queue](report/uncertain.csv), or [unidentified clips](report/unidentified.csv). [Source totals](report/source_summary.csv) include every original, including any with zero assignments. The original searchable HTML and full 200-panel image set were reduced for public packaging; the complete machine-readable results and all review-queue panels remain.

### How to interpret the times

Times are relative to the first decoded video frame of each supplied original, not a longer film, wall-clock time, or sharing-site timecode. The fitted relationship is:

`source_time_seconds = source_start_seconds + source_seconds_per_clip_second × clip_time_seconds`

For example, 1.10 means the clip advances through the source approximately 10% faster. Confident fitted speeds range from 0.964 to 1.023; values very close to 1 should not be interpreted as proof of deliberate speed editing. The underlying masters are 24 fps. Millisecond output formatting is for convenient machine processing, **not millisecond precision**.

For confident timing, a practical review tolerance is approximately **±0.25 seconds**, informed by the held-out controls below. This is not a statistically calibrated confidence interval or a guarantee for every real clip. Uncertain timing estimates are search/review starting points; some can be wrong by a second or more, especially on static title cards or maps. `offset_profile_width_seconds` is only a diagnostic sensitivity measure with speed held fixed; it is not a confidence interval.

## Files and integrity

- Originals: 45 MP4s, all 640×480, 24 fps, approximately 40 seconds each; total 1799.125 seconds.
- Clips: 200 MP4s, approximately 6.08–13.92 seconds each; total 1957.164 seconds. Their sizes and frame rates vary; 43 have no audio stream.
- Every input was hashed with SHA-256, probed, and fully video-decoded. **245/245 inputs decoded without reported errors and retained their original hashes.** See [inventory](analysis/inventory.csv), the case-study [context manifest](../../context/context-manifest.json), and [input audit](analysis/input_audit.json).
- The supplied directories contained only video files; no source-to-clip mapping or ground-truth labels were provided. Filename numbering was not used as source evidence.
- All project outputs, evidence images, generated test clips, scripts, and logs are inside this working directory. The originals and clips were not modified. No media or fingerprints were sent to an external service.

## Method

### 1. Retrieve candidate visual correspondences

Sample each original once per second (1,800 reference frames across the library), resize to 400 pixels wide and convert to grayscale. Extract up to approximately 500 SIFT local features per frame and apply RootSIFT normalization. Local features permit matching the surviving portion of a cropped image and tolerate resizing, moderate compression, color changes, and overlays better than a whole-frame hash.

Sample each clip at seven times spread across its duration. Search a FLANN descriptor index, take six descriptor neighbors, vote for reference frames, and verify the top 16 frames for each query. A descriptor-ratio test of 0.76 rejects weak correspondences. RANSAC fits an affine spatial transformation with a 3-pixel reprojection threshold. Record inlier counts, spatial coverage and errors rather than treating a retrieval hit as a match.

### 2. Require a coherent sequence

Group geometric correspondences by original and fit a source-time/clip-time relationship. The initial clock search considers rates from 0.8–1.2 source seconds per clip second and a coarse temporal tolerance of 0.8 seconds, appropriate to the one-second reference spacing. Cap each frame's vote contribution so a single richly textured image cannot stand in for a sequence. Candidate scores and all competing source evidence are retained.

The **43 weak/unmatched first-pass clips** underwent a broader second search: 11 clip samples, 12 descriptor neighbors, higher search effort, and 40 candidate reference frames per sample. This strengthened three initially partial candidates (`clip_061`, `clip_115`, `clip_196`). The remaining isolated wrong-source hits never became sustained sequences.

### 3. Calibrate spatial alignment and refine the clock

Decode candidate originals at their actual frame timestamps. Use five new clip samples and a local quarter-second source search to calibrate the crop/resize transformation, suppressing excessive shear that can otherwise compensate for camera/object movement in a nearby but incorrect frame.

Evaluate **15 clip samples** against dense source frames in a ±4-second local window. Warp each clip into the source coordinate system, mask outer edges, and calculate both grayscale normalized correlation and high-pass correlation (weights 0.45 and 0.55). Optimize one start time and speed across the sequence, trimming the worst 20% of frame scores to tolerate occlusion/cuts. Final speed bounds remain 0.8–1.2; start is searched within ±3 seconds of the coarse estimate. This is a second visual verification method, although spatial calibration and optimization reuse some verification samples; it is not a statistically independent holdout of the real clips.

Retain every frame's best source time, fitted time, correlation, peak prominence, and residual. Broad peaks and inconsistent times are evidence of timing ambiguity even when the source is visually clear. Static cards, maps, slow motion, film jitter, and repetitive actions can make a unique frame-accurate start impossible to establish this way.

### 4. Apply explicit confidence rules

**High source confidence** requires at least three sequence-consistent geometric samples, median ≥18 geometric inliers, median spatial coverage ≥2.5% of the normalized reference area, support spanning ≥35% of the clip, at least eight dense-frame scores above 0.60, and aggregate dense visual score ≥0.65. No alternative source cleared a comparable sequence threshold in this dataset.

**High timing confidence** additionally requires at least six informative timing samples (peak prominence >0.015 and peak score >0.55), informative-sample temporal RMSE ≤0.12 seconds, fixed-speed offset-profile width ≤0.25 seconds, and a speed away from the search boundary. A high source plus high timing is labeled `confident`. A repeated candidate failing either set is `uncertain`. Isolated or absent geometric evidence is `unidentified`.

Audio was intentionally excluded, so removed/replaced audio cannot create or suppress a match. The method does not assume that every clip belongs to the library.

## Validation

### Known-answer edited controls

Generated **18 development controls** from 18 originals with known frame-exact starts, 0.9×/1.0×/1.1× source-time rates, cropping, resizing, color/contrast changes, a translucent overlay, optional borders, H.264 CRF 31 compression, and no audio. Development tests exposed an overly narrow speed-refinement window and a camera-motion alignment issue; the method was corrected before the held-out evaluation.

- Correct source ranked first: **18/18**.
- Confident source-and-time classifications: **10/18**.
- Among confident controls, median absolute start error **0.008 s**, maximum **0.100 s**.
- Across all development controls, including uncertain cases, median absolute start error **0.017 s**, maximum **0.928 s**. Keeping those ambiguous cases out of the confident group is consequential.

Then froze the algorithm and confidence thresholds and generated **12 held-out controls from different originals**, using new starts, 0.92×/1.00×/1.06× rates, a different off-center crop, nonuniform resizing, different color adjustments, overlays/borders and compression.

- Correct source ranked first: **12/12**.
- Confident source-and-time classifications: **11/12**.
- Among confident held-out controls, median absolute start error **0.023 s**, maximum **0.174 s**.
- Across all held-out controls, median absolute start error **0.023 s**, maximum **0.174 s**.

These are recovery measurements on generated controls, not claimed accuracy figures for the unlabeled 200 real clips. Full expected/estimated sources, starts, speeds and frame evidence are preserved in [development validation](analysis/validation_positive.json), [held-out validation](analysis/validation_holdout.json), and [validation summary](report/validation_summary.json).

### Source-withheld negative controls

For six transformed development controls, removed all descriptors belonging to the true original and rebuilt the retrieval index. **0/6 produced a sequence-supported source assignment.** Five had no candidate; one produced only a single weak accidental hit, below the required sequence threshold. This directly checks the tendency to force a match when the source is unavailable. Six controls are a useful sanity check, not a calibrated false-positive-rate study. See [negative-control evidence](analysis/validation_negative.json).

### Visual and integrity checks

Generated three paired clip/source frames for every assigned candidate and three clip frames for every unidentified clip. Spot-checked representative confident matches, low-score candidates and static/ambiguous cases. A same-scene hard negative, `clip_003`, was compared against several points in `master_02`: the people/location resemble each other, but the observed shots do not provide an exact sequence match. It remains unidentified rather than being assigned from resemblance alone.

The private trial record retains every retrieval and dense-check sample, not just the three illustrative frames shown in each panel. [Visual-review notes](analysis/visual_review.json) identify exactly which paired panels were inspected; this was agent still-frame review, not independent human annotation or full-video playback. The mid-clip contact sheet of all 40 unidentified clips was also inspected. No automated classification was overridden. Automated deliverable checks verified 200 unique clip rows, the original evidence-image set, valid source paths and timeline boundaries; see [output audit](report/output_audit.json). The public package retains the full review queue plus one accepted and one unidentified example.

## Review queue

### Source candidate requires review (7)

- **clip_021.mp4 → master_00.mp4**, estimated start 00:00:00.875, rate 1.0000. Dense visual score 0.541; [paired frames](report/evidence/clip_021.jpg).
- **clip_028.mp4 → master_21.mp4**, estimated start 00:00:03.292, rate 1.0000. Dense visual score 0.474; [paired frames](report/evidence/clip_028.jpg).
- **clip_042.mp4 → master_32.mp4**, estimated start 00:00:14.719, rate 1.0180. Dense visual score 0.607; [paired frames](report/evidence/clip_042.jpg).
- **clip_065.mp4 → master_16.mp4**, estimated start 00:00:25.333, rate 1.0000. Dense visual score 0.554; [paired frames](report/evidence/clip_065.jpg).
- **clip_113.mp4 → master_01.mp4**, estimated start 00:00:00.125, rate 1.0000. Dense visual score 0.593; [paired frames](report/evidence/clip_113.jpg).
- **clip_177.mp4 → master_29.mp4**, estimated start 00:00:05.876, rate 1.0610. Dense visual score 0.589; [paired frames](report/evidence/clip_177.jpg).
- **clip_198.mp4 → master_21.mp4**, estimated start 00:00:09.281, rate 1.0119. Dense visual score 0.546; [paired frames](report/evidence/clip_198.jpg).

### Source is high confidence; timing requires review (16)

- **clip_024.mp4 → master_36.mp4**, estimated start 00:00:23.837, rate 0.9853; [paired frames](report/evidence/clip_024.jpg).
- **clip_033.mp4 → master_41.mp4**, estimated start 00:00:06.295, rate 0.9899; [paired frames](report/evidence/clip_033.jpg).
- **clip_045.mp4 → master_34.mp4**, estimated start 00:00:04.373, rate 1.0062; [paired frames](report/evidence/clip_045.jpg).
- **clip_051.mp4 → master_34.mp4**, estimated start 00:00:18.083, rate 1.0000; [paired frames](report/evidence/clip_051.jpg).
- **clip_080.mp4 → master_23.mp4**, estimated start 00:00:25.853, rate 1.1905; [paired frames](report/evidence/clip_080.jpg).
- **clip_082.mp4 → master_15.mp4**, estimated start 00:00:20.841, rate 0.8851; [paired frames](report/evidence/clip_082.jpg).
- **clip_092.mp4 → master_34.mp4**, estimated start 00:00:12.258, rate 0.9773; [paired frames](report/evidence/clip_092.jpg).
- **clip_104.mp4 → master_44.mp4**, estimated start 00:00:00.115, rate 0.9935; [paired frames](report/evidence/clip_104.jpg).
- **clip_116.mp4 → master_23.mp4**, estimated start 00:00:25.833, rate 1.0000; [paired frames](report/evidence/clip_116.jpg).
- **clip_120.mp4 → master_16.mp4**, estimated start 00:00:13.500, rate 1.0000; [paired frames](report/evidence/clip_120.jpg).
- **clip_128.mp4 → master_23.mp4**, estimated start 00:00:26.167, rate 1.0000; [paired frames](report/evidence/clip_128.jpg).
- **clip_137.mp4 → master_15.mp4**, estimated start 00:00:08.083, rate 1.0000; [paired frames](report/evidence/clip_137.jpg).
- **clip_155.mp4 → master_36.mp4**, estimated start 00:00:07.063, rate 0.9845; [paired frames](report/evidence/clip_155.jpg).
- **clip_159.mp4 → master_44.mp4**, estimated start 00:00:00.210, rate 0.9948; [paired frames](report/evidence/clip_159.jpg).
- **clip_165.mp4 → master_36.mp4**, estimated start 00:00:00.958, rate 1.0000; [paired frames](report/evidence/clip_165.jpg).
- **clip_182.mp4 → master_44.mp4**, estimated start 00:00:02.695, rate 1.0048; [paired frames](report/evidence/clip_182.jpg).

### Unidentified clips (40)

`clip_002.mp4`, `clip_003.mp4`, `clip_004.mp4`, `clip_010.mp4`, `clip_013.mp4`, `clip_019.mp4`, `clip_022.mp4`, `clip_026.mp4`, `clip_036.mp4`, `clip_041.mp4`, `clip_046.mp4`, `clip_048.mp4`, `clip_054.mp4`, `clip_056.mp4`, `clip_059.mp4`, `clip_072.mp4`, `clip_081.mp4`, `clip_086.mp4`, `clip_091.mp4`, `clip_097.mp4`, `clip_099.mp4`, `clip_107.mp4`, `clip_109.mp4`, `clip_110.mp4`, `clip_125.mp4`, `clip_133.mp4`, `clip_135.mp4`, `clip_142.mp4`, `clip_149.mp4`, `clip_157.mp4`, `clip_162.mp4`, `clip_167.mp4`, `clip_169.mp4`, `clip_175.mp4`, `clip_181.mp4`, `clip_189.mp4`, `clip_190.mp4`, `clip_193.mp4`, `clip_195.mp4`, `clip_199.mp4`.

## Limits and recommended use

“Unidentified” is not proof that a clip comes from outside the library. Severe edits, very small surviving image regions, minimal texture, very brief matching sections or transformations outside the model can evade retrieval. The broader recovery search reduces but does not eliminate this risk. Several unidentified clips appear to share a film or general setting with an original; that is weaker evidence than sharing its actual frames.

This implementation assumes a single source and approximately constant speed within each clip. It does not exhaustively solve multi-source montages, reversals, horizontal mirroring, large rotations, nonlinear time warps, or clips using only a very short fragment of a source. Those were not demonstrated by the accepted evidence. Sequence sampling also cannot certify that every unsampled frame belongs to the proposed source.

Review the 23 uncertain rows first, using the linked source video and evidence. Treat the 40 unidentified clips as an open queue if additional originals become available. For forensic or frame-exact editing use, confirm the boundary in the original video rather than treating decimal formatting or similarity scores as proof of exact timing.

## Reproduction

The public package retains the implementation scripts, result tables, compact validation records, input-integrity evidence, and selected paired panels. See [README.md](README.md) for the run card and file boundary. Large reproducible indexes, caches, logs, generated control media, the exact machine environment, and redundant panels are intentionally excluded. No external models or services are required by the media-matching pipeline itself.
