"""Inventory and contact sheets. All outputs stay beside the supplied videos."""
from pathlib import Path
import concurrent.futures as cf
import hashlib
import json
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'analysis'
OUT.mkdir(exist_ok=True)
cv2.setNumThreads(1)

def probe(p):
    data = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(p)]))
    v = next(s for s in data['streams'] if s['codec_type'] == 'video')
    return dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size,
                sha256=hashlib.file_digest(p.open('rb'), 'sha256').hexdigest(),
                duration=float(v.get('duration', data['format']['duration'])),
                width=v['width'], height=v['height'], fps=v['avg_frame_rate'],
                audio=any(s['codec_type']=='audio' for s in data['streams']), probe=data)

def frame(path, t, width=320):
    cap=cv2.VideoCapture(str(path)); cap.set(cv2.CAP_PROP_POS_MSEC, t*1000)
    ok, im=cap.read(); cap.release()
    if not ok: raise RuntimeError(f'Cannot read {path} at {t}')
    return cv2.resize(im, (width, round(im.shape[0]*width/im.shape[1])))

def sheet(rows, name):
    canvas=Image.new('RGB',(1000,150*((len(rows)+3)//4)), '#eeeeee'); d=ImageDraw.Draw(canvas)
    for i,r in enumerate(rows):
        im=Image.fromarray(cv2.cvtColor(frame(ROOT/r['path'],r['duration']*.4),cv2.COLOR_BGR2RGB))
        im.thumbnail((248,120)); x=(i%4)*250; y=(i//4)*150
        canvas.paste(im,(x,y)); d.text((x+2,y+122),Path(r['path']).name,fill='black')
    canvas.save(OUT/name)

if __name__=='__main__':
    paths=sorted((ROOT/'masters').glob('*.mp4'))+sorted((ROOT/'clips').glob('*.mp4'))
    with cf.ThreadPoolExecutor(max_workers=8) as ex: rows=list(ex.map(probe,paths))
    (OUT/'inventory.json').write_text(json.dumps(rows,indent=2))
    for kind in ['masters','clips']:
        sub=[r for r in rows if r['path'].startswith(kind+'/')]
        print(kind, len(sub), 'seconds',sum(r['duration'] for r in sub),'duration range',min(r['duration'] for r in sub),max(r['duration'] for r in sub),'sizes',sorted(set((r['width'],r['height']) for r in sub)),'audio',sum(r['audio'] for r in sub))
        for start in range(0,len(sub),48): sheet(sub[start:start+48],f'{kind}_{start:03}.jpg')
