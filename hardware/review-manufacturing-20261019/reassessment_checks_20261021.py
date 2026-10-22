"""Read-only design reassessment plus bounded RTL and electrical envelope tests."""
import csv,hashlib,json,math,os,subprocess,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from native_review import ROOT,PROJECT

REPO=ROOT.parent.parent
OUT=ROOT/'reassessment-20261021';OUT.mkdir(exist_ok=True)
MAIN=Path('C:/Users/Sakuya/FPGA-Music-project')
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((ROOT/'route-checkpoint-0clear-78open-quality-r1-20261021.json').read_text())
assert digest(PROJECT/'pcb/PCB1.epcb2')==manifest['pcb_sha256']
for rel,sha in manifest['files'].items():assert digest(PROJECT/rel)==sha,rel
source=json.loads((ROOT/'quality-r1-source-78.json').read_text())
expected=json.loads((ROOT/'expected-pin-nets.json').read_text());seen=set();bad=[]
for p in source['pads']:
    if p['ref'] not in expected:continue
    k=(p['ref'],p['n']);assert k not in seen;seen.add(k)
    if (p['net'] or None)!=expected[p['ref']][p['n']]:bad.append(k)
assert not bad and len(seen)==1054
assert seen=={(ref,pin) for ref,pins in expected.items() for pin in pins}
old_audit=json.loads((ROOT/'connectivity-audit.json').read_text())
for name,sha in old_audit['hashes'].items():assert digest(ROOT/name)==sha,name
design=json.loads((ROOT/'design.json').read_text(encoding='utf-8'))
parts={p['ref']:p for p in design['parts']}
netlist=json.loads((ROOT/'v2-sch-netlist.json').read_text(encoding='utf-8'))
values={p['props']['Designator']:p['props'].get('Value') for p in netlist['components'].values()}
pullups={net:[] for net in ['I2C_SDA','I2C_SCL','I2C_MOD_SDA','I2C_MOD_SCL']}
for ref,p in parts.items():
    if not ref.startswith('R'):continue
    nets=list(p['nets'].values())
    for net in pullups:
        if net in nets and any(n in ['3V3_IO','3V3_PERIPH'] for n in nets):pullups[net].append({'ref':ref,'value':values[ref]})
identities={}
for rel in ['src/rtl/i2s_tx.v','src/rtl/audio_clk_en.v','src/rtl/tdm_top.v','src/rtl/pad_scan.v']:
    identities[rel]={'worktree_sha256':digest(REPO/rel),'main_sha256':digest(MAIN/rel),
                     'same_text_after_newline_normalization':(REPO/rel).read_text(encoding='utf-8-sig')==(MAIN/rel).read_text(encoding='utf-8-sig')}
assert all(p['same_text_after_newline_normalization'] for p in identities.values())

env=dict(os.environ,PYTHONIOENCODING='utf-8');iv=Path('D:/iverilog/bin')
tests={}
configs=[('clock','tb_audio_clk_en',['audio_clk_en.v']),('i2s_std','tb_i2s_std',['audio_clk_en.v','i2s_tx.v']),('pad_digital','tb_pad',['pad_scan.v'])]
for name,top,files in configs:
    dest=OUT/name;dest.mkdir(exist_ok=True)
    sources=[REPO/'src/rtl'/f for f in files]+[REPO/'src/sim'/(top+'.v')]
    cmd=[str(iv/'iverilog.exe'),'-g2012','-s',top,'-o','sim.vvp',*[str(p) for p in sources]]
    compile_result=subprocess.run(cmd,cwd=dest,capture_output=True,env=env,timeout=60)
    text=(compile_result.stdout+compile_result.stderr).decode('utf-8',errors='replace')
    (dest/'compile.log').write_text(text,encoding='utf-8')
    result={'sources':{str(p):digest(p) for p in sources},'compile_rc':compile_result.returncode,'command':cmd}
    if compile_result.returncode==0:
        sim=subprocess.run([str(iv/'vvp.exe'),'sim.vvp'],cwd=dest,capture_output=True,env=env,timeout=180)
        log=(sim.stdout+sim.stderr).decode('utf-8',errors='replace');(dest/'simulation.log').write_text(log,encoding='utf-8')
        result['simulation_rc']=sim.returncode
        if name=='i2s_std':
            check=subprocess.run([sys.executable,str(REPO/'tools/scripts/i2s_std_check.py'),'--simdir',str(dest)],capture_output=True,env=env,timeout=60)
            (dest/'judge.log').write_text((check.stdout+check.stderr).decode('utf-8',errors='replace'),encoding='utf-8')
            result['judge_rc']=check.returncode;result['passed']=sim.returncode==0 and check.returncode==0
        else:result['passed']=sim.returncode==0 and ('[PASS]' in log if name=='clock' else 'RESULT pad=PASS' in log) and '[FAIL]' not in log
    else:result['passed']=False
    tests[name]=result;print('RTL',name,result['passed'],flush=True)

