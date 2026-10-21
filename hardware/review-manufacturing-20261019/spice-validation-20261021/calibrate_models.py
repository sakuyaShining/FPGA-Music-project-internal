"""Reject incompatible vendor logic, then validate a minimal syntax adapter."""
import difflib,json
import numpy as np
from spice_runner import ROOT,VENDOR,COMPAT,ENGINE,digest,run_case,transient_control

raw=VENDOR.read_text(encoding='utf-8')
old='E_ABMGATE  YINT 0 VALUE {{IF(V(A) > {VTHRESH}  ^  \n+ V(B) > {VTHRESH},{VSS},{VDD})}}'
new='E_ABMGATE  YINT 0 VALUE {{IF((V(A) > {VTHRESH}) != (V(B) > {VTHRESH}),{VSS},{VDD})}}'
assert raw.count(old)==1 and raw.count('^')==1,'Review adapter against changed vendor source'
adapted=raw.replace(old,new)
COMPAT.write_text(adapted,encoding='utf-8')
(ROOT/'ngspice-compatibility.diff').write_text(''.join(difflib.unified_diff(raw.splitlines(True),adapted.splitlines(True),fromfile='TI-original',tofile='ngspice41-local-syntax-adapter')),encoding='utf-8')

def gates(lib,label):
    circuit=f'Gate compatibility truth table\n.include "{lib.as_posix()}"\nVzero n0 0 0\nVone n1 0 1\n'
    signals=[];expected=[]
    for g in ['XNOR2','AND2','OR2']:
        for a in [0,1]:
            for b in [0,1]:
                out=f'{g.lower()}_{a}{b}';circuit+=f'X{out} n{a} n{b} {out} {g}_BASIC_GEN\n';signals.append('v('+out+')')
                expected.append(int(a==b) if g=='XNOR2' else int(a and b) if g=='AND2' else int(a or b))
    circuit+='.control\nset wr_singlescale\nset wr_vecnames\nop\nwrdata logic.txt '+' '.join(signals)+'\nquit\n.endc\n.end\n'
    data=run_case(label,circuit,output='logic.txt')
    actual=(data[0,1:]>.5).astype(int).tolist()
    return {'expected':expected,'actual':actual,'passed':actual==expected}

original=gates(VENDOR,'gates_original');compatible=gates(COMPAT,'gates_compatible')
assert not original['passed'],'Original compatibility fault no longer reproduced; remove unnecessary adapter'
assert compatible['passed'],'Syntax adapter failed independent truth table'

def power_calibration(name,vin,en,load=6.25,rilim=23700):
    circuit=f'''TPS2553 basic functional calibration
.include "{COMPAT.as_posix()}"
Vsrc vin 0 {vin}
Ven en 0 {en}
Vpull pull 0 3.3
Xswitch vin 0 en 0 fault ilim out TPS2553_TRANS
Rilim ilim 0 {rilim}
Rfault pull fault 100k
Cin vin 0 2.2u
Cout out 0 2.2u
Rload out 0 {load}
'''+transient_control(.02,2e-6,'v(vin) v(en) v(out) v(fault) i(Vsrc)')
    data=run_case(name,circuit,.02);tail=data[data[:,0]>.019]
    return {'vout_tail_v':float(np.mean(tail[:,3])),'input_tail_a':float(-np.mean(tail[:,5])),'fault_tail_v':float(np.mean(tail[:,4]))}

disabled=power_calibration('cal_disabled','PWL(0 0 1m 0 1.01m 5 20m 5)','0')
enabled=power_calibration('cal_enabled','PWL(0 0 1m 0 1.01m 5 20m 5)','PWL(0 0 3m 0 3.01m 3.3 20m 3.3)')
uvlo=power_calibration('cal_uvlo','2','3.3')
limited=power_calibration('cal_current_limit','PWL(0 0 1m 0 1.01m 5 20m 5)','PWL(0 0 3m 0 3.01m 3.3 20m 3.3)',load=1.)
assert disabled['vout_tail_v']<.05,disabled
assert enabled['vout_tail_v']>4.8 and .75<enabled['input_tail_a']<.85,enabled
assert uvlo['vout_tail_v']<.05,uvlo
assert 1.002<limited['input_tail_a']<1.184 and limited['fault_tail_v']<.4,limited
result={'engine':'ngspice-41 conda-forge win-64','engine_sha256':digest(ENGINE),'vendor_model_sha256':digest(VENDOR),
        'vendor_model_header':'TPS2553_TRANS Final 1.00, 2011-10-19, PSpice 16.2, SLVM425A package',
        'adapter_sha256':digest(COMPAT),'adapter_change':'PSpice boolean XOR in XNOR2 rewritten as explicitly parenthesized inequality; no device parameters changed',
        'original_vendor_logic':original,'adapter_logic':compatible,'disabled':disabled,'enabled':enabled,'uvlo':uvlo,'current_limit':limited,
        'basic_compatibility_calibration_passed':True,'not_pspice_equivalence_or_physical_validation':True,'manufacturing_release':False}
(ROOT/'model-calibration.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)
