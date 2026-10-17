"""
Robustness validation: apply realistic transforms to a cut segment and confirm
the matcher still recovers master + offset. Transforms: resize/crop, JPEG
compression, brightness/saturation shift, speed change, watermark overlay.
"""
import os, sys, subprocess, tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fingerprint import fingerprint_video
from match import match_clip

ROOT = os.path.dirname(os.path.abspath(__file__))
MASTERS = os.path.join(ROOT, "masters")
CACHE = os.path.join(ROOT, "cache")
TMP = tempfile.mkdtemp(dir="/tmp/opencode")

def make_transformed_clip(master_i, start_s, dur_s, vf, name):
    src = f"{MASTERS}/master_{master_i:02d}.mp4"
    out = f"{TMP}/{name}.mp4"
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start_s), "-t", str(dur_s),
           "-i", src, "-vf", vf, "-an", "-c:v", "libx264", "-preset", "ultrafast",
           "-crf", "28", "-y", out]
    subprocess.run(cmd, check=True, capture_output=True)
    return out

def test():
    master_d = {}
    for mi in [0, 1, 2, 3]:
        d, t, f = fingerprint_video(f"{MASTERS}/master_{mi:02d}.mp4", fps=1.0,
                                    cache=f"{CACHE}/m_{mi:02d}.npz")
        master_d[mi] = d

    transforms = [
        ("resize_crop", 0, 8.0, 6.0, "crop=400:300:20:10,scale=320:240"),
        ("jpeg_compress", 1, 6.0, 6.0, "scale=320:240,format=yuv420p"),  # crf handles compress
        ("bright_sat", 1, 6.0, 6.0, "eq=brightness=0.15:saturation=1.4"),
        ("speedup", 2, 6.0, 6.0, "setpts=0.9*PTS"),
        ("slowdown", 2, 6.0, 6.0, "setpts=1.1*PTS"),
        ("watermark", 3, 6.0, 6.0, "drawbox=x=10:y=10:w=200:h=40:color=white@0.7:t=fill"),
        ("flip_h", 0, 6.0, 6.0, "hflip"),
    ]

    # for speed transforms dur changes, only use for detection not offset-exact
    print(f"{'transform':16s} {'master':>6s} {'start':>6s} {'recov':>6s} {'ratio':>6s} {'score':>8s}")
    for name, mi, start_s, dur_s, vf in transforms:
        p = make_transformed_clip(mi, start_s, dur_s, vf, name)
        cd, ct, cf = fingerprint_video(p, fps=1.0)
        # match against all masters
        best_master, best_score, best_o, best_r = None, None, None, None
        for mj in master_d:
            score, o, r = match_clip(cd, master_d[mj])
            if best_score is None or score < best_score:
                best_master, best_score, best_o, best_r = mj, score, o, r
        print(f"{name:16s} {mi:6d} {start_s:6.1f} {best_o:6d} {best_r:6.2f} {best_score:8.4f}  master={best_master}")

if __name__ == "__main__":
    test()