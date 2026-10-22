"""Compatibility gate using the complete current manifest, not historical prose."""
import argparse
import json
from pathlib import Path
from project_version import ROOT, check

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--simdir')
    parser.add_argument('--doc',type=Path,help='Explicit JSON manifest; historical Markdown is rejected')
    args=parser.parse_args()
    try:
        manifest=args.doc or ROOT/json.loads((ROOT/'project/state.json').read_text(encoding='utf-8'))['source_manifest']
        record,errors=check(ROOT,manifest)
    except (OSError,ValueError,KeyError) as e:
        print('FAIL',e);return 1
    for e in errors:print('FAIL',e)
    print('全部源码、数据表、约束、GUI与构建入口一致' if not errors else '存在源码不一致')
    print('RESULT spec_sha='+('FAIL' if errors else 'PASS'))
    return int(bool(errors))

if __name__=='__main__':raise SystemExit(main())
