"""Restore the already verified stage76 image after user-authorized power cycling.
Only operation2/SRAM; no Flash, TF, configuration edit or audible test command.
"""
from pathlib import Path
import hashlib,json,datetime,subprocess,importlib.util,time
import serial
from serial.tools import list_ports
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent
OLD=P/'experiments/envelope_resources_20261017';image=OLD/'package/config-sram.fs'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((OLD/'package/manifest.json').read_text(encoding='utf-8'))
for rel,h in manifest['files'].items():assert sha(OLD/'package'/rel)==h,rel
assert sha(image)=='8c2d52e59b13b8d343b54a9d602d265154dc6cc9640320df10835f2e1b1c253c'
ports=[p for p in list_ports.comports() if (p.vid,p.pid,p.serial_number)==(0x0403,0x6010,'2025030317B')]
assert len(ports)==1,[(p.device,p.serial_number) for p in list_ports.comports()]
S=N/('restore-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));S.mkdir()
(N/'latest-restore.txt').write_text(str(S),encoding='utf-8')
CLI='D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/Programmer/bin/programmer_cli.exe'
record=dict(status='IN PROGRESS',port=ports[0].device,image=str(image),image_sha256=sha(image),script_sha256=sha(Path(__file__)),flash_read_or_written=False,tf_accessed=False,audio_test_started=False)
def save(): (S/'result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
def command(label,args):
    out=subprocess.run([CLI,*args],cwd=S,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
    log=out.stdout+out.stderr;(S/(label+'.log')).write_text(log,encoding='utf-8')
    assert out.returncode==0,(label,out.returncode,log)
    return log
save()
try:
    assert '2: SRAM Program;' in command('help',['--help'])
    assert 'USB Debugger A/0/' in command('cables',['--scan-cables'])
    scan=command('scan',['--scan'])
    assert 'Family: GW2AR' in scan and '0x0000081B' in scan and '1 device(s) found!' in scan
    args=['--device','GW2AR-18C','--operation_index','2','--chain_size','1','--chain_index','0','--channel','0','--fsFile',str(image)]
    record['program_command']=[CLI,*args];save()
    log=command('sram',args)
    assert 'failed' not in log.lower() and 'error' not in log.lower()
    for marker in ('Operation "SRAM Program" for device#1','100%','Status Code is: 0x00006020','Finished.'):assert marker in log,marker
    time.sleep(1.3)
    spec=importlib.util.spec_from_file_location('board_check',P/'experiments/board_audio_20261017/board_check.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    with serial.Serial(ports[0].device,115200,timeout=.2,write_timeout=1) as com:
        com.reset_input_buffer();board=mod.Board(com)
        values={('%02X'%a):board.read(a) for a in (0xC0,0xC2,0xC3,0xD0,0xD1,0xA4,0xA9)}
        assert values=={'C0':0x72,'C2':0x76,'C3':1,'D0':0x75,'D1':1,'A4':0xD3,'A9':32},values
        record['identity']=values;record['snapshot']=board.snapshot();record['board_status']=board.status()
        assert record['snapshot']['active']==0 and not record['board_status']['fault']
        assert (record['snapshot']['period_min'],record['snapshot']['period_max'])==(512,512)
        samples=board.capture();assert len(samples)==2048 and not any(samples)
        (S/'silence-s24le.bin').write_bytes(bytes(2048*3));record['zero_pcm_samples']=2048
    record['status']='PASS restored stage76 SRAM; identity/sample period/zero PCM verified'
except Exception as exc:
    record['status']='FAIL';record['error']=repr(exc);raise
finally:save()
print(json.dumps(record,indent=2))
