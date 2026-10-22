"""Read-only source/price artifact audit; no hardware, GUI or serial access."""
import csv, hashlib, importlib.util, json, subprocess
from decimal import Decimal as D
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
OUT=PROJECT/'hardware/cost-right-hand-audit-20261016'
OUT.mkdir(parents=True,exist_ok=True)
HOST=Path('C:/Users/Sakuya/.codex/worktrees/ca03/FPGA-Music-project')
ENGINE=Path('C:/Users/Sakuya/.codex/worktrees/instrument-engine-safety/FPGA-Music-project')
files=[HOST/'tools/host/workbench.py',HOST/'tools/host/config_editor.py',HOST/'tools/host/advanced_tools.py',HOST/'tools/host/device_config.py',HOST/'tools/host/dsp_gui.py',HOST/'tools/scripts/dsp_host.py',HOST/'src/rtl/note_map.v',HOST/'src/rtl/tdm_top.v',ENGINE/'src/rtl/note_map.v',ENGINE/'src/rtl/tdm_top.v',ENGINE/'src/rtl/tdm_engine.v']
sources=[]
needles=['def _apply_document','本版本仅在空闲时应用','def send_spectrum','def cmd_spectrum','def cmd_refresh','pad_mask[k] ?','wire [15:0] pad_mask_eff','else if (gact[rf_grp','pe_mem [load_slot] <=']
for p in files:
 raw=p.read_bytes();lines=raw.decode('utf-8-sig').splitlines()
 anchors=[dict(line=i+1,text=line.strip()) for i,line in enumerate(lines) if any(n in line for n in needles)]
 sources.append(dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),anchors=anchors))
spec=importlib.util.spec_from_file_location('audit_dsp_host',HOST/'tools/scripts/dsp_host.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
writes=len(mod.cmd_spectrum('replace',[0]*16).items)+len(mod.cmd_refresh('all').items)
assert writes==20
old=json.loads((PROJECT/'hardware/cost-survey-20261016/cost-summary.json').read_text(encoding='utf-8'))
new=json.loads((PROJECT/'hardware/cost-compression-20261016/calculation.json').read_text(encoding='utf-8'))
base=D(new['examples'][1]['new_conditional_partial_purchase_cny'])+D('315')+D('180')
assert base==D('557.9049')
sensitivity=[dict(case='Both cost alternatives qualify',reference_total_cny=str(base)),dict(case='ESD alternative fails; revert original TI reference',reference_total_cny=str(base+D('41.3368'))),dict(case='MUX alternative fails; revert original TI reference',reference_total_cny=str(base+D('19.7232'))),dict(case='Both alternatives fail',reference_total_cny=str(base+D('61.0600')))]
assert D(sensitivity[-1]['reference_total_cny'])==D(str(old['screen_scenarios'][0]['total_scenario_cny']))
calculations=dict(status='Arithmetic only; not measured performance',screen_frame_bytes=800*480*2,ideal_fullframe_ms_at_6_75MHz=800*480*16/6750000*1000,ideal_fullframe_fps_at_6_75MHz=6750000/(800*480*16),raw_payload_limit_bytes_per_50ms=6750000/8*.05,gt911_100Hz_period_ms=10,previous_five_point_I2C_ideal_ms=477/400000*1000,nominal_100Hz_phase_plus_I2C_ms=10+477/400000*1000,uart_spectrum_and_refresh_writes=writes,uart_bytes=writes*2,uart_8n1_ideal_ms_at_115200=writes*2*10/115200*1000,original_Logic_remaining=20736-19777,original_BSRAM_remaining=46-38,cost_sensitivity=sensitivity,budget_equation='power_reuse_saving + manufacturing_saving + other_confirmed_saving >= 57.9049 + extra_interface_cost + other_uncovered_cost')
(OUT/'calculations.json').write_text(json.dumps(calculations,ensure_ascii=False,indent=2),encoding='utf-8')
versions={str(p):subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip() for p in [PROJECT,HOST,ENGINE]}
result=dict(date='2026-10-16',review_status='已验证 within source/identity/arithmetic only',cost_release_status='讨论中',right_hand_product_status='部分实现; physical path待实现/待验证',source_heads=versions,source_is_uncommitted_on_host=True,sources=sources,electrical_tests_run=False,rtl_simulation_run=False,pnr_run=False,hardware_touched=False,orders_placed=False)
assert all(hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'] for r in sources)
(OUT/'source-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(source_files=len(sources),source_unchanged=True,reference_base=str(base),fallback_totals=sensitivity,uart_writes=writes,hardware_verified=False),ensure_ascii=True))
