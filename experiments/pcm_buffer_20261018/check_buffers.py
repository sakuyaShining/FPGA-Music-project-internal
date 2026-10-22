from common import *
files=[R/'rtl/pcm_sync_fifo.v',R/'rtl/pcm_storage_buffers.v',R/'tb_buffers.v']
before={p.relative_to(R).as_posix():sha(p) for p in files+[Path(__file__).resolve(),R/'common.py']}
run([IV,'-g2012','-s','tb_buffers','-o',str(E/'buffers.vvp'),*map(str,files)],'compile-buffers')
log=run([VVP,str(E/'buffers.vvp')],'run-buffers')
assert all(sha(R/p)==h for p,h in before.items())
(E/'buffers.json').write_text(json.dumps(dict(status='PASS bounded storage stream simulation; no physical backend',log=log,inputs=before),indent=2))
print(log)
