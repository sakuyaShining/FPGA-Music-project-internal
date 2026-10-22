"""Hide automatic wire labels duplicated by the explicit port names."""
import json
import sys
from phase import ROOT,PROJECT,invoke,call
if len(sys.argv)>1 and sys.argv[1]=='open':
    print(call('open',['open','--path',str(PROJECT/(PROJECT.name+'.eprj3')),'--headless','true'],90))
else:
    made=json.loads((ROOT/'evidence/repaired-final-button-wires.json').read_text())['value']['made']
    code="""await eda.dmt_EditorControl.openDocument('ba336973a1f81bda');const changed=[];for(const p of __CLI__.args.made){for(const a of await eda.sch_PrimitiveAttribute.getAll(p.id)){if(a.getState_Value()!==p.net)continue;const e=a.toAsync();e.setState_ValueVisible(false);await e.done();changed.push({key:a.getState_Key(),value:p.net});}}return {changed,saved:await eda.sch_Document.save()};"""
    print(invoke('hide-duplicated-wire-labels',code,{'made':made}))
