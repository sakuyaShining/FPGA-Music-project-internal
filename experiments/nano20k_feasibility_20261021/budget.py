"""Reproducible measured ledger + explicitly unmeasured product allocations.

Planning allocations are design caps, NOT synthesis predictions or lower bounds.
Missing implementations stay unqualified, even when the arithmetic fits.
"""
from pathlib import Path
from fractions import Fraction as F
import csv, hashlib, json

R=Path(__file__).resolve().parent
MAIN=Path('C:/Users/Sakuya/FPGA-Music-project')
HW=Path('C:/Users/Sakuya/.codex/worktrees/06df/FPGA-Music-project/hardware/review-manufacturing-20261019')
U=MAIN/'experiments/joint_probe_resources_20261019'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
J=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
inputs={}
def read(p):
    b=p.read_bytes();inputs[str(p)]=hashlib.sha256(b).hexdigest();return b.decode('utf-8-sig')
docs={}
for n in (38,39,49,86):
    p=next((MAIN/'docs/02-技术方案').glob(str(n)+'-*.md'))
    s=read(p)
    local=R.parents[1]/p.relative_to(MAIN)
    docs[str(n)]=dict(path=str(p),bytes=p.stat().st_size,lines=len(s.splitlines()),local_identical=sha(local)==sha(p))
checkpoint=J(HW/'REGIONAL-WORK-IN-PROGRESS.json');read(HW/'REGIONAL-WORK-IN-PROGRESS.json')
capture=J(Path(checkpoint['source_capture']));read(Path(checkpoint['source_capture']))
for name in ('readme','review','drc'):read(Path(checkpoint[name]))
pcb=Path(checkpoint['project'])/'pcb/PCB1.epcb2'
assert sha(pcb)==checkpoint['pcb_sha256'],'Native PCB no longer matches checkpoint'
inputs[str(pcb)]=sha(pcb)
for name in ('expected-pin-nets.json','harness-contract.csv','hardware-contract-20261021-r1/README.md',
             'hardware-contract-20261021-r1/contract-results.json','供电与模块接口-v2.md','屏幕出货配置核对-20261020.md'):
    read(HW/name)
read(U/'project/CURRENT.md');read(U/'delivery.json');read(U/'evidence/resource-map.json')
delivery=J(U/'delivery.json')
drift=[rel for rel,h in delivery['files'].items() if sha(U/rel)!=h]
source_drift=[rel for rel in drift if rel.startswith(('engine/','rtl/','constraints/'))]
assert not source_drift,source_drift
resource_map=J(U/'evidence/resource-map.json')
xml_path=U/'build_nominal_v4/impl/gwsynthesis/board_syn_rsc.xml'
assert sha(xml_path)==resource_map['inputs']['build_nominal_v4/impl/gwsynthesis/board_syn_rsc.xml']
inputs[str(xml_path)]=sha(xml_path)
ledger=J(U/'evidence/resource-map.json')['summary']
measured=[x for x in ledger if x['path'] in ['joint_timing_top/system/'+n for n in ('music','visualizer','sensor','transport','sdram')]]
system=next(x for x in ledger if x['path']=='joint_timing_top/system')
for k in ('logic','register','bsram'):assert sum(x[k] for x in measured)==system[k]
pins=J(HW/'expected-pin-nets.json')
native={(p['ref'],str(p['n'])):p['net'] for p in capture['pads']}
for ref in ('J5','J6','U8','U9'):
    for n,net in pins[ref].items():assert native[(ref,n)]==(net or ''),(ref,n)
