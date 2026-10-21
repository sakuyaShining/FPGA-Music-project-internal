"""Executed SPICE envelopes; not full-board, thermal or firmware signoff."""
import csv,hashlib,json,math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from spice_runner import ROOT,COMPAT,VENDOR,digest,run_case,transient_control

cal=json.loads((ROOT/'model-calibration.json').read_text())
assert cal['basic_compatibility_calibration_passed'] and digest(COMPAT)==cal['adapter_sha256'] and digest(VENDOR)==cal['vendor_model_sha256']
project=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019')
pcb=project/'pcb/PCB1.epcb2';before=digest(pcb)
assert before==json.loads((ROOT.parent/'route-checkpoint-0clear-78open-quality-r1-20261021.json').read_text())['pcb_sha256']

def crossing(t,v,threshold,start=0):
    for i in np.flatnonzero((t[1:]>=start)&(v[1:]>=threshold)&(v[:-1]<threshold))+1:
        return float(t[i-1]+(threshold-v[i-1])/(v[i]-v[i-1])*(t[i]-t[i-1]))
    return None

def passive_case(name,rp,cp,stuck=False):
    net=f'''I2C single-segment passive RC, no active buffer model
Vcc vcc 0 3.3
Vctrl ctrl 0 PWL(0 1 1u 1 1.001u 0 30u 0)
Sdriver bus 0 ctrl 0 OD
.model OD SW(Ron=2 Roff=1e12 Vt=.5 Vh=0)
Rp vcc bus {rp:.12g}
Cb bus 0 {cp*1e-12:.12g}
'''
    if stuck:net+='Rstuck bus 0 .1\n'
    net+=transient_control(30e-6,5e-9,'v(bus) v(ctrl) i(Vcc)')
    w=run_case(name,net,30e-6);a=crossing(w[:,0],w[:,1],.99,1e-6);b=crossing(w[:,0],w[:,1],2.31,1e-6)
    tr=None if a is None or b is None else (b-a)*1e9
    expected=math.log(.7/.3)*rp*cp*1e-3
    if not stuck:assert tr is not None and abs(tr/expected-1)<.015,(name,tr,expected)
    else:assert tr is None and np.max(w[:,1])<.05,'Stuck-low negative control not detected'
    return dict(case=name,rp_ohm=rp,assumed_capacitance_pf=cp,stuck_low=stuck,rise_ns=tr,analytical_rise_ns=expected,
                standard_rise_only_ok=tr is not None and tr<=1000,fast_rise_only_ok=tr is not None and tr<=300)

i2c=[]
for count in [1,2,3]:
    for cp in [50,100,200,400,600]:i2c.append(passive_case(f'i2c_r{count}_c{cp}',4700/count,cp))
i2c.append(passive_case('i2c_stuck_low',4700,100,True))
print('I2C completed',len(i2c),'cases',flush=True)

