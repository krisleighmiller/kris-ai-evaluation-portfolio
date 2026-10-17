"""Shared measurement helpers for the master QC suite.

Everything decodes through ffmpeg to raw planes/PCM and does the math in
numpy, so no check depends on swscale's colorspace handling (which silently
ignores range overrides).

Raw decodes pass -fps_mode passthrough so one decoded frame is one coded
frame. Without it ffmpeg silently conforms the output to the guessed constant
rate, which breaks the frame-index-to-pts mapping on variable-rate input.
They also pin the swscale range conversion off, so the levels measured are the
coded levels rather than something swscale rescaled on the way out.
"""

import json
import re
import subprocess

import numpy as np


def ffprobe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format",
         "-of", "json", str(path)], check=True, capture_output=True,
        text=True).stdout
    return json.loads(out)


def vstream(info):
    return next(s for s in info["streams"] if s["codec_type"] == "video")


def astream(info):
    return next(s for s in info["streams"] if s["codec_type"] == "audio")


def frame_pts(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "frame=pts_time", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True).stdout
    return [float(x.strip().rstrip(","))
            for x in out.split() if x.strip().rstrip(",")]


def keyframe_pts(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "frame=key_frame,pts_time", "-of", "csv=p=0",
         str(path)], check=True, capture_output=True, text=True).stdout
    pts = []
    for line in out.splitlines():
        parts = [p for p in line.strip().split(",") if p != ""]
        if len(parts) >= 2 and parts[0] == "1":
            pts.append(float(parts[1]))
    return pts


