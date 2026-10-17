"""
Main matching pipeline.

For each clip:
  1. Video fingerprint (2 fps), scan all 45 masters at ratio 1.0 to find the
     best master, then refine ratio on it (0.8..1.2) for speed tolerance.
     Compute score, offset (begin time), and uniqueness.
  2. Audio fingerprint (10 fps) when present, cross-correlate against masters
     for an independent corroborating match + 0.1s offset.
  3. Fine video refinement for begin time (0.25 s resolution).
  4. Classify: confident / likely / uncertain / not-identified.

Outputs: results.json, results.csv, plus classification summary.
"""
import os, sys, json, csv, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fingerprint import fingerprint_video
from match import match_clip, coherence_features, frame_distance_matrix
from audio_fingerprint import audio_features, audio_match

ROOT = os.path.dirname(os.path.abspath(__file__))
MASTERS = os.path.join(ROOT, "masters")
CLIPS = os.path.join(ROOT, "clips")
VCACHE = os.path.join(ROOT, "cache", "vid")
ACACHE = os.path.join(ROOT, "cache", "aud")

N_MASTERS = 45
N_CLIPS = 200
VFPS = 2.0
AFPS = 10.0
RATIOS = tuple(np.arange(0.80, 1.21, 0.025))


def load_masters():
    md = {}
    for mi in range(N_MASTERS):
        d, t, f = fingerprint_video(f"{MASTERS}/master_{mi:02d}.mp4",
                                    fps=VFPS, cache=f"{VCACHE}/m_{mi:02d}.npz")
        md[mi] = d
    return md


def load_master_audio():
    ma = {}
    for mi in range(N_MASTERS):
        f, t, sr = audio_features(f"{MASTERS}/master_{mi:02d}.mp4", fps=AFPS,
                                  cache=f"{ACACHE}/m_{mi:02d}.npz")
        ma[mi] = f
    return ma


def video_match_clip(cd, md):
    """Scan ratio 1.0 over all masters, then refine ratio on best master."""
    best_s, best_m, best_o = None, None, None
    # fast pass ratio 1.0
    for mj in md:
        s, o, r = match_clip(cd, md[mj], ratios=(1.0,))
        if best_s is None or s < best_s:
            best_s, best_m, best_o = s, mj, o
    # refine ratio on best master
    s, o, r, feats = match_clip(cd, md[best_m], ratios=RATIOS, with_features=True)
    # second-best master (ratio 1.0) for cross-master margin
    second_s = None
    second_m = None
    for mj in md:
        if mj == best_m:
            continue
        s2, o2, r2 = match_clip(cd, md[mj], ratios=(1.0,))
        if second_s is None or s2 < second_s:
            second_s, second_m = s2, mj
    return {
        "best_master": best_m, "score": s, "offset": o, "ratio": r,
        "uniqueness": feats["uniqueness"], "coherence": feats["coherence"],
        "second_master": second_m, "second_score": second_s,
    }


def fine_video_offset(clip_path, clip_dur, master_idx, coarse_time):
    """Refine begin time to ~0.25s by matching first frames at higher fps."""
    fpf = 4.0  # frames per second for refinement
    # clip first ~3 s of frames
    cd, ct, _ = fingerprint_video(clip_path, fps=fpf)
    # master window: coarse +/- 3s
    lo = max(0.0, coarse_time - 3.0)
    hi = min(40.0, coarse_time + clip_dur + 3.0)
    # extract master frames in window at fpf
    import subprocess, tempfile
    # simpler: fingerprint full master at fpf (cached) and slice
    md_full, mt, _ = fingerprint_video(f"{MASTERS}/master_{master_idx:02d}.mp4",
                                       fps=fpf, cache=f"{VCACHE}/m_{master_idx:02d}_4fps.npz")
    lo_idx = int(round(lo * fpf))
    hi_idx = int(round(hi * fpf))
    mw = md_full[lo_idx:hi_idx]
    # match clip (first K frames) against window
    K = min(len(cd), int(clip_dur * fpf))
    cd_use = cd[:K]
    if len(cd_use) < 4 or len(mw) < len(cd_use):
        return coarse_time
    s, o, r = match_clip(cd_use, mw, ratios=(1.0,))
    fine_time = (lo_idx + o) / fpf
    return fine_time


