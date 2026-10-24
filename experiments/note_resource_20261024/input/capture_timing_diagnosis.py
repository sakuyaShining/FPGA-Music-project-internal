from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import zipfile

from diagnose_timing import ROOT, PROJECT, digest


CASES = (
    'minimal-full', 'minimal-clock', 'router-clock', 'router-uncertainty', 'router-io',
    'router-full', 'router-input', 'router-output', 'input-max', 'input-min',
    'input-controls', 'input-data', 'input-data-min', 'registered-full',
    'hold-off', 'explicit-bits', 'alternate-full',
)


def main():
    parser = argparse.ArgumentParser(description='Preserve diagnostic successes, crashes and inconclusive cases without product qualification')
    parser.add_argument('--runs', type=Path, required=True)
    parser.add_argument('--shell', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if output.exists() or PROJECT/'project/reviews' not in output.parents:
        raise ValueError('Use a new project/reviews directory')
    roots = [('router-crash-'+case+'-20261024-01', arguments.runs/('router-crash-'+case+'-20261024-01')) for case in CASES]
    roots.append(('shell-equivalence', arguments.shell.resolve()))
    for label, directory in roots:
        if not directory.is_dir():
            raise ValueError('Missing evidence case: '+label)
    output.mkdir(parents=True)
    archive = output/'diagnostic-evidence.zip'
    members = {}
    summaries = []
    allowed_suffixes = {'.py', '.v', '.sdc', '.cst', '.gprj', '.tcl', '.json', '.log', '.txt', '.do', '.cfg'}
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for label, directory in roots:
            result_path = directory/'results.json'
            aborted_path = directory/'aborted.json'
            result = json.loads((result_path if result_path.is_file() else aborted_path).read_text(encoding='utf-8'))
            if result.get('source_changes') or result.get('export_changes') or result.get('tool_changes'):
                raise ValueError('Changed evidence input: '+label)
            summaries.append(dict(case=label, directory=str(directory), status=result['status'],
                returncode=result.get('returncode'), slack_ns=result.get('slack_ns'),
                logic=result.get('logic'), constraints=result.get('constraints'),
                input_ports=result.get('input_ports', 'all'), hold_correction=result.get('hold_correction', 'on'),
                strategy=result.get('strategy', 'default')))
            for path in sorted(directory.rglob('*')):
                if not path.is_file() or 'temporary' in path.relative_to(directory).parts:
                    continue
                if path.suffix not in allowed_suffixes and path.name != 'router_tr_content.html':
                    continue
                name = label+'/'+path.relative_to(directory).as_posix()
                members[name] = digest(path)
                entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                bundle.writestr(entry, path.read_bytes())
    current = [ROOT/name for name in ('diagnose_timing.py', 'verify_timing_shell.py', 'capture_timing_diagnosis.py',
               'tests/test_timing_diagnosis.py', 'tb/tb_router_shell_pipeline.v',
               'rtl/note_event_router.v', 'rtl/note_router_timing_probe.v',
               'constraints/router_probe.sdc', 'constraints/router_probe.cst')]
    summary = dict(schema=1, captured_at=datetime.now(timezone.utc).isoformat(),
        status='TRIGGER_LOCALIZED_NOT_FIXED', source_base_commit='4036d84a94c61c09aabc154b44d78d551edb29f7',
        inputs={path.relative_to(PROJECT).as_posix(): digest(path) for path in current},
        archive=dict(path=archive.relative_to(PROJECT).as_posix(), sha256=digest(archive),
                     members=members, exclusions='No executable binaries, vendor libraries, vvp images, bitstreams, temporary directories or full vendor netlists; their recorded hashes remain in case results'),
        cases=summaries,
        finding='Original-router data-input minimum-delay coverage triggers gowin.dll access violation; maximum-only, controls-only and output-only cases complete. Disabling automatic hold correction completes full-constraint routing but reports hold -1.402ns, so it is not a timing solution.',
        rejected_alternatives=['Registered-all-input shell: equivalence passes but full PnR still crashes',
            'Explicit input-bit spelling: full PnR still crashes', 'Alternate place/route strategy: full PnR still crashes'],
        inference='Automatic hold repair interaction is localized by controlled comparisons; internal vendor defect mechanism is not proven.',
        product_acceptance=False, full_product_pnr=False, full_product_sta=False,
        hardware_accessed=False, programming_allowed=False)
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status=summary['status'], cases=len(summaries), members=len(members), archive_bytes=archive.stat().st_size)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
