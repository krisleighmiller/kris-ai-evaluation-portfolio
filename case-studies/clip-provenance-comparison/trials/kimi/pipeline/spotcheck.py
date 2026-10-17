#!/usr/bin/env python3
"""Render side-by-side validation panels: for a clip/master/t0/rate match,
show 3 clip frames vs the mapped master frames, plus the master frame with
the estimated crop rectangle. Usage:
  spotcheck.py decisions.json out.png clip1 clip2 ...   (or 'ALLUNCERTAIN')
"""
import os, json, sys
import numpy as np
import cv2
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'out')
CLIPS_DIR = os.environ.get('CLIPS_DIR', os.path.join(ROOT, 'clips'))


def grab(path, frame=None, sec=None):
    cap = cv2.VideoCapture(path)
    if frame is not None:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame))
    else:
        cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
    ok, f = cap.read()
    cap.release()
    return cv2.cvtColor(f, cv2.COLOR_BGR2RGB) if ok else None


def panel(cname, mid, t0, rate, crop, tier, ncc):
    cap = cv2.VideoCapture(os.path.join(CLIPS_DIR, cname))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); cap.release()
    fracs = [0.15, 0.5, 0.85]
    ims = []
    labs = []
    for fr in fracs:
        ci = int(total * fr)
        mt = t0 + rate * ci / 24.0
        cim = grab(os.path.join(CLIPS_DIR, cname), frame=ci)
        mim = grab(os.path.join(ROOT, 'masters', f'master_{mid:02d}.mp4'), sec=mt)
        if cim is None or mim is None:
            continue
        ims.append((cim, mim)); labs.append(f'f{ci}/t{mt:.1f}')
    if not ims:
        return None
    h = 150
    cw_ = max(i[0].shape[1] * h // i[0].shape[0] for i in ims)
    mw = max(i[1].shape[1] * h // i[1].shape[0] for i in ims)
    W = cw_ + mw + 30
    H = h * 3 + 40
    canvas = Image.new('RGB', (W, H), 'black')
    d = ImageDraw.Draw(canvas)
    d.text((3, 3), f'{cname} -> master_{mid:02d} [{tier}] ncc={ncc:.2f} t0={t0:.2f} rate={rate:.3f}', fill='yellow')
    for r, ((cim, mim), lab) in enumerate(zip(ims, labs)):
        cp = Image.fromarray(cim).resize((cw_, h))
        mp = Image.fromarray(mim)
        if crop:
            x, y, w, hh = crop
            scale = mw / mim.shape[1]
            mp = mp.resize((mw, int(mim.shape[0] * mw / mim.shape[1])))
            dd = ImageDraw.Draw(mp)
            dd.rectangle([x * scale, y * scale, (x + w) * scale, (y + hh) * scale], outline='red', width=2)
        mp = mp.resize((mw, h))
        y0 = 30 + r * h
        canvas.paste(cp, (0, y0)); canvas.paste(mp, (cw_ + 30, y0))
        d.text((cw_ + 2, y0 + 2), lab, fill='lime')
    return canvas


def main():
    dec = json.load(open(os.path.join(OUT, sys.argv[1])))
    out_png = sys.argv[2]
    which = sys.argv[3:]
    rows = {r['clip']: r for r in dec}
    if which and which[0] == 'ALLNONCONF':
        sel = [r['clip'] for r in dec if r['tier'] != 'confident' and r['master'] is not None]
    elif which and which[0] == 'SAMPLECONF':
        conf = [r['clip'] for r in dec if r['tier'] == 'confident']
        rng = np.random.default_rng(0)
        sel = list(rng.choice(conf, min(12, len(conf)), replace=False))
    else:
        sel = which
    panels = []
    for c in sel:
        r = rows.get(c)
        if not r or r['master'] is None:
            continue
        p = panel(c, r['master'], r['t0'] or 0, r['rate'] or 1.0, r.get('crop'), r['tier'], r['ncc'] or 0)
        if p:
            panels.append(p)
    if not panels:
        print('no panels'); return
    cols = 2
    w = max(p.width for p in panels); h = max(p.height for p in panels)
    rowsn = (len(panels) + cols - 1) // cols
    canvas = Image.new('RGB', (cols * w, rowsn * h), 'gray')
    for k, p in enumerate(panels):
        canvas.paste(p, ((k % cols) * w, (k // cols) * h))
    canvas.save(out_png)
    print('saved', out_png, canvas.size)


if __name__ == '__main__':
    main()
