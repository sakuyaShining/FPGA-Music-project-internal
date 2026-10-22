"""Arithmetic and hardware planning only; does not edit RTL, EDA or old BOMs."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'hardware/recorded-accompaniment-plan-20261015'
OUT.mkdir(parents=True,exist_ok=True)
fs=27_000_000/512
rate=fs*2
calc=dict(status='planning_not_hardware_validation',sample_rate_hz=fs,
    storage_format='mono signed PCM16; native sample counter/time base',bytes_per_second=rate,
    bclk_hz=fs*32,sample_period_us=1_000_000/fs,
    durations=[dict(minutes=m,pcm_bytes=rate*60*m,decimal_MB=rate*60*m/1_000_000) for m in (5,30,60)],
    buffers=[dict(bytes=b,seconds_at_pcm_rate=b/rate) for b in (512,4096,262144,524288)],
    proposed_sdram_reservation_bytes=1048576,
    proposed_playback_buffer_bytes=262144,proposed_record_buffer_bytes=262144,
    proposed_event_queue_bytes=65536,proposed_filesystem_workspace_bytes=65536,
    proposed_spare_bytes=393216,
    sd_spi_candidate_hz=6_750_000,sd_spi_raw_ceiling_Bps=6_750_000/8,
    sequential_effective_rate_target_Bps=500_000,
    future_read_plus_write_pcm_Bps=rate*2,
    budget_allocations_cny=dict(microSD_card=30,aux_DAC_jack_and_support=50,subtotal=80),
    budget_scope='allocation targets, not quotations; AUX already required by whole product')
assert sum(calc[k] for k in ('proposed_playback_buffer_bytes','proposed_record_buffer_bytes',
    'proposed_event_queue_bytes','proposed_filesystem_workspace_bytes','proposed_spare_bytes'))==1048576
(OUT/'calculation.json').write_text(json.dumps(calc,ensure_ascii=False,indent=2),encoding='utf-8')
rows=[
    ('FPGA','Tang Nano20K',0,'yes','Existing GW2AR-18C; full integration synthesis/PnR required','existing','unverified_full_product',''),
    ('card socket','Nano onboard TF slot',0,'yes','Reserve package pins80-85; SPI candidate uses81-84','existing','board_revision_check_pending',''),
    ('buffer RAM','64Mbit / 8MiB SDR SDRAM',0,'yes','Propose1MiB reservation incl256KiB playback and256KiB recording','existing','controller_and_arbiter_pending',''),
    ('recording media','microSDHC 16/32GB; prefer32GB',1,'no','FAT32; C10/U1 or better; measure actual SPI busy/read stalls','KIOXIA EXCERIA32GB LMEX1L032GG4 reference candidate','not_order_qualified',30),
    ('speaker path','onboard MAX98357A + existing4ohm3W speaker',0,'yes','Use mixed digital output; qualify electrical format and volume','existing','analog_output_verification_pending',''),
    ('AUX DAC','stereo line-output DAC or documented module',1,'no','3.3V logic;16bit PCM;52734.375Hz and1.6875MHz32fs compatibility; ground-referenced line output','MPN not frozen; PCM5102A not assumed compatible','clock_and_supply_qualification_pending',''),
    ('audio connector','3.5mm TRS jack',1,'no','TipL RingR SleeveGND; same mono program to both; no direct headphone requirement','exact manufacturer pinout pending','not_order_qualified',''),
    ('analog support','DAC regulator/decoupling/output/protection',1,'no','Plan low-noise3.3V150mA rail; actual current/PSRR/filter/protection per DAC','exact regulator and passives pending','not_order_qualified',''),
    ('controls','existing press encoder and display menus',0,'no_new_extra','Physical record/stop/select/play operation; dedicated keys optional','reuse accepted controls','interaction_pending',''),
    ('nonvolatile settings','24LC256 32KiB candidate',0,'already_in_system_BOM','Instrument settings only; do not store PCM here','existing system candidate','persistence_pending',''),
    ('power','stable5V >=2A system planning capacity','conditional','conditional','Measure board+twoLCD+TFwrite+speaker peaks; avoid USB backfeed','exact adapter pending','not_final_power_budget',''),
]
with (OUT/'hardware-requirements.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.writer(f)
    writer.writerow(('category','item','new_quantity','existing','required_specification','candidate','status','budget_allocation_cny_not_quote'))
    writer.writerows(rows)
sources=[
    dict(title='Sipeed Nano20K official board specifications',url='https://wiki.sipeed.com/hardware/en/tang/tang-nano-20k/nano-20k.html'),
    dict(title='KIOXIA EXCERIA microSD official specs and32GB part numbers',url='https://apac.kioxia.com/en-apac/personal/micro-sd/exceria.html'),
    dict(title='SD Association speed-class scope',url='https://www.sdcard.org/developers/sd-standard-overview/speed-class/'),
    dict(title='TI PCM510xA datasheet; clock detection±4% and PLL table',url='https://www.ti.com/lit/ds/symlink/pcm5102a.pdf'),
    dict(title='NXP UDA1334ATS datasheet;50-100kHz audio mode reference only',url='https://www.nxp.com/docs/en/data-sheet/UDA1334ATS.pdf'),
    dict(title='NXP official discontinuance includesUDA1334ATS',url='https://www.nxp.com/pcn/201804014DN'),
]
(OUT/'sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
rejection=dict(query='PCM5102APWR',tool='lcsc skill search_lcsc.py via jlcsearch',
    returned=dict(lcsc='C7541714',mpn='KH-A2508-03A'),accepted=False,
    reason='MPN mismatch; connector is not the queried DAC. No manufacturer/price/stock imported into BOM.')
(OUT/'rejected-search.json').write_text(json.dumps(rejection,ensure_ascii=False,indent=2),encoding='utf-8')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'}
manifest['generator_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(sample_rate_hz=fs,bytes_per_second=rate,minutes30_MB=rate*1800/1_000_000,
    buffer256KiB_seconds=262144/rate,hardware_rows=len(rows),status='plan_only'),ensure_ascii=False))
