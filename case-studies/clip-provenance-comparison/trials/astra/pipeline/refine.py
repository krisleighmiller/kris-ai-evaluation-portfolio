"""Independent dense-frame validation and subsecond temporal refinement."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json
from pathlib import Path
import cv2
import numpy as np
from scipy.optimize import differential_evolution
from investigate import ROOT,OUT
from match import sample,features,verify

cv2.setNumThreads(1)
W,H=240,180

def decode(path):
    cap=cv2.VideoCapture(str(path)); ts=[]; ims=[]
    while True:
        ok,im=cap.read()
        if not ok:break
        ts.append(cap.get(cv2.CAP_PROP_POS_MSEC)/1000)
        ims.append(cv2.resize(cv2.cvtColor(im,cv2.COLOR_BGR2GRAY),(W,H)))
    cap.release()
    return np.array(ts),np.array(ims)

def highpass(im):
    im=im.astype(np.float32)
    return cv2.GaussianBlur(im,(0,0),.8)-cv2.GaussianBlur(im,(0,0),4)

def ncc(q,refs,mask):
    a=q[mask].astype(np.float32);a-=a.mean();a/=max(np.linalg.norm(a),1e-8)
    b=refs[:,mask].astype(np.float32);b-=b.mean(axis=1,keepdims=True)
    return (b@a)/np.maximum(np.linalg.norm(b,axis=1),1e-8)

def refine_one(row,candidate,ts,refs,calibrate=True,refhp=None):
    # New timestamps interleaved with, rather than reused from, retrieval samples.
    cts,qims=sample(ROOT/row['clip'],np.linspace(.32,row['duration']-.38,15))
    mats=np.array([x['affine'] for x in candidate['evidence']])
    mat=np.median(mats,axis=0); mat*=W/400
    predictions=candidate['start']+candidate['speed']*np.array(cts)
    calibration=[]
    if calibrate:
        cache={}
        for j in [1,4,7,10,13]:
            qp,qd=features(qims[j]);matches=[]
            for target in np.arange(predictions[j]-3,predictions[j]+3.01,.25):
                k=int(np.argmin(abs(ts-target)))
                if k not in cache:cache[k]=features(cv2.resize(refs[k],(400,300)))
                rp,rd=cache[k];v=verify(qp,qd,rp,rd)
                if v:
                    a=np.array(v['affine'])
                    # Supplied edit model has crop/resize, not shear. This suppresses
                    # accidental compensation for camera/object motion in nearby frames.
                    if abs(a[0,1])<.025 and abs(a[1,0])<.025:
                        matches.append(dict(source_time=float(ts[k]),clip_time=cts[j],**v))
            if matches:calibration.append(max(matches,key=lambda v:v['inliers']*v['ratio']))
        if len(calibration)>=3:
            mat=np.median(np.array([v['affine'] for v in calibration]),axis=0)*W/400
    curves=[]; samples=[]
    if refhp is None:refhp=np.array([highpass(im) for im in refs])
    for t,q,pred in zip(cts,qims,predictions):
        mask=np.zeros_like(q,np.uint8)
        hh,ww=q.shape; mask[round(hh*.08):round(hh*.92),round(ww*.06):round(ww*.94)]=1
        warped=cv2.warpAffine(q,mat,(W,H))
        valid=cv2.warpAffine(mask,mat,(W,H),flags=cv2.INTER_NEAREST)>0
        valid=cv2.erode(valid.astype(np.uint8),np.ones((5,5),np.uint8)).astype(bool)
        ix=np.where(abs(ts-pred)<4.0)[0]
        if not len(ix) or valid.sum()<500: continue
        raw=ncc(warped,refs[ix],valid)
        hp=ncc(highpass(warped),refhp[ix],valid)
        score=.45*raw+.55*hp
        curves.append((t,ts[ix],score))
        k=int(np.argmax(score)); far=abs(ts[ix]-ts[ix[k]])>.4
        prominence=float(score[k]-np.max(score[far])) if far.any() else 0
        samples.append(dict(clip_time=t,source_time=float(ts[ix[k]]),score=float(score[k]),raw_ncc=float(raw[k]),highpass_ncc=float(hp[k]),prominence=prominence))
    if len(curves)<3:return None
    def objective(v):
        start,speed=v
        scores=np.array([np.interp(start+speed*t,x,y,left=-1,right=-1) for t,x,y in curves])
        # Trim the worst 20% to tolerate cuts/occlusion; retain full diagnostics.
        return -float(np.mean(np.sort(scores)[len(scores)//5:]))
    b=candidate['start'];s=candidate['speed']
    opt=differential_evolution(objective,[(max(-.5,b-3.0),b+3.0),(.8,1.2)],seed=20261015,tol=1e-7,popsize=25)
    b,s=map(float,opt.x)
    for e,(t,x,y) in zip(samples,curves):
        e['predicted_source_time']=b+s*t
        e['residual']=e['source_time']-e['predicted_source_time']
        e['aligned_score']=float(np.interp(b+s*t,x,y,left=-1,right=-1))
    informative=[e for e in samples if e['prominence']>.015 and e['score']>.55]
    residuals=[e['residual'] for e in informative]
    shifts=np.arange(-.8,.801,.02)
    profile=[-objective((b+d,s)) for d in shifts]
    near=[float(d) for d,v in zip(shifts,profile) if v>=-opt.fun-.01]
    return dict(path=candidate['path'],start=b,speed=s,score=float(-opt.fun),
                median_aligned_score=float(np.median([e['aligned_score'] for e in samples])),
                informative_samples=len(informative),timing_rmse=float(np.sqrt(np.mean(np.square(residuals)))) if residuals else None,
                offset_profile_width=max(near)-min(near) if near else 0,
                affine_clip400_to_master240=mat.tolist(),samples=samples,calibration=calibration,method_version=2)

def refine_group(item):
    path,rs=item
    ts,refs=decode(ROOT/path);refhp=np.array([highpass(im) for im in refs])
    dest=OUT/'refined'
    for r in rs:
        out=dest/(Path(r['clip']).stem+'.json')
        if out.exists():
            existing=json.loads(out.read_text())
            if existing and existing.get('method_version')==2 and existing.get('retrieval_support')==r['candidates'][0]['support']:continue
        result=refine_one(r,r['candidates'][0],ts,refs,refhp=refhp)
        if result:result['retrieval_support']=r['candidates'][0]['support']
        out.write_text(json.dumps(result,indent=2))
        print(Path(r['clip']).name,None if result is None else {k:round(v,3) if isinstance(v,float) else v for k,v in result.items() if k not in ['samples','affine_clip400_to_master240','calibration']},flush=True)

def main():
    from build_report import load_rows
    rows=load_rows()
    dest=OUT/'refined';dest.mkdir(exist_ok=True)
    groups={}
    for row in rows:
        if not row['candidates']:continue
        c=row['candidates'][0]
        if c['support']>=3:groups.setdefault(c['path'],[]).append(row)
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=6) as ex:list(ex.map(refine_group,sorted(groups.items())))

if __name__=='__main__':main()
