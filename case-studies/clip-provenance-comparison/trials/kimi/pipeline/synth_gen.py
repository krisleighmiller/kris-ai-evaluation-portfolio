#!/usr/bin/env python3
"""Generate synthetic clips from masters with the brief's transformations,
keeping ground truth. Used to validate the pipeline end-to-end."""
import os, json, random, subprocess
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNDIR = os.path.join(ROOT, 'work', 'synth', 'clips')
os.makedirs(SYNDIR, exist_ok=True)
random.seed(1234)
np.random.seed(1234)

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
if not os.path.exists(FONT):
    FONT = None

masters = sorted(os.listdir(os.path.join(ROOT, 'masters')))
chosen = random.sample(masters, 10)

gt = []
n = 0
for m in chosen:
    mid = int(m.split('_')[1].split('.')[0])
    for rep in range(2):
        n += 1
        name = f'synth_{n:03d}.mp4'
        dur_master = 40.0
        rate = random.choice([1.0, 1.0, 0.9, 1.1, 0.85, 1.15, 0.95])
        clipdur = random.uniform(6.0, 13.0)
        span = clipdur * rate
        t0 = random.uniform(1.0, dur_master - span - 1.0)
        # crop window (fractions of 640x480), keep >=50% each dim
        cw_f = random.uniform(0.5, 1.0)
        ch_f = random.uniform(0.5, 1.0)
        cx_f = random.uniform(0, 1 - cw_f)
        cy_f = random.uniform(0, 1 - ch_f)
        W, H = 640, 480
        cw, ch = int(W * cw_f), int(H * ch_f)
        cx, cy = int(W * cx_f), int(H * cy_f)
        # target size
        tw = random.choice([320, 400, 480, 560, 640, 704, 800])
        th = int(round(ch * tw / cw / 2)) * 2
        # color adjustments
        bright = random.uniform(-0.08, 0.08)
        contrast = random.uniform(0.75, 1.3)
        gamma = random.uniform(0.8, 1.25)
        sat = random.uniform(0.5, 1.3)
        tint = random.choice([None, 'green', 'sepia', 'blue'])
        wm = random.choice([None, 'REPOST', 'VIDSHARE', 'MEDIAHUB', '[archive copy]'])
        crf = random.randint(24, 34)

        vf = [f'crop={cw}:{ch}:{cx}:{cy}', f'scale={tw}:{th}',
              f'eq=brightness={bright:.3f}:contrast={contrast:.3f}:gamma={gamma:.3f}:saturation={sat:.3f}']
        if tint == 'green':
            vf.append('colorbalance=gm=0.25:bh=-0.15:gh=0.2')
        elif tint == 'sepia':
            vf.append('colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131')
        elif tint == 'blue':
            vf.append('colorbalance=bm=0.25:bh=0.2:gh=-0.1')
        if wm and FONT:
            pos = random.choice(['x=w-tw-10:y=h-th-10', 'x=10:y=10', 'x=w-tw-10:y=10'])
            vf.append(f"drawtext=fontfile={FONT}:text='{wm}':fontsize=20:fontcolor=white@0.8:{pos}:borderw=1:bordercolor=black@0.6")
        vf.append(f'setpts=PTS/{rate}')
        cmd = ['ffmpeg', '-v', 'error', '-y', '-ss', f'{t0:.3f}', '-i', os.path.join(ROOT, 'masters', m),
               '-t', f'{span:.3f}', '-vf', ','.join(vf), '-r', '24',
               '-an', '-c:v', 'libx264', '-crf', str(crf), '-preset', 'fast',
               os.path.join(SYNDIR, name)]
        subprocess.run(cmd, check=True)
        gt.append(dict(clip=name, master=mid, t0=t0, rate=rate, dur=clipdur,
                       crop=[cx, cy, cw, ch], out=[tw, th], wm=wm, tint=tint, crf=crf))
        print(name, 'from', m, f't0={t0:.2f} rate={rate} dur={clipdur:.1f}', flush=True)

with open(os.path.join(ROOT, 'work', 'synth', 'gt.json'), 'w') as f:
    json.dump(gt, f, indent=1)
print('ground truth saved:', len(gt))
