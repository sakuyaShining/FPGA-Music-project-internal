from pathlib import Path
import json,hashlib,datetime
E=Path(__file__).parent;B=E.parent
c=json.loads((E/'sensor-fourlayer-control-candidate-current.json').read_text());s=json.loads((E/'sensor-today-schematic-readonly-current.json').read_text())['value']
assert c['all_routes_physical_pass'] and c['new_vias_physical_pass'] and c['all_drill_spacing_pass']
checks=json.loads((E/'control-power-current-plan.json').read_text())['native_file_checks'];assert all(hashlib.sha256(Path(x['file']).read_bytes()).hexdigest()==x['actual'] for x in checks)
plan=[]
for ch in c['proposed_PAD_net_changes']:
 p=next(p for p in s['pins'] if p['ref']==ch['ref'] and p['pin']==ch['pin'])['data'];nc=p['noConnected'];row=dict(ch,was_NC=nc,pin_id=p['primitiveId'],pin_xy=[p['x'],p['y']]);assert nc==(ch['old']=='')
 if not nc:
  ws=[w for w in s['wires'] if any(abs(w['line'][i]-p['x'])<1e-7 and abs(w['line'][i+1]-p['y'])<1e-7 for i in range(0,len(w['line']),2))];assert len(ws)==1,(ch,ws)
  w=ws[0];assert w['net'] in ['',ch['old']]
  ends=list(zip(w['line'][::2],w['line'][1::2]));end=next(q for q in ends if q!=(p['x'],p['y']))
  ps=[q for q in s['ports'] if abs(q['x']-end[0])<1e-7 and abs(q['y']-end[1])<1e-7];assert len(ps)==1 and ps[0]['net']==ch['old'],ch
  row.update(wire_id=w['primitiveId'],wire_old_net=w['net'],port_id=ps[0]['primitiveId'])
 plan.append(row)
assert len(plan)==35 and sum(x['was_NC'] for x in plan)==14
(E/'sensor-today-sync-schematic.request.json').write_text(json.dumps(dict(plan=plan),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
now=datetime.datetime.now().astimezone().isoformat()
for n in ['PCB-CURRENT-CAPACITY-RECOVERY-20261024.json','PCB-ACTIVE-WORK.json','实体交付当前入口.json','模块方案-当前证据.json']:
 p=B/n;d=json.loads(p.read_text(encoding='utf-8-sig'));d['sensor_fourlayer_trial_current']=dict(at=now,phase='prepared-35PAD-schematic-first',candidate=str(E/'sensor-fourlayer-control-candidate-current.json'),native_apply_log=str(E/'sensor-today-sync-schematic-result-current.json'),recovery=str(E/'sensor-fourlayer-native-recovery-current/recovery-manifest.json'),source_PCB2_SHA=c['source_sha256'],layer_change_explicit_candidate=True,budget_quote_unverified=True,accepted=False);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Prepared35pin changes:21existing netport edits +14NC externalbridge connections. Existing21 wires have unnamed net inherited from checked port; preserve them rather than inventing net labels.')
