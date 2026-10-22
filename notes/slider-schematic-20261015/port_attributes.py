import json
from phase import ROOT,invoke
p=json.loads((ROOT/'evidence/wired-core.json').read_text())['value']['pins'][0]
print(json.dumps(invoke('port-attribute-inspect',"await eda.dmt_EditorControl.openDocument('ba336973a1f81bda');return (await eda.sch_PrimitiveAttribute.getAll(__CLI__.args.id)).map(a=>({id:a.getState_PrimitiveId(),key:a.getState_Key(),value:a.getState_Value(),x:a.getState_X(),y:a.getState_Y(),r:a.getState_Rotation(),visible:a.getState_ValueVisible()}));",{'id':p['label']}),ensure_ascii=True))
