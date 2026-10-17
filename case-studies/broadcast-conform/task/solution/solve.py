"""Reference solution for broadcast-conform.

Conforms the seven mismatched sources in /app/footage to the delivery spec
and assembles them per the cut list, writing /app/master.mp4.

Nothing is hardcoded from authoring-time knowledge:
  * each source's colorimetry is MEASURED from its picture, because the color
    tags in this batch cannot be trusted: the patch strip's white/black levels
    give the signal range, and gamut legality of the saturated patches gives
    the matrix. The spec's untagged rule is the fallback if the measurement is
    ever indecisive;
  * the displayed raster comes from probing rotation and pixel aspect ratio;
  * the audio timebase error is MEASURED per source by detecting the white
    flash frames and 1 kHz beeps and fitting audio_time = a + b * video_time,
    which separates a constant slip (a) from a drifting clock (b);
  * loudness gains come from EBU R128 measurement per segment plus a final
    program trim.

SOLVE_APP overrides the /app root for local runs outside the harness.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

import numpy as np

APP = Path(os.environ.get("SOLVE_APP", "/app"))
SPEC = json.loads((APP / "delivery_spec.json").read_text())
TIMELINE = json.loads((APP / "timeline.json").read_text())
FOOTAGE = APP / "footage"

M = SPEC["master"]
TARGET_W, TARGET_H = M["width"], M["height"]
TARGET_FPS = Fraction(M["frame_rate"])
TARGET_I = M["audio"]["integrated_loudness_lufs"]

ZMATRIX = {"bt709": "709", "smpte170m": "170m", "bt470bg": "470bg"}
COEFS = {"bt709": (1.5748, 0.1873, 0.4681, 1.8556),
         "smpte170m": (1.402, 0.344136, 0.714136, 1.772)}
PATCH_FRAC = 0.12      # the strip occupies the top ~12% of every source
FIT_RESIDUAL_MAX = 0.025

# Claiming full range on both sides of a swscale conversion turns its range
# handling into a no-op, so code values pass through untouched. Without this,
# swscale rescales 0-255 to 16-235 for any source that declares full range (a
# yuvj pix_fmt or a full_range VUI flag) - which erases the very evidence the
# range measurement reads, silently and inconsistently across ffmpeg versions.
# Applied to both the measuring decode and the head of the conform chain so
# that what is measured is exactly what is later converted.
RANGE_PIN = "scale=in_range=full:out_range=full"


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True,
                   capture_output=True, text=True)


def ffprobe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of",
         "json", str(path)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def decode_frame(path, t, rw, rh):
    """One decoded frame as full-resolution (Y, U, V) planes, in raw code
    values.

    -fps_mode passthrough keeps one decoded frame per coded frame, which
    matters on the variable-rate source. RANGE_PIN is what makes the levels
    trustworthy: see its definition."""
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.6f}", "-i", str(path),
         "-frames:v", "1", "-fps_mode", "passthrough", "-vf", RANGE_PIN,
         "-pix_fmt", "yuv444p", "-f", "rawvideo", "-"],
        check=True, capture_output=True).stdout
    d = np.frombuffer(p, np.uint8).astype(np.float64)
    n = rw * rh
    if d.size != n * 3:
        raise RuntimeError(f"{path}: got {d.size} samples, expected {n * 3}")
    return (d[:n].reshape(rh, rw), d[n:2 * n].reshape(rh, rw),
            d[2 * n:].reshape(rh, rw))


def raster_of(path):
    """Decoded raster size (display rotation already applied by ffmpeg)."""
    info = ffprobe(path)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    w, h = v["width"], v["height"]
    rotation = 0
    for sd in v.get("side_data_list", []):
        if "rotation" in sd:
            rotation = int(sd["rotation"])
    if rotation % 180 != 0:
        w, h = h, w
    return w, h, rotation


def patch_strip(path, rw, rh, t=3.0):
    """Raw (Y, U, V) at the 8 patch centers, in raster coordinates."""
    Y, U, V = decode_frame(path, t, rw, rh)
    out = []
    for i in range(8):
        cx, cy = int((i + 0.5) * rw / 8), int(PATCH_FRAC * rh / 2)
        out.append((Y[cy - 2:cy + 3, cx - 2:cx + 3].mean(),
                    U[cy - 2:cy + 3, cx - 2:cx + 3].mean(),
                    V[cy - 2:cy + 3, cx - 2:cx + 3].mean()))
    return out


def measure_colorimetry(path, rw, rh):
    """What the pixels actually are, not what the bitstream claims.

    White and black patches sit at 235/16 in limited range and 255/0 in full
    range. The other six are saturated primaries, so decoding them with the
    wrong matrix pushes channels outside [0, 255]; the correct matrix keeps
    them legal.
    """
    patches = patch_strip(path, rw, rh)
    white, black = patches[0][0], patches[1][0]
    full = (abs(white - 255.0) + abs(black)
            < abs(white - 235.0) + abs(black - 16.0))
    scores = {}
    for matrix, (kr, kgb, kgr, kb) in COEFS.items():
        err = 0.0
        for y, u, v in patches:
            if full:
                yp, cb, cr = y, u - 128.0, v - 128.0
            else:
                yp = (y - 16.0) * 255.0 / 219.0
                cb, cr = (u - 128.0) * 255.0 / 224.0, (v - 128.0) * 255.0 / 224.0
            for c in (yp + kr * cr, yp - kgb * cb - kgr * cr, yp + kb * cb):
                err += max(0.0, -c) + max(0.0, c - 255.0)
        scores[matrix] = err
    best = min(scores, key=scores.get)
    if max(scores.values()) < 3.0 * max(min(scores.values()), 1e-6):
        # Indecisive: fall back on the spec's rule for untagged sources.
        best = SPEC["source_interpretation"]["untagged_color"]["matrix"]
    return best, ("pc" if full else "tv")


def probe_source(path, trust_tags=False, ignore_sar=False):
    info = ffprobe(path)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next(s for s in info["streams"] if s["codec_type"] == "audio")
    rw, rh, rotation = raster_of(path)

    sar = Fraction(1, 1)
    if not ignore_sar:
        raw = v.get("sample_aspect_ratio") or "1:1"
        if raw not in ("0:1", "N/A"):
            num, den = (int(x) for x in raw.split(":"))
            sar = Fraction(num, den)
        if rotation % 180 != 0:
            sar = 1 / sar
    if sar >= 1:
        dw, dh = int(round(rw * sar)), rh
    else:
        dw, dh = rw, int(round(rh / sar))

    if trust_tags:
        matrix = v.get("color_space")
        rng = v.get("color_range")
        if not matrix or matrix == "unknown":
            matrix = SPEC["source_interpretation"]["untagged_color"]["matrix"]
        if not rng or rng == "unknown":
            rng = SPEC["source_interpretation"]["untagged_color"]["range"]
        if rng == "limited":
            rng = "tv"
    else:
        matrix, rng = measure_colorimetry(path, rw, rh)
    if matrix == "bt470bg":
        matrix = "smpte170m"

    return {
        "path": path, "raster_w": rw, "raster_h": rh, "rotation": rotation,
        "display_w": dw, "display_h": dh, "matrix": matrix, "range": rng,
        "audio_rate": int(a["sample_rate"]),
    }


def flash_times(path):
    """First-frame pts of every white flash. Flash frames are bright and
    chroma-neutral; the saturated background never is."""
    pts_out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "frame=pts_time", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True).stdout
    pts = [float(x.strip().rstrip(","))
           for x in pts_out.split() if x.strip().rstrip(",")]
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-fps_mode", "passthrough",
         "-vf", "scale=48x28", "-pix_fmt", "yuv420p", "-f", "rawvideo", "-"],
        check=True, capture_output=True).stdout
    fsz = 48 * 28 * 3 // 2
    n = len(raw) // fsz
    times, prev = [], False
    for i in range(n):
        f = np.frombuffer(raw[i * fsz:(i + 1) * fsz], np.uint8)
        ymean = f[:48 * 28].mean()
        chroma = np.abs(f[48 * 28:].astype(np.int16) - 128).mean()
        is_hot = ymean > 200 and chroma < 12
        if is_hot and not prev and i < len(pts):
            times.append(pts[i])
        prev = bool(is_hot)
    return times


def beep_onsets(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-af", "bandpass=f=1000:width_type=q:w=4,"
                "bandpass=f=1000:width_type=q:w=4",
         "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        check=True, capture_output=True).stdout
    x = np.frombuffer(raw[:len(raw) // 2 * 2], np.int16).astype(np.float64)
    win = 32  # 2 ms at 16 kHz
    nwin = len(x) // win
    rms = np.sqrt((x[:nwin * win].reshape(nwin, win) ** 2).mean(axis=1))
    thresh = 0.02 * 32767
    onsets, quiet = [], True
    for i, v in enumerate(rms):
        if v > thresh and quiet:
            onsets.append(i * win / 16000.0)
            quiet = False
        elif v < thresh * 0.5:
            quiet = True
    return onsets


def measure_timebase(path):
    """Fit audio_time = a + b * video_time over the flash/beep marker pairs.

    a is a constant sync slip, b is a clock-rate error. A large residual means
    the marker pairing itself is unreliable, so claim nothing rather than
    "correct" a source by a bogus amount.
    """
    ft, bt = flash_times(path), beep_onsets(path)
    if len(ft) < 4 or len(ft) != len(bt):
        return 0.0, 1.0
    b, a = np.polyfit(np.array(ft), np.array(bt), 1)
    resid = np.abs(np.array(bt) - (a + b * np.array(ft))).max()
    if resid > FIT_RESIDUAL_MAX:
        return 0.0, 1.0
    return float(a), float(b)


def integrated_lufs(path):
    p = subprocess.run(
        ["ffmpeg", "-nostats", "-i", str(path),
         "-filter_complex", "ebur128", "-f", "null", "-"],
        capture_output=True, text=True)
    lines = p.stderr.splitlines()
    for i, ln in enumerate(lines):
        if "Integrated loudness" in ln:
            for ln2 in lines[i:i + 4]:
                if re.search(r"\bI:", ln2):
                    return float(ln2.split("I:")[1].split("LUFS")[0])
    raise RuntimeError("ebur128 summary not found:\n" + p.stderr[-2000:])


def fit_geometry(dw, dh):
    scale = min(TARGET_W / dw, TARGET_H / dh)
    fw = int(round(dw * scale / 2)) * 2
    fh = int(round(dh * scale / 2)) * 2
    return fw, fh, (TARGET_W - fw) // 2, (TARGET_H - fh) // 2


def conform_segment(seg, src, drift, out_video, out_audio, opts):
    path = src["path"]
    t_in, t_out = seg["source_in_sec"], seg["source_out_sec"]
    dur = t_out - t_in

    # Video: CFR conform, explicit colorimetry conversion, fit-and-pad. The
    # scale from the raster to the fitted size is what applies the pixel
    # aspect ratio, so anamorphic sources come out geometrically right.
    fw, fh, px, py = fit_geometry(src["display_w"], src["display_h"])
    vf = ["setpts=PTS-STARTPTS", f"fps={TARGET_FPS}", RANGE_PIN]
    if not opts.retag_only:
        vf.append(f"zscale=matrixin={ZMATRIX[src['matrix']]}"
                  f":rangein={'full' if src['range'] == 'pc' else 'limited'}"
                  f":matrix=709:range=limited")
    vf.append("format=yuv420p")
    vf.append(f"scale={fw}:{fh}:in_range=limited:out_range=limited")
    if (fw, fh) != (TARGET_W, TARGET_H):
        vf.append(f"pad={TARGET_W}:{TARGET_H}:{px}:{py}:black")
    vf.append("setsar=1")
    run(["ffmpeg", "-y", "-v", "error", "-ss", t_in, "-t", dur, "-i", path,
         "-an", "-vf", ",".join(vf),
         "-c:v", "libx264", "-preset", "fast", "-crf", "10",
         "-video_track_timescale", "90000", out_video])

    # Audio: undo the measured timebase error, cut, resample.
    a, b = drift
    af = []
    if abs(b - 1.0) > 2e-4:
        af.append(f"asetrate={round(src['audio_rate'] * b)}")
    shift = a / b
    if abs(shift) > 0.015:
        if shift > 0:
            af.append(f"atrim=start={shift:.6f}")
        else:
            af.append(f"adelay={int(-shift * 1000)}|{int(-shift * 1000)}")
    if af:
        af.append("asetpts=PTS-STARTPTS")
    af.append(f"atrim=start={t_in}:end={t_out}")
    af.append("asetpts=PTS-STARTPTS")
    af.append("aresample=48000")
    run(["ffmpeg", "-y", "-v", "error", "-i", path, "-vn",
         "-af", ",".join(af), "-ac", "2", "-c:a", "pcm_s16le", out_audio])


def main():
    ap = argparse.ArgumentParser()
    # Deliberately wrong variants, used at authoring time to confirm each
    # check actually discriminates. The default run is the real solution.
    ap.add_argument("--retag-only", action="store_true")
    ap.add_argument("--trust-tags", action="store_true")
    ap.add_argument("--ignore-sar", action="store_true")
    ap.add_argument("--no-drift-fix", action="store_true")
    ap.add_argument("--global-gain-only", action="store_true")
    ap.add_argument("--out", default=None)
    opts = ap.parse_args()

    out_path = Path(opts.out) if opts.out else APP / "master.mp4"
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        vlist, alist = [], []
        for seg in TIMELINE["segments"]:
            path = FOOTAGE / seg["source"]
            src = probe_source(path, opts.trust_tags, opts.ignore_sar)
            drift = (0.0, 1.0) if opts.no_drift_fix else measure_timebase(path)
            ov, oa = td / f"v{seg['index']}.mp4", td / f"a{seg['index']}.wav"
            conform_segment(seg, src, drift, ov, oa, opts)
            vlist.append(ov)
            alist.append(oa)
            print(f"segment {seg['index']} ({seg['source']}) conformed: "
                  f"{src['matrix']}/{src['range']} raster "
                  f"{src['raster_w']}x{src['raster_h']} display "
                  f"{src['display_w']}x{src['display_h']} slip "
                  f"{drift[0] * 1000:+.0f}ms rate {drift[1]:.6f}", flush=True)

        # Per-segment leveling to the program target, then a program trim.
        if opts.global_gain_only:
            gains = [0.0] * len(alist)
        else:
            gains = [TARGET_I - integrated_lufs(oa) for oa in alist]
        program = td / "program.wav"
        ain, fc = [], []
        for i, (oa, g) in enumerate(zip(alist, gains)):
            ain += ["-i", str(oa)]
            fc.append(f"[{i}:a]volume={g:.3f}dB[g{i}]")
        fc.append("".join(f"[g{i}]" for i in range(len(alist))) +
                  f"concat=n={len(alist)}:v=0:a=1[out]")
        run(["ffmpeg", "-y", "-v", "error", *ain,
             "-filter_complex", ";".join(fc), "-map", "[out]",
             "-c:a", "pcm_s16le", program])
        trim = TARGET_I - integrated_lufs(program)

        lst = td / "concat.txt"
        lst.write_text("".join(f"file '{v}'\n" for v in vlist))
        run(["ffmpeg", "-y", "-v", "error",
             "-f", "concat", "-safe", "0", "-i", lst, "-i", program,
             "-map", "0:v", "-map", "1:a",
             # setparams stamps the color description into the frame props;
             # modern ffmpeg encoders take VUI tags from frames, not CLI flags.
             "-vf", (f"fps={TARGET_FPS},setsar=1,"
                     "setparams=colorspace=bt709:color_primaries=bt709"
                     ":color_trc=bt709:range=tv"),
             "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-g", M["max_keyframe_interval_frames"], "-fps_mode", "cfr",
             "-colorspace", "bt709", "-color_primaries", "bt709",
             "-color_trc", "bt709", "-color_range", "tv",
             "-af", f"volume={trim:.3f}dB,aresample=48000",
             "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
             "-brand", "isom", "-movflags", "+faststart", out_path])
    print(f"wrote {out_path}")


if __name__ == "__main__":
    sys.exit(main())
