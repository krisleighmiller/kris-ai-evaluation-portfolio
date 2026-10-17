"""QC suite for the delivered master (/app/master.mp4).

Every assertion traces to a requirement in instruction.md or in
delivery_spec.json. Reference numbers come from tests/ground_truth.json,
built at authoring time from the seed sources; the cut list is baked into
those references, so nothing here reads /app/timeline.json. Thresholds come
from tests/delivery_spec.json, never from the agent-writable /app copy: that
copy publishes the same requirements and the same numbers, and an agent
editing it changes nothing (test_inputs_unmodified also re-hashes it). The
only keys this copy adds are prose for reviewers and verifier_measurement,
which holds the limited-range reference levels rather than any tolerance the
agent is held to. Measurement machinery that is not a bound on the master
(sampling boxes, detector gates, measurement windows) lives in qc_lib.py and
in the test bodies, deliberately outside both spec copies.

QC_APP overrides the /app root for local runs outside the harness.
"""

import hashlib
import json
import os
import sys
from fractions import Fraction
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import qc_lib as qc

APP = Path(os.environ.get("QC_APP", "/app"))
SPEC = json.loads((TESTS / "delivery_spec.json").read_text())
GT = json.loads((TESTS / "ground_truth.json").read_text())
INPUT_HASHES = json.loads((TESTS / "input_hashes.json").read_text())
MASTER = APP / "master.mp4"

M = SPEC["master"]
TOL = SPEC["tolerances"]
MEAS = SPEC["verifier_measurement"]
FPS = Fraction(M["frame_rate"])
FRAME = 1.0 / float(FPS)
RGB_TOL = TOL["patch_rgb_tolerance"]
LUMA_WHITE = MEAS["reference_luma_white"]
LUMA_BLACK = MEAS["reference_luma_black"]
LUMA_TOL = TOL["luma_tolerance"]
CHROMA_TOL = TOL["chroma_neutral_tolerance"]
DUR_TOL_FRAMES = TOL["duration_tolerance_frames"]
PROG_DUR_TOL = TOL["program_duration_tolerance_ms"] / 1000.0
# Program length comes from the cut list through the ground truth rather than
# a literal, so a change to the cut list cannot leave a stale constant here.
PROGRAM_SEC = max(s["master_start"] + s["duration"] for s in GT["segments"])
PROGRAM_FRAMES = round(PROGRAM_SEC * float(FPS))
SYNC_TOL = M["av_sync_tolerance_ms"] / 1000.0
SPACING_TOL = M["beep_interval_tolerance_ms"] / 1000.0
MATCH_WIN = M["marker_placement_tolerance_ms"] / 1000.0
# Closest bed tones sit ~5-6% apart; measurement error is ~0.15 Hz and
# residual drift <1%, so 3% separates every wrong-source case from the
# right one.
BED_HZ_REL_TOL = TOL["bed_hz_relative_tolerance"]
# Brands that identify an ISO base-media file, matched against the major
# brand or the compatible-brand list. A file that names none of them (notably
# a QuickTime one, whose "qt  " brand declares only itself) is a different
# container wearing an .mp4 name.
ISO_BRANDS = {"isom", "iso2", "iso4", "iso5", "iso6", "mp41", "mp42", "mp71",
              "avc1", "m4v", "mmp4", "dash", "cmfc", "msdh"}

_cache = {}


def flash_metrics():
    if "fmetrics" not in _cache:
        _cache["fmetrics"] = qc.frame_flash_metrics(MASTER)
    return _cache["fmetrics"]


def flashes():
    if "flashes" not in _cache:
        _cache["flashes"] = qc.onsets_from_metrics(*flash_metrics())
    return _cache["flashes"]


def beeps():
    if "beeps" not in _cache:
        _cache["beeps"] = qc.beep_onsets(MASTER)
    return _cache["beeps"]


def program_loudness():
    if "loud" not in _cache:
        _cache["loud"] = qc.ebur128_summary(MASTER)
    return _cache["loud"]


