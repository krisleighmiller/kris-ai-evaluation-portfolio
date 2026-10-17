"""
Calibration: build score distributions for (a) genuine matches and
(b) foreign (non-matching) clips, to derive confidence thresholds.

- Genuine: cut random sub-segments from real masters, apply a random
  transform (none / resize / compress / color / speed / crop / watermark).
- Foreign: (i) pure synthetic noise videos, (ii) sub-segments from a
  HOLD-OUT master (excluded from the search set), (iii) shuffled frame
  sequences (breaks temporal coherence).

We report, for each case, the best score vs. all search masters and the
margin = (best vs second-best master).
"""
import os, sys, subprocess, tempfile, random
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fingerprint import fingerprint_video
from match import match_clip

ROOT = os.path.dirname(os.path.abspath(__file__))
MASTERS = os.path.join(ROOT, "masters")
CACHE = os.path.join(ROOT, "cache")
TMP = tempfile.mkdtemp(dir="/tmp/opencode")

SEARCH_MASTERS = list(range(40))   # exclude 40..44 as held-out foreign
HOLDOUT = [41, 42, 43]

random.seed(1234)
np.random.seed(1234)


def make_clip(src, start, dur, vf, out):
    if vf:
        cmd = ["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(dur),
               "-i", src, "-vf", vf, "-an", "-c:v", "libx264",
               "-preset", "ultrafast", "-crf", "26", "-y", out]
    else:
        cmd = ["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(dur),
               "-i", src, "-an", "-c:v", "libx264",
               "-preset", "ultrafast", "-crf", "26", "-y", out]
    subprocess.run(cmd, check=True, capture_output=True)


def random_transform(rng):
    r = rng.random()
    if r < 0.30:
        return None
    elif r < 0.45:
        return "scale=320:240"                      # resize only
    elif r < 0.60:
        w = rng.uniform(0.75, 0.95)
        return f"crop=iw*{w:.2f}:ih*{w:.2f},scale=360:270"  # crop+resize
    elif r < 0.72:
        b = rng.uniform(-0.15, 0.15)
        return f"eq=brightness={b:.2f}:saturation={rng.uniform(0.8,1.5):.2f}"
    elif r < 0.84:
        return f"setpts={rng.uniform(0.9,1.1):.2f}*PTS"     # speed change
    elif r < 0.93:
        return "drawbox=x=20:y=20:w=180:h=36:color=white@0.6:t=fill"  # watermark
    else:
        return "scale=320:240,format=yuv420p"         # heavy-ish resize


def build_master_descs(ms=SEARCH_MASTERS):
    md = {}
    for mi in ms:
        d, t, f = fingerprint_video(f"{MASTERS}/master_{mi:02d}.mp4", fps=2.0,
                                    cache=f"{CACHE}/m_{mi:02d}.npz")
        md[mi] = d
    return md


def best_match(cd, master_d):
    best_m, best_s, best_o = None, None, None
    second_s = None
    for mj in master_d:
        s, o, r = match_clip(cd, master_d[mj])
        if best_s is None or s < best_s:
            second_s = best_s
            best_s, best_m, best_o = s, mj, o
        elif second_s is None or s < second_s:
            second_s = s
    return best_m, best_s, best_o, second_s


def run():
    master_d = build_master_descs()

    genuine = []   # (true_master, pred_master, score, offset, true_offset, margin)
    foreign = []   # (kind, pred_master, score, offset, margin)

    # ---- Genuine clips ----
    print("Generating genuine clips...")
    for _ in range(60):
        mi = random.choice(SEARCH_MASTERS)
        dur = random.uniform(5, 12)
        start = random.uniform(0, 40 - dur)
        vf = random_transform(random)
        out = f"{TMP}/g_{len(genuine)}.mp4"
        make_clip(f"{MASTERS}/master_{mi:02d}.mp4", start, dur, vf, out)
        cd, ct, cf = fingerprint_video(out, fps=2.0)
        pm, ps, po, sec = best_match(cd, master_d)
        genuine.append((mi, pm, ps, po, start, sec))

    # ---- Foreign: synthetic noise video ----
    print("Generating noise clips...")
    for _ in range(15):
        out = f"{TMP}/n_{len(foreign)}.mp4"
        # colored moving noise
        cmd = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
               f"nullsrc=s=640x480:d=8,geq=random(1)*255:128:128",
               "-c:v", "libx264", "-preset", "ultrafast", "-t", "8", "-y", out]
        subprocess.run(cmd, check=True, capture_output=True)
        cd, ct, cf = fingerprint_video(out, fps=2.0)
        pm, ps, po, sec = best_match(cd, master_d)
        foreign.append(("noise", pm, ps, po, sec))

    # ---- Foreign: hold-out master cuts ----
    print("Generating hold-out clips...")
    for _ in range(15):
        mi = random.choice(HOLDOUT)
        start = random.uniform(0, 30)
        out = f"{TMP}/h_{len(foreign)}.mp4"
        make_clip(f"{MASTERS}/master_{mi:02d}.mp4", start, 8, None, out)
        cd, ct, cf = fingerprint_video(out, fps=2.0)
        pm, ps, po, sec = best_match(cd, master_d)
        foreign.append(("holdout", pm, ps, po, sec))

    # ---- Foreign: shuffled-frame (temporal coherence broken) ----
    print("Generating shuffled clips...")
    for _ in range(15):
        mi = random.choice(SEARCH_MASTERS)
        out = f"{TMP}/sh_{len(foreign)}.mp4"
        # sample frames then shuffle order via ffmpeg select is hard; instead
        # we simulate in descriptor space below.
    # do shuffled in descriptor space:
    for _ in range(15):
        mi = random.choice(SEARCH_MASTERS)
        d = master_d[mi]
        L = len(d)
        idx = np.random.choice(L, size=min(12, L), replace=False)
        seq = d[np.sort(idx)]  # keep sorted -> coherent but skip (already covered)
        # shuffle to break coherence:
        seq = d[idx]
        pm, ps, po, sec = best_match(seq, master_d)
        foreign.append(("shuffled", pm, ps, po, sec))

    np.savez(os.path.join(ROOT, "calibration_genuine.npz"), genuine=genuine)
    np.savez(os.path.join(ROOT, "calibration_foreign.npz"), foreign=foreign)

    print("\n=== GENUINE (true_master, pred_master, score, pred_offset, true_offset, margin) ===")
    gs = [g[2] for g in genuine]
    gm = [g[5] for g in genuine]
    print(f"n={len(gs)}  score mean={np.mean(gs):.4f} median={np.median(gs):.4f} "
          f"max={np.max(gs):.4f} p95={np.percentile(gs,95):.4f}")
    print(f"margin (best vs 2nd master) mean={np.mean(gm):.4f} median={np.median(gm):.4f} min={np.min(gm):.4f}")

    print("\n=== FOREIGN (kind, pred_master, score, offset, margin) ===")
    fs = [f[2] for f in foreign]
    print(f"n={len(fs)}  score mean={np.mean(fs):.4f} median={np.median(fs):.4f} "
          f"min={np.min(fs):.4f} p5={np.percentile(fs,5):.4f}")

    # accuracy of master ID for genuine
    correct = sum(1 for g in genuine if g[0] == g[1])
    print(f"\ngenuine master-ID accuracy: {correct}/{len(genuine)}")
    # offset error
    errs = [abs(g[3] - int(g[4] * 2)) / 2 for g in genuine]  # offset in 0.5s units
    print(f"offset error (s): mean={np.mean(errs):.2f} median={np.median(errs):.2f} p95={np.percentile(errs,95):.2f}")


if __name__ == "__main__":
    run()