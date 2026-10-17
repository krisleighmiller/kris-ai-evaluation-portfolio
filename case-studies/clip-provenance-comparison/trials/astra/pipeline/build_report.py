"""Create auditable CSV/JSON results, an offline HTML review report and evidence panels."""
import csv,html,json,collections
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
from investigate import ROOT,OUT,frame

REPORT=ROOT/'report'

def load_rows():
    rows=[]
    for p in sorted((OUT/'coarse').glob('*.json')):
        r=json.loads(p.read_text());r['sample_count']=7
        recovery=OUT/'recovery'/p.name
        if recovery.exists():
            rr=json.loads(recovery.read_text());rr['sample_count']=11
            if rr['candidates'] and (not r['candidates'] or rr['candidates'][0]['score']>r['candidates'][0]['score']):r=rr
        rows.append(r)
    return rows

def classify(r,f):
    c=r['candidates'][0] if r['candidates'] else None
    source='unidentified'; timing='not_available'; status='unidentified'; reason='No temporally consistent, geometrically verified source found in the supplied library.'
    if c and f:
        ev=c['evidence'];span=(max(e['clip_time'] for e in ev)-min(e['clip_time'] for e in ev))/r['duration']
        n=float(np.median([e['inliers'] for e in ev]));cov=float(np.median([e['coverage'] for e in ev]))
        aligned=sum(e['aligned_score']>.6 for e in f['samples'])
        if c['support']>=3 and n>=18 and cov>=.025 and span>=.35 and aligned>=8 and f['score']>=.65:
            source='high'
            precise=f['informative_samples']>=6 and f['timing_rmse'] is not None and f['timing_rmse']<=.12 and f['offset_profile_width']<=.25 and .805<f['speed']<1.195
            timing='high' if precise else 'uncertain'
            status='confident' if precise else 'uncertain'
            reason='Repeated geometric matches and independent aligned-frame verification.'
            if not precise:reason+=' Source is strong; exact start/speed is less certain because timing peaks are broad, inconsistent, or weak.'
        elif c['support']>=3:
            source='uncertain';timing='uncertain';status='uncertain'
            reason='A source candidate has repeated geometric evidence but does not satisfy all independent validation thresholds.'
    return source,timing,status,reason

def tc(t):
    if t is None:return ''
    return f'{int(t)//3600:02}:{int(t)%3600//60:02}:{t%60:06.3f}'

def panel(r,f,dest):
    ts=np.linspace(.4,r['duration']-.5,3)
    canvas=Image.new('RGB',(960,520 if f else 260),'#eeeeee');draw=ImageDraw.Draw(canvas)
    for i,t in enumerate(ts):
        im=Image.fromarray(cv2.cvtColor(frame(ROOT/r['clip'],t),cv2.COLOR_BGR2RGB));im.thumbnail((318,220))
        canvas.paste(im,(i*320,24));draw.text((i*320+4,4),f"{Path(r['clip']).name} @ {t:.2f}s",fill='black')
        if f:
            st=f['start']+f['speed']*t
            im=Image.fromarray(cv2.cvtColor(frame(ROOT/f['path'],max(0,min(39.9,st))),cv2.COLOR_BGR2RGB));im.thumbnail((318,220))
            canvas.paste(im,(i*320,284));draw.text((i*320+4,264),f"{Path(f['path']).name} @ {st:.2f}s",fill='black')
    canvas.save(dest,quality=85)