def expected_markers():
    return sorted(t for s in GT["segments"] for t in s["markers_master"])


def nearest(vals, t):
    return min(vals, key=lambda v: abs(v - t)) if vals else None


def test_deliverable_exists():
    """Instruction: the finished master must be written to /app/master.mp4."""
    assert MASTER.is_file(), f"{MASTER} does not exist"
    assert MASTER.stat().st_size > 0, f"{MASTER} is empty"


def test_inputs_unmodified():
    """Instruction: the footage and both JSON files must be left byte for
    byte unchanged. Compares sha256 of every input against authoring-time
    hashes."""
    for rel, expected in INPUT_HASHES.items():
        p = APP / Path(rel).relative_to("/app")
        assert p.is_file(), f"input file {rel} is missing"
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        assert got == expected, f"input file {rel} was modified"


def test_stream_properties():
    """Spec: mp4 container, progressive h264, 1920x1080 square-pixel,
    yuv420p, BT.709 limited tags, AAC 48 kHz stereo."""
    info = qc.ffprobe(MASTER)
    v, a = qc.vstream(info), qc.astream(info)
    fmt = info["format"]
    assert "mp4" in fmt["format_name"].split(","), fmt["format_name"]
    tags = fmt.get("tags", {})
    brand = tags.get("major_brand", "").strip().lower()
    # An ISO base-media file may carry an unlisted major brand and still
    # declare a listed one among its compatible brands, which is how the
    # format advertises conformance; accept either. ffprobe reports the
    # compatible list as concatenated four-character codes.
    compat = tags.get("compatible_brands", "").lower()
    compat = {compat[i:i + 4].strip() for i in range(0, len(compat), 4)}
    assert brand in ISO_BRANDS or compat & ISO_BRANDS, (
        f"major_brand {brand!r} is not an ISO base-media brand and the "
        f"compatible brands {sorted(compat)} name none either; the spec "
        f"requires a genuine MP4")
    n_v = sum(1 for s in info["streams"] if s["codec_type"] == "video")
    n_a = sum(1 for s in info["streams"] if s["codec_type"] == "audio")
    assert (n_v, n_a, len(info["streams"])) == (1, 1, 2), (
        f"spec requires exactly one video and one audio stream, found "
        f"{len(info['streams'])} streams ({n_v} video, {n_a} audio)")
    assert v["codec_name"] == "h264", v["codec_name"]
    # Rejects any explicit interlaced coding claim. "unknown" is accepted
    # because encoders are not obliged to write the field order and a correct
    # progressive master must not fail on a missing tag; every conform path
    # available here (all seven sources are progressive) yields progressive
    # pixels, so an interlaced delivery would have to be constructed on
    # purpose and would still have to declare itself to be caught.
    assert v.get("field_order", "unknown") in ("progressive", "unknown"), (
        f"scan must be progressive, or leave the field order unspecified; "
        f"got {v.get('field_order')}")
    assert (v["width"], v["height"]) == (M["width"], M["height"])
    # Square pixels: an anamorphic master would display the wrong shape even
    # at the right coded size.
    sar = (v.get("sample_aspect_ratio") or "1:1").strip()
    if sar not in ("N/A", "0:1", ""):
        num, den = (int(x) for x in sar.split(":"))
        assert num == den, (
            f"master must have {M['sample_aspect_ratio']} pixel aspect ratio, "
            f"got {sar}")
    assert v["pix_fmt"] == M["pix_fmt"], v["pix_fmt"]
    assert v.get("color_space") == "bt709", v.get("color_space")
    assert v.get("color_primaries") == "bt709", v.get("color_primaries")
    assert v.get("color_transfer") == "bt709", v.get("color_transfer")
    assert v.get("color_range") == "tv", v.get("color_range")
    assert a["codec_name"] == "aac", a["codec_name"]
    assert a["sample_rate"] == str(M["audio"]["sample_rate_hz"])
    assert a["channels"] == M["audio"]["channels"]


