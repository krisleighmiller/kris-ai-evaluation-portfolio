"""Comprehensive calibration to lock classification thresholds.

Genuine: cuts from search masters with a range of transform severities.
Foreign: hold-out master cuts + synthetic noise + shuffled sequences.
Reports score + uniqueness distributions.
"""
import os, sys, subprocess, tempfile, random
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fingerprint import fingerprint_video
from match import match_clip, coherence_features

ROOT = os.path.dirname(os.path.abspath(__file__))
MASTERS = os.path.join(ROOT, "masters")
CACHE = os.path.join(ROOT, "cache")
TMP = tempfile.mkdtemp(dir="/tmp/opencode")

SEARCH = list(range(40))
HOLD = [40, 41, 42, 43, 44]
random.seed(7)
np.random.seed(7)


def make(src, start, dur, vf, out):
    cmd = ["ffmpeg", "-v", "error"]
    if vf is None:
        cmd += ["-ss", str(start), "-t", str(dur), "-i", src, "-an",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-y", out]
    else:
        cmd += ["-ss", str(start), "-t", str(dur), "-i", src, "-vf", vf, "-an",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-y", out]
    subprocess.run(cmd, check=True, capture_output=True)


def transforms_hard():
    return [
        None,
        "scale=320:240",
        "crop=iw*0.85:ih*0.85,scale=360:270",
        "eq=brightness=0.2:saturation=1.6",
        "eq=brightness=-0.2:saturation=0.6",
        "setpts=0.9*PTS",
        "setpts=1.1*PTS",
        "drawbox=x=20:y=20:w=180:h=36:color=white@0.7:t=fill",
        "scale=320:240,format=yuv420p",
        "crop=400:300:60:40,scale=320:240",
        "eq=brightness=0.12:saturation=0.7,hue=h=30",
    ]


def features_for(cd, md):
    best_s, best_m, best_o, best_r = None, None, None, None
    for mj in md:
        s, o, r = match_clip(cd, md[mj])
        if best_s is None or s < best_s:
            best_s, best_m, best_o, best_r = s, mj, o, r
    feats = coherence_features(cd, md[best_m], best_o)
    return best_s, best_m, best_o, best_r, feats


def main():
    md = {}
    for mi in SEARCH:
        md[mi] = fingerprint_video(f"{MASTERS}/master_{mi:02d}.mp4",
                                   fps=2.0, cache=f"{CACHE}/m_{mi:02d}.npz")[0]

    G, F = [], []
    # Genuine with hard transforms
    for _ in range(80):
        mi = random.choice(SEARCH)
        dur = random.uniform(5, 11)
        start = random.uniform(0, 40 - dur)
        vf = random.choice(transforms_hard())
        out = f"{TMP}/g_{len(G)}.mp4"
        make(f"{MASTERS}/master_{mi:02d}.mp4", start, dur, vf, out)
        cd = fingerprint_video(out, fps=2.0)[0]
        s, bm, bo, br, feats = features_for(cd, md)
        G.append((mi, bm, s, feats["uniqueness"]))

    # Foreign holdout
    for _ in range(30):
        mi = random.choice(HOLD)
        start = random.uniform(0, 28)
        out = f"{TMP}/f_{len(F)}.mp4"
        make(f"{MASTERS}/master_{mi:02d}.mp4", start, 8, None, out)
        cd = fingerprint_video(out, fps=2.0)[0]
        s, bm, bo, br, feats = features_for(cd, md)
        F.append(("holdout", bm, s, feats["uniqueness"]))

    # Foreign noise
    for _ in range(12):
        out = f"{TMP}/n_{len(F)}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "nullsrc=s=640x480:d=8,geq=random(1)*255:128:128",
                        "-c:v", "libx264", "-preset", "ultrafast", "-t", "8",
                        "-y", out], check=True, capture_output=True)
        cd = fingerprint_video(out, fps=2.0)[0]
        s, bm, bo, br, feats = features_for(cd, md)
        F.append(("noise", bm, s, feats["uniqueness"]))

    np.savez(os.path.join(ROOT, "cal_final.npz"), G=np.array(G), F=np.array(F))

    gs = [g[2] for g in G]; gu = [g[3] for g in G]
    fs = [f[2] for f in F]; fu = [f[3] for f in F]
    acc = sum(1 for g in G if int(g[0]) == int(g[1]))

    print("=== GENUINE ===")
    print(f"n={len(G)} masterID_accuracy={acc}/{len(G)}")
    print("score:   mean %.3f med %.3f p95 %.3f max %.3f" % (
        np.mean(gs), np.median(gs), np.percentile(gs,95), np.max(gs)))
    print("uniq:    mean %.3f med %.3f p95 %.3f max %.3f" % (
        np.mean(gu), np.median(gu), np.percentile(gu,95), np.max(gu)))
    print("=== FOREIGN ===")
    print("score:   mean %.3f med %.3f p5 %.3f min %.3f" % (
        np.mean(fs), np.median(fs), np.percentile(fs,5), np.min(fs)))
    print("uniq:    mean %.3f med %.3f p5 %.3f min %.3f" % (
        np.mean(fu), np.median(fu), np.percentile(fu,5), np.min(fu)))

    # decision surface check
    print("\nworst genuine uniqueness:", np.sort(gu)[-10:].round(3))
    print("best foreign uniqueness:", np.sort(fu)[:10].round(3))


if __name__ == "__main__":
    main()