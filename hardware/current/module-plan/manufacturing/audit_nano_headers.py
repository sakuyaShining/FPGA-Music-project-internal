"""Join saved carrier pad nets to the visually reviewed official Nano3921 header table."""
from pathlib import Path
import csv, hashlib, json
from audit_saved_sensor import documents

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).parent
PCB=ROOT/'hardware/current/native/pcb/PCB1.epcb2'
PDF=ROOT/'hardware/current/module-plan/evidence/Nano20K-3921-official-schematic.pdf'
# Transcription of J5/J6, official schematic Rev1.30 (2023-07-11), page2.
# Rendered page was visually reviewed; not inferred from FPGA package pin order.
HEADERS={
 'J5':['+5V','GND',76,80,42,41,56,54,51,48,55,49,86,79,'GND','+3V3',72,71,53,52],
 'J6':[73,74,75,85,77,15,16,27,28,25,26,29,30,31,17,20,19,18,'+3V3','GND']}

def main():
 assert hashlib.sha256(PCB.read_bytes()).hexdigest()=='951ce88a1a2fcc2d758f9a53222a400cbddd3bc5b689cc2a37c98b8303d9ca4d'
 board=next(d for d in documents(PCB) if d['head']['docType']=='PCB')
 names={v['parentId']:v['value'] for h,v in board['records'] if h['type']=='ATTR' and v['key']=='Designator'}
 rows=[]
 for h,v in board['records']:
  if h['type']!='PAD_NET':continue
  identity=json.loads(h['id']);ref=names.get(identity[1])
  if ref not in HEADERS:continue
  pin=int(identity[2]);physical=HEADERS[ref][pin-1]
  rows.append(dict(header=ref,pin=pin,FPGA_pin=physical if isinstance(physical,int) else '',power=physical if isinstance(physical,str) else '',net=v['padNet']))
 rows.sort(key=lambda x:(x['header'],x['pin']))
 assert len(rows)==40 and len({(r['header'],r['pin']) for r in rows})==40
 actual={(r['header'],str(r['pin'])):r for r in rows}
 contract=json.loads((OUT.parent/'evidence/edit-control-interface-current.json').read_text(encoding='utf-8'))
 for pin in contract['external_header_nets']:
  r=actual[pin['header'],pin['pin']]
  assert r['net']==pin['net'] and r['FPGA_pin']==pin['FPGA_pin'],pin
 with (OUT/'nano-header-netmap-current.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['header','pin','FPGA_pin','power','net']);w.writeheader();w.writerows(rows)
 report=dict(status='PASS_SAVED_CARRIER_TO_REVIEWED_OFFICIAL_HEADER_TABLE',source_PCB_sha256=hashlib.sha256(PCB.read_bytes()).hexdigest(),official_PDF_sha256=hashlib.sha256(PDF.read_bytes()).hexdigest(),official_PDF_page=2,official_revision='Rev1.30 2023-07-11',mapping_provenance='Visual review of official PDF page2; script joins all40 native carrier pad-net records to that transcription.',rows=rows,edit_control_pins_checked=len(contract['external_header_nets']),corrections=[dict(header='J6',pin=15,old_FPGA_pin=18,correct_FPGA_pin=17),dict(header='J6',pin=17,old_FPGA_pin=20,correct_FPGA_pin=19)],PCB_changed=False,RTL_changed=False,physical_continuity_test='UNMEASURED')
 (OUT/'nano-header-audit-current.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(status=report['status'],header_pads=40,edit_control_pins_checked=6,PCB_changed=False)))

if __name__=='__main__':main()