def test_cfr_and_duration():
    """Spec: 30/1 constant frame rate declared and delivered, and the cut
    list's program length honoured by the video stream, the container and the
    audio stream, so neither a trailing audio tail nor a truncated audio
    track can hide behind an exactly correct video stream."""
    pts = qc.frame_pts(MASTER)
    assert abs(len(pts) - PROGRAM_FRAMES) <= DUR_TOL_FRAMES, (
        f"{len(pts)} frames, expected {PROGRAM_FRAMES}")
    deltas = [b - a for a, b in zip(pts, pts[1:])]
    # 1 ms absorbs container timescales that cannot represent 1/30 exactly
    # (e.g. 1000: 33/34 ms ticks) while still rejecting real VFR cadences,
    # whose intervals deviate by multiple milliseconds.
    bad = [d for d in deltas if abs(d - FRAME) > 1e-3]
    assert not bad, f"{len(bad)} non-CFR frame intervals, e.g. {bad[:3]}"
    assert abs(pts[-1] + FRAME - PROGRAM_SEC) <= DUR_TOL_FRAMES * FRAME + 1e-3, (
        f"video duration {pts[-1] + FRAME}, expected {PROGRAM_SEC}")
    info = qc.ffprobe(MASTER)
    # The declared rate must agree with the delivered cadence: a master that
    # places frames on a 1/30 grid while announcing 30000/1001 is mislabelled.
    # 0.05% admits every exact representation of 30 and still rejects 29.97.
    raw_rate = qc.vstream(info).get("avg_frame_rate") or ""
    try:
        declared = float(Fraction(raw_rate))
    except (ValueError, ZeroDivisionError):
        declared = 0.0
    assert abs(declared / float(FPS) - 1.0) <= 5e-4, (
        f"declared frame rate {raw_rate!r} does not match {M['frame_rate']}")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), {})
    reported = {"container": info["format"].get("duration"),
                "audio stream": a.get("duration")}
    for what, d in reported.items():
        assert d is not None, (
            f"master reports no {what} duration; the spec requires both to "
            f"match the program length")
        assert abs(float(d) - PROGRAM_SEC) <= PROG_DUR_TOL, (
            f"{what} duration {float(d):.3f}s, expected {PROGRAM_SEC}s within "
            f"{PROG_DUR_TOL * 1000:.0f} ms")


def test_keyframe_interval():
    """Spec: max keyframe interval of 60 frames (2 s)."""
    kf = qc.keyframe_pts(MASTER)
    assert kf and kf[0] < FRAME, "first frame must be a keyframe"
    limit = M["max_keyframe_interval_frames"] * FRAME + 1e-3
    gaps = [b - a for a, b in zip(kf, kf[1:])]
    assert all(g <= limit for g in gaps), f"max GOP {max(gaps):.2f}s"
    end = qc.frame_pts(MASTER)[-1] + FRAME
    assert end - kf[-1] <= limit, "tail GOP exceeds limit"


def test_limited_range_levels():
    """Spec: pixel data must genuinely be limited range in every segment.
    The white and black patches of the strip must sit at Y=235/16, not
    255/0. This is the check that catches a full-range source whose pixels
    were retagged instead of converted: saturated RGB patches clip to
    near-identical values under both range interpretations, but raw luma
    cannot hide 255-vs-235."""
    for seg in GT["segments"]:
        t = seg["patches"]["master_t"]
        wx, wy = seg["patches"]["centers"][0]
        kx, ky = seg["patches"]["centers"][1]
        wl = qc.sample_luma(MASTER, t, wx, wy)
        kl = qc.sample_luma(MASTER, t, kx, ky)
        assert abs(wl - LUMA_WHITE) <= LUMA_TOL, (
            f"segment {seg['index']} ({seg['source']}) white patch "
            f"Y={wl:.1f} (expect ~{LUMA_WHITE})")
        assert abs(kl - LUMA_BLACK) <= LUMA_TOL, (
            f"segment {seg['index']} ({seg['source']}) black patch "
            f"Y={kl:.1f} (expect ~{LUMA_BLACK})")


