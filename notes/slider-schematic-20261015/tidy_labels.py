"""Adjust port text for readability without changing wire endpoints or nets."""
import json
from phase import ROOT,invoke

def run(key):
    page=json.loads((ROOT/'pages.json').read_text())[key]
    pins=json.loads((ROOT/f'evidence/wired-{key}.json').read_text(encoding='utf-8'))['value']['pins']
    argv=json.loads((ROOT/f'evidence/layout-{key}.request.json').read_text())['args']
    deltas=json.loads(argv[argv.index('--args')+1])['deltas']
    code="""await eda.dmt_EditorControl.openDocument(__CLI__.args.page);const changed=[];for(const p of __CLI__.args.pins){if(!p.label)continue;const attrs=await eda.sch_PrimitiveAttribute.getAll(p.label);for(const a of attrs){if(a.getState_Key()!=='Name'||a.getState_Value()!==p.net)continue;const r=p.r;const dx=r===0?30:r===180?-30:0;const dy=r===90?30:r===270?-30:0;const d=__CLI__.args.deltas[p.ref]||[0,0];const e=a.toAsync();e.setState_FontSize(6);e.setState_X(p.x+d[0]+dx);e.setState_Y(p.y+d[1]+dy+1);e.setState_Rotation(dy?90:0);e.setState_AlignMode(dx<0?9:3);e.setState_ValueVisible(true);await e.done();changed.push({id:a.getState_PrimitiveId(),ref:p.ref,pin:p.pin,net:p.net});}}return {changed,saved:await eda.sch_Document.save()};"""
    result=invoke('tidy-visible-'+key,code,{'page':page,'pins':pins,'deltas':deltas})
    print(key,'labels',len(result['changed']),result['saved'])

if __name__=='__main__':
    import sys
    run(sys.argv[1])
