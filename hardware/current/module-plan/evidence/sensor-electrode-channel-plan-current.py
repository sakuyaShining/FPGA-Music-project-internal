"""Offline, bounded planning only. Never writes native CAD or changes nets in it."""
from pathlib import Path
import copy, datetime, hashlib, json, sys
sys.path.insert(0, 'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
from shapely import from_wkb
from shapely.geometry import Point, LineString, box
from shapely.affinity import rotate

E = Path(__file__).parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n, d): (E/n).write_text(json.dumps(d, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
source = E/'sensor-front-14nets-current.epcb2'
expected = '83b238dfec46b08fd8f0825804fd37d57b1d44181c30f0f27e93c53e7ddcbab3'
assert sha(source) == expected
native_checks = json.loads((E/'control-power-current-plan.json').read_text(encoding='utf-8'))['native_file_checks']
assert all(sha(Path(r['file'])) == r['actual'] for r in native_checks)
pads = json.loads((E/'sensor-front-exact-source-pads-14nets-current.json').read_text())['pads']
assert len(pads) == 150
original = copy.deepcopy(pads)
by = {(p['ref'], p['pin']): p for p in pads}
order = json.loads((E/'sensor-front-electrode-whole-channel-order-current.json').read_text())['nets']
actual = json.loads((E/'sensor-front-native-14nets-reopened-DRC-current.json').read_text())['value']
gnd = from_wkb((E/'sensor-front-real-bottom-ground-14nets-current.wkb').read_bytes())
width = .1651
changes = []
for ref in range(3,11):
    p = by[(f'R{ref}', '1')]
    old = p['net']; p['net'] = f'L0_E{10-ref:02}'
    changes.append(dict(ref=p['ref'], pin=p['pin'], old=old, proposed=p['net'], reason='Reverse only left8 external input assignment; M00..07 remain unchanged'))
pairs = {'1':'10','2':'9','4':'7','5':'6'}
bridges = []
for row in order:
    d = row['ESD']; p = by[(d['ref'], d['pin'])]
    q = by[(d['ref'], pairs[d['pin']])]
    assert q['net'] == ''
    q['net'] = p['net']
    changes.append(dict(ref=q['ref'], pin=q['pin'], old='', proposed=q['net'], reason='TI optional straight-through NC landing; requires external copper bridge'))
    bridges.append(dict(net=p['net'], start=[p['x_mm'],p['y_mm']], end=[q['x_mm'],q['y_mm']], pads=[p['ref']+'.'+p['pin'],q['ref']+'.'+q['pin']]))

def shape(p):
    s = p['shape']; w=s['width']*.0254; h=s['height']*.0254
    if s['padType']=='ELLIPSE' and abs(w-h)<1e-6:
        return Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=64)
    return rotate(box(p['x_mm']-w/2,p['y_mm']-h/2,p['x_mm']+w/2,p['y_mm']+h/2),p['angle'],origin=(p['x_mm'],p['y_mm']))
obs = [(p['ref']+'.'+p['pin'],p['net'],shape(p),.1651) for p in pads]
for t in actual['lines']:
    obs.append((t['primitiveId'],t['net'],LineString([(t['startX']*.0254,t['startY']*.0254),(t['endX']*.0254,t['endY']*.0254)]).buffer(t['lineWidth']*.0254/2,quad_segs=64),.1651))
for v in actual['vias']:
    obs.append((v['primitiveId'],v['net'],Point(v['x']*.0254,v['y']*.0254).buffer(v['diameter']*.0254/2,quad_segs=64),.2501))
for b in bridges: obs.append(('candidate:'+b['net'],b['net'],LineString([b['start'],b['end']]).buffer(width/2,quad_segs=64),.1651))
violations = []; bridge_checks=[]
for b in bridges:
    cu = LineString([b['start'],b['end']]).buffer(width/2,quad_segs=64)
    margins=[]
    for name,n,o,c in obs:
        if n != b['net']:
            dd=cu.distance(o); margins.append(dd-c)
            if dd < c-1e-8: violations.append(dict(net=b['net'],other=name,actual_mm=dd,required_mm=c))
    missing=cu.difference(gnd).area
    if missing>1e-8: violations.append(dict(net=b['net'],reference_missing_mm2=missing))
    bridge_checks.append(dict(**b,width_mm=width,length_mm=LineString([b['start'],b['end']]).length,minimum_clearance_extra_mm=min(margins),full_width_reference_missing_mm2=missing))

# A full function-preserving physical harness proposal, not an accepted pin map.
mapping=[]
for lane in range(6):
    for row in range(14):
        header = 8-row if row<8 else row+1
        old_e = header-1
        r = by[(f'R{row+3}','1')]
        assert r['net']==f'L0_E{old_e:02}'
        mapping.append(dict(lane=lane,physical_row=row,logical_index=row*6+lane,board=f'BANK{lane}',J1_pin=header,electrode_net=r['net'],series_resistor=f'R{row+3}',MUX_channel=row,internal_net=f'L0_M{row:02}'))
assert sorted(x['logical_index'] for x in mapping)==list(range(84))
assert len({(x['lane'],x['J1_pin']) for x in mapping})==84
for lane in range(6): assert sorted(x['MUX_channel'] for x in mapping if x['lane']==lane)==list(range(14))
left=[]
for row in order[:8]:
    p = next(p for p in pads if p['ref'].startswith('R') and p['pin']=='1' and p['net']==row['net'])
    left.append((row['ESD']['y_mm'],p['y_mm']))
inversions=sum((a[0]-b[0])*(a[1]-b[1])<0 for i,a in enumerate(left) for b in left[i+1:])
assert inversions == 0
unchanged_nonempty = [p for p,q in zip(original,pads) if p['net'] and p['net']==q['net']]
assert len(changes)==22 and sum(p['net']!=q['net'] for p,q in zip(original,pads))==22
assert all(by[(f'R{r}','2')]['net']==f'L0_M{r-3:02}' for r in range(3,17))
assert all(sha(Path(r['file']))==r['actual'] for r in native_checks)
result=dict(at=datetime.datetime.now().astimezone().isoformat(),state='OFFLINE_CHANNEL_PLAN_ONLY_NO_NATIVE_NET_CHANGES',source_sha256=expected,
    native_files_checked=len(native_checks),native_files_unchanged=True,original_pad_count=150,
    source_evidence=dict(url='https://www.ti.com/lit/ds/symlink/tpd4e02b04.pdf',file=str(E/'TI-TPD4E02B04-SLVSD85B.pdf'),sha256=sha(E/'TI-TPD4E02B04-SLVSD85B.pdf'),pages=[3,15],document='SLVSD85B, July2016',reviewed_pin_table_image='TPD4E02B04-pin-table-page3-current.png'),
    NC_interpretation='Pins6/7/9/10 internally NC. Optional external straight-through routing allowed. No internal 1-to10/2-to9/4-to7/5-to6 connection exists or is assumed.',
    proposed_pad_net_changes=changes,proposed_pad_net_change_count=22,proposed_empty_NC_assignments=14,proposed_existing_input_net_changes=8,
    left8_order_inversions_before=28,left8_order_inversions_after=0,
    candidate14_ESD_external_bridge_checks=bridge_checks,candidate_bridge_physical_and_full_width_reference_pass=not violations,violations=violations,
    full84_mapping=mapping,logical84_bijection_pass=True,internal14_MUX_nets_unchanged=True,calibration_channels14_15_unchanged=True,
    candidate_only=True,native_applied=False,complete14electrode_routing_proved=False,native_DRC_for_candidate_performed=False,
    unchanged_original_J1_mapping='Original native J1.1..14 still E00..13; this report proposes a future input-side resistor mapping + compensated external electrode harness, not an accepted replacement.',
    pending=['All14 full J1-toESD-toR routes planned jointly, including right6 perimeter corridors and all existing Cu obstacles','Schematic/PCB/netlist explicit22PAD change audit and 84harness labels if candidate adopted','Native source identity/rules/recovery/autosave/PID/memory preflight before any mutation','Actual new Ground pours and all-source-Cu physical/reference/return/old-contact/DC/manufacturing audit','Strict native DRC, save/close/reopen and actual all150PAD map','All21 remaining nets completion, sixboard factory preweld quote and delivery within700wholebudget'],
    physical_tests='UNMEASURED',manufacturing_release=False,complete_purchase_plan=False)
write('sensor-electrode-channel-plan-current.json',result)
rows='\n'.join(f"| {r} | {8-r if r<8 else r+1} | E{7-r if r<8 else r:02} | R{r+3} | CH{r} |" for r in range(14))
(E/'sensor-electrode-channel-plan-current.md').write_text(f'''# 84路电极整组通道候选：仅离线规划

当前源83b238df不变，原951主板不变。没有原生改网、布线、移动或RTL操作。本文件不是制造或采购放行文件。

原左8路端点反序有28对交叉；候选仅反转R3—R10的输入侧E00—E07网，输出M00—M07与现有铜保持；外部电极按下表补偿。数学核对84个row*6+lane索引和84个板/针位置均一一对应，未删减电极。校准CH14/15、六路独立SENSE_OUT、J10不变。**只反转排线而不改电阻输入网并不能解决当前交叉。**

## 候选每板14路连接（六板同表；lane=0..5）

| 实体电极row | J1针 | 保护侧网 | 串阻 | MUX |
|---|---|---|---|---|
{rows}

每个电极索引=row*6+lane。表只在候选原理图/PCB同步改网且通过验收后使用；当前原生板仍采用旧映射，不能照本表接线宣称完成。

## ESD封装直通出口

TI原厂SLVSD85B第3页明确6/7/9/10为内部NC，并允许可选直通布线；第15页要求保护器靠近连接器、线路尽量直。候选把D1—D3的10/9/7/6及D4的10/9接到对应IO1/2/4/5同一网络，并由**外部真实铜线**跨接。不得把NC误解成芯片内已接通。总计14个NC焊盘赋网及8个串阻输入改网，共22个PAD，需要同步原理图和PCB。

14段0.1651mm宽、约0.8mm长的封装内直通桥已相对当前150PAD、91段原铜、36孔和全部候选桥做离线实际距离检查；通过={not violations}，并按现有真实Bottom地铜核全线宽参考。这仅证明14个短桥的局部可行性，**没有证明14路电极全路径可布通**，也没有原生DRC或新增完整地审签。

下一步先共同规划14网完整的J1—ESD—串阻路径，尤其右6路绕行；通过后才能在同一工程做可回滚候选，显式审22PAD差异、全部84映射/校准、全部旧铜/规则/回流/接触和保存重开。当前仍21网56项未连；工厂预焊费和交期、完整700元预算未闭合。实物UNMEASURED。
''',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['state','native_files_checked','proposed_pad_net_change_count','left8_order_inversions_after','candidate_bridge_physical_and_full_width_reference_pass','violations','logical84_bijection_pass','native_applied','complete14electrode_routing_proved']},ensure_ascii=False))