def test_patch_colorimetry():
    """Instruction/spec: color must actually be converted to BT.709 limited.
    Every segment's patch strip, decoded as BT.709 limited, must match the
    authoring-time reference values.

    This is also what enforces conversion_scope_note's prohibition on
    gamut-mapping primaries or remapping the transfer curve, which no
    assertion names directly: a SMPTE 170M to BT.709 primaries conversion
    moves these references by up to 79 per channel against a tolerance of
    10, so it fails here rather than passing unnoticed."""
    for seg in GT["segments"]:
        p = seg["patches"]
        for (cx, cy), exp in zip(p["centers"], p["rgb"]):
            got = qc.sample_rgb(MASTER, p["master_t"], cx, cy, "bt709", "tv")
            err = max(abs(g - e) for g, e in zip(got, exp))
            assert err <= RGB_TOL, (
                f"segment {seg['index']} ({seg['source']}) patch at "
                f"({cx},{cy}): got {[round(g) for g in got]} "
                f"expected {[round(e) for e in exp]} (err {err:.0f})")


def test_segment_content_and_cuts():
    """Instruction/spec: the correct source frame must land at the correct
    master time. Checked via the background hue signature at five times per
    segment including 2 frames inside each side of every cut, so a boundary
    displaced by 3+ frames samples the wrong source and fails hard;
    finer placement inside segments is bounded by test_av_sync's
    marker_placement_tolerance_ms."""
    for seg in GT["segments"]:
        for s in seg["samples"]:
            x, y = s["xy"]
            got = qc.sample_rgb(MASTER, s["master_t"], x, y, "bt709", "tv")
            err = max(abs(g - e) for g, e in zip(got, s["rgb"]))
            assert err <= RGB_TOL, (
                f"segment {seg['index']} ({seg['source']}) at master "
                f"t={s['master_t']}: got {[round(g) for g in got]} "
                f"expected {[round(e) for e in s['rgb']]} (err {err:.0f})")


