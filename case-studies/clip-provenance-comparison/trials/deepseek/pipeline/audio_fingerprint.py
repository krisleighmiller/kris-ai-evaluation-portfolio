"""
Audio fingerprinting for corroborating video matches.

Decode audio to 8 kHz mono, compute a coarse log-spectrum spectrogram
(robust to re-compression and mild speed/pitch shifts), and support
sliding cross-correlation of a clip's spectrogram against a master's.
"""
import os
import subprocess
import numpy as np


def decode_audio(path, sr=8000):
    """Return mono float32 audio array at sample rate sr (None if no audio)."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", path],
        capture_output=True, text=True)
    if not out.stdout.strip():
        return None
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr),
         "-f", "f32le", "-"],
        capture_output=True)
    if p.returncode != 0:
        return None
    data = np.frombuffer(p.stdout, dtype=np.float32)
    if data.size == 0:
        return None
    return data


def spectrogram(audio, sr=8000, win=256, hop=160, nbands=40, fps=10.0):
    """Return (features T x nbands) float32, and frame times.

    log-magnitude STFT reduced to `nbands` log-spaced bands, then time-averaged
    to `fps` frames/sec.
    """
    audio = audio.astype(np.float32)
    if audio.std() > 0:
        audio = (audio - audio.mean()) / (audio.std() + 1e-9)
    n = len(audio)
    nfft = win
    nframes = max(1, (n - win) // hop + 1)
    # hann window
    w = np.hanning(win).astype(np.float32)
    # collect frames
    idx = np.arange(win)[None, :] + hop * np.arange(nframes)[:, None]
    if idx.max() >= n:
        nframes = max(1, (n - win) // hop + 1)
        idx = np.arange(win)[None, :] + hop * np.arange(nframes)[:, None]
    frames = audio[idx] * w[None, :]
    spec = np.abs(np.fft.rfft(frames, n=nfft, axis=1))  # (nframes, nfft/2+1)
    # log-magnitude
    spec = np.log1p(spec)
    nb = spec.shape[1]  # nfft/2+1
    # log-spaced band edges (skip DC)
    freqs = np.fft.rfftfreq(nfft, 1.0 / sr)
    edges = np.logspace(np.log10(max(freqs[1], 1e-9) * 1.0), np.log10(freqs[-1]),
                        nbands + 1)
    bandidx = np.zeros(nb, dtype=np.int32)
    for b in range(nbands):
        bandidx[(freqs >= edges[b]) & (freqs < edges[b + 1])] = b
    bandidx[bandidx == 0] = 0
    # handle first band explicitly
    bandfeat = np.zeros((nframes, nbands), dtype=np.float32)
    for b in range(nbands):
        m = bandidx == b
        if m.sum() > 0:
            bandfeat[:, b] = spec[:, m].mean(axis=1)
    # time-average to fps
    agg = int(round(1.0 / fps * sr / hop)) or 1
    nout = max(1, nframes // agg)
    feats = bandfeat[:nout * agg].reshape(nout, agg, nbands).mean(axis=1)
    times = np.arange(nout) / fps
    return feats, times


def audio_features(path, sr=8000, fps=10.0, cache=None, nbands=40):
    if cache and os.path.exists(cache):
        d = np.load(cache)
        return d["feat"], d["times"], float(d["sr"])
    a = decode_audio(path, sr=sr)
    if a is None:
        feat = np.zeros((0, nbands), dtype=np.float32)
        times = np.zeros(0)
        src_sr = sr
    else:
        feat, times = spectrogram(a, sr=sr, nbands=nbands, fps=fps)
        src_sr = sr
    if cache:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        np.savez_compressed(cache, feat=feat, times=times, sr=np.array(src_sr))
    return feat, times, src_sr


def audio_match(cfeat, mfeat):
    """Slide clip audio features along master audio features.

    Returns (best_score, best_offset_idx, peak_corr).  Score is negative of
    normalized correlation so lower is better (consistent with video matcher).
    cfeat (C x B), mfeat (M x B).
    """
    C = cfeat.shape[0]
    M = mfeat.shape[0]
    if C == 0 or M == 0 or C > M:
        return None
    # normalize each band across the whole sequence (z-score) for robustness
    def znorm(x):
        mu = x.mean(axis=0, keepdims=True)
        sd = x.std(axis=0, keepdims=True) + 1e-9
        return (x - mu) / sd

    c = znorm(cfeat)
    m = znorm(mfeat)
    B = c.shape[1]
    # normalized cross-correlation per offset
    # for each offset o, corr = sum_i <c_i, m_{o+i}> / (sqrt(sum c^2) * sqrt(sum m^2))
    # simpler: mean cosine similarity
    best = None
    cnorm = np.sqrt((c ** 2).sum())
    for o in range(M - C + 1):
        mseg = m[o:o + C]
        mnorm = np.sqrt((mseg ** 2).sum())
        if mnorm == 0:
            continue
        corr = (c * mseg).sum() / (cnorm * mnorm + 1e-9)
        if best is None or corr > best[1]:
            best = (o, corr)
    if best is None:
        return None
    return best[1], best[0]  # (corr, offset)   higher corr = better


if __name__ == "__main__":
    import sys
    f, t, sr = audio_features(sys.argv[1])
    print(sys.argv[1], "audio frames:", f.shape, "dur~", round(len(t) / 10.0, 1), "s")