def main():
    REPORT.mkdir(exist_ok=True);(REPORT/'evidence').mkdir(exist_ok=True)
    results=[];details=[]
    for r in load_rows():
        name=Path(r['clip']).stem;fp=OUT/'refined'/(name+'.json');f=json.loads(fp.read_text()) if fp.exists() else None
        c=r['candidates'][0] if r['candidates'] else None
        source,timing,status,reason=classify(r,f)
        accepted=source!='unidentified'
        row=dict(clip=Path(r['clip']).name,status=status,source_confidence=source,timing_confidence=timing,
                 source_video=Path(f['path']).name if accepted else '',
                 source_start_seconds=round(f['start'],3) if accepted else None,
                 source_start_timecode=tc(f['start']) if accepted else '',
                 source_seconds_per_clip_second=round(f['speed'],5) if accepted else None,
                 clip_duration_seconds=round(r['duration'],3),
                 geometric_support=c['support'] if c else 0,geometric_samples=r['sample_count'],
                 median_geometric_inliers=round(float(np.median([e['inliers'] for e in c['evidence']])),1) if c else 0,
                 aligned_visual_score=round(f['score'],4) if f else None,
                 informative_timing_samples=f['informative_samples'] if f else 0,
                 timing_residual_rmse_seconds=round(f['timing_rmse'],4) if f and f['timing_rmse'] is not None else None,
                 offset_profile_width_seconds=round(f['offset_profile_width'],3) if f else None,
                 evidence=f'evidence/{name}.jpg',reason=reason)
        results.append(row)
        panel_path=REPORT/row['evidence']
        if not panel_path.exists():panel(r,f if accepted else None,panel_path)
        details.append(dict(result=row,coarse=r,refined=f))
    (REPORT/'results.json').write_text(json.dumps(results,indent=2))
    (REPORT/'evidence_details.json').write_text(json.dumps(details,indent=2))
    with (REPORT/'matches.csv').open('w',newline='') as handle:
        w=csv.DictWriter(handle,fieldnames=results[0].keys());w.writeheader();w.writerows(results)
    for status in ['confident','uncertain','unidentified']:
        with (REPORT/f'{status}.csv').open('w',newline='') as handle:
            w=csv.DictWriter(handle,fieldnames=results[0].keys());w.writeheader();w.writerows(r for r in results if r['status']==status)
    with (REPORT/'source_summary.csv').open('w',newline='') as handle:
        w=csv.DictWriter(handle,fieldnames=['source_video','candidate_clips','confident','uncertain']);w.writeheader()
        for p in sorted((ROOT/'masters').glob('*.mp4')):
            selected=[r for r in results if r['source_video']==p.name]
            w.writerow(dict(source_video=p.name,candidate_clips=len(selected),confident=sum(r['status']=='confident' for r in selected),uncertain=sum(r['status']=='uncertain' for r in selected)))
    counts=collections.Counter(r['status'] for r in results)
    source_counts=collections.Counter(r['source_confidence'] for r in results)
    positive=json.loads((OUT/'validation_positive.json').read_text()) if (OUT/'validation_positive.json').exists() else []
    negative=json.loads((OUT/'validation_negative.json').read_text()) if (OUT/'validation_negative.json').exists() else []
    holdout=json.loads((OUT/'validation_holdout.json').read_text()) if (OUT/'validation_holdout.json').exists() else []
    summary=dict(status_counts=dict(counts),source_counts=dict(source_counts),total=len(results),positive_controls=len(positive),correct_positive_sources=sum(r['correct_source'] for r in positive),negative_controls=len(negative))
    summary.update(holdout_controls=len(holdout),correct_holdout_sources=sum(r['correct_source'] for r in holdout))
    (REPORT/'summary.json').write_text(json.dumps(summary,indent=2))
    doc='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Video provenance investigation</title>
