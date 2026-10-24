from common import *
import shutil,filecmp,gzip
P=R.parents[1];U=R/'handoff_support/resource_safety_20261016'
gold=json.loads((U/'evidence/music-equivalence-all.json').read_text(encoding='utf-8'))
for name in ('sustain.hex','strike.hex'):shutil.copyfile(U/name,R/name)
results={};inputs=sources()+[R/'tb/vendor_ram16sdp4.v']
for name,top,tb in [('compat','tb_music','tb_compat_music.v'),('layers','tb_layers','tb_layers.v'),('sensor','tb_sensor_layers','tb_sensor_layers.v')]:
    # Simulator cwd is engine/src, two levels below these test data files.
    (R/tb).write_text((U/tb).read_text(encoding='utf-8').replace('"../','"../../'),encoding='utf-8')
    # 参考轨迹在 handoff_support 里是 gzip 存的（compat-all.tsv.gz 等），
    # 本脚本原来直接读 .tsv —— 那个文件早就不存在了，于是永远 FileNotFoundError，
    # 而报错是"文件找不到"，看起来像环境问题而不是测试坏了。
    # 解到 evidence/（已 gitignore）再用；哈希仍按【解压后】的内容核对。
    reference=U/'evidence'/(name+'-all.tsv')
    if not reference.exists():
        gz=U/'evidence'/(name+'-all.tsv.gz')
        assert gz.exists(),('missing reference trace',str(gz))
        # 解到 evidence/（已 gitignore）而不是 next to the .gz：
        #   解到原地会留下一个未跟踪、又没被忽略的 .tsv，污染仓库
        #   （manifest 会把它当成"未登记的工程文件"）。
        reference=E/(name+'-all.tsv')
        reference.write_bytes(gzip.decompress(gz.read_bytes()))
    assert sha(reference)==gold['traces'][name+'-all']['sha256']
    files=[p for p in sources() if p.name not in ('joint_timing_top.v','probe_scan_store.v')]+[R/tb,R/'tb/vendor_ram16sdp4.v']
    run([IV,'-g2012','-DTIMING_RTL_SIM','-I',str(R/'engine/src'),'-s',top,'-o',str(E/(name+'-compat.vvp')),*map(str,files)],'compile-engine-'+name)
    trace=E/(name+'-compat.tsv')
    log=run([VVP,str(E/(name+'-compat.vvp')),'+trace='+trace.as_posix()],'run-engine-'+name,R/'engine/src')
    assert filecmp.cmp(reference,trace,shallow=False),('engine behavior changed with default boot scrub off',name)
    results[name]=dict(log=log,trace_sha256=sha(trace),reference_sha256=sha(reference));inputs.append(R/tb)
(E/'engine-compatibility.json').write_text(json.dumps(dict(status='PASS original 71 traces identical with default board options off',results=results,inputs={p.relative_to(R).as_posix():sha(p) for p in inputs+list(R.glob('*.hex'))+list((R/'engine/src').glob('*.hex'))+list((R/'engine/src').glob('*.vh'))+[Path(__file__).resolve(),R/'common.py']}),indent=2),encoding='utf-8')
