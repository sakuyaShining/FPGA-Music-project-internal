from common import *
import sys
P=R.parents[1];N=P/'notes/resource-safety-20261016'
paths=['selected/finger_pitch.v','selected/note_map_owned.v','selected/left_contact_bridge.v','reference/finger_pitch.v','reference/note_map_owned.v','reference/left_contact_bridge.v','tb_compat_music.v','tb_layers.v','tb_sensor_layers.v','tb_bridge_equiv.v','upstream.json']
before={name:sha(R/name) for name in paths}
generators=[N/name for name in ('prepare.py','prepare_candidates.py','prepare_bridge.py','prepare_music_tests.py','prepare_bridge_test.py')]
for script in generators:subprocess.run([sys.executable,str(script)],cwd=P,check=True)
assert all(sha(R/name)==digest for name,digest in before.items()),'generated inputs drifted'
record('derivations.json',dict(status='PASS deterministic source and test derivations',files=before,generators={p.relative_to(P).as_posix():sha(p) for p in generators}),[Path(__file__).resolve(),R/'common.py'])
print('PASS derivations reproduce tested sources and test inputs byte for byte')
