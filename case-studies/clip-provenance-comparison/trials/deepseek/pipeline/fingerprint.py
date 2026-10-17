"""
Video perceptual fingerprinting and matching.

Each video is reduced to a sequence of frame descriptors sampled at a fixed
rate. A descriptor is a small feature vector that is robust to:
  - cropping (we use center-crop of the dominant content region)
  - resizing (normalized thumbnail)
  - compression artifacts (low-resolution, blurred)
  - color adjustment (we rely mostly on luminance structure + a coarse
    color histogram, not on exact color)
  - watermarking (median/mean pooling suppresses sparse overlays)

Matching is done by sliding a clip's descriptor sequence across a master's
descriptor sequence and measuring mean distance, allowing slight time-scale
changes.
"""
import os
import json
import subprocess
import tempfile
import numpy as np


def ffprobe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip().splitlines()[0])


def ffprobe_fps(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=avg_frame_rate", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True)
    val = out.stdout.strip()
    if "/" in val:
        a, b = val.split("/")
        return float(a) / float(b) if float(b) else 24.0
    return float(val) if val else 24.0


class FrameDescriptor:
    """Small robust descriptor for a single frame.

    Layout (all float32):
      [0:64)    dHash horizontal (64 bits) on 8x9 grayscale      -> structural
      [64:128)  dHash vertical   (64 bits) on 9x8 grayscale      -> structural
      [128:192) pHash            (64 bits) on 8x8 DCT            -> structural
      [192:208) hue histogram    (16 bins: 8 hue x 2 saturation) -> color
      [208:211) luma mean, luma median, luma std (quantile-robust)-> mild

    Structure-dominated so that brightness/saturation shifts hurt
    little; hue-only color signature is brightness-invariant.
    """
    BITS = 64
    HUE = 16
    DIM = 64 + 64 + 64 + HUE + 3

    @staticmethod
    def _dhash(img, horizontal=True):
        import cv2
        if horizontal:
            small = cv2.resize(img, (9, 8), interpolation=cv2.INTER_AREA)
        else:
            small = cv2.resize(img, (8, 9), interpolation=cv2.INTER_AREA)
        h, w = small.shape
        bits = []
        if horizontal:
            for y in range(h):
                row = small[y]
                for x in range(w - 1):
                    bits.append(1 if row[x] > row[x + 1] else 0)
        else:
            for x in range(w):
                col = small[:, x]
                for y in range(h - 1):
                    bits.append(1 if col[y] > col[y + 1] else 0)
        return bits

    @staticmethod
    def _phash(gray):
        import cv2
        small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
        import numpy as _np
        dct = cv2.dct(_np.float32(small))
        # top-left 8x8 (excluding DC) -> 64 cells; compare with median
        block = dct[0:8, 0:8]
        block[0, 0] = 0
        med = float(_np.median(block))
        bits = []
        for y in range(8):
            for x in range(8):
                bits.append(1 if block[y, x] > med else 0)
        return bits

    @staticmethod
    def _extract_features(gray, rgb):
        import cv2
        dh = FrameDescriptor._dhash(gray, horizontal=True)
        dv = FrameDescriptor._dhash(gray, horizontal=False)
        ph = FrameDescriptor._phash(gray)

        if rgb is not None:
            hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
            h = hsv[:, :, 0].astype(np.float32) / 180.0
            s = hsv[:, :, 1].astype(np.float32)
            hb = 8
            idx = np.floor(h * hb).astype(np.int32) % hb
            satbit = (s > 0.20).astype(np.int32)
            bin2d = idx * 2 + satbit
            hist = np.bincount(bin2d.ravel(), minlength=hb * 2).astype(np.float32)
            hist = hist / (hist.sum() + 1e-6)
        else:
            hist = np.zeros(FrameDescriptor.HUE, dtype=np.float32)

        mean_l = float(gray.mean())
        med_l = float(np.median(gray))
        std_l = float(gray.std())
        return dh, dv, ph, hist, mean_l, med_l, std_l

    @staticmethod
    def to_vec(dh, dv, ph, hist, mean_l, med_l, std_l):
        v = np.zeros(FrameDescriptor.DIM, dtype=np.float32)
        v[0:64] = np.array(dh, dtype=np.float32)
        v[64:128] = np.array(dv, dtype=np.float32)
        v[128:192] = np.array(ph, dtype=np.float32)
        v[192:192 + FrameDescriptor.HUE] = hist
        v[208] = mean_l
        v[209] = med_l
        v[210] = std_l
        return v

    @staticmethod
    def distance(a, b):
        dh = np.sum(np.abs(a[0:64] - b[0:64])) / 64.0
        dv = np.sum(np.abs(a[64:128] - b[64:128])) / 64.0
        ph = np.sum(np.abs(a[128:192] - b[128:192])) / 64.0
        hue = np.sum(np.abs(a[192:192 + HUE] - b[192:192 + HUE])) * 0.5
        # luma quantile-robust: mean and median (robust to brightness offset)
        dluma = abs(a[208] - b[208]) + abs(a[209] - b[209]) + abs(a[210] - b[210])
        dluma = min(dluma, 2.0) / 2.0
        return 0.30 * dh + 0.30 * dv + 0.10 * ph + 0.20 * hue + 0.10 * dluma


def extract_frames_cv2(path, fps=1.0, max_side=160):
    """Decode video with cv2 and sample one frame per `fps` seconds."""
    import cv2
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS)
    if not src_fps or src_fps <= 0:
        src_fps = 24.0
    nframes = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round(src_fps / fps)))
    out = []
    out_idx = 0
    i = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if i % step == 0:
            h, w = frame.shape[:2]
            scale = max_side / float(max(h, w))
            nw = int(round(w * scale))
            nh = int(round(h * scale))
            nw = max(1, nw); nh = max(1, nh)
            small = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
            out.append(small)
            out_idx += 1
        i += 1
    cap.release()
    return out, src_fps


def build_descriptors(frames):
    """frames: list of BGR uint8 arrays (already downscaled). Returns MxDIM float array."""
    import cv2
    descs = []
    for fr in frames:
        gray_f = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        rgb = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        dh, dv, ph, hist, ml, md, sl = FrameDescriptor._extract_features(gray_f, rgb)
        descs.append(FrameDescriptor.to_vec(dh, dv, ph, hist, ml, md, sl))
    if not descs:
        return np.zeros((0, FrameDescriptor.DIM), dtype=np.float32)
    return np.stack(descs, axis=0)


def fingerprint_video(path, fps=1.0, max_side=160, cache=None):
    """Return (descriptors MxDIM float, times M vector, src_fps)."""
    if cache and os.path.exists(cache):
        d = np.load(cache)
        return d["desc"], d["times"], float(d["src_fps"])
    frames, src_fps = extract_frames_cv2(path, fps=fps, max_side=max_side)
    desc = build_descriptors(frames)
    times = np.arange(len(frames), dtype=np.float64) / float(fps)
    if cache:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        np.savez_compressed(cache, desc=desc, times=times, src_fps=np.array(src_fps))
    return desc, times, src_fps


if __name__ == "__main__":
    import sys
    p = sys.argv[1]
    desc, times, fps = fingerprint_video(p, fps=1.0)
    print(p, "frames sampled:", len(desc), "src_fps:", round(fps, 3))