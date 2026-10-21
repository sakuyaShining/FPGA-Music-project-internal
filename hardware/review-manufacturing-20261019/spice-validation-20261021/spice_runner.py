"""Local ngspice process runner with explicit inputs, outputs and provenance."""
import hashlib,json,os,re,subprocess
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent
ENGINE=Path('D:/FPGA-Project/codex-tools/ngspice-condaforge-41/Library/bin/ngspice_con.exe')
VENDOR=next((ROOT/'vendor-TI-TPS2553').rglob('*.lib'))
COMPAT=ROOT/'tps2553_ngspice41_compat.lib'
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def run_case(name,circuit,stop=None,output='waveform.txt',timeout=90):
    assert re.fullmatch(r'[a-z0-9][a-z0-9_-]*',name)
    folder=ROOT/'cases'/name;folder.mkdir(parents=True,exist_ok=True)
    (folder/'.spiceinit').write_text('set ngbehavior=ps\n',encoding='ascii')
    net=folder/'circuit.cir';net.write_text(circuit,encoding='ascii')
    data=folder/output;data.unlink(missing_ok=True)
    cmd=[str(ENGINE),'-b','-o','run.log',net.name]
    env=dict(os.environ,SPICE_SCRIPTS=str(ENGINE.parent.parent/'share/ngspice/scripts'))
    try:
        result=subprocess.run(cmd,cwd=folder,env=env,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:
        (folder/'process.json').write_text(json.dumps({'command':cmd,'returncode':None,'accepted':False,
            'error':'TimeoutExpired','timeout_s':timeout,'circuit_sha256':digest(net),'engine_sha256':digest(ENGINE)},indent=2),encoding='utf-8')
        raise
    status={'command':cmd,'returncode':result.returncode,'circuit_sha256':digest(net),'engine_sha256':digest(ENGINE),
            'stdout':result.stdout.decode(errors='replace'),'stderr':result.stderr.decode(errors='replace')}
    (folder/'process.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    assert result.returncode==0 and data.is_file(),(name,status,(folder/'run.log').read_text(errors='replace')[-1500:])
    values=np.atleast_2d(np.loadtxt(data,skiprows=1))
    assert np.isfinite(values).all(),name+' nonfinite values'
    if stop is not None:assert abs(values[-1,0]-stop)<max(1e-12,stop*1e-6),name+' incomplete transient'
    return values

def transient_control(stop,step,signals):
    return f'.save {signals}\n.control\nset wr_singlescale\nset wr_vecnames\ntran {step:.12g} {stop:.12g}\nwrdata waveform.txt {signals}\nquit\n.endc\n.end\n'
