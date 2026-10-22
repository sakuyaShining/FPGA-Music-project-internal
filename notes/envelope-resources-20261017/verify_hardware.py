"""Bounded configuration/audio checks; never invokes a programmer or Flash."""
from pathlib import Path
import sys,json,hashlib,time,datetime
from types import SimpleNamespace
from serial.tools import list_ports
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/envelope_resources_20261017'
S=Path((N/'latest-hardware.txt').read_text(encoding='utf-8'));D=S/'uart';D.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
program=json.loads((S/'program-result.json').read_text());assert program['operation']==2 and program['bitstream_sha256']==sha(R/'package/config-sram.fs')
sys.path[:0]=[str(R/'gui'),str(R/'scripts'),str(R/'host'),str(P/'experiments/board_audio_20261017')]
from serial_link import SerialLink
from device_config import apply_supported
from config_transport_client import CAPABILITY,apply_document,checksum,payload_for
from config_adapter import compile_document
from instrument_config import default_config
from board_check import Board,analyze
ports=[p for p in list_ports.comports() if p.vid==0x0403 and p.pid==0x6010 and p.serial_number=='2025030317B'];assert len(ports)==1
result=dict(status='STARTED',hardware_tested=True,flash_read_or_written=False,bitstream_sha256=program['bitstream_sha256'],port=ports[0].device,port_hwid=ports[0].hwid,script_sha256=sha(Path(__file__).resolve()),captures={},applications={})
(D/'attempt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
link=SerialLink(ports[0].device);opened=False;identified=False
def save():
 (D/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
def send(pairs):return link.send(SimpleNamespace(items=[(a,d,'bounded hardware check') for a,d in pairs]))
def note(note,on):send([(0x60,note|(128 if on else 0)),(0x61,4 if on else 0)])
def document(name,attack,release,slot=0,mode='sustain'):
 doc=default_config(name,mode);doc['preset']=slot;doc['spectrum']=[128]+[0]*15
 doc['articulation'].update(attack_ms=attack,decay_ms=80 if mode=='strike' else 0,sustain_level=0 if mode=='strike' else 255,release_ms=release)
 return doc
def apply(name,doc):
 record=apply_supported(link,doc);result['applications'][name]=record;save()
 assert record['status']=='VOLATILE_CONFIG_CONFIRMED' and record['commit_state']=='confirmed' and not record['persisted'],record
 print('PASS device-confirmed application',name,'revision',record['ack']['revision'],flush=True)
def read_capture(name,already_started=False):
 if not already_started:board.write(0x80,1)
 deadline=time.monotonic()+2
 while not board.read(0x80)&2:
    assert time.monotonic()<deadline,'capture timeout';time.sleep(.005)
 board.write(15,0xa8);raw=board.read_exact(6145);assert raw[0]==0xa8
 values=[]
 for i in range(2048):
    v=int.from_bytes(raw[1+i*3:4+i*3],'little');values.append(v-(1<<24) if v&(1<<23) else v)
 (D/(name+'.s24le.bin')).write_bytes(raw[1:]);stats=analyze(values)
 stats['pcm_sha256']=sha(D/(name+'.s24le.bin'));result['captures'][name]=stats;save()
 assert stats['saturated']==0,(name,'clipping')
 print(name,stats,flush=True);return stats
try:
 link.open();opened=True;board=Board(link.ser);link.ser.reset_input_buffer()
 identity={a:board.read(a) for a in (0xc0,0xc1,0xc2,0xc3,0xa4,0xa7,0xa9)}
 cap=tuple(link.read_reg(0xd0+i) for i in range(6));result['identity']=dict(registers=identity,configuration_capability=cap)
 assert (identity[0xc0],identity[0xc2],identity[0xc3],identity[0xa4],identity[0xa7],identity[0xa9])==(0x72,0x76,1,0xd3,8,32) and cap==CAPABILITY
 assert identity[0xc1]==0x19 and link.read_reg(0xe9)==1
 identified=True;result['before']=board.snapshot();assert result['before']['active']==0
 assert read_capture('initial-silence')['nonzero']==0
 for name,doc in [('fast',document('fast',0,80)),('slow',document('slow',200,200))]:
    apply(name,doc)
    # Trigger capture in the same UART write as ON; no USB read precedes the
    # onset capture. This avoids treating host scheduling delays as attack time.
    send([(0x60,0xc5),(0x61,4),(0x80,1)])
    stats=read_capture(name+'-onset',True);assert stats['nonzero']>100
    state=board.snapshot();assert state['active']==1 and (state['period_min'],state['period_max'])==(512,512)
    result[name+'_snapshot']=state
    note(69,False);time.sleep(.4)
    assert read_capture(name+'-released')['nonzero']==0
    assert board.snapshot()['active']==0
 fast=result['captures']['fast-onset'];slow=result['captures']['slow-onset']
 assert fast['rms']>3*slow['rms'],'attack differentiation failed'
 assert fast['peak_hz'] is not None and abs(fast['peak_hz']-440)<15,'A4 frequency mismatch'
 result['attack_rms_ratio']=fast['rms']/max(1,slow['rms'])
 # CRC rejection must preserve the published revision and release sandbox.
 revision=link.read_reg(0xde)|(link.read_reg(0xdf)<<8)
 words,_=compile_document(document('bad CRC',0,80));data=payload_for(words);crc=checksum(0,0x5678,data)
 corrupted=bytearray(data);corrupted[17]^=1
 send([(0xe0,0xa5),(0xe1,0),(0xe2,0x78),(0xe3,0x56)]+[(0xe4,b) for b in corrupted]+[(0xe5,crc&255),(0xe6,crc>>8),(0xe7,0x5a)])
 time.sleep(.03);result['crc_rejection']=dict(result=link.read_reg(0xd7),revision=link.read_reg(0xde)|(link.read_reg(0xdf)<<8),sandbox=link.read_reg(0xe9))
 assert result['crc_rejection']['result']==2 and result['crc_rejection']['revision']==revision and result['crc_rejection']['sandbox']&2
 send([(0xe0,0xc3)]);assert link.read_reg(0xe9)==1
 unsupported=document('unsupported',0,80);unsupported['vibrato']['enabled']=True;sent=link._sent
 record=apply_document(link,unsupported);assert record['status']=='FAILED' and not record['writes'] and link._sent==sent
 result['unsupported_rejection']=record
 # Strike decays with the gate still held; note ownership remains until OFF.
 apply('strike',document('strike',2,50,mode='strike'))
 send([(0x60,0xc5),(0x61,4),(0x80,1)]);assert read_capture('strike-onset',True)['nonzero']>100
 time.sleep(.3);assert read_capture('strike-held-silence')['nonzero']==0
 assert board.snapshot()['active']==1;note(69,False);time.sleep(.1)
 assert board.snapshot()['active']==0
 # Two independently configured voices; this is not a physical layering test.
 apply('duet-fast',document('duet-fast',0,80,0));apply('duet-slow',document('duet-slow',200,200,1))
 send([(0x37,0),(0x60,0xc5),(0x61,4),(0x37,1),(0x60,0xc8),(0x61,4)])
 time.sleep(.15);result['duet_snapshot']=board.snapshot()
 assert bin(result['duet_snapshot']['active']).count('1')==2
 assert read_capture('two-voices')['nonzero']>100
 sent=link._sent;busy=apply_document(link,document('busy',0,80));result['busy_rejection']=busy
 assert busy['status']=='FAILED' and not busy['writes'] and link.read_reg(0xe9)==0
 note(69,False);note(72,False);time.sleep(.4)
 assert read_capture('final-silence')['nonzero']==0
 result['after']=board.snapshot();assert result['after']['active']==0 and link.read_reg(0xe9)==1
 result['status']='PASS bounded device configuration/PCM checks; no analog listening verdict'
except Exception as exc:
 result['status']='FAILED';result['error']=str(exc);raise
finally:
 if opened and identified:
    try:
        time.sleep(.03)
        if link.read_reg(0xe9)&2:
            assert link.read_reg(0xd6)==0,'configuration still busy during cleanup';send([(0xe0,0xc3)])
        note(69,False);note(72,False);time.sleep(.4)
        result['cleanup_snapshot']=board.snapshot()
        result['cleanup_pcm']=read_capture('cleanup-silence')
        assert result['cleanup_snapshot']['active']==0 and result['cleanup_pcm']['nonzero']==0
    except Exception as exc:result['cleanup_error']=str(exc);result['status']='FAILED'
 if opened:link.close()
 result['completed_time']=datetime.datetime.now().astimezone().isoformat();save()
 print(result['status'],flush=True)
