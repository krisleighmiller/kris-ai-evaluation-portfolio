"""Input decode/integrity audit and final deliverable consistency checks."""
import concurrent.futures as cf
import csv,hashlib,json,platform,subprocess,sys
from pathlib import Path
import cv2,numpy,scipy,PIL
from investigate import ROOT,OUT

def inputs():
    rows=json.loads((OUT/'inventory.json').read_text())
    def check(r):
        p=ROOT/r['path']
        sha=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
        result=subprocess.run(['ffmpeg','-v','error','-threads','1','-i',str(p),'-map','0:v:0','-an','-f','null','-'],capture_output=True,text=True)
        return dict(path=r['path'],sha256_unchanged=sha==r['sha256'],decode_returncode=result.returncode,decode_messages=result.stderr)
    with cf.ThreadPoolExecutor(max_workers=6) as ex:checks=list(ex.map(check,rows))
    (OUT/'input_audit.json').write_text(json.dumps(checks,indent=2))
    versions=dict(python=sys.version,platform=platform.platform(),opencv=cv2.__version__,numpy=numpy.__version__,scipy=scipy.__version__,pillow=PIL.__version__,ffmpeg=subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0])
    (OUT/'environment.json').write_text(json.dumps(versions,indent=2))
    keys=['path','bytes','sha256','duration','width','height','fps','audio']
    with (OUT/'inventory.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(rows)
    print('Inputs:',len(checks),'unchanged:',sum(c['sha256_unchanged'] for c in checks),'decode failures:',sum(c['decode_returncode']!=0 or bool(c['decode_messages']) for c in checks))

def outputs():
    report=ROOT/'report'
    rs=json.loads((report/'results.json').read_text()); inv={Path(r['path']).name:r for r in json.loads((OUT/'inventory.json').read_text())}
    assert len(rs)==200 and len({r['clip'] for r in rs})==200
    issues=[]
    for r in rs:
        assert (report/r['evidence']).exists()
        assert r['clip'] in inv
        if r['source_video']:
            assert r['source_video'] in inv
            start=r['source_start_seconds'];end=start+r['source_seconds_per_clip_second']*(r['clip_duration_seconds']-1/24)
            if start<-.1 or end>inv[r['source_video']]['duration']+.2:issues.append(dict(clip=r['clip'],start=start,end=end,source_duration=inv[r['source_video']]['duration']))
        else:assert r['status']=='unidentified' and r['source_start_seconds'] is None
    result=dict(rows=len(rs),evidence_panels=len(list((report/'evidence').glob('*.jpg'))),timeline_boundary_issues=issues)
    (report/'output_audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':
    inputs() if len(sys.argv)<2 or sys.argv[1]=='inputs' else outputs()
