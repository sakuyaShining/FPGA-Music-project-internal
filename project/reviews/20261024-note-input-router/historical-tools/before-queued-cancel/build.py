from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slacks(text):
    result={}
    for kind in ('Setup','Hold','Recovery','Removal'):
        section=re.search(r'name="'+kind+r'_Slack_Table"(.*?)(?=<a name=|\Z)',text,re.S)
        if not section:
            result[kind]=None
            continue
        values=[]
        for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',section.group(1),re.S|re.I):
            cells=[html.unescape(re.sub('<[^>]*>','',cell)).strip() for cell in re.findall(r'<td\b[^>]*>(.*?)</td>',row,re.S|re.I)]
            if len(cells)>=9 and cells[0].isdigit():
                values.append(float(cells[1]))
        result[kind]=min(values) if values else None
    return result


def main():
    parser=argparse.ArgumentParser(description='Unit-router timing shell or integrated audio synthesis; never program hardware')
    parser.add_argument('--mode',choices=('timing','integrated'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    arguments=parser.parse_args()
    output=arguments.output.resolve()
    if output.exists() or output==PROJECT or PROJECT in output.parents:
        raise ValueError('Use a new output outside repository')
    executable=Path(os.environ.get('FPGA_GOWIN_GW_SH','D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'))
    if not executable.is_file():
        raise ValueError('Missing Gowin shell')
    sources=[ROOT/'rtl/note_event_router.v']
    if arguments.mode=='timing':
        top='note_router_timing_probe'
        sources += [ROOT/'rtl/note_router_timing_probe.v',ROOT/'constraints/router_probe.sdc',ROOT/'constraints/router_probe.cst']
    else:
        top='note_duet_probe'
        sources += [ROOT/'rtl/note_duet_probe.v']+sorted((ROOT.parent/'audio/renderer/rtl').glob('*.v'))+sorted((ROOT.parent/'audio/rtl').glob('*.v'))
        sources += [ROOT.parent/'rtl/note_resource_mgr.v']
        sources += [PROJECT/'fpga/current/engine/src'/name for name in ('osc_env.v','pitch_mod.v','pitch_native_store.v','instrument_table.v','sine256.hex','note_inc.hex','preset_part.hex','tilt_wtab.hex','vel_wtab.hex')]
    inputs={path.relative_to(PROJECT).as_posix():digest(path) for path in sources+[ROOT/'build.py']}
    output.mkdir(parents=True)
    entries=[]
    for source in sources:
        shutil.copyfile(source,output/source.name)
        kind={'.v':'file.verilog','.sdc':'file.sdc','.cst':'file.cst'}.get(source.suffix)
        if kind:
            entries.append('<File path="'+source.name+'" type="'+kind+'" enable="1"/>')
    project=output/'router.gprj'
    project.write_text('<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE gowin-fpga-project><Project><Template>FPGA</Template><Version>5</Version><Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device><FileList>'+''.join(entries)+'</FileList></Project>',encoding='utf-8')
    script=output/'build.tcl'
    script.write_text('open_project "'+project.as_posix()+'"\nset_option -top_module '+top+'\n'+('run all' if arguments.mode=='timing' else 'run syn')+'\nexit\n',encoding='utf-8')
    started=time.monotonic()
    with (output/'console.log').open('wb') as console:
        process=subprocess.Popen([str(executable),str(script)],cwd=output,stdout=console,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        print('GOWIN PID '+str(process.pid),flush=True)
        try:
            code=process.wait(timeout=900)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            process.wait();code=124
    console=(output/'console.log').read_text(encoding='utf-8',errors='replace')
    changed=[name for name,expected in inputs.items() if digest(PROJECT/name)!=expected]
    success=code==0 and not changed and not re.search(r'\bERROR\s*\(',console)
    timing_file=output/'impl/pnr/router_tr_content.html'
    timing=slacks(timing_file.read_text(encoding='utf-8')) if timing_file.is_file() else None
    if arguments.mode=='timing':
        success=success and 'Bitstream generation completed' in console and timing is not None
        status='PASS_UNIT_ROUTER_TIMING_ONLY' if success and all(value is not None and value>=0 for value in timing.values()) else 'FAIL_OR_INCOMPLETE_TIMING'
    else:
        success=success and (output/'impl/gwsynthesis/router_syn_resource.html').is_file()
        status='PASS_INTEGRATED_SYNTHESIS_ONLY' if success else 'FAIL'
    reports={path.relative_to(output).as_posix():digest(path) for path in sorted((output/'impl').rglob('*')) if path.is_file() and path.suffix in ('.html','.txt','.fs')}
    result=dict(schema=1,tested_at=datetime.now(timezone.utc).isoformat(),mode=arguments.mode,inputs=inputs,source_changes=changed,
        tool=dict(path=str(executable),sha256=digest(executable)),returncode=code,elapsed_seconds=round(time.monotonic()-started,2),
        console_sha256=digest(output/'console.log'),warnings=re.findall(r'WARNING[^\r\n]*',console),reports=reports,slack_ns=timing,status=status,
        scope='Register-driven router-only scan shell with explicit27MHz I/O envelope, auto-assigned non-clock pins; NOT product pinout/bitstream' if arguments.mode=='timing' else 'Dual tagged logical input router + real renderer/32group/512partial TDM; not complete device',
        full_product_pnr=False,full_product_sta=False,product_acceptance=False,hardware_accessed=False,programming_allowed=False)
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=status,slack_ns=timing,output=str(output))))
    return 0 if status.startswith('PASS') else 1


if __name__=='__main__':
    raise SystemExit(main())
