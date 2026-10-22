"""Bounded volatile SDRAM bench. Always restore verified stage76 SRAM image.

No Flash, TF or audio commands. Run only for the authorized connected Nano20K.
"""
from pathlib import Path
import datetime, hashlib, importlib.util, json, subprocess, time, traceback
import serial
from serial.tools import list_ports

P=Path(__file__).resolve().parents[2]; N=Path(__file__).resolve().parent
R=P/'experiments/sdram_timing_20261018'; OLD=P/'experiments/envelope_resources_20261017'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
CLI='D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/Programmer/bin/programmer_cli.exe'

def save(path,obj):path.write_text(json.dumps(obj,indent=2),encoding='utf-8')

def main():
 audit=read(R/'evidence/timing-audit.json')
 assert audit['bench_gate'] is True and audit['production_qualified'] is False
 assert audit['status'].startswith('PASS')
 for rel,h in audit['inputs'].items():assert sha(R/rel)==h,rel
 for mode in ('nominal','stress'):
  assert min(audit['selected'][mode]['slack_ns'].values())>=0
 fs=R/'build_pll32_nominal/impl/pnr/board.fs'
 assert sha(fs)==audit['selected']['nominal']['bitstream_sha256']
 manifest=read(OLD/'package/manifest.json')
 for rel,h in manifest['files'].items():assert sha(OLD/'package'/rel)==h,rel
 rollback=OLD/'package/config-sram.fs'
 oldaudit=read(OLD/'evidence/board-build-audit.json')
 assert sha(rollback)==oldaudit['bitstream_sha256']
 ports=[p for p in list_ports.comports() if (p.vid,p.pid,p.serial_number)==(0x0403,0x6010,'2025030317B')]
 assert len(ports)==1,[(p.device,p.serial_number) for p in list_ports.comports()]
 port=ports[0].device
 spec=importlib.util.spec_from_file_location('board_check',P/'experiments/board_audio_20261017/board_check.py')
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 S=N/('hardware-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));S.mkdir()
 (N/'latest-hardware.txt').write_text(str(S),encoding='utf-8')
 (S/'bench_hardware_attempt.py').write_bytes(Path(__file__).read_bytes())
 record=dict(status='IN PROGRESS',time=datetime.datetime.now().astimezone().isoformat(),port=port,
  script_sha256=sha(Path(__file__)),audit_sha256=sha(R/'evidence/timing-audit.json'),
  test_bitstream_sha256=sha(fs),restore_bitstream_sha256=sha(rollback),
  flash_read_or_written=False,tf_accessed=False,audio_played=False,runs=[])
 save(S/'result.json',record)

 def command(label,args):
  try:
   out=subprocess.run(args,cwd=S,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
  except subprocess.TimeoutExpired as exc:
   (S/(label+'.log')).write_bytes((exc.stdout or b'')+(exc.stderr or b''));raise
  log=out.stdout+out.stderr;(S/(label+'.log')).write_text(log,encoding='utf-8')
  print(label+': '+log.strip(),flush=True)
  assert out.returncode==0,(label,out.returncode)
  return log

 def program(label,image):
  assert image in (fs,rollback)
  expected=record['test_bitstream_sha256'] if image==fs else record['restore_bitstream_sha256']
  assert sha(image)==expected
  args=[CLI,'--device','GW2AR-18C','--operation_index','2','--chain_size','1','--chain_index','0','--channel','0','--fsFile',str(image)]
  save(S/(label+'-attempt.json'),dict(operation=2,mode='SRAM only',image=str(image),sha256=expected,command=args))
  log=command(label,args)
  assert 'failed' not in log.lower() and 'error' not in log.lower(),label
  for marker in ('Operation "SRAM Program" for device#1','100%','Status Code is: 0x00006020','Finished.'):
   assert marker in log,('missing programmer completion marker',label,marker)

 def identity(capture=False):
  with serial.Serial(port,115200,timeout=.2,write_timeout=1) as com:
   com.reset_input_buffer();board=mod.Board(com)
   values={('%02X'%a):board.read(a) for a in (0xC0,0xC2,0xC3,0xD0,0xD1,0xA4,0xA9)}
   assert values=={'C0':0x72,'C2':0x76,'C3':1,'D0':0x75,'D1':1,'A4':0xD3,'A9':32},values
   snapshot=board.snapshot();assert snapshot['active']==0,snapshot
   result=dict(identity=values,status=board.status(),snapshot=snapshot)
   if capture:
    samples=board.capture();assert len(samples)==2048 and not any(samples)
    (S/'restored-silence-s24le.bin').write_bytes(bytes(2048*3))
    result['zero_pcm_samples']=2048
   return result

 def sweep(number):
  raw=bytearray();pending=bytearray();frames=[];deadline=time.monotonic()+60
  with serial.Serial(port,115200,timeout=.2,write_timeout=1) as com:
   # Do not discard startup bytes: the firmware snapshots immediately after reset.
   while time.monotonic()<deadline:
    data=com.read(256);raw.extend(data);pending.extend(data)
    while len(pending)>=16:
     if pending[:3]!=b'\xa5\x81\x01':del pending[0];continue
     b=bytes(pending[:16]);checksum=0
     for v in b[:15]:checksum^=v
     if checksum!=b[15]:del pending[0];continue
     del pending[:16]
     d=dict(elapsed_s=round(60-(deadline-time.monotonic()),4),state=(b[3]>>3)&7,
      initialized=bool(b[3]&4),fail=bool(b[3]&2),passed=bool(b[3]&1),phase=b[4]&1,
      index=int.from_bytes(b[5:8],'little'),observed=int.from_bytes(b[8:10],'little'),
      expected=int.from_bytes(b[10:12],'little'),completed=int.from_bytes(b[12:15],'little')|(((b[4]>>1)&1)<<24),hex=b.hex())
     frames.append(d);print('sweep%d '%number+json.dumps(d),flush=True)
     (S/('sweep%d.bin'%number)).write_bytes(raw);save(S/('sweep%d.json'%number),frames)
     assert not d['fail'],('SDRAM mismatch',d)
     assert len(frames)==1 or d['completed']>=frames[-2]['completed'],('unexpected reset',d)
     if d['passed']:
      assert d['state']==5 and d['initialized'] and d['phase']==1
      assert d['completed']==(1<<24) and d['index']==(1<<22)-1
      assert d['observed']==d['expected']
      return dict(status='PASS bounded 8MiB two-pattern write/read sweep',frames=len(frames),final=d,
       address_halfwords=1<<22,write_halfwords=1<<23,read_halfwords=1<<23,
       raw_sha256=sha(S/('sweep%d.bin'%number)),frames_sha256=sha(S/('sweep%d.json'%number)))
   (S/('sweep%d.bin'%number)).write_bytes(raw);save(S/('sweep%d.json'%number),frames)
   raise TimeoutError('no valid PASS in 60s; %d frames'%len(frames))

 attempted=False;failure=None
 try:
  record['before']=identity();save(S/'result.json',record)
  assert '2: SRAM Program;' in command('programmer-help',[CLI,'--help'])
  assert 'USB Debugger A/0/' in command('cables',[CLI,'--scan-cables'])
  scan=command('jtag-scan',[CLI,'--scan'])
  assert 'Family: GW2AR' in scan and '0x0000081B' in scan and '1 device(s) found!' in scan
  for number in (1,2):
   attempted=True;program('sweep%d-sram'%number,fs)
   record['runs'].append(sweep(number));save(S/'result.json',record)
  record['status']='PASS bounded SDRAM bench; restoration pending'
 except Exception as exc:
  failure=exc;record['status']='FAIL';record['error']=repr(exc)
  (S/'exception.log').write_text(traceback.format_exc(),encoding='utf-8')
 finally:
  if attempted:
   try:
    program('restore-stage76',rollback);time.sleep(1.3)
    record['restored']=identity(capture=True)
   except Exception as exc:
    record['restore_error']=repr(exc);record['status']='FAIL restoration not verified'
    if failure is None:failure=exc
  if failure is None and len(record['runs'])==2 and 'restored' in record:
   record['status']='PASS two bounded SDRAM sweeps and restored stage76 identity/silence'
  record['finished']=datetime.datetime.now().astimezone().isoformat();save(S/'result.json',record)
 print(json.dumps(record,indent=2),flush=True)
 if failure is not None:raise failure

if __name__=='__main__':main()
