"""Call the documented EasyEDA CLI with argument arrays and retain evidence."""
import argparse
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
EXE=Path('C:/Users/Sakuya/AppData/Local/Programs/LCEDA-Pro/lceda-pro.exe')


def call(name, args, timeout=75):
    result=subprocess.run([str(EXE),*args],capture_output=True,timeout=timeout)
    target=ROOT/'evidence'
    target.mkdir(exist_ok=True)
    (target/f'{name}.request.json').write_text(json.dumps({'args':args,'timeout':timeout},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (target/f'{name}.stdout.raw').write_bytes(result.stdout)
    (target/f'{name}.stderr.raw').write_bytes(result.stderr)
    for encoding in ('utf-8','gb18030'):
        try: output=result.stdout.decode(encoding);break
        except UnicodeDecodeError: continue
    else: raise RuntimeError('Unknown CLI stdout encoding')
    envelope=json.loads(output.strip())
    (target/f'{name}.json').write_text(json.dumps(envelope,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if result.returncode!=0 or not envelope.get('ok'):
        raise RuntimeError(json.dumps(envelope,ensure_ascii=True))
    return envelope.get('value')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('request',type=Path)
    args=parser.parse_args()
    request=json.loads(args.request.read_text(encoding='utf-8'))
    result=call(request['name'],request['args'],request.get('timeout',75))
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__': main()
