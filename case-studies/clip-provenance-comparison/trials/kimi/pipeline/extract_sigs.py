#!/usr/bin/env python3
"""Extract per-frame perceptual-hash signatures from all masters and clips.

For each video we decode at 3 fps grayscale and compute, per frame:
  - 3 x 64-bit pHashes: full frame, center-75% region, center-50% region
  - frame luminance std (to flag degenerate/flat frames)
Output: work/sig/{masters,clips}_sig.npz
"""
import os, subprocess, sys, json
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from scipy.fftpack import dct as scipy_dct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIGDIR = os.path.join(ROOT, 'work', 'sig')
CLIPS_DIR = os.environ.get('CLIPS_DIR', os.path.join(ROOT, 'clips'))
CLIPS_SIG = os.environ.get('CLIPS_SIG', 'clips_sig.npz')
os.makedirs(SIGDIR, exist_ok=True)

FPS = 3
SZ = 32  # phash grid


def dct2(a):
    return scipy_dct(scipy_dct(a, axis=0, norm='ortho'), axis=1, norm='ortho')


def phash64(img32):
    """img32: float32 32x32 -> 64-bit hash (low 8x8 DCT minus DC, vs median)."""
    d = dct2(img32)
    low = d[:8, :8].flatten()[1:]  # drop DC, 63 values... need 64 -> use 9x9? keep simple: 8x8 minus DC = 63, pad
    low64 = d[:9, :8].flatten()[:64]  # 72 -> first 64 low-freq coeffs (includes DC at [0])
    med = np.median(low64[1:])
    bits = (low64 > med).astype(np.uint64)
    h = np.uint64(0)
    for b in bits:
        h = (h << np.uint64(1)) | np.uint64(b)
    return h


def center_crop(a, frac):
    h, w = a.shape
    ch, cw = int(h * frac), int(w * frac)
    y0, x0 = (h - ch) // 2, (w - cw) // 2
    return a[y0:y0 + ch, x0:x0 + cw]


def decode_gray(path, w=SZ, h=SZ, fps=FPS):
    cmd = ['ffmpeg', '-v', 'error', '-i', path, '-vf', f'fps={fps},scale={w}:{h}',
           '-f', 'rawvideo', '-pix_fmt', 'gray', '-']
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (w * h)
    arr = np.frombuffer(raw[:n * w * h], dtype=np.uint8).reshape(n, h, w)
    return arr


def process(path):
    frames = decode_gray(path).astype(np.float32)
    n = frames.shape[0]
    hashes = np.zeros((n, 3), dtype=np.uint64)
    stds = np.zeros(n, dtype=np.float32)
    for i in range(n):
        f = frames[i]
        stds[i] = f.std()
        hashes[i, 0] = phash64(f)
        hashes[i, 1] = phash64(center_crop(f, 0.75))
        hashes[i, 2] = phash64(center_crop(f, 0.50))
    return n, hashes, stds


def run(kind, files):
    out = {}
    with ProcessPoolExecutor(max_workers=24) as ex:
        src = CLIPS_DIR if kind == 'clips' else os.path.join(ROOT, kind)
        for name, res in zip(files, ex.map(process, [os.path.join(src, f) for f in files])):
            out[name] = res
            print(kind, name, res[0], 'frames', flush=True)
    n_frames = np.array([out[k][0] for k in files])
    offsets = np.concatenate([[0], np.cumsum(n_frames)])
    hashes = np.concatenate([out[k][1] for k in files])
    stds = np.concatenate([out[k][2] for k in files])
    sig_name = CLIPS_SIG if kind == 'clips' else f'{kind}_sig.npz'
    np.savez_compressed(os.path.join(SIGDIR, sig_name),
                        names=np.array(files), hashes=hashes, stds=stds,
                        offsets=offsets, n_frames=n_frames)


if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if which in ('all', 'masters'):
        files = sorted(os.listdir(os.path.join(ROOT, 'masters')))
        run('masters', files)
    if which in ('all', 'clips'):
        files = sorted(os.listdir(CLIPS_DIR))
        run('clips', files)