def decode_yuv_frame(path, t):
    """Decode the first frame with pts >= t to planar YUV420 numpy arrays.
    Auto-rotation applies. Returns (Y, U, V) with U/V at half resolution.

    in_range=full:out_range=full makes the pixel-format conversion a true
    no-op on the code values: without it, swscale rescales 0-255 to 16-235
    whenever the input declares full range (a yuvj pix_fmt or a full_range
    VUI flag), which both destroys the evidence this suite measures and
    varies by ffmpeg version. Every level here is a raw code value."""
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{max(t - 0.008, 0):.6f}",
         "-i", str(path), "-frames:v", "1", "-fps_mode", "passthrough",
         "-vf", "scale=in_range=full:out_range=full",
         "-pix_fmt", "yuv420p", "-f", "rawvideo", "-"],
        check=True, capture_output=True)
    data = np.frombuffer(p.stdout, np.uint8)
    for w, h in [(1920, 1080), (1440, 1080), (1080, 1920), (1280, 1024),
                 (1280, 720)]:
        if data.size == w * h * 3 // 2:
            y = data[:w * h].reshape(h, w).astype(np.float64)
            u = data[w * h:w * h + w * h // 4].reshape(h // 2, w // 2)
            v = data[w * h + w * h // 4:].reshape(h // 2, w // 2)
            return y, u.astype(np.float64), v.astype(np.float64)
    raise RuntimeError(f"unexpected raw frame size {data.size} from {path}")


# BT.709 / BT.601 YUV -> RGB, limited or full range, done in numpy so the
# interpretation is explicit.
_COEFS = {"bt709": (1.5748, 0.1873, 0.4681, 1.8556),
          "smpte170m": (1.402, 0.344136, 0.714136, 1.772)}


def yuv_to_rgb(y, u, v, matrix, rng, clip=True):
    kr_cr, kg_cb, kg_cr, kb_cb = _COEFS[matrix]
    if rng in ("tv", "limited"):
        yp = (y - 16.0) * 255.0 / 219.0
        cb = (u - 128.0) * 255.0 / 224.0
        cr = (v - 128.0) * 255.0 / 224.0
    else:
        yp = y.copy() if hasattr(y, "copy") else y
        cb = u - 128.0
        cr = v - 128.0
    r = yp + kr_cr * cr
    g = yp - kg_cb * cb - kg_cr * cr
    b = yp + kb_cb * cb
    if not clip:
        return [r, g, b]
    return [np.clip(c, 0, 255) for c in (r, g, b)]


def sample_rgb(path, t, x, y, matrix="bt709", rng="tv", box=5):
    """Mean RGB of a box x box region centered at (x, y) in display pixels."""
    Y, U, V = decode_yuv_frame(path, t)
    h = box // 2
    ys, ye = y - h, y + h + 1
    xs, xe = x - h, x + h + 1
    yy = Y[ys:ye, xs:xe]
    uu = U[ys // 2:ye // 2 + 1, xs // 2:xe // 2 + 1]
    vv = V[ys // 2:ye // 2 + 1, xs // 2:xe // 2 + 1]
    r, g, b = yuv_to_rgb(yy.mean(), np.array(uu.mean()), np.array(vv.mean()),
                         matrix, rng)
    return float(r), float(g), float(b)


def sample_luma(path, t, x, y, box=5):
    Y, _, _ = decode_yuv_frame(path, t)
    h = box // 2
    return float(Y[y - h:y + h + 1, x - h:x + h + 1].mean())


def sample_yuv(path, t, x, y, box=5):
    """Mean raw (Y, U, V) of a box x box region centered at (x, y)."""
    Y, U, V = decode_yuv_frame(path, t)
    h = box // 2
    yy = Y[y - h:y + h + 1, x - h:x + h + 1].mean()
    uu = U[(y - h) // 2:(y + h) // 2 + 1, (x - h) // 2:(x + h) // 2 + 1].mean()
    vv = V[(y - h) // 2:(y + h) // 2 + 1, (x - h) // 2:(x + h) // 2 + 1].mean()
    return float(yy), float(uu), float(vv)


def bed_frequency(path, ss, t):
    """Dominant audio frequency in the 100-600 Hz band over [ss, ss+t].

    Each source's audio bed is a distinct low-frequency tone, so this
    identifies which source's audio is present. The 1 kHz sync beeps are
    excluded by the band limit."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{ss:.6f}", "-t", f"{t:.6f}",
         "-i", str(path), "-ac", "1", "-ar", "8000", "-f", "f32le", "-"],
        check=True, capture_output=True).stdout
    x = np.frombuffer(raw[:len(raw) // 4 * 4], np.float32).astype(np.float64)
    if x.size < 8000:
        raise RuntimeError(f"only {x.size} audio samples decoded from {path}")
    spec = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    freqs = np.fft.rfftfreq(x.size, 1.0 / 8000.0)
    band = (freqs >= 100.0) & (freqs <= 600.0)
    return float(freqs[band][np.argmax(spec[band])])


FLASH_LUMA = 200      # a flash frame is white across the central half
FLASH_NEUTRAL = 24    # ...and close to neutral, so bright colour cannot fake one
BACKGROUND_LUMA = 150  # every other frame of this material sits well below this


def frame_flash_metrics(path):
    """(pts, [(mean luma, chroma non-neutrality)]) per frame.

    Measured on the central half of the picture so pillarbox/letterbox bars
    cannot dilute a flash. One decode serves both the flash detector and the
    frame-synthesis check, so callers should share the result."""
    pts = frame_pts(path)
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-fps_mode", "passthrough",
         "-vf", "scale=48x28", "-pix_fmt", "yuv420p", "-f", "rawvideo", "-"],
        check=True, capture_output=True).stdout
    fsz = 48 * 28 * 3 // 2
    out = []
    for i in range(len(raw) // fsz):
        f = np.frombuffer(raw[i * fsz:(i + 1) * fsz], np.uint8)
        y = f[:48 * 28].reshape(28, 48)[7:21, 12:36]
        u = f[48 * 28:48 * 28 + 24 * 14].reshape(14, 24)[4:11, 6:18]
        v = f[48 * 28 + 24 * 14:].reshape(14, 24)[4:11, 6:18]
        neutral = (np.abs(u.astype(np.int16) - 128).mean() +
                   np.abs(v.astype(np.int16) - 128).mean())
        out.append((float(y.mean()), float(neutral)))
    return pts, out


def is_flash(luma, neutral):
    return luma > FLASH_LUMA and neutral < FLASH_NEUTRAL


def onsets_from_metrics(pts, metrics):
    """pts of the first frame of every white flash."""
    onsets, prev = [], False
    for i, (luma, neutral) in enumerate(metrics):
        hot = is_flash(luma, neutral)
        if hot and not prev and i < len(pts):
            onsets.append(pts[i])
        prev = hot
    return onsets


def flash_onsets(path):
    return onsets_from_metrics(*frame_flash_metrics(path))


def beep_onsets(path):
    """Onsets of the 1 kHz sync bursts, isolated from the low tone bed.

    Two cascaded narrow bandpass stages put the loudest bed residue ~28 dB
    under the weakest beep of a correctly conformed master, so the threshold
    below sits about 14 dB clear of both. That headroom is the point: the
    delivery spec lets each segment's level move by up to 1 LU, and a master
    may legitimately pass through a limiter to meet true peak, so a detector
    riding only a few dB under a good beep would drop real events and fail a
    correct master on a count mismatch."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-af", "bandpass=f=1000:width_type=q:w=4,"
                "bandpass=f=1000:width_type=q:w=4",
         "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        check=True, capture_output=True).stdout
    x = np.frombuffer(raw[:len(raw) // 2 * 2], np.int16).astype(np.float64)
    win = 32  # 2 ms
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


def ebur128_summary(path, ss=None, t=None):
    """(integrated LUFS, true peak dBTP, [short-term readings for t>=3s])."""
    cmd = ["ffmpeg", "-nostats"]
    if ss is not None:
        cmd += ["-ss", str(ss)]
    if t is not None:
        cmd += ["-t", str(t)]
    cmd += ["-i", str(path), "-filter_complex", "ebur128=peak=true",
            "-f", "null", "-"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    err = p.stderr
    integrated = None
    peak = None
    shorts = []
    for m in re.finditer(r"t:\s*([\d.]+)\s.*?S:\s*(-?[\d.]+)", err):
        tt, s = float(m.group(1)), float(m.group(2))
        if tt >= 3.0 and s > -70:
            shorts.append(s)
    lines = err.splitlines()
    for i, ln in enumerate(lines):
        if "Integrated loudness" in ln:
            for ln2 in lines[i:i + 4]:
                if re.search(r"\bI:", ln2):
                    integrated = float(ln2.split("I:")[1].split("LUFS")[0])
        if "True peak" in ln:
            for ln2 in lines[i:i + 3]:
                if "Peak:" in ln2:
                    peak = float(ln2.split("Peak:")[1].split("dBFS")[0])
    if integrated is None:
        raise RuntimeError("ebur128 summary not found")
    return integrated, peak, shorts
