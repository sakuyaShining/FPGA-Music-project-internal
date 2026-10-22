"""Verify the complete recorded source/artifact identity, then load 09 to SRAM."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(record_path):
    record_path=Path(record_path).resolve()
    record=json.loads(record_path.read_text(encoding='utf-8'))
    if record.get('schema')!=1 or 'TangNano20K GW2AR-18C' not in record.get('configuration',''):
        raise ValueError('Expected identified Tang Nano 20K build')
    manifest_path=Path(record['source_manifest'])
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    files=manifest['files']
    tree=hashlib.sha256(json.dumps(files,sort_keys=True).encode('utf-8')).hexdigest()
    if not files or tree!=manifest['tree_sha256'] or tree!=record['source_tree_sha256']:
        raise ValueError('Invalid source manifest digest')
    source=manifest_path.parent/'source'
    for name,expected in files.items():
        if digest(source/name)!=expected:raise ValueError('Source drift: '+name)
    for name,item in record['artifacts'].items():
        if digest(item['path'])!=item['sha256']:raise ValueError('Artifact mismatch: '+name)
    if record['timing']['setup_violations'] or record['timing']['hold_violations']:
        raise ValueError('Timing violations')
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record',type=Path,required=True)
    parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--programmer',default='D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/Programmer/bin/programmer_cli.exe')
    args=parser.parse_args()
    try:
        record=verify(args.record)
        fs=record['artifacts']['tdm_live_test.fs']
        print('Identity PASS; SHA256 '+fs['sha256'],flush=True)
        if args.check_only:return 0
        print('Temporary SRAM download; release the GUI serial connection first.',flush=True)
        return subprocess.call([args.programmer,'--device','GW2AR-18C','--operation_index','2',
            '--frequency','2.5MHz','--fsFile',fs['path']],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except (OSError,ValueError,KeyError) as exc:
        print('Identity check failed; download refused: '+str(exc))
        return 1


if __name__=='__main__':raise SystemExit(main())
