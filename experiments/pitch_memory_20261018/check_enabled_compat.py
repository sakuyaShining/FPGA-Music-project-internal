from common import *
import filecmp
U=R.parents[1]/'experiments/resource_safety_20261016';results={};inputs=sources()
for name,top,original,override in [('compat','tb_music','tb_compat_music.v','dut.core.INSTRUMENT_ENV'),('layers','tb_layers','tb_layers.v','dut.INSTRUMENT_ENV')]:
    original_path=R/original;text=original_path.read_text(encoding='utf-8')
    if name=='compat':
        # The legacy test concatenates internal state fields. Compare its original
        # 31-bit metadata separately from the new 40 zero extension bits.
        text=text.replace('dut.core.u_tdm.epar1}', 'dut.core.u_tdm.epar1[30:0]}')
        text=text.replace('if(cycles>2000)begin','if(cycles>2000)begin\n            if(dut.core.u_tdm.epar1[70:31]!==40\'d0)$fatal(1,"legacy profile acquired custom metadata");')
    text=text.replace('endmodule','defparam '+override+'=1;\ninitial #1 if('+override+'!=1)$fatal(1,"envelope option was not enabled");\nendmodule')
    tb=R/('tb_enabled_'+name+'.v');tb.write_text(text,encoding='utf-8')
    files=sources()+[tb];run([IV,'-g2012','-I',str(R/'engine/src'),'-s',top,'-o',str(E/('enabled-'+name+'.vvp')),*map(str,files)],'compile-enabled-'+name)
    trace=E/('enabled-'+name+'.tsv');log=run([VVP,str(E/('enabled-'+name+'.vvp')),'+trace='+trace.as_posix()],'run-enabled-'+name,R/'engine/src')
    reference=U/'evidence'/(name+'-all.tsv');assert filecmp.cmp(trace,reference,shallow=False),(name,'enabled legacy envelope fallback changed')
    results[name]=dict(trace_sha256=sha(trace),reference_sha256=sha(reference),log=log);inputs.append(tb)
(E/'enabled-compatibility.json').write_text(json.dumps(dict(status='PASS option enabled and legacy profiles unchanged',results=results,inputs={p.relative_to(R).as_posix():sha(p) for p in inputs+list((R/'engine/src').glob('*.hex'))+list(R.glob('*.hex'))+[Path(__file__).resolve(),R/'common.py']}),indent=2),encoding='utf-8')
