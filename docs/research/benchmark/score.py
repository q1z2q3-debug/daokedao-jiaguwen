#!/usr/bin/env python3
"""甲骨文证据型基准评分器。
用法：
  python3 score.py --tasks tasks.jsonl --pred predictions.jsonl --out score.json
"""
import argparse, json, re
from pathlib import Path

def load_jsonl(p):
    out=[]
    for line in Path(p).read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if line: out.append(json.loads(line))
    return out

def first_han(s):
    if not isinstance(s,str): return ''
    m=re.search(r'[\u4e00-\u9fff]',s)
    return m.group(0) if m else s.strip()

def text_of(obj):
    if isinstance(obj,str): return obj
    if isinstance(obj,dict): return ' '.join(text_of(v) for v in obj.values())
    if isinstance(obj,list): return ' '.join(text_of(v) for v in obj)
    return str(obj)

def valid_evidence(cand, ids):
    ev=cand.get('evidence') or []
    for e in ev:
        if isinstance(e,dict):
            sid=e.get('id') or e.get('source') or ''
            if sid in ids: return True
            if any(sid.endswith(x) for x in []) : return True
    return False

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--tasks',required=True); ap.add_argument('--pred',required=True); ap.add_argument('--out',required=True)
    a=ap.parse_args()
    tasks=load_jsonl(a.tasks); preds={p.get('task_id'):p for p in load_jsonl(a.pred)}
    index=json.loads((Path(a.tasks).parent/'evidence_index.json').read_text(encoding='utf-8'))
    ids={x['id'] for x in index}
    per=[]; top1=top3=0; n_rank=0; net_overlap=[]; src_cov=[]; schema_ok=[]; banned=[]; damage_bad=[]; compose_ok=[]
    for t in tasks:
        p=preds.get(t['id'],{})
        flags=[]
        cands=p.get('candidates') or []
        # schema basics
        ok=bool(cands) or t['type']=='network'
        if t['type']!='network' and not cands: ok=False
        if t['type']=='network' and not isinstance(p.get('neighbors'),list): ok=False
        schema_ok.append(ok)
        if not ok: flags.append('schema')
        # source coverage
        if t['type']!='network':
            cov=[valid_evidence(c,ids) for c in cands] if cands else []
            src_cov.append(sum(cov)/len(cov) if cov else 0.0)
        else:
            ev=p.get('evidence') or []
            src_cov.append(1.0 if any((e.get('id') or e.get('source') or '') in ids for e in ev if isinstance(e,dict)) else 0.0)
        # banned / damage
        txt=text_of(p)
        if re.search('出土|原拓|新发现|商代新字',txt): banned.append(t['id']); flags.append('banned')
        for c in cands:
            if str(c.get('level','')) in ('C','D') and '复原' in text_of(c): banned.append(t['id']); flags.append('false_restoration')
        vp=p.get('verifier') or {}
        if 'no补笔' not in str(vp.get('damage_policy','')) and '不补笔' not in str(vp.get('damage_policy','')):
            damage_bad.append(t['id']); flags.append('damage_policy')
        # task metrics
        score=None
        if t['type'] in ('glyph_id','context_fill'):
            n_rank+=1
            got=[first_han(c.get('reading','')) for c in cands]
            exp=t.get('expected','')
            if got and got[0]==exp: top1+=1
            if exp in got[:3]: top3+=1
        elif t['type']=='network':
            exp=t.get('expected') or []
            got=p.get('neighbors') or []
            ov=len(set(got[:3])&set(exp))/max(1,len(set(exp)))
            net_overlap.append(ov)
        else:
            levels=[c.get('level') for c in cands]
            compose_ok.append(1.0 if (cands and all(x=='D' for x in levels)) else 0.0)
        per.append({'task_id':t['id'],'type':t['type'],'schema':ok,'source_coverage':src_cov[-1] if src_cov else 0.0,'flags':flags})
    results={
      'n_tasks':len(tasks),'n_predictions':len(preds),
      'top1_accuracy':top1/n_rank if n_rank else None,
      'top3_accuracy':top3/n_rank if n_rank else None,
      'network_mean_overlap':sum(net_overlap)/len(net_overlap) if net_overlap else None,
      'source_coverage':sum(src_cov)/len(src_cov) if src_cov else None,
      'schema_valid_rate':sum(schema_ok)/len(schema_ok),
      'banned_claims':sorted(set(banned)),
      'damage_policy_violations':damage_bad,
      'compose_level_D_rate':sum(compose_ok)/len(compose_ok) if compose_ok else None,
      'per_task':per
    }
    Path(a.out).write_text(json.dumps(results,ensure_ascii=False,indent=1),encoding='utf-8')
    print(json.dumps({k:v for k,v in results.items() if k!='per_task'},ensure_ascii=False,indent=1))

if __name__=='__main__': main()