def classify(v, a):
    """Return (label, master, begin_time, reason).

    Confidence combines two INDEPENDENT signals that are each robust to
    different transforms:
      - video structural alignment (tolerates resize/compress/watermark; its
        'uniqueness' = score at best offset / score at best non-overlapping
        offset, calibrated: genuine mostly < 0.6, foreign mostly > 0.85)
      - audio spectral cross-correlation (tolerates crop/resize/color; robust
        to speed changes up to ~30%, corr stays > 0.55)

    Agreement between the two (different transforms, same answer) is treated
    as strong evidence even at moderate strength in either channel.
    """
    uniq = v["uniqueness"]
    corr = a["corr"] if a else None
    a_master = a["master"] if a else None

    audio_strong = corr is not None and corr > 0.70          # audio decisive alone
    agree = (corr is not None and corr > 0.55
             and a_master == v["best_master"])               # cross-channel agreement

    # determine master/begin with audio preference when strong
    if audio_strong or (agree and a_master is not None):
        master = a_master
        begin = a["offset"]
    else:
        master = v["best_master"]
        begin = v["offset"] / VFPS

    if audio_strong:
        return "confident", master, begin, "audio decisive (corr %.2f)" % corr
    if agree and uniq <= 0.80:
        return "confident", master, begin, "audio+video agree (corr %.2f, uniq %.2f)" % (corr, uniq)
    if agree:
        return "likely", master, begin, "audio+video agree but weak video (corr %.2f, uniq %.2f)" % (corr, uniq)
    if uniq <= 0.50:
        return "confident", master, begin, "strong unique video alignment (uniq %.2f)" % uniq
    if uniq <= 0.80:
        return "likely", master, begin, "moderate video alignment (uniq %.2f)" % uniq
    if uniq <= 0.93:
        return "uncertain", master, begin, "ambiguous video alignment (uniq %.2f)" % uniq
    return "not-identified", master, begin, "no reliable alignment (uniq %.2f)" % uniq


def main():
    t0 = time.time()
    md = load_masters()
    ma = load_master_audio()
    print(f"loaded masters + audio in {time.time()-t0:.1f}s", flush=True)

    results = []
    for ci in range(N_CLIPS):
        cp = f"{CLIPS}/clip_{ci:03d}.mp4"
        dur = _probe_dur(cp)
        cd, ct, _ = fingerprint_video(cp, fps=VFPS, cache=f"{VCACHE}/c_{ci:03d}.npz")
        v = video_match_clip(cd, md)
        # audio
        af, at, _ = audio_features(cp, fps=AFPS, cache=f"{ACACHE}/c_{ci:03d}.npz")
        a = None
        if af.shape[0] > 0:
            best_corr, best_m, best_o = None, None, None
            for mj in ma:
                r = audio_match(af, ma[mj])
                if r is None:
                    continue
                corr, off = r
                if best_corr is None or corr > best_corr:
                    best_corr, best_m, best_o = corr, mj, off
            a = {"corr": best_corr, "master": best_m,
                 "offset": best_o / AFPS if best_o is not None else None}

        coarse_time = v["offset"] / VFPS
        fine_time = fine_video_offset(cp, dur, v["best_master"], coarse_time)
        label, resolved_master, resolved_begin, reason = classify(v, a)
        # final begin time: prefer audio (0.1s) when decisive/agreed, else fine video
        aud_decisive = (a is not None and a["corr"] is not None and a["corr"] > 0.70)
        aud_agree = (a is not None and a["corr"] is not None and a["corr"] > 0.55
                     and a["master"] == v["best_master"])
        if aud_decisive or aud_agree:
            final_begin = a["offset"]
        else:
            final_begin = fine_time if v["uniqueness"] <= 0.93 else coarse_time

        results.append({
            "clip": f"clip_{ci:03d}", "duration_s": round(dur, 3),
            "classification": label,
            "source_master": int(resolved_master),
            "begin_time_s": round(float(final_begin), 3),
            "video_master": int(v["best_master"]),
            "video_begin_s": round(float(fine_time), 3),
            "score": round(float(v["score"]), 4),
            "uniqueness": round(float(v["uniqueness"]), 4),
            "coherence": round(float(v["coherence"]), 4),
            "ratio": round(float(v["ratio"]), 4),
            "second_master": int(v["second_master"]),
            "second_score": round(float(v["second_score"]), 4),
            "audio_corr": round(float(a["corr"]), 4) if a and a["corr"] else None,
            "audio_master": int(a["master"]) if a else None,
            "audio_begin_s": round(float(a["offset"]), 3) if a and a["offset"] is not None else None,
            "reason": reason,
        })
        if ci % 20 == 0:
            print(f"  clip {ci:03d}/200 done ({time.time()-t0:.1f}s)", flush=True)

    with open(os.path.join(ROOT, "results.json"), "w") as f:
        json.dump(results, f, indent=1)
    with open(os.path.join(ROOT, "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    # summary
    from collections import Counter
    cnt = Counter(r["classification"] for r in results)
    print("\n=== CLASSIFICATION SUMMARY ===")
    for k in ["confident", "likely", "uncertain", "not-identified"]:
        print(f"  {k:14s} : {cnt.get(k,0)}")
    print(f"total clips: {len(results)}")
    print(f"total time: {time.time()-t0:.1f}s")


def _probe_dur(p):
    import subprocess
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration", "-of", "csv=p=0", p],
                         capture_output=True, text=True)
    return float(out.stdout.strip().splitlines()[0])


if __name__ == "__main__":
    main()