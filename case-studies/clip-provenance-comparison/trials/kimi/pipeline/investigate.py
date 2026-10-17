#!/usr/bin/env python3
"""Render investigation panels: per clip, top rows = clip frames, then one row per
master candidate at the candidate's predicted corresponding times."""
import os, json, sys
import numpy as np
import cv2
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decide  # noqa

def grab(path, sec):
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_MSEC, max(sec, 0) * 1000)
    ok, f = cap.read(); cap.release()
    return cv2.cvtColor(f, cv2.COLOR_BGR2RGB) if ok else None

def clip_frame(path, idx):
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
    ok, f = cap.read(); cap.release()
    return cv2.cvtColor(f, cv2.COLOR_BGR2RGB) if ok else None

def panel(cname, cands, out):
    cpath = os.path.join(ROOT, 'clips', cname)
    cap = cv2.VideoCapture(cpath); total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); cap.release()
    fracs = [0.15, 0.5, 0.85]
    cidxs = [int(total * f) for f in fracs]
    rows = []
    h = 150; w = 240
    d0 = [ImageDraw.Draw(Image.new('RGB', (10, 10)))]
    # clip row
    row = Image.new('RGB', (w * 3 + 130, h), 'black')
    d = ImageDraw.Draw(row)
    d.text((2, 2), cname, fill='yellow')
    for k, ci in enumerate(cidxs):
        im = clip_frame(cpath, ci)
        if im is not None:
            row.paste(Image.fromarray(im).resize((w, h)), (130 + k * w, 0))
    rows.append(row)
    for x in cands:
        row = Image.new('RGB', (w * 3 + 130, h), 'black')
        d = ImageDraw.Draw(row)
        d.text((2, 2), f"m{x['master']:02d} ncc={x['ncc']:.2f}\nt0={x['t0']:.1f} r={x['rate']:.2f}", fill='cyan')
        for k, ci in enumerate(cidxs):
            mt = x['t0'] + x['rate'] * ci / 24.0
            im = grab(os.path.join(ROOT, 'masters', f"master_{x['master']:02d}.mp4"), mt)
            if im is not None:
                row.paste(Image.fromarray(im).resize((w, h)), (130 + k * w, 0))
            d.text((130 + k * w + 2, h - 14), f"t={mt:.1f}", fill='lime')
        rows.append(row)
    W = max(r.width for r in rows); H = sum(r.height for r in rows)
    canvas = Image.new('RGB', (W, H), 'gray')
    y = 0
    for r in rows:
        canvas.paste(r, (0, y)); y += r.height
    canvas.save(out)

if __name__ == '__main__':
    files = ['verify.json', 'orball_verify.json']
    by_clip = {}
    for fn in files:
        dd = decide.collect(json.load(open(os.path.join(ROOT, 'work', 'out', fn))))
        for c, lst in dd.items():
            by_clip.setdefault(c, []).extend(lst)
    inv = sys.argv[1:]
    for c in inv:
        cands = {}
        for x in by_clip.get(c, []):
            m = x['master']
            if m not in cands or x['ncc'] > cands[m]['ncc']:
                cands[m] = x
        s = sorted(cands.values(), key=lambda x: -x['ncc'])[:3]
        panel(c, s, os.path.join(ROOT, 'work', 'inspect', f'inv_{c}.png'))
        print('rendered', c)
