"""Move complete connected groups away from the title block, rotate ports outward."""
import json
from phase import ROOT,invoke

def run(key):
    pages=json.loads((ROOT/'pages.json').read_text())
    pins=json.loads((ROOT/f'evidence/wired-{key}.json').read_text(encoding='utf-8'))['value']['pins']
    deltas={}
    if key=='core':deltas={'SW2':[-40,0],'SW3':[0,0],'SW4':[40,0],'SW5':[80,0],'SW6':[120,0]}
    if key=='rc':
        deltas={**{f'R{21+i}':[0,(i//3)*15] for i in range(12)},
                **{f'C{16+i}':[0,55] for i in range(6)},'R1':[100,600],'R2':[100,600]}
    if key=='support':deltas={'J1':[230,430],'R51':[0,30],'R52':[0,30]}
    code="""await eda.dmt_EditorControl.openDocument(__CLI__.args.page);const all=await eda.sch_PrimitiveComponent.getAll();const moved=[];
for(const [ref,d] of Object.entries(__CLI__.args.deltas)){const c=all.find(c=>c.getState_Designator()===ref);if(!c)throw new Error('Missing '+ref);const e=c.toAsync();e.setState_X(c.getState_X()+d[0]);e.setState_Y(c.getState_Y()+d[1]);await e.done();moved.push(ref);}
for(const p of __CLI__.args.pins){if(!p.wire)continue;const d=__CLI__.args.deltas[p.ref]||[0,0];const x=p.x+d[0],y=p.y+d[1],r=p.r;const dx=r===0?30:r===180?-30:0,dy=r===90?30:r===270?-30:0;const w=await eda.sch_PrimitiveWire.modify(p.wire,{line:[x,y,x+dx,y+dy]});if(!w)throw new Error('Wire move');const c=await eda.sch_PrimitiveComponent.get(p.label);const e=c.toAsync();e.setState_X(x+dx);e.setState_Y(y+dy);e.setState_Rotation((r+180)%360);await e.done();}
return {moved,saved:await eda.sch_Document.save()};"""
    print(key,invoke('layout-'+key,code,{'page':pages[key],'pins':pins,'deltas':deltas}))

if __name__=='__main__':
    import sys
    run(sys.argv[1])
