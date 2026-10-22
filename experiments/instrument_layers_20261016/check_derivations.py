from pathlib import Path
import hashlib,subprocess,sys,json
R=Path(__file__).resolve().parent;P=R.parents[1]
paths=['engine/finger_pitch.v','optimization/note_map_owned.v','candidate/tdm_top_owned.v','candidate/compat_music_probe.v','rtl/left_layer_music_probe.v','rtl/instrument_layer_probe.v','rtl/layer_dispatch.v','tb_sensor_layers.v','upstream.json','sustain.json','strike.json','sustain.hex','strike.hex']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={k:sha(R/k) for k in paths}
generators=[P/'notes/instrument-layers-20261016/prepare.py']+[R/k for k in ['prepare_wrappers.py','prepare_sensor_test.py','prepare_memory_opt.py','check_slot_format.py']]
for script in generators:subprocess.run([sys.executable,str(script)],cwd=P,check=True)
assert all(sha(R/k)==v for k,v in before.items()),'generated source differs from tested source'
(R/'evidence/derivations.json').write_text(json.dumps(dict(status='PASS deterministic derivations',files=before,generators={p.relative_to(P).as_posix():sha(p) for p in generators}),indent=2),encoding='utf-8')
print('PASS deterministic generated source, table and test inputs')
