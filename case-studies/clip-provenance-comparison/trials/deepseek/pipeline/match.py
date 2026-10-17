"""
Match clips against masters via sliding-window descriptor alignment.

For each clip:
  - try multiple time-scale ratios (to handle speed changes)
  - slide the (rescaled) clip descriptor sequence along each master
  - compute mean frame distance; pick best (master, offset, ratio)
"""
import os
import json
import numpy as np
from fingerprint import fingerprint_video, FrameDescriptor


def frame_distance_matrix(cdesc, mdesc):
    """Pairwise descriptor distance: cdesc (CxD), mdesc (MxD) -> (C,M)."""
    C = cdesc.shape[0]
    M = mdesc.shape[0]

    def bits(a_sub_c, a_sub_m):
        return np.abs(a_sub_c[:, None, :] - a_sub_m[None, :, :]).sum(axis=2)

    dh = bits(cdesc[:, 0:64], mdesc[:, 0:64]) / 64.0 * 0.30
    dv = bits(cdesc[:, 64:128], mdesc[:, 64:128]) / 64.0 * 0.30
    ph = bits(cdesc[:, 128:192], mdesc[:, 128:192]) / 64.0 * 0.10
    hue = np.abs(cdesc[:, None, 192:208] - mdesc[None, :, 192:208]).sum(axis=2) * 0.20
    dluma = (np.abs(cdesc[:, None, 208] - mdesc[None, :, 208])
             + np.abs(cdesc[:, None, 209] - mdesc[None, :, 209])
             + np.abs(cdesc[:, None, 210] - mdesc[None, :, 210]))
    dluma = np.minimum(dluma, 2.0) / 2.0 * 0.10
    return dh + dv + ph + hue + dluma


def match_clip(cdesc, mdesc, ratios=(0.9, 0.95, 1.0, 1.05, 1.1), with_features=False):
    """Return best (score, offset_idx, ratio), or (score, offset_idx, ratio,
    dict) if with_features=True.  Offset is index in master descriptors where
    the clip's first frame aligns.  Uniqueness/coherence are computed on the
    resampled clip for internal consistency."""
    C = cdesc.shape[0]
    M = mdesc.shape[0]
    best = None  # (score, o, r, resampled_desc, L, dist)
    for r in ratios:
        L = max(1, int(round(C / r)))
        if L > M:
            continue
        idx = np.linspace(0, C - 1, L)
        rcdesc = cdesc[np.round(idx).astype(int)]
        dist = frame_distance_matrix(rcdesc, mdesc)
        if L == 0:
            continue
        totals = np.zeros(M - L + 1, dtype=np.float64)
        for i in range(L):
            totals += dist[i, i:i + (M - L + 1)]
        o = int(np.argmin(totals))
        score = totals[o] / L
        if best is None or score < best[0]:
            best = (score, o, r, rcdesc, L, dist)
    score, o, r, rcdesc, L, dist = best
    if not with_features:
        return score, o, r
    # uniqueness + coherence on the resampled clip
    diag = np.mean([dist[i, o + i] for i in range(L)])
    permin = np.mean([dist[i].min() for i in range(L)])
    coherence = diag / (permin + 1e-9)
    totals = np.zeros(M - L + 1, dtype=np.float64)
    for i in range(L):
        totals += dist[i, i:i + (M - L + 1)]
    mask = np.ones_like(totals)
    lo = max(0, o - L + 1)
    hi = min(M - L, o + L - 1)
    mask[lo:hi + 1] = 0
    nz = totals[mask > 0]
    second = nz.min() / L if len(nz) else totals[o] / L
    uniqueness = (totals[o] / L) / (second + 1e-9)
    return score, o, r, {"uniqueness": float(uniqueness),
                         "coherence": float(coherence),
                         "permin": float(permin)}


def coherence_features(cdesc, mdesc, offset, L=None):
    """For a given alignment offset, compute discrimination features.

    Returns dict:
      score       : mean diagonal distance at offset
      coherence   : score / (mean per-frame minimum over entire master)
      uniqueness  : score / (best score over non-overlapping offsets)
                    (how uniquely the offset stands out)
    """
    if L is None:
        L = cdesc.shape[0]
    dist = frame_distance_matrix(cdesc, mdesc)
    diag = np.mean([dist[i, offset + i] for i in range(L)])
    permin = np.mean([dist[i].min() for i in range(L)])
    coherence = diag / (permin + 1e-9)

    M = mdesc.shape[0]
    # uniqueness: compare to best non-overlapping offset
    totals = np.zeros(M - L + 1, dtype=np.float64)
    for i in range(L):
        totals += dist[i, i:i + (M - L + 1)]
    best = totals[offset] / L
    # exclude overlapping offsets [offset-L+1, offset+L-1]
    mask = np.ones_like(totals)
    lo = max(0, offset - L + 1)
    hi = min(M - L, offset + L - 1)
    mask[lo:hi + 1] = 0
    nz = totals[mask > 0]
    if len(nz) == 0:
        uniqueness = 1.0
    else:
        second = nz.min() / L
        uniqueness = best / (second + 1e-9)
    return {"score": float(best), "coherence": float(coherence),
            "uniqueness": float(uniqueness), "permin": float(permin)}


def load_all(path_dir, prefix, indices, fps=1.0, cache_dir=None):
    out = {}
    for i in indices:
        p = f"{path_dir}/{prefix}_{i:03d}.mp4"
        c = None
        if cache_dir:
            c = f"{cache_dir}/{prefix}_{i:03d}.npz"
        desc, times, f = fingerprint_video(p, fps=fps, cache=c)
        out[i] = (desc, times, f)
    return out