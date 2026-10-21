"""Rebuild ground, reopen saved PCB, and run a source-stable full native DRC."""
import argparse,json,subprocess,sys
from native_review import ROOT,invoke

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('stage')
args=parser.parse_args()
for layer in [1,2]:
    print('GROUND',layer,invoke(args.stage+'-rebuild-'+str(layer),"""const ps=(await eda.pcb_PrimitivePour.getAll()).filter(p=>p.getState_Layer()===__CLI__.args.layer&&p.getState_Net()==='GND');if(ps.length!==1)throw new Error('Wrong ground pour');if(!await ps[0].rebuildCopperRegion())throw new Error('Ground rebuild failed');if(!await eda.pcb_Document.save())throw new Error('Save failed');return {layer:__CLI__.args.layer,saved:true};""",{'layer':layer},150),flush=True)
print('REOPEN',invoke(args.stage+'-reopen',"""if(!await eda.pcb_Document.save())throw new Error('Save failed');const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.uuid!=='c3fd8656cf425e9f')throw new Error('Wrong document');if(!await eda.dmt_EditorControl.closeDocument(d.tabId))throw new Error('Close failed');const tab=await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f');if(!tab)throw new Error('Open failed');await eda.pcb_Drc.stopRealTimeDrc();return {tab,document:await eda.dmt_SelectControl.getCurrentDocumentInfo()};""",timeout=90),flush=True)
subprocess.run([sys.executable,str(ROOT/'check_route_stage.py'),args.stage,'--keep-session'],check=True)