<style>body{font:15px system-ui,sans-serif;margin:36px auto;max-width:1200px;padding:0 20px;color:#20242a;background:#fafafa}h1{font-size:28px}h2{margin-top:32px}.lead{font-size:19px;max-width:900px}.metrics{display:flex;gap:50px;margin:28px 0}.metrics b{display:block;font-size:30px}.note{color:#555;max-width:950px;line-height:1.6}input,select{font:inherit;padding:8px;margin:6px 10px 18px 0}table{border-collapse:collapse;width:100%;background:white}th,td{text-align:left;padding:10px;border-bottom:1px solid #ddd}th{position:sticky;top:0;background:#eee}a{color:#165689}summary{cursor:pointer}details img{width:100%;max-width:960px}code{background:#eee;padding:2px 4px}.tag{font-weight:600}.uncertain{color:#81520d}.confident{color:#196645}.unidentified{color:#555}#viewer{margin:20px 0}#viewer img{max-width:100%}.small{font-size:12px;color:#666}</style>
<h1>Video provenance investigation</h1><p class="lead">45 originals · 200 clips · visual source identification and start-time estimation</p>
<div class="metrics">'''
    for key,label in [('confident','Confident source & timing'),('uncertain','Needs timing / match review'),('unidentified','Unidentified')]:doc+=f'<div><b>{counts[key]}</b>{label}</div>'
    doc+=f'''</div><p class="note"><b>{source_counts['high']} clips have high-confidence source identification.</b> “Uncertain” can mean the source is clear but the precise start or playback speed is ambiguous. “Unidentified” means no defensible match was found; it does not prove the clip is absent from the library.</p>
<p><a href="matches.csv">Download all results (CSV)</a> · <a href="results.json">JSON</a> · <a href="../REPORT.md">Detailed methodology and validation</a> · <a href="evidence_details.json">Full numerical evidence</a></p>
<h2>Validation</h2><p class="note">Known-answer tests recovered {sum(x['correct_source'] for x in positive)} of {len(positive)} development controls and {sum(x['correct_source'] for x in holdout)} of {len(holdout)} separate held-out transformed controls. Separate tests withheld the true source from the search library ({len(negative)} controls). Each candidate was checked with geometric correspondence and 15 fresh dense-frame comparisons. See the detailed report for measured timing errors and limitations; these categories are evidence thresholds, not calibrated probabilities.</p>
<h2>Review all clips</h2><p class="note">Source start is measured from the first decoded frame of the supplied original. Speed is source seconds per clip second: 1.10 means the clip plays approximately 10% faster. Click a clip to see three paired frames and links to the videos. Millisecond formatting is not a claim of millisecond accuracy.</p>
<input id="query" placeholder="Search clip or source" aria-label="Search clip or source"><select id="filter" aria-label="Filter status"><option value="">All statuses</option><option>confident</option><option>uncertain</option><option>unidentified</option></select><span id="count"></span><div id="viewer"></div>
<table><thead><tr><th>Clip</th><th>Status</th><th>Source</th><th>Source start</th><th>Speed</th><th>Source / timing confidence</th><th>Geometry</th></tr></thead><tbody id="rows"></tbody></table>
<p class="small">Source: supplied masters/ and clips/ files. All processing and evidence are local. No audio used.</p><script>const data='''+json.dumps(results)+''';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(){const q=document.getElementById('query').value.toLowerCase(),f=document.getElementById('filter').value;const rs=data.filter(r=>(!f||r.status===f)&&(!q||(r.clip+' '+r.source_video).toLowerCase().includes(q)));document.getElementById('count').textContent=rs.length+' clips';document.getElementById('rows').innerHTML=rs.map(r=>`<tr><td><a href="#viewer" data-clip="${esc(r.clip)}">${esc(r.clip)}</a></td><td class="tag ${r.status}">${r.status}</td><td>${esc(r.source_video)||'—'}</td><td>${esc(r.source_start_timecode)||'—'}</td><td>${r.source_seconds_per_clip_second??'—'}</td><td>${r.source_confidence} / ${r.timing_confidence}</td><td>${r.geometric_support}/${r.geometric_samples}</td></tr>`).join('');document.querySelectorAll('[data-clip]').forEach(a=>a.onclick=()=>show(a.dataset.clip));}
function show(name){const r=data.find(r=>r.clip===name);document.getElementById('viewer').innerHTML=`<h3>${esc(name)} — ${esc(r.status)}</h3><p>${esc(r.reason)}</p><p><a href="../clips/${esc(r.clip)}" target="_blank">Open clip</a> ${r.source_video?` · <a href="../masters/${esc(r.source_video)}#t=${r.source_start_seconds}" target="_blank">Open source at estimated start</a>`:''}</p><img src="${esc(r.evidence)}" alt="Three clip frames above corresponding estimated source frames"><p class="small">Visual score ${r.aligned_visual_score??'—'} · informative timing samples ${r.informative_timing_samples}/15 · timing residual RMSE ${r.timing_residual_rmse_seconds??'—'} seconds. Contact sheets are illustrative; see full numerical evidence for all sampled frames.</p>`;}
document.getElementById('query').oninput=render;document.getElementById('filter').onchange=render;render();</script></html>'''
    (REPORT/'index.html').write_text(doc)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
