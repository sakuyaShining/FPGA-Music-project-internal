from pathlib import Path
from datetime import datetime, timezone
import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess

from reference import INPUT_FIELDS, OUTPUT_FIELDS, generate, unpack

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mutate(text, fault):
    changes = {
        'fixed-source':('score_valid&&(!live_valid||next_source)','score_valid&&!live_valid'),
        'ignore-token':('state==WAIT_RESPONSE&&response_token==event_token','state==WAIT_RESPONSE'),
        'wrong-payload':('event_note<=select_score?score_note:live_note;','event_note<=live_note;')
    }
    if fault not in changes:
        return text
    before, after = changes[fault]
    if text.count(before)!=1:
        raise ValueError('Mutation anchor changed: '+fault)
    return text.replace(before,after)


def compare(path, expected):
    rows = path.read_text(encoding='utf-8').splitlines() if path.is_file() else []
    if len(rows)!=len(expected):
        return dict(field='count',expected=len(expected),observed=len(rows))
    for cycle,(row,value) in enumerate(zip(rows,expected)):
        words=row.split()
        if len(words)!=2 or words[0]!=str(cycle):
            return dict(field='format',cycle=cycle)
        try:
            actual=int(words[1],16)
        except ValueError:
            return dict(field='unknown',cycle=cycle)
        if actual!=value:
            before,after=unpack(OUTPUT_FIELDS,value),unpack(OUTPUT_FIELDS,actual)
            field=next(name for name,width in OUTPUT_FIELDS if before[name]!=after[name])
            return dict(field=field,cycle=cycle,expected=before[field],observed=after[field])
    return None


def run(command, path, directory):
    try:
        process=subprocess.run(command,cwd=directory,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
        raw,code=process.stdout,process.returncode
    except subprocess.TimeoutExpired as error:
        raw,code=(error.stdout or b'')+b'\nTIMEOUT\n',124
    path.write_bytes(raw)
    return dict(command=command,returncode=code,log_sha256=digest(path),text=raw.decode('utf-8',errors='replace'))


def main():
    parser=argparse.ArgumentParser(description='Independent two-source request/response router cycle oracle')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--fault-checks',action='store_true')
    arguments=parser.parse_args()
    output=arguments.output.resolve()
    if output.exists() or output==PROJECT or PROJECT in output.parents:
        raise ValueError('Use a new output outside repository')
    compiler=Path(os.environ.get('FPGA_IVERILOG') or shutil.which('iverilog') or 'D:/iverilog/bin/iverilog.exe').resolve()
    simulator=Path(os.environ.get('FPGA_VVP') or shutil.which('vvp') or 'D:/iverilog/bin/vvp.exe').resolve()
    sources=[ROOT/name for name in ('rtl/note_event_router.v','tb/tb_note_event_router.v','reference.py','verify.py')]
    identities={path.relative_to(PROJECT).as_posix():digest(path) for path in sources}
    inputs,expected,coverage=generate()
    assert sum(width for name,width in INPUT_FIELDS)==236
    assert sum(width for name,width in OUTPUT_FIELDS)==168
    output.mkdir(parents=True)
    (output/'INPUTS.json').write_text(json.dumps(identities,indent=2)+'\n',encoding='utf-8')
    reports=[]
    for case in ['candidate']+(['fixed-source','ignore-token','wrong-payload'] if arguments.fault_checks else []):
        directory=output/case;directory.mkdir()
        (directory/'inputs.hex').write_text(''.join('%059x\n'%value for value in inputs),encoding='utf-8')
        (directory/'expected.hex').write_text(''.join('%042x\n'%value for value in expected),encoding='utf-8')
        rtl=directory/'note_event_router.v'
        rtl.write_bytes(mutate((ROOT/'rtl/note_event_router.v').read_text(encoding='utf-8'),case).encode())
        binary=directory/'router.vvp'
        compilation=run([str(compiler),'-g2012','-s','tb_note_event_router','-o',str(binary),str(rtl),str(ROOT/'tb/tb_note_event_router.v')],directory/'compile.log',directory)
        report=dict(case=case,compilation=compilation,passed=False,generated_source_sha256=digest(rtl),inputs_sha256=digest(directory/'inputs.hex'),expected_sha256=digest(directory/'expected.hex'))
        if compilation['returncode']==0:
            trace=directory/'trace.tsv'
            simulation=run([str(simulator),str(binary),'+inputs='+(directory/'inputs.hex').as_posix(),'+trace='+trace.as_posix()],directory/'run.log',directory)
            difference=compare(trace,expected)
            designated={'fixed-source':['live_ready','score_ready','event_token'],'ignore-token':['response_ready','live_response_valid','score_response_valid'],'wrong-payload':['event_note']}
            valid=simulation['returncode']==0 and 'PASS event_router cycles=24000' in simulation['text']
            report.update(simulation=simulation,first_difference=difference,
                passed=valid and (difference is None if case=='candidate' else difference is not None and difference['field'] in designated[case]))
            if trace.is_file():
                report['trace_sha256']=digest(trace)
                (directory/'trace.tsv.gz').write_bytes(gzip.compress(trace.read_bytes(),mtime=0))
        reports.append(report)
        print(case+': '+('PASS' if report['passed'] else 'FAIL'),flush=True)
    changed=[name for name,value in identities.items() if digest(PROJECT/name)!=value]
    result=dict(schema=1,tested_at=datetime.now(timezone.utc).isoformat(),inputs=identities,source_changes=changed,
        tools={str(path):digest(path) for path in (compiler,simulator)},coverage=coverage,results=reports,
        status='PASS' if all(report['passed'] for report in reports) and not changed else 'FAIL',
        scope='Two tagged ready/valid logical sources; transport cycle oracle, not physical adapters or PCM acceptance',product_acceptance=False,hardware_accessed=False)
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],coverage=coverage)))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