def power_case(name,vin=5.,rup=.35,cap_uf=104.4,iload=.8,order='vin_first',load='constant_current',rset=23700,stop=.04,host_off=False,unplug=False,collapse=False,step=False):
    # Source and load values are scenarios. RUP lumps cable/PTC/PMOS resistance;
    # it does NOT reproduce PMOS reverse polarity or PTC thermal behavior.
    vi=f'PWL(0 0 1m 0 1.01m {vin} {stop} {vin})'
    en=f'PWL(0 0 3m 0 3.01m 3.3 {stop} 3.3)'
    if order=='en_first':
        vi=f'PWL(0 0 3m 0 3.01m {vin} {stop} {vin})';en=f'PWL(0 0 1m 0 1.01m 3.3 {stop} 3.3)'
    dynamic=host_off or unplug or collapse or step
    if dynamic:assert stop>=.1
    if host_off:en=f'PWL(0 0 3m 0 3.01m 3.3 60m 3.3 60.01m 0 {stop} 0)'
    if collapse:vi=f'PWL(0 0 1m 0 1.01m {vin} 60m {vin} 60.01m 0 {stop} 0)'
    # A forced zero-volt source is a supply collapse/clamp, not an unplug.
    # Opening this separate ideal switch represents a disconnected adapter.
    if unplug:
        connector='''Splug adapter connected plugctl 0 PLUG
.model PLUG SW(Ron=.001 Roff=1e12 Vt=.5 Vh=0)
Vplugctl plugctl 0 PWL(0 1 60m 1 60.01m 0 100m 0)
Rup connected vin '''+str(rup)
    else:connector=f'Rup adapter vin {rup}'
    net=f'''TPS2553 local application scenario, vendor model with audited syntax adapter
.include "{COMPAT.as_posix()}"
Vadapter adapter 0 {vi}
{connector}
Cin vin 0 2.2u
Vsense vin switch_in 0
Ven en 0 {en}
Xswitch switch_in 0 en 0 fault ilim out TPS2553_TRANS
Rilim ilim 0 {rset}
* Idealized powered pullup only; not an AP2112 regulator model.
Bpull pull 0 V={{min(max(V(out),0),3.3)}}
Rfault pull fault 100k
Rbleed out 0 10k
Resr out cap .05
Ctotal cap 0 {cap_uf*1e-6:.12g}
'''
    if load=='resistor':net+=f'Rload out 0 {5/iload:.12g}\n'
    else:
        if step:
            net+='Vloadctl loadctl 0 PWL(0 0 60m 0 60.01m 1 100m 1)\n'
            net+=f'Bload out 0 I={{(0.2+({iload}-.2)*V(loadctl))*tanh(V(out)/.05)}}\n'
        else:net+=f'Bload out 0 I={{{iload}*tanh(V(out)/.05)}}\n'
    net+=transient_control(stop,5e-6,'v(adapter) v(vin) v(en) v(out) v(fault) i(Vadapter) i(Vsense)')
    w=run_case(name,net,stop);tail=w[w[:,0]>.9*stop]
    pre=w[(w[:,0]>=.055)&(w[:,0]<.059)] if dynamic else None
    if dynamic:assert len(pre)>0 and np.min(pre[:,4])>4.5,'Event occurred before healthy supply settled'
    metric=dict(case=name,assumed_adapter_v=vin,assumed_upstream_ohm=rup,assumed_total_cap_uf=cap_uf,load_model=load,requested_load_a=iload,
                order=order,rset_ohm=rset,host_off=host_off,unplug=unplug,collapse=collapse,step=step,
                event_time_s=.06 if dynamic else None,pre_event_out_v=float(np.mean(pre[:,4])) if dynamic else None,
                simulated_stop_s=stop,final_out_v=float(np.mean(tail[:,4])),final_input_a=float(-np.mean(tail[:,6])),peak_forward_input_a=float(max(0,np.max(-w[:,6]))),peak_reverse_input_a=float(max(0,np.max(w[:,6]))),
                peak_reverse_switch_a=float(max(0,-np.min(w[:,7]))),
                time_to_assumed_4p5_v=crossing(w[:,0],w[:,4],4.5),last_fault_v=float(np.mean(tail[:,5])))
    return metric,w

power=[];plots={}
for order in ['vin_first','en_first']:
    for cap in [4.4,104.4,1004.4]:
        for load in [.2,.8,1.2]:
            name=f'power_{order}_c{int(cap)}_i{int(load*1000)}'
            m,w=power_case(name,cap_uf=cap,iload=load,order=order,stop=.08 if cap>1000 else .04);power.append(m)
            if order=='vin_first' and cap==1004.4:plots[name]=w
for vin in [4.75,5.]:
    for rup in [.25,.5,.75]:
        m,w=power_case(f'power_drop_v{int(vin*100)}_r{int(rup*100)}',vin=vin,rup=rup);power.append(m)
for rset in [23700*.99,23700*1.01]:
    m,w=power_case(f'power_rset_{int(rset)}',rset=rset,iload=1.2,load='resistor');power.append(m)
for load in ['resistor','constant_current']:
    m,w=power_case('power_compare_'+load,cap_uf=1004.4,iload=1.2,load=load,stop=.08);power.append(m);plots[m['case']]=w
