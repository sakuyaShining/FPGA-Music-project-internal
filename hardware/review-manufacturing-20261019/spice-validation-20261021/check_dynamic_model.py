"""Independent timing calibration and local timestep sensitivity checks."""
import json
import numpy as np
from spice_runner import ROOT,COMPAT,run_case,transient_control

def cross(t,v,threshold,start):
    idx=np.flatnonzero((t[1:]>=start)&(v[1:]>=threshold)&(v[:-1]<threshold))+1
    if not len(idx):return None
    k=idx[0]
    return float(t[k-1]+(threshold-v[k-1])/(v[k]-v[k-1])*(t[k]-t[k-1]))

# Datasheet electrical-characteristics condition: CL=1uF, RL=100 ohm.
net=f'''TPS2553 datasheet timing condition sanity check
.include "{COMPAT.as_posix()}"
Vsrc vin 0 5
Ven en 0 PWL(0 0 3m 0 3.01m 3.3 20m 3.3 20.01m 0 30m 0)
Vpull pull 0 3.3
Xswitch vin 0 en 0 fault ilim out TPS2553_TRANS
Rilim ilim 0 23700
Rfault pull fault 100k
Cout out 0 1u
Rload out 0 100
'''+transient_control(.03,1e-6,'v(en) v(out) v(fault) i(Vsrc)')
w=run_case('datasheet_timing',net,.03)
on_en=cross(w[:,0],w[:,1],1.65,.003)
on_out=cross(w[:,0],w[:,2],4.5,.003)
off_en=cross(w[:,0],-w[:,1],-1.65,.020)
off_out=cross(w[:,0],-w[:,2],-.5,.020)
timing={'condition':'5 V / CL 1uF / RL 100 ohm / Rilim 23.7k / EN 0..3.3V',
        'en50_to_vout90_s':None if on_out is None else on_out-on_en,
        'en50_to_vout10_s':None if off_out is None else off_out-off_en,
        'datasheet_ton_toff_max_s':.003,
        'not_full_timing_equivalence':True}
timing['basic_timing_within_3ms']=all(timing[k] is not None and 0<timing[k]<=.003 for k in ['en50_to_vout90_s','en50_to_vout10_s'])

original=(ROOT/'cases/power_input_collapse/circuit.cir').read_text(encoding='ascii')
assert 'tran 5e-06 0.1' in original
ref=[]
for step in [1e-7,5e-8]:
    net=original.replace('tran 5e-06 0.1',f'tran {step:.12g} .0603 .0599 {step:.12g}')
    w=run_case('collapse_refine_'+str(int(step*1e9))+'ns',net,.0603)
    pre=w[w[:,0]<.06]
    assert np.min(pre[:,4])>4.5
    ref.append({'max_step_s':step,'peak_reverse_adapter_a':float(max(0,np.max(w[:,6]))),
                'peak_reverse_switch_a':float(max(0,-np.min(w[:,7]))),
                'out_at_window_start_v':float(w[0,4]),'end_time_s':float(w[-1,0])})
relative=abs(ref[0]['peak_reverse_switch_a']/ref[1]['peak_reverse_switch_a']-1)
assert relative<.02,'Reverse-current peak is not numerically stable within 2%'
result={'datasheet_timing_sanity':timing,'collapse_timestep_checks':ref,
        'refined_peak_agreement_within_2_percent':True,
        'physical_peak_not_validated':True,
        'reason':'Forced input clamp through lumped 0.35 ohm; no real cable inductance, PMOS gate dynamics or full supply behavior',
        'manufacturing_release':False}
(ROOT/'dynamic-model-checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)
