"""Capability-gated volatile upload. No programming/Flash operations.

Confirmation requires sequence, slot, byte count, CRC and new device revision.
No automatic retry after ambiguous acknowledgement; preserve unknown outcomes.
"""
from pathlib import Path
from types import SimpleNamespace
import binascii,json,time,secrets
from config_adapter import compile_document
from instrument_config import validate_config
CAPABILITY=(0x75,1,4,16,11,7)
def payload_for(words):return b''.join(w.to_bytes(11,'little') for w in words)
def checksum(slot,sequence,payload):return binascii.crc_hqx(bytes([1,slot,sequence&255,sequence>>8])+payload,0xffff)
def apply_document(link,document,slot=None,select=True,sequence=None,timeout=3.0,preset_only=False):
    record=dict(status='FAILED',source=getattr(link,'kind','transport'),requested=document,preset_only=preset_only,writes=[],readback={},sent_complete=False,audio_verified=False,persisted=False,scope='spectrum and articulation only',commit_state='not_started')
    lock=getattr(link,'_transaction',None);acquired=False;entered=False;confirmed=False
    def read(addr):
        value=link.read_reg(addr)
        if type(value) is not int or not 0<=value<=255:raise RuntimeError('register timeout/invalid echo at %02x'%addr)
        record['readback']['%02x'%addr]=value;return value
    def word(addr):return read(addr)|(read(addr+1)<<8)
    def send(pairs):
        items=[(a,d,'volatile instrument upload') for a,d in pairs];record['writes'].extend(items)
        n=link.send(SimpleNamespace(items=items))
        if n!=2*len(items):raise RuntimeError('short configuration write')
    try:
        document=validate_config(document)
        if preset_only:
            rom=Path(__file__).resolve().parents[1]/'src/preset_part.hex'
            words=[int(w,16) for w in rom.read_text(encoding='ascii').split()][document['preset']*16:document['preset']*16+16]
            quantization={'status':'original preset words; global envelope fallback','format':'slot-v1/88-bit'}
            record['scope']='original preset only; draft spectrum and articulation omitted explicitly'
        else:
            words,quantization=compile_document(document)
        record['quantization']=quantization
        if slot is None:slot=document['preset']
        if type(slot) is not int or not 0<=slot<4:raise ValueError('invalid target slot')
        if sequence is None:sequence=secrets.randbits(16)
        if type(sequence) is not int or not 0<=sequence<=65535:raise ValueError('invalid transaction ID')
        data=payload_for(words);crc=checksum(slot,sequence,data)
        record.update(slot=slot,sequence=sequence,crc16=crc,payload_bytes=len(data))
        if lock is not None:
            acquired=lock.acquire(blocking=False)
            if not acquired:raise RuntimeError('device transaction is busy')
        actual=tuple(read(0xd0+i) for i in range(6))
        if actual!=CAPABILITY:raise RuntimeError('unsupported configuration device; no upload sent')
        if read(0xd6)!=0 or read(0xe9)!=1:raise RuntimeError('device not idle or previous upload still locked')
        revision=word(0xde);record['revision_before']=revision
        entered=True;record['commit_state']='unknown'
        send([(0xe0,0xa5),(0xe1,slot),(0xe2,sequence&255),(0xe3,sequence>>8)])
        if read(0xd6)!=1 or word(0xd8)!=sequence or read(0xda)!=slot or read(0xdb)!=0:raise RuntimeError('upload header not accepted')
        send([(0xe4,b) for b in data]+[(0xe5,crc&255),(0xe6,crc>>8),(0xe7,0x5a)])
        record['sent_complete']=True;deadline=time.monotonic()+timeout
        while True:
            state=read(0xd6);result=read(0xd7)
            if state==0 or state==3:
                seq=word(0xd8);target=read(0xda);count=read(0xdb);actual_crc=word(0xdc);new_revision=word(0xde)
                ack=dict(state=state,result=result,sequence=seq,slot=target,count=count,crc16=actual_crc,revision=new_revision);record['ack']=ack
                if seq!=sequence or target!=slot:raise RuntimeError('stale or mismatched acknowledgement')
                if result!=1:
                    if new_revision==revision:record['commit_state']='rejected'
                    raise RuntimeError('device rejected configuration (code %d)'%result)
                if count!=176 or actual_crc!=crc or new_revision!=((revision+1)&65535):raise RuntimeError('incomplete or mismatched confirmation')
                record['commit_state']='confirmed';confirmed=True;break
            if time.monotonic()>deadline:raise RuntimeError('upload acknowledgement timeout; commit outcome unknown')
            time.sleep(.02)
    except Exception as exc:record['error']=str(exc)
    finally:
        if entered:
            try:
                deadline=time.monotonic()+.5
                while read(0xd6)!=0:
                    if time.monotonic()>deadline:raise RuntimeError('upload sandbox remains active')
                    time.sleep(.03)
                send([(0xe0,0xc3)])
                if read(0xe9)&2:raise RuntimeError('upload sandbox release not confirmed')
            except Exception as exc:record['cleanup_error']=str(exc);confirmed=False
        if confirmed and select:
            try:
                ctrl=(read(0x00)|8)&~2
                send([(0x37,slot),(0x40,1),(0x00,ctrl)])
                if read(0x37)!=slot or read(0x40)!=1 or read(0x00)!=ctrl:raise RuntimeError('performance selection not confirmed')
                record['readback'].update(CTRL=ctrl,PRESET=slot,FX_CTRL=1)
                record['selection_confirmed']=True
            except Exception as exc:record['selection_error']=str(exc);confirmed=False
        if confirmed:record['status']='VOLATILE_CONFIG_CONFIRMED'
        if acquired:lock.release()
    return record