m,w=power_case('power_load_step',iload=.8,step=True,stop=.1);power.append(m);plots[m['case']]=w
m,w=power_case('power_host_off',iload=.02,host_off=True,stop=.1);power.append(m);plots[m['case']]=w
m,w=power_case('power_input_unplug',iload=.2,unplug=True,stop=.1);power.append(m);plots[m['case']]=w
m,w=power_case('power_input_collapse',iload=.2,collapse=True,stop=.1);power.append(m);plots[m['case']]=w
print('Power completed',len(power),'cases',flush=True)
(ROOT/'matrix-measurements.json').write_text(json.dumps({'i2c':i2c,'power':power},indent=2),encoding='utf-8')

# Reject an invalid inference: heavy constant-current demand cannot be reported
# as a successful boot merely because the simulator converged.
over=[m for m in power if m['load_model']=='constant_current' and m['requested_load_a']==1.2 and not m['step']]
assert over and all(m['time_to_assumed_4p5_v'] is None and m['final_out_v']<1 for m in over)
for cap in [4.4,104.4,1004.4]:
    a=next(m for m in power if m['case']==f'power_vin_first_c{int(cap)}_i800')
    b=next(m for m in power if m['case']==f'power_en_first_c{int(cap)}_i800')
    assert abs(a['final_out_v']-b['final_out_v'])<.02,'Power order failed eventual steady-state check'

def csv_write(name,rows):
    with (ROOT/name).open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
csv_write('i2c-spice-results.csv',i2c);csv_write('power-spice-results.csv',power)
fig,axs=plt.subplots(2,2,figsize=(13.8,8.5),dpi=150)
for name,w in plots.items():
    if name.startswith('power_vin_first'):
        axs[0,0].plot(w[:,0]*1e3,w[:,4],label=name.rsplit('_',1)[-1][1:]+' mA demand')
    if name.startswith('power_compare'):
        axs[0,1].plot(w[:,0]*1e3,w[:,4],label=name.removeprefix('power_compare_'))
for name in ['power_load_step','power_host_off','power_input_unplug','power_input_collapse']:
    w=plots[name];axs[1,0].plot(w[:,0]*1e3,w[:,4],label=name.removeprefix('power_'))
w=plots['power_input_collapse'];axs[1,1].plot(w[:,0]*1e3,-w[:,6],label='adapter forward current');axs[1,1].plot(w[:,0]*1e3,w[:,7],label='switch input current',ls='--')
axs[1,0].axvline(60,color='gray',ls=':',label='event at 60 ms')
axs[1,1].set_xlim(59.9,60.2)
axs[0,0].set_title('Startup: assumed 1004.4 uF / 5 V / 0.35 ohm upstream')
axs[0,1].set_title('Same 1.2 A nominal label, different load models')
axs[1,0].set_title('Load step and supply-sequence scenarios')
axs[1,1].set_title('Input collapse: capacitor discharge vs. switch current')
for ax in axs.flat:
    ax.set_xlabel('Time (ms)');ax.grid(alpha=.25);ax.legend(fontsize=7)
for ax in [axs[0,0],axs[0,1],axs[1,0]]:ax.set_ylabel('Output voltage (V)')
axs[1,1].set_ylabel('Current (A)')
fig.suptitle('EXECUTED ngspice transient | TPS2553 vendor model + audited syntax adapter | assumed loads, not full power-chain signoff',fontsize=10)
fig.tight_layout(rect=[0,0,1,.96]);fig.savefig(ROOT/'spice-transients.png');plt.close(fig)
summary={'pcb_sha256':before,'pcb_unchanged':digest(pcb)==before,'i2c_executed_cases':len(i2c),'power_executed_cases':len(power),
         'i2c_analytical_agreement_within_1p5_percent':True,'stuck_low_negative_control_detected':True,
         'constant_current_overload_cases_fail_to_reach_assumed_4p5v':len(over),'assumed_4p5v_not_a_confirmed_screen_spec':True,
         'power_model_calibration':cal,'power_results':power,'i2c_results':i2c,
         'omissions':['PTC heating/trip','real DMP2035U reverse polarity and gate dynamics','AP2112 full regulators','real screen UVLO/inrush/internal converters','trace parasitics','process/thermal corners','firmware timeout/recovery'],
         'manufacturing_release':False}
assert summary['pcb_unchanged']
(ROOT/'spice-validation-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print('SPICE validation evidence complete; no manufacturing signoff.',flush=True)