# Analytical sensitivity sweeps, not transistor-level/SPICE or extracted PCB
# simulation. Unknown cable/module capacitance and resistance are scenarios.
i2c=[]
for pullup_count in [1,2,3]:
    rp=4700/pullup_count
    for cp in [50,100,200,400,600]:
        tr=math.log(.7/.3)*rp*cp*1e-12
        i2c.append(dict(parallel_4k7_count=pullup_count,rp_ohm=rp,assumed_bus_capacitance_pf=cp,rise_30_to_70_ns=tr*1e9,
                        within_standard_mode_rise_limit=tr<=1000e-9,within_fast_mode_rise_limit=tr<=300e-9))
power=[]
for vin in [4.75,5.,5.25]:
    for series in [.21,.35,.5,.75]:
        for current in [.2,.5,.8,1.]:power.append(dict(assumed_input_v=vin,assumed_total_series_ohm=series,load_a=current,load_v=vin-series*current,series_dissipation_w=series*current**2))
rc=[]
for rfactor in [.99,1,1.01]:
    for cp in [10,30,50,100,200]:
        for threshold in [.3,.5,.7]:
            t=-47000*rfactor*cp*1e-12*math.log(threshold)
            rc.append(dict(r_ohm=47000*rfactor,assumed_total_c_pf=cp,assumed_threshold_fraction=threshold,ideal_decay_s=t,counts_at_27mhz=t*27e6))
def write_csv(name,rows):
    with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
write_csv('i2c-rise-envelope.csv',i2c);write_csv('power-drop-envelope.csv',power);write_csv('rc-sense-envelope.csv',rc)
fig,axs=plt.subplots(1,3,figsize=(15,4.7),dpi=150)
cap=np.linspace(10,600,250)
for count in [1,2,3]:axs[0].plot(cap,math.log(.7/.3)*4700/count*cap*1e-3,label=f'{count} x 4.7k in parallel')
axs[0].axhline(300,color='red',ls='--',label='Fast-mode rise limit');axs[0].axhline(1000,color='gray',ls=':',label='Standard-mode rise limit')
axs[0].set(xlabel='Assumed bus capacitance (pF)',ylabel='30%-70% rise time (ns)',title='I2C passive rise envelope');axs[0].legend(fontsize=6)
amps=np.linspace(0,1.1,150)
for resistance in [.21,.35,.5,.75]:axs[1].plot(amps,4.75-resistance*amps,label=f'R total={resistance} ohm')
axs[1].set(xlabel='Assumed load (A)',ylabel='Load voltage (V)',title='4.75 V input: resistive drop only');axs[1].legend(fontsize=7)
for threshold in [.3,.5,.7]:axs[2].plot(cap,-47000*cap*1e-12*np.log(threshold)*27e6,label=f'Threshold={threshold} x Vinitial')
axs[2].set(xlabel='Assumed total capacitance (pF)',ylabel='Ideal discharge count @ 27 MHz',title='47k ideal RC: no MUX/leakage model');axs[2].legend(fontsize=7)
for ax in axs:ax.grid(alpha=.25)
fig.suptitle('PARAMETER ENVELOPES ONLY: assumed parasitics / loads, not measured or full-circuit SPICE',fontsize=11)
fig.tight_layout(rect=[0,0,1,.93]);fig.savefig(OUT/'electrical-envelopes.png');plt.close(fig)
drc=json.loads((ROOT/'drc-stage-reassessment-20261021-quality-r1.json').read_text(encoding='utf-8'))
assert all(c['name']=='Connection Error' for c in drc)
report={'pcb_sha256':manifest['pcb_sha256'],'current_native_drc':drc,'mapped_component_pins_checked':len(seen),'pin_mapping_mismatches':bad,
        'all_19_native_files_match_checkpoint':True,'historical_schematic_export_hashes_still_match':True,'rtl_scope':'Existing baseline units; not the complete 84-channel dualscreen system',
        'baseline_source_identity':identities,'rtl_tests':tests,'onboard_i2c_pullups':pullups,
        'analytical_models':{'i2c_cases':len(i2c),'power_cases':len(power),'rc_cases':len(rc),'not_full_spice':True,
        'unknown_parameters':['actual screen load/inrush','adapter/cable resistance','module pullups and capacitance','electrode/cable/overlay capacitance','MUX resistance/leakage','input thresholds/temperature']},
        'full_joint_pnr_rerun':False,'manufacturing_release':False}
(OUT/'reassessment.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
assert digest(PROJECT/'pcb/PCB1.epcb2')==manifest['pcb_sha256']
print('PULLUPS',pullups,flush=True)
print('Read-only reassessment complete; PCB unchanged.',flush=True)
