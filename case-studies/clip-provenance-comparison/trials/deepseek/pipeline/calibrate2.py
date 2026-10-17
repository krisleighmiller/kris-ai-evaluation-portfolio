"""Compute coherence/uniqueness feature distributions for calibration."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fingerprint import fingerprint_video
from match import match_clip, coherence_features

ROOT = os.path.dirname(os.path.abspath(__file__))
MASTERS = os.path.join(ROOT, "masters")
CACHE = os.path.join(ROOT, "cache")

SEARCH_MASTERS = list(range(40))


def main():
    md = {}
    for mi in SEARCH_MASTERS:
        d, t, f = fingerprint_video(f"{MASTERS}/master_{mi:02d}.mp4", fps=2.0,
                                    cache=f"{CACHE}/m_{mi:02d}.npz")
        md[mi] = d

    g = np.load(os.path.join(ROOT, "calibration_genuine.npz"), allow_pickle=True)["genuine"]
    f = np.load(os.path.join(ROOT, "calibration_foreign.npz"), allow_pickle=True)["foreign"]

    # We can't easily re-fingerprint the synthetic clips (they were in a temp dir
    # that may be gone), so instead rebuild representative samples directly.
    # For simplicity, we recompute features for stored (mi, start) by recutting.
    import subprocess, tempfile
    TMP = tempfile.mkdtemp(dir="/tmp/opencode")

    def features_for(master_d, clip_d):
        best_s, best_m, best_o, best_r = None, None, None, None
        L = None
        for mj in master_d:
            s, o, r = match_clip(clip_d, master_d[mj])
            if best_s is None or s < best_s:
                best_s, best_m, best_o, best_r = s, mj, o, r
        feats = coherence_features(clip_d, master_d[best_m], best_o)
        rescale = best_r
        return best_s, best_m, best_o, feats, rescale

    # Rebuild genuine from calibration genuine (which has true master/start stored)
    print("=== GENUINE features (coherence, uniqueness) ===")
    gcoh, guniq = [], []
    for (mi, pm, ps, po, start, sec) in g[:40]:
        mi = int(mi); start = float(start)
        # recut from true master
        out = f"{TMP}/rg.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-ss", str(start), "-t", "8",
                        "-i", f"{MASTERS}/master_{mi:02d}.mp4", "-an", "-c:v",
                        "libx264", "-preset", "ultrafast", "-crf", "26", "-y", out],
                       check=True, capture_output=True)
        cd, ct, cf = fingerprint_video(out, fps=2.0)
        bs, bm, bo, feats, r = features_for(md, cd)
        gcoh.append(feats["coherence"]); guniq.append(feats["uniqueness"])
        print(f"  true m={mi} pred m={bm} score={bs:.3f} coh={feats['coherence']:.2f} uniq={feats['uniqueness']:.2f}")

    print("\nGenuine coherence: mean %.2f median %.2f p95 %.2f max %.2f" % (
        np.mean(gcoh), np.median(gcoh), np.percentile(gcoh, 95), np.max(gcoh)))
    print("Genuine uniqueness: mean %.2f median %.2f p5 %.2f" % (
        np.mean(guniq), np.median(guniq), np.percentile(guniq, 5)))

    # Foreign: use holdout masters (41,42,43)
    print("\n=== FOREIGN (holdout) features ===")
    fcoh, funiq = [], []
    for mi in [41, 42, 43]:
        for start in [3.0, 10.0, 20.0]:
            out = f"{TMP}/rf.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-ss", str(start), "-t", "8",
                            "-i", f"{MASTERS}/master_{mi:02d}.mp4", "-an", "-c:v",
                            "libx264", "-preset", "ultrafast", "-crf", "26", "-y", out],
                           check=True, capture_output=True)
            cd, ct, cf = fingerprint_video(out, fps=2.0)
            bs, bm, bo, feats, r = features_for(md, cd)
            fcoh.append(feats["coherence"]); funiq.append(feats["uniqueness"])
            print(f"  holdout m={mi} best-match m={bm} score={bs:.3f} coh={feats['coherence']:.2f} uniq={feats['uniqueness']:.2f}")
    print("\nForeign coherence: mean %.2f median %.2f min %.2f" % (
        np.mean(fcoh), np.median(fcoh), np.min(fcoh)))
    print("Foreign uniqueness: mean %.2f median %.2f max %.2f" % (
        np.mean(funiq), np.median(funiq), np.max(funiq)))


if __name__ == "__main__":
    main()