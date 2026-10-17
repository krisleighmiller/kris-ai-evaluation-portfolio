"""Visual provenance: RootSIFT retrieval, geometric verification, temporal consensus.
Run: OPENBLAS_NUM_THREADS=1 python3 match.py index|search
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import concurrent.futures as cf
import json, time, argparse
import cv2
import numpy as np
from investigate import ROOT, OUT

cv2.setNumThreads(1)
WIDTH=400
SIFT=cv2.SIFT_create(nfeatures=500,contrastThreshold=.025)

def features(im):
    # Each worker owns its SIFT instance.
    sift=cv2.SIFT_create(nfeatures=500,contrastThreshold=.025)
    kp,d=sift.detectAndCompute(im,None)
    if d is None: return np.empty((0,2),np.float32),np.empty((0,128),np.float32)
    d=np.sqrt(d/(d.sum(axis=1,keepdims=True)+1e-9))
    return np.float32([k.pt for k in kp]),d

def sample(path,times):
    cap=cv2.VideoCapture(str(path)); frames=[]; actual=[]
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC,float(t)*1000); ok,im=cap.read()
        if not ok: continue
        actual.append(cap.get(cv2.CAP_PROP_POS_MSEC)/1000)
        im=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
        frames.append(cv2.resize(im,(WIDTH,round(im.shape[0]*WIDTH/im.shape[1]))))
    cap.release()
    return actual,frames

def make_index():
    inventory=json.loads((OUT/'inventory.json').read_text())
    rows=[r for r in inventory if r['path'].startswith('masters/')]
    def one(r):
        ts,ims=sample(ROOT/r['path'],np.arange(0,r['duration']-.05,1.0))
        fs=[features(im) for im in ims]
        return r,ts,fs
    ds=[]; xy=[]; ids=[]; frames=[]; offsets=[0]
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for r,ts,fs in ex.map(one,rows):
            for t,(p,d) in zip(ts,fs):
                fid=len(frames); frames.append({'path':r['path'],'time':t})
                ds.append(d); xy.append(p); ids.append(np.full(len(d),fid,np.int32)); offsets.append(offsets[-1]+len(d))
            print('indexed',r['path'],flush=True)
    np.savez(OUT/'index.npz',descriptors=np.concatenate(ds),xy=np.concatenate(xy),frame_ids=np.concatenate(ids),offsets=np.array(offsets))
    (OUT/'index_frames.json').write_text(json.dumps(frames))

def verify(qp,qd,rp,rd):
    if len(qd)<8 or len(rd)<8: return None
    matches=cv2.BFMatcher().knnMatch(qd,rd,k=2)
    good=[a for a,b in matches if a.distance<.76*b.distance]
    if len(good)<7:return None
    a=np.float32([qp[m.queryIdx] for m in good]); b=np.float32([rp[m.trainIdx] for m in good])
    # Cropping, nonuniform resizing and letterboxing are affine transforms.
    H,mask=cv2.estimateAffine2D(a,b,method=cv2.RANSAC,ransacReprojThreshold=3,maxIters=2000,confidence=.995)
    if H is None:return None
    mask=mask.ravel().astype(bool); n=int(mask.sum())
    if n<6:return None
    det=np.linalg.det(H[:,:2]); sv=np.linalg.svd(H[:,:2],compute_uv=False)
    if det<=0 or sv.min()<.15 or sv.max()>6:return None
    hull=cv2.convexHull(a[mask]); area=float(cv2.contourArea(hull))/(WIDTH*WIDTH*.75)
    err=float(np.median(np.linalg.norm(a[mask]@H[:,:2].T+H[:,2]-b[mask],axis=1)))
    return dict(inliers=n,ratio=n/len(good),coverage=area,error=err,affine=H.tolist())

def search(source_rows=None,destname='coarse',exclude=None,recovery=False):
    z=np.load(OUT/'index.npz'); desc=z['descriptors']; xy=z['xy']; ids=z['frame_ids']; offsets=z['offsets']
    frames=json.loads((OUT/'index_frames.json').read_text())
    if exclude:
        keep=np.array([f['path']!=exclude for f in frames])[ids]
        # Verification still uses the complete per-frame arrays; only retrieval is filtered.
        retrieval_desc=desc[keep]; retrieval_ids=ids[keep]
    else:
        retrieval_desc=desc;retrieval_ids=ids
    cv2.setRNGSeed(20261015)
    flann=cv2.FlannBasedMatcher(dict(algorithm=1,trees=4),dict(checks=192 if recovery else 96))
    print('building retrieval index',len(retrieval_desc),flush=True); flann.add([retrieval_desc]); flann.train()
    inventory=json.loads((OUT/'inventory.json').read_text())
    clips=source_rows if source_rows is not None else [r for r in inventory if r['path'].startswith('clips/')]
    dest=OUT/destname; dest.mkdir(exist_ok=True,parents=True)
    for row in clips:
        output=dest/(Path(row['path']).stem+'.json')
        if output.exists():continue
        ts,ims=sample(ROOT/row['path'],np.linspace(.15,row['duration']-.25,11 if recovery else 7))
        evidence=[]
        for t,im in zip(ts,ims):
            qp,qd=features(im)
            if len(qd)<8:continue
            nearest=flann.knnMatch(qd,k=12 if recovery else 6)
            votes=np.zeros(len(frames))
            for ns in nearest:
                seen=set()
                for m in ns:
                    fid=int(retrieval_ids[m.trainIdx])
                    if m.distance>.65 or fid in seen:continue
                    seen.add(fid); votes[fid]+=(max(0,1-m.distance/.7))**2
            top=np.argsort(votes)[-(40 if recovery else 16):][::-1]
            for fid in top:
                lo,hi=offsets[fid:fid+2]
                v=verify(qp,qd,xy[lo:hi],desc[lo:hi])
                if v:
                    evidence.append(dict(clip_time=t,**frames[fid],**v))
        # Compete all retrieved masters using independent clip times and a consistent clock.
        candidates=[]
        for path in sorted(set(e['path'] for e in evidence)):
            es=[e for e in evidence if e['path']==path and e['inliers']>=8 and e['coverage']>=.015]
            best=None
            for e in es:
                for speed in np.arange(.8,1.201,.025):
                    start=e['time']-speed*e['clip_time']
                    selected=[]
                    for t in ts:
                        eligible=[x for x in es if x['clip_time']==t and abs(x['time']-start-speed*t)<.8]
                        if eligible:selected.append(max(eligible,key=lambda x:x['inliers']))
                    score=sum(min(x['inliers'],100)*min(1,x['coverage']/.1) for x in selected)
                    if best is None or score>best['score']:
                        best=dict(path=path,start=start,speed=float(speed),score=score,support=len(selected),evidence=selected)
            if best:
                ev=best['evidence']
                if len(ev)>=3:
                    slope,inter=np.polyfit([x['clip_time'] for x in ev],[x['time'] for x in ev],1)
                    best.update(start=float(inter),speed=float(slope))
                candidates.append(best)
        candidates.sort(key=lambda x:x['score'],reverse=True)
        result=dict(clip=row['path'],duration=row['duration'],candidates=candidates,evidence=evidence)
        output.write_text(json.dumps(result,indent=2))
        print(Path(row['path']).name,[(Path(c['path']).stem,round(c['score']),c['support'],round(c['start'],2),round(c['speed'],3)) for c in candidates[:2]],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['index','search']);args=p.parse_args()
    make_index() if args.stage=='index' else search()
