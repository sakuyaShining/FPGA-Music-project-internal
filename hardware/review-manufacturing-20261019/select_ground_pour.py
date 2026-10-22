"""Select exactly one named candidate pour for the visible native rebuild UI."""
import sys
from native_review import invoke
layer=int(sys.argv[1]);assert layer in [1,2]
print(invoke('ground-ui-select-'+str(layer),"""const ps=(await eda.pcb_PrimitivePour.getAll()).filter(p=>p.getState_Layer()===__CLI__.args.layer&&p.getState_PourName()==='GND_V2_'+__CLI__.args.layer);if(ps.length!==1)throw new Error('Expected one named GND pour');await eda.pcb_SelectControl.clearSelected();const selected=await eda.pcb_SelectControl.doSelectPrimitives(ps[0].getState_PrimitiveId());return {selected,name:ps[0].getState_PourName(),layer:ps[0].getState_Layer()};""",{'layer':layer}),flush=True)
