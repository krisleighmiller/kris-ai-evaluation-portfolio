"""Known-answer transformation controls and source-withheld negative controls."""
import json, subprocess, argparse
from pathlib import Path
from investigate import ROOT,OUT,probe
from match import search
from refine import decode,refine_one

def generate(holdout=False):
    prefix='holdout' if holdout else 'controls'
    dest=OUT/prefix;dest.mkdir(exist_ok=True)
    rows=[]
    mids=[1,5,8,11,14,17,19,22,24,28,31,40] if holdout else [0,2,4,7,10,13,15,18,20,23,26,29,32,34,37,38,41,44]
    for i,mid in enumerate(mids):
        start=round((2.417+(i%6)*3.125)*24)/24 if holdout else 3.0+(i%7)*2.25
        speed=[.92,1.06,1.0][i%3] if holdout else [.9,1.,1.1][i%3]
        path=dest/f'{"holdout" if holdout else "control"}_{i:02}.mp4';master=f'masters/master_{mid:02}.mp4'
        fps=24
        # trim uses frame boundaries, so source time at output t=0 is known.
        vf=f'trim=start_frame={round(start*fps)}:end_frame={round((start+8*speed)*fps)},setpts=(PTS-STARTPTS)/{speed},'
        vf+=('crop=420:390:110:40,scale=352:240,eq=brightness=-0.03:contrast=0.92:saturation=1.2,' if holdout else 'crop=480:360:80:60,scale=320:240,eq=brightness=0.04:contrast=1.12:saturation=0.6,')
        if i%2:vf+='pad=392:280:20:20,' if holdout else 'pad=360:280:20:20,'
        vf+="drawbox=x=10:y=10:w=85:h=18:color=white@0.5:t=fill,fps=24"
        subprocess.run(['ffmpeg','-v','error','-threads','1','-i',str(ROOT/master),'-vf',vf,'-an','-c:v','libx264','-threads','1','-crf','31','-y',str(path)],check=True)
        r=probe(path);r.update(expected_master=master,expected_start=start,expected_speed=speed)
        rows.append(r)
    (OUT/f'{prefix}.json').write_text(json.dumps(rows,indent=2))

def run(holdout=False):
    prefix='holdout' if holdout else 'control'
    rows=json.loads((OUT/('holdout.json' if holdout else 'controls.json')).read_text())
    search(rows,f'{prefix}_coarse')
    results=[]
    for r in rows:
        c=json.loads((OUT/f'{prefix}_coarse'/(Path(r['path']).stem+'.json')).read_text())
        best=c['candidates'][0] if c['candidates'] else None
        ref=None
        if best and best['support']>=3:
            ts,ims=decode(ROOT/best['path']);ref=refine_one(c,best,ts,ims)
        results.append(dict(control=r['path'],expected_master=r['expected_master'],expected_start=r['expected_start'],expected_speed=r['expected_speed'],best=best,refined=ref,
                            correct_source=bool(best and best['path']==r['expected_master']),
                            start_error=ref['start']-r['expected_start'] if ref else None,
                            speed_error=ref['speed']-r['expected_speed'] if ref else None))
        print('CONTROL',r['path'],results[-1]['correct_source'],results[-1]['start_error'],flush=True)
    (OUT/('validation_holdout.json' if holdout else 'validation_positive.json')).write_text(json.dumps(results,indent=2))

def negatives():
    rows=json.loads((OUT/'controls.json').read_text())
    results=[]
    for r in rows[::3]:
        search([r],'control_negative',exclude=r['expected_master'])
        c=json.loads((OUT/'control_negative'/(Path(r['path']).stem+'.json')).read_text())
        results.append(dict(control=r['path'],withheld=r['expected_master'],candidates=c['candidates']))
    (OUT/'validation_negative.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['generate','positive','negative','holdout']);a=p.parse_args()
    if a.stage=='holdout':generate(True);run(True)
    else:{'generate':generate,'positive':run,'negative':negatives}[a.stage]()
