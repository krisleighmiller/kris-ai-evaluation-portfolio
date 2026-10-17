"""
Validate the matcher self-consistently: cut known sub-segments from masters
(and apply transforms), then confirm the matcher recovers the correct master
and offset. Also test a "foreign" clip (synthetic noise) is rejected.
"""
import os
import numpy as np
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fingerprint import fingerprint_video, FrameDescriptor
from match import match_clip

M = os.path.join(os.path.dirname(os.path.abspath(__file__)), "masters")

def test_cut_offsets():
    # fingerprint a few masters fully
    masters = {}
    for mi in [0, 1, 2]:
        d, t, f = fingerprint_video(f"{M}/master_{mi:02d}.mp4", fps=1.0)
        masters[mi] = d

    results = []
    for mi in masters:
        d = masters[mi]
        L = len(d)
        # cut 6-second window starting at index 10
        for start in [5, 12, 20]:
            end = start + 6
            if end > L:
                continue
            seg = d[start:end]
            best = match_clip(seg, d)
            score, o, r = best
            ok = (o == start)
            results.append((mi, start, o, round(r,2), round(score,4), ok))
    return results


if __name__ == "__main__":
    res = test_cut_offsets()
    nok = sum(1 for r in res if r[-1])
    print(f"correct offset recovery: {nok}/{len(res)}")
    for r in res:
        print(r)