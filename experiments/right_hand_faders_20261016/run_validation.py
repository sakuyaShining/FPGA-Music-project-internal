"""Run behavioral, randomized RTL and browser-model parity tests, offline."""
import hashlib, importlib.util, json, random, subprocess, sys
from pathlib import Path
from reference import resolve,Touch
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'evidence';OUT.mkdir(exist_ok=True)
def pack(values,width):return sum(v<<(i*width) for i,v in enumerate(values))
def run(args,log):
    result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
    (OUT/log).write_text(result.stdout+result.stderr,encoding='utf-8')
    if result.returncode:raise RuntimeError((OUT/log).read_text(encoding='utf-8'))
    return result.stdout

def vectors(nf,panel=False):
    step=800//nf;axes=[i*step+step//2 for i in range(nf)];zones=[(i*step,(i+1)*step) for i in range(nf)]
    rng=random.Random(20261016+nf);held=[420 if panel else 479]*nf;rows=[];cases=[]
    for frame in range(620):
        cmd=1 if frame%37==0 else 0
        radius=rng.choice([0,1,10,step//2,1023])
        lo,hi=rng.choice([(0,479),(52,420),(0,1023),(100,100)])
        if panel:lo,hi=52,420
        ids=rng.sample(range(16),rng.randrange(6))
        touches=[Touch(i,rng.randrange(1024),rng.randrange(1024)) for i in ids]
        # Directed shapes recur amid random traffic; test empty/reorder/edge/on-axis.
        shape=frame%17;x=axes[0]
        if shape==0:touches=[]
        elif shape==1:touches=[Touch(4,x-1,144),Touch(2,x+1,335)]
        elif shape==2:touches=[Touch(4,x-3,20),Touch(2,x-1,400)]
        elif shape==3:touches=[Touch(4,x,1023),Touch(2,x-1,100),Touch(1,x+1,0)]
        elif shape==4:touches=[Touch(4,zones[0][1]-1,100)]
        elif shape==5:touches=[Touch(4,x-1,40),Touch(1,x-1,300)]
        rng.shuffle(touches)
        seed=[rng.randrange(1024) for _ in range(nf)]
        if panel:seed=[420]*nf
        if cmd:result=[max(lo,min(hi,v)) for v in seed];sel=[(None,None)]*nf
        else:result,sel=resolve(axes,zones,touches,held,radius,lo,hi)
        fields=[cmd,(1<<len(touches))-1,pack([t.x for t in touches],10),pack([t.y for t in touches],10),pack([t.id for t in touches],4),pack(axes,10),pack([z[0] for z in zones],10),pack([z[1] for z in zones],10),radius,lo,hi,pack(seed,10),pack(result,10),pack([int(l is not None) for l,r in sel],1),pack([int(r is not None) for l,r in sel],1),pack([l or 0 for l,r in sel],4),pack([r or 0 for l,r in sel],4)]
        rows.append(str(fields[0])+' '+' '.join(format(v,'x') for v in fields[1:]))
        cases.append(dict(command=cmd,axes=axes,zones=zones,touches=[vars(t) for t in touches],held=held,radius=radius,lo=lo,hi=hi,seed=seed,expected=result,selected=sel))
        held=result
    suffix='panel' if panel else str(nf)
    path=OUT/('vectors-%s.txt'%suffix);path.write_text('\n'.join(rows)+'\n',encoding='ascii')
    (OUT/('cases-%s.json'%suffix)).write_text(json.dumps(cases),encoding='utf-8')
    return path

def main():
    results={}
    print(run([sys.executable,'-m','unittest','-v','test_reference.py'],'python-tests.log'))
    for nf in (1,8,16):
        path=vectors(nf)
        run(['D:/iverilog/bin/iverilog.exe','-g2012','-Wall','-s','tb_faders','-Ptb_faders.NF=%d'%nf,'-o',str(OUT/('faders-%d.vvp'%nf)),'rtl/rh_fader_bank.v','tb_faders.v'],'compile-%d.log'%nf)
        text=run(['D:/iverilog/bin/vvp.exe',str(OUT/('faders-%d.vvp'%nf)),'+vectors='+str(path)],'rtl-%d.log'%nf)
        assert 'PASS' in text
        print(text.strip());results[str(nf)]=dict(frames=620,log=text.strip(),cycles=nf*6+1,inferred_processing_us_at_27MHz=(nf*6+1)/27)
    vectors(8,panel=True)
    run(['D:/iverilog/bin/iverilog.exe','-g2012','-Wall','-s','tb_panel','-o',str(OUT/'panel.vvp'),'rtl/rh_fader_bank.v','rtl/rh_fader_panel.v','tb_panel.v'],'compile-panel.log')
    text=run(['D:/iverilog/bin/vvp.exe',str(OUT/'panel.vvp')],'rtl-panel.log')
    assert 'PASS' in text;print(text.strip());results['panel']=dict(frames=620,cycles=49,log=text.strip())
    browser=ROOT/'preview/test_model.mjs'
    if browser.exists():
        print(run(['C:/Users/Sakuya/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe',str(browser)],'browser-model.log').strip())
    inputs=['rtl/rh_fader_bank.v','rtl/rh_fader_panel.v','reference.py','test_reference.py','tb_faders.v','tb_panel.v','run_validation.py','prepare_synthesis.py','serve_preview.py','test_ui.mjs']
    inputs += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'preview').glob('*') if p.is_file()]
    result=dict(status='PASS within isolated digital behavior',profiles=results,input_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in inputs},product_engine_changed=False,audio_applied=False,touch_screen_driver_implemented=False,hardware_verified=False)
    (OUT/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
if __name__=='__main__':main()