panel=[(ref,n,net) for ref in ('J5','J6') for n,net in pins[ref].items() if net and net not in ('GND','3V3_IO','I2S_BCK','I2S_DIN','I2S_LRCK')]
assert len(panel)==17
# Explicit engineering allocations for the incremental product functions.
# These are not claimed measured costs and are not silently counted as zero.
specs=[
 ('four_layers','Four simultaneous slots, generation/ownership, independent configuration',600,700,2,0),
 ('i2c_services','Shared I2C, FT53xx report, EEPROM journal, PCM5122 startup/readback',700,450,2,0),
 ('physical_control','Bounded shared SPI arbiter, 595 reset state, 165/encoder/buttons, octave selection, physical map',600,500,1,0),
 ('entity_ui_score','RA8875 fader graphics, on-device edit/draft/save, score guide, fonts/commands',1100,700,2,0),
 ('files_events','SD SPI, FAT/file allocation, PCM/event pairing, sector CRC, recovery',1600,850,3,0),
 ('play_live_mix','Independent PCM playback + live sum, saturation/levels, sample alignment',150,80,0,1),
 ('management','Cold boot/reset fence, errors/flow control/telemetry, persistent restore',300,200,1,0),
]
alloc=[dict(id=i,scope=s,logic=l,register=f,bsram=b,dsp=d,status='UNMEASURED design allocation, not predicted cost') for i,s,l,f,b,d in specs]
total={k:sum(v[k] for v in alloc) for k in ('logic','register','bsram','dsp')}
hz=27000000;fs=F(hz,512);byte_rate=fs*2
timing=dict(clock_hz=hz,period_ns=float(F(10**9,hz)),sample_hz=float(fs),sample_us=float(F(512*10**6,hz)),
    oscillator_slots_per_sample=512,groups=32,partials=16,max_full_four_layer_combinations_no_tails=8,
    bck_hz=float(F(hz,16)),pcm16_mono_bytes_per_s=float(byte_rate),
    fifo1024_ms=float(F(1024*1000,1)/fs),ring256KiB_ms=float(F(262144*1000,1)/byte_rate),
    full_sdram_mono16_seconds=float(F(8*1024*1024,1)/byte_rate),
    duplex_pcm_bytes_per_s=float(byte_rate*2),
    sd_6_75MHz_raw_bytes_per_s=843750,sd_6_75MHz_duplex_payload_fraction=float(byte_rate*2/843750),
    scan_historical_cycles_no_grant_wait=50192,scan_historical_cycles_grant_wait64=54288,
    scan_historical_ms_no_wait=float(F(50192*1000,hz)),scan_historical_ms_grant_wait64=float(F(54288*1000,hz)),
    positions_upper_planning_cycles=26*36,
    left_worst_phase_two_confirm_frames_factor=3,
    left_historical_digital_phase_envelope_ms=float(F(3*54288*1000,hz)),
    left_deadline_alloc_ms=dict(scan_and_two_frame_confirmation=6.2,event_allocation=0.8,
        queues_slew_and_output=0.2,analog_and_system_margin=2.8),
    touch_i2c_34bytes_400kHz_wire_ms=float(F((34+3)*9*1000,400000)),
    right_deadline_scenarios=[dict(sensor_hz=h,worst_ms=1000/h+float(F((34+3)*9*1000,400000))+.3)
                              for h in (100,125,200)],
    right_sensor_rates_are_scenarios_not_chip_qualifications=True,
    spi_hz=6750000,small_full_frame_ms=float(F(320*240*16*1000,6750000)),
    large_full_frame_ms=float(F(800*480*16*1000,6750000)),
    scan_bus_min_word_payload_us=float(F(64*8*1000000,1687500)),
    scan_bus_word_occupancy_planning_us=360,
    shared_spi_planning_fraction=dict(scan=.20,small_display=.65,large_display=.10,keys=.01,margin=.04),
    small_display_budget_ms_per_50ms=32.5,
    historical_small_display_interface_stress_ms=51.720555555555556,
    requirements=['All rates require measured worst-case arbitration, I2C stretch and device processing bounds.',
        'No unbounded nonpreemptible panel transaction or EEPROM write may delay audio/control.',
        'SD uses board TF pins, not the carrier shared display/scan bus.',
        '512 oscillator slots already occupied: extra oscillators cannot be added for free.'])
assert sum(timing['left_deadline_alloc_ms'].values())==10
assert sum(timing['shared_spi_planning_fraction'].values())==1
result=dict(status='Feasibility NOT CLOSED; no complete product top or product timing qualification',documents=docs,
    hardware_checkpoint=checkpoint,hardware_interface_pad_audit='PASS J5/J6/U8/U9 against current capture',
    upstream86_delivery_file_drift=drift,measured_synthesis=measured,measured_system=system,
    capacity=dict(logic=20736,register=15552,cls=10368,bsram=46,bsram_bits=46*18432,dsp=24,pll=2,sdram_bytes=8*1024*1024),
    incremental_design_allocations=alloc,incremental_allocations_total=total,
    additive_planning_total_before_optimization=dict(logic=system['logic']+total['logic'],register=system['register']+total['register'],bsram=system['bsram']+total['bsram'],dsp=13.75+total['dsp']),
    logic_optimization_needed_for_allocations=dict(no_route_margin=system['logic']+total['logic']-20736,
        with_10percent_engineering_margin=system['logic']+total['logic']-(20736-2074)),
    sensitivity=[dict(unmeasured_added_logic=n,saving_needed_no_margin=max(0,system['logic']+n-20736),
                     saving_needed_with_10percent_margin=max(0,system['logic']+n-18662)) for n in (2500,5000,8000)],
    budget_caveat='Design allocations are neither lower bounds nor promises. Actual joint mapping must replace every allocation. CLS/packing/routing and RAM modes may invalidate arithmetic.',
    timing=timing,panel_gpio=panel,
    storage=dict(one_four_slot_88bit_definition_bytes=4*16*88//8,double_runtime_bytes=2*4*16*88//8,
        draft_bytes=4*16*88//8,eeprom_bytes=32768,pcm_bytes_for_5min=float(byte_rate*300),
        note='88-bit table is current prototype schema only. Future complete definition/version/journal size unmeasured; 5 min is example, not requirement.'),
    inputs=inputs)
(R/'budget.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
with (R/'resource-allocations.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(alloc[0]));w.writeheader();w.writerows(alloc)
print(json.dumps(dict(status=result['status'],upstream_drift=drift,known_logic=system['logic'],planned_incremental=total,hardware_panel_gpio=len(panel)),ensure_ascii=False))