def test_padding():
    """Spec: sources whose displayed shape does not fill the frame must be
    centered over limited-range black padding (Y~16, neutral chroma); sources
    whose displayed shape does fill it must have no padding at all. Samples
    the middle of every pad bar, so grey, mirrored, or blurred fills fail, and
    samples just inside both side edges of every full-frame segment, so a
    source left pillarboxed (an anamorphic raster treated as square pixels, or
    an undersized source not scaled up) fails too. That second check reads the
    absence of limited-range black rather than the presence of picture, which
    is what makes it safe on any source content: every seed source carries a
    saturated background out to its edges, well clear of black."""
    for seg in GT["segments"]:
        x0, y0, w, h = seg["content_rect"]  # pad offset + fitted size
        if (w, h) == (M["width"], M["height"]):
            t = seg["patches"]["master_t"]
            for px in (6, M["width"] - 7):
                yy, uu, vv = qc.sample_yuv(MASTER, t, px, M["height"] // 2)
                assert not (abs(yy - LUMA_BLACK) <= LUMA_TOL
                            and abs(uu - 128) <= CHROMA_TOL
                            and abs(vv - 128) <= CHROMA_TOL), (
                    f"segment {seg['index']} ({seg['source']}) fills the "
                    f"frame in the cut list but is black at ({px},"
                    f"{M['height'] // 2}): picture must reach the edges")
            continue
        t = seg["patches"]["master_t"]
        centers = []
        if x0 > 0:  # pillarbox bars
            centers.append((x0 // 2, M["height"] // 2))
            centers.append(((x0 + w + M["width"]) // 2, M["height"] // 2))
        if y0 > 0:  # letterbox bars
            centers.append((M["width"] // 2, y0 // 2))
            centers.append((M["width"] // 2, (y0 + h + M["height"]) // 2))
        for px, py in centers:
            yy, uu, vv = qc.sample_yuv(MASTER, t, px, py)
            assert (abs(yy - LUMA_BLACK) <= LUMA_TOL
                    and abs(uu - 128) <= CHROMA_TOL
                    and abs(vv - 128) <= CHROMA_TOL), (
                f"segment {seg['index']} ({seg['source']}) pad at "
                f"({px},{py}): YUV=({yy:.1f},{uu:.1f},{vv:.1f}), expected "
                f"limited-range black (~{LUMA_BLACK},128,128)")


def test_av_sync():
    """Spec: the master must contain exactly the flash/beep events the cut
    list places inside it, each within marker_placement_tolerance_ms of its
    cut-list position, and every flash/beep pair must agree within
    av_sync_tolerance_ms."""
    fl, bp = flashes(), beeps()
    exp = expected_markers()
    for what, got in (("white flashes", fl), ("beeps", bp)):
        missing = [f"{t:.3f}" for t in exp
                   if nearest(got, t) is None
                   or abs(nearest(got, t) - t) > MATCH_WIN]
        assert len(got) == len(exp), (
            f"expected {len(exp)} {what}, detected {len(got)}"
            + (f"; nothing within {MATCH_WIN * 1000:.0f} ms of master "
               f"t={', '.join(missing)}" if missing else ""))
    for t in exp:
        f = nearest(fl, t)
        b = nearest(bp, t)
        assert f is not None and abs(f - t) <= MATCH_WIN, (
            f"no flash near master t={t} (nearest {f})")
        assert b is not None and abs(b - t) <= MATCH_WIN, (
            f"no beep near master t={t} (nearest {b})")
        assert abs(f - b) <= SYNC_TOL, (
            f"marker at t={t}: flash {f:.3f} vs beep {b:.3f} "
            f"offset {(f - b) * 1000:.0f} ms")
    # "None extra" in both directions: matching every expected marker to a
    # detected one leaves room, in principle, for a spurious event elsewhere
    # to be balanced by two expected markers sharing a detection.
    for what, got in (("flash", fl), ("beep", bp)):
        for d in got:
            assert abs(d - nearest(exp, d)) <= MATCH_WIN, (
                f"unexpected {what} at master t={d:.3f}: the cut list places "
                f"no marker there")


def test_no_synthesized_frames():
    """Spec (cut_point_note): every master frame must be a source frame, not
    one mixed from two of them.

    Checked at the flashes, which the spec sentence names, because they are the
    one place in this material where consecutive frames differ sharply: a
    source frame is either full-frame white or ordinary picture, so on this
    gate a correct master reads 235.0 for every flash and 63-105 for
    everything else, with nothing between. A frame mixed from a flash and its
    neighbour lands in that empty middle. The band starts 45 code values above
    the brightest ordinary frame and stops 35 below a flash, so no faithful
    conform can reach it however it duplicates or decimates.

    Scope, measured: an unconditional blend puts 22 frames inside the band,
    while ffmpeg's framerate and minterpolate filters suppress blending at
    scene changes and pass. Their blends elsewhere shift the slow background
    hue by ~0.14 of a code value, which nothing on this near-static material
    can separate from a faithful frame, so this check is deliberately the
    narrow one the spec describes rather than a general synthesis detector."""
    pts, metrics = flash_metrics()
    for i, (luma, neutral) in enumerate(metrics):
        if qc.is_flash(luma, neutral):
            continue
        t = pts[i] if i < len(pts) else i * FRAME
        assert luma < qc.BACKGROUND_LUMA, (
            f"frame at master t={t:.3f} is neither a flash nor ordinary "
            f"picture (central luma {luma:.1f}, non-neutrality {neutral:.1f}): "
            f"it looks like a flash blended with its neighbour, so it is not a "
            f"frame that exists in the source")


def test_beep_spacing():
    """Spec: spacing between consecutive beeps inside a segment must match
    the drift-normalized spacing of those beeps in the source audio within
    beep_interval_tolerance_ms. The reference (beep_gaps_master) was measured
    from each source's own beep onsets at authoring time with the recorder
    clock drift fitted out, so a faithful conform matches it near-exactly
    while uncorrected drift misses by ~30 ms. Catches residual drift that a
    constant offset would hide.

    The references are deliberately the source's real spacing and not the
    nominal 5 s of the marker grid: the recordings place their beeps on a
    ~21 ms gate grid, so consecutive source gaps genuinely run 4.992-5.014 s.
    Copying a source's audio faithfully reproduces that; re-timing beeps onto
    the flash grid does not, and the spec sentence asks for the former."""
    bp = beeps()
    for seg in GT["segments"]:
        marks = seg["markers_master"]
        gaps_exp = seg["beep_gaps_master"]
        if len(marks) < 2:
            continue
        got = [nearest(bp, t) for t in marks]
        for i, expected_gap in enumerate(gaps_exp):
            gap = got[i + 1] - got[i]
            assert abs(gap - expected_gap) <= SPACING_TOL, (
                f"segment {seg['index']} ({seg['source']}): beep spacing "
                f"{gap:.4f}s vs expected {expected_gap:.4f}s")


def test_segment_audio_provenance():
    """Spec: each segment's audio must be its own source's audio. Every
    source's bed is a distinct low-frequency tone, so the dominant 100-600 Hz
    frequency inside each master segment must match the authoring-time value
    for that segment's source. Substituting another source's bed moves the
    measurement to that source's discrete tone; the closest such pair sits
    4.9% apart (E.mov 330.00 Hz, F.mp4 346.95 Hz), which a 3% band around the
    right answer does not reach."""
    for seg in GT["segments"]:
        ss = seg["master_start"] + 0.5
        dur = seg["duration"] - 1.5
        got = qc.bed_frequency(MASTER, ss, dur)
        exp = seg["bed_hz"]
        assert abs(got - exp) <= BED_HZ_REL_TOL * exp, (
            f"segment {seg['index']} ({seg['source']}) audio bed at "
            f"{got:.1f} Hz, expected ~{exp:.1f} Hz: wrong or substituted "
            f"audio")


def test_program_loudness():
    """Spec: integrated loudness -14 LUFS within 0.5 LU, and an oversampled
    true peak no higher than true_peak_max_dbtp (-1 dBTP) plus the published
    true_peak_tolerance_db (0.2 dB), so the enforced ceiling is -0.8 dBTP.
    Both numbers are published, and the allowance exists because the master is
    written by one ffmpeg build and measured by another, whose oversampled peak
    reading is not guaranteed to agree to the last tenth of a dB."""
    integrated, peak, _ = program_loudness()
    target = M["audio"]["integrated_loudness_lufs"]
    tol = M["audio"]["integrated_loudness_tolerance_lu"]
    assert abs(integrated - target) <= tol, f"integrated {integrated} LUFS"
    peak_limit = (M["audio"]["true_peak_max_dbtp"]
                  + M["audio"]["true_peak_tolerance_db"])
    assert peak is not None and peak <= peak_limit, (
        f"true peak {peak} dBTP exceeds {M['audio']['true_peak_max_dbtp']} "
        f"dBTP plus the {M['audio']['true_peak_tolerance_db']} dB "
        f"measurement allowance")


def test_segment_loudness():
    """Spec: each segment's mean short-term loudness must sit within
    segment_loudness_tolerance_lu of the program integrated loudness."""
    integrated, _, _ = program_loudness()
    tol = M["audio"]["segment_loudness_tolerance_lu"]
    for seg in GT["segments"]:
        _, _, shorts = qc.ebur128_summary(
            MASTER, ss=seg["master_start"], t=seg["duration"])
        assert shorts, f"segment {seg['index']}: no short-term readings"
        mean_s = sum(shorts) / len(shorts)
        assert abs(mean_s - integrated) <= tol, (
            f"segment {seg['index']} ({seg['source']}) mean short-term "
            f"{mean_s:.1f} LUFS vs program {integrated:.1f} LUFS")
