from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[2]/'experiments/board_audio_20261017'
D=R/'build_ready';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert 'Bitstream generation completed' not in (D/'console.txt').read_text(encoding='utf-8',errors='replace')
record=dict(status='FAILED routing timeout; excluded from release',top='board_audio_top',returncode=124,timeout_seconds=600,termination='verified own gw_sh PID60936 command line then stopped its process tree; unrelated process preserved',inputs=json.loads((D/'inputs.json').read_text(encoding='utf-8')),project_sha256=sha(D/'board_audio.gprj'),tcl_sha256=sha(D/'build.tcl'),hardware_programmed=False)
(D/'run.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print('recorded non-release strategy timeout')
