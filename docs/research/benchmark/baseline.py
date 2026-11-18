#!/usr/bin/env python3
"""共现基线：不是大模型，只是给 30 题一个可复算的下限。"""
import json
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parent
tasks=[json.loads(x) for x in (ROOT/'tasks.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
edges=json.load(open('/tmp/research/edges.json'))
deg=defaultdict(int)
for e in edges:
    deg[e['a']]=deg.get(e['a'],0)+e['w']; deg[e['b']]=deg.get(e['b'],0)+e['w']
from collections import Counter
adj=Counter(); rows=json.load(open('/tmp/research/entries.json'))
for r in rows:
    txt=r.get('clean','')
    for i in range(len(txt)-1):
        if '\u4e00'<=txt[i]<='\u9fff' and '\u4e00'<=txt[i+1]<='\u9fff':
            adj[(txt[i],txt[i+1])]+=1
pred=[]; detail=[]
for t in tasks:
    if t['type'] in ('glyph_id','context_fill'):
        ctx=t.get('context',''); pos=ctx.find('□')
        left=ctx[pos-1] if pos>0 else ''; right=ctx[pos+1] if pos+1<len(ctx) else ''
        sc=defaultdict(int)
        for c in set(x['char'] for x in []):
            pass
        # candidate inventory: all chars in index
        for c in {r['char_norm'] for r in rows}:
            sc[c]=adj.get((left,c),0)+adj.get((c,right),0)
        cand=[c for c,w in sorted(sc.items(),key=lambda x:-x[1]) if w>0][:3]
        pred.append({'task_id':t['id'],'candidates':[{'reading':c,'components':[],'evidence':[{'source':t['source_id'],'id':t['source_id']}],'level':'B','confidence':0.3,'counter_evidence':['共现基线，未做字形判断']} for c in cand],'verifier':{'damage_policy':'no补笔','review_required':True}})
    elif t['type']=='network':
        predn=[c for c,w in sorted(deg.items(),key=lambda x:-x[1]) if c!=t['char']][:3]
        pred.append({'task_id':t['id'],'neighbors':predn,'evidence':[{'source':t['source_id'],'id':t['source_id']}],'verifier':{'damage_policy':'no补笔','review_required':True},'confidence':0.8})
    else:
        pred.append({'task_id':t['id'],'candidates':[{'reading':'拟形','components':['未检出'],'evidence':[],'level':'D','confidence':0.0,'counter_evidence':['未做构件检索']}],'verifier':{'damage_policy':'no补笔','review_required':True}})
(ROOT/'baseline_predictions.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in pred)+'\n',encoding='utf-8')
print('wrote',len(pred))